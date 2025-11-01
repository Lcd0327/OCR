import os
import time
import json
import re
import importlib.util
from typing import List, Dict, Any, Tuple

from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
from dotenv import load_dotenv

# 載入 .env（若不存在也不會中斷）
_DOTENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'azure.env')
if os.path.exists(_DOTENV_PATH):
    load_dotenv(dotenv_path=_DOTENV_PATH)

class OCRConfig:
    """簡化的 OCR 配置，主要用於排序容差與支援副檔名"""
    def __init__(self):
        self.subscription_key = os.getenv("AZURE_SUBSCRIPTION_KEY")
        self.endpoint = os.getenv("AZURE_ENDPOINT")
        # 不拋錯，讓呼叫端決定是否可用
        self.supported_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.pdf']
        self.y_tolerance = 12  # 群組化時的垂直容差（像素或相對單位）
        # 常用關鍵字（用於 heuristics）
        self.keywords = ['姓名','中文姓名','name','手機','電話','phone','Email','E-mail','email',
                         '地址','通訊地址','居住地','學校','學歷','科系','性別','生日','出生日期',
                         '應徵職務','職稱','自傳','簡介','工作經歷','技能','證照','語言能力']

class TextLine:
    """簡單行資料結構（從 bounding_box 推算 x1,y1,x2,y2）"""
    def __init__(self, text: str, bbox: List[float]):
        self.text = (text or '').strip()
        # Azure read boundingBox 通常為 8 floats: [x0,y0,x1,y1,x2,y2,x3,y3]
        if bbox and len(bbox) >= 6:
            self.x1 = float(bbox[0])
            self.y1 = float(bbox[1])
            self.x2 = float(bbox[4]) if len(bbox) >= 6 else float(bbox[0])
            self.y2 = float(bbox[5]) if len(bbox) >= 6 else float(bbox[1])
        else:
            self.x1 = self.y1 = self.x2 = self.y2 = 0.0
        self.center_x = (self.x1 + self.x2) / 2
        self.center_y = (self.y1 + self.y2) / 2

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

class OCRProcessor:
    """簡化的 OCR 處理器：重點是按順序抓行並做 key/value 偵測"""
    def __init__(self, config: OCRConfig = None):
        self.config = config or OCRConfig()
        # 若環境變數沒設定，不要立即拋錯，部分功能仍可用（例如把現有 OCR JSON 轉結構化）
        if self.config.subscription_key and self.config.endpoint:
            self.client = ComputerVisionClient(
                self.config.endpoint,
                CognitiveServicesCredentials(self.config.subscription_key)
            )
        else:
            self.client = None

    def is_supported_file(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            return False
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.config.supported_extensions

    def _lines_from_page(self, page) -> List[TextLine]:
        lines = []
        for line in getattr(page, 'lines', []):
            bbox = getattr(line, 'bounding_box', None)
            # line.text 為 Azure read SDK 的文字
            lines.append(TextLine(getattr(line, 'text', ''), bbox))
        # 依 center_y (top->down) 與 x1 (left->right) 排序，保證閱讀順序
        return sorted(lines, key=lambda l: (l.center_y, l.x1))

    def _group_lines_by_row(self, lines: List[TextLine]) -> List[List[TextLine]]:
        """把同一水平帶的行群組在一起（容差 self.config.y_tolerance）"""
        if not lines:
            return []
        groups = []
        current = [lines[0]]
        for ln in lines[1:]:
            avg_y = sum(l.center_y for l in current) / len(current)
            if abs(ln.center_y - avg_y) <= self.config.y_tolerance:
                current.append(ln)
            else:
                groups.append(sorted(current, key=lambda l: l.x1))
                current = [ln]
        if current:
            groups.append(sorted(current, key=lambda l: l.x1))
        return groups

    # 簡單正則：email, phone
    _re_email = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
    _re_phone = re.compile(r'(\+?\d[\d\-\s]{5,}\d)')

    def _detect_kv_pairs(self, groups: List[List[TextLine]]) -> List[Dict[str,str]]:
        """把每個群組轉成 一行文字，然後用 heuristics 偵測 key/value"""
        pairs = []
        pending_key = None  # 若上一行被判為 key 但沒有 value，可用下一行當 value
        for group in groups:
            line_text = ' '.join([ln.text for ln in group]).strip()
            if not line_text:
                continue

            # 1) 若包含冒號，直接切分 key:value（只分第一次出現）
            if ':' in line_text or '：' in line_text:
                sep = ':' if ':' in line_text else '：'
                key, val = [s.strip() for s in line_text.split(sep, 1)]
                pairs.append({"key": key, "value": val})
                pending_key = None
                continue

            # 2) 若行含 email 或 phone，當成 value，嘗試附加到前一個 pending_key，否則當成獨立項
            if self._re_email.search(line_text) or self._re_phone.search(line_text):
                if pending_key:
                    pairs.append({"key": pending_key, "value": line_text})
                    pending_key = None
                else:
                    # 試將 email/phone 放在合適的 key（簡單 heuristics）
                    if self._re_email.search(line_text):
                        pairs.append({"key": "Email", "value": line_text})
                    else:
                        pairs.append({"key": "Phone", "value": line_text})
                continue

            # 3) 若行包含明顯關鍵字（如「姓名」「手機」「地址」等），將關鍵字當 key，剩餘當 value（若沒有剩餘，標記為 pending）
            matched_kw = None
            for kw in self.config.keywords:
                if kw in line_text:
                    matched_kw = kw
                    break
            if matched_kw:
                # remove first occurrence of keyword
                idx = line_text.find(matched_kw)
                after = line_text[idx + len(matched_kw):].strip()
                if after:
                    pairs.append({"key": matched_kw, "value": after})
                    pending_key = None
                else:
                    pending_key = matched_kw
                continue

            # 4) 若上一行是 pending_key，則把此行當成其 value
            if pending_key:
                pairs.append({"key": pending_key, "value": line_text})
                pending_key = None
                continue

            # 5) 否則將該行當成一般獨立項（key=text, value=''）
            pairs.append({"key": line_text, "value": ""})

        # 若結束時仍有 pending_key，加入空 value
        if pending_key:
            pairs.append({"key": pending_key, "value": ""})
        return pairs


    #TODO: visual layout analysis (tables, columns) can be added in future enhancements and formatting
    def _extract_compact_contact(self, rows: List[Dict[str, Any]]) -> Dict[str, str]:
        """從 rows 嘗試擷取並把姓名/手機/Email 盡量排在一起回傳（不含座標）"""
        email = ""
        phone = ""
        name = ""

        # 展平所有 segments（保持 top->down, left->right）
        segments = []
        for r_idx, r in enumerate(rows):
            segs = sorted(r.get("texts", []), key=lambda s: s.get("x1", 0))
            for s in segs:
                seg = s.copy()
                seg["_row_idx"] = r_idx
                seg["_center_x"] = (seg.get("x1", 0) + seg.get("x2", 0)) / 2
                seg["_center_y"] = (seg.get("y1", 0) + seg.get("y2", 0)) / 2
                segments.append(seg)

        # 1) 先找 email / phone（全頁第一個符合）
        for seg in segments:
            txt = seg.get("text", "")
            if not email:
                m = self._re_email.search(txt)
                if m:
                    email = m.group(0)
            if not phone:
                m2 = self._re_phone.search(txt)
                if m2:
                    phone = m2.group(0)
            if email and phone:
                break

        # 2) 嘗試用「姓名」標籤附近找姓名（同一 row、或下一 row）
        name_kw = ['姓名', '中文姓名', 'name']
        for i, seg in enumerate(segments):
            txt = seg.get("text", "")
            for kw in name_kw:
                if kw in txt:
                    row_idx = seg["_row_idx"]
                    candidates = [s for s in segments if s["_row_idx"] == row_idx and s["_center_x"] > seg["_center_x"]]
                    if candidates:
                        name = candidates[0].get("text", "").strip()
                        break
                    next_row_idx = row_idx + 1
                    next_row_segs = [s for s in segments if s["_row_idx"] == next_row_idx]
                    if next_row_segs:
                        next_row_segs = sorted(next_row_segs, key=lambda s: s["_center_x"])
                        name = next_row_segs[0].get("text", "").strip()
                        break
            if name:
                break

        # 3) fallback：若仍找不到 name，挑第一個看起來像名字的 segment（無數字、長度合理）
        if not name:
            for seg in segments:
                txt = seg.get("text", "").strip()
                if not txt:
                    continue
                if any(kw in txt for kw in name_kw):
                    continue
                if self._re_email.search(txt) or self._re_phone.search(txt):
                    continue
                if sum(ch.isdigit() for ch in txt) > 0:
                    continue
                if 1 < len(txt) <= 30:
                    name = txt
                    break

        return {"姓名": name or "", "手機": phone or "", "Email": email or ""}

    def process_page(self, page, page_number: int) -> Dict[str, Any]:
        lines = self._lines_from_page(page)
        groups = self._group_lines_by_row(lines)

        # 建立 rows 僅供內部處理（但不會回傳座標）
        rows = []
        for g in groups:
            rows.append({
                "y": sum(l.center_y for l in g) / len(g),
                "texts": [ln.to_dict() for ln in g]
            })

        # page_text 使用每個群組的文字（群組內以空白連接，群組間以換行）
        page_text = '\n'.join([' '.join(ln.text for ln in g) for g in groups])

        # 嘗試組合姓名/手機/Email（供顯示用）
        compact_contact = self._extract_compact_contact(rows)

        # 若有至少一項資訊，建立一行格式化字串放在最前面（不包含座標或原始行/rows）
        contact_line_parts = []
        if compact_contact.get("姓名"):
            contact_line_parts.append(f"姓名: {compact_contact['姓名']}")
        if compact_contact.get("手機"):
            contact_line_parts.append(f"手機: {compact_contact['手機']}")
        if compact_contact.get("Email"):
            contact_line_parts.append(f"Email: {compact_contact['Email']}")
        contact_line = "    ".join(contact_line_parts) if contact_line_parts else ""

        # formatted_text 為整個頁面的「純文字」輸出，並在最上方加入 contact_line（如果有）
        if contact_line:
            formatted_text = contact_line + "\n\n" + page_text
        else:
            formatted_text = page_text

        return {
            "page_number": page_number,
            "page_text": page_text,
            "formatted_text": formatted_text,
            "compact_contact": compact_contact,
            "total_lines": len(lines)
        }

    def process_file(self, file_path: str) -> Tuple[bool, Dict[str, Any]]:
        """使用 Azure Read API 處理檔案並回傳簡化 JSON（若未配置 Azure，回傳錯誤）"""
        if not self.is_supported_file(file_path):
            return False, {"error": f"不支援的檔案或不存在: {file_path}"}
        if not self.client:
            return False, {"error": "Azure Computer Vision client 未配置，請設定 AZURE_SUBSCRIPTION_KEY / AZURE_ENDPOINT"}

        try:
            with open(file_path, "rb") as fs:
                read_response = self.client.read_in_stream(fs, raw=True)
            operation_location = read_response.headers.get("Operation-Location")
            if not operation_location:
                return False, {"error": "無法取得 Operation-Location"}
            operation_id = operation_location.split("/")[-1]

            # 等待結果完成
            while True:
                result = self.client.get_read_result(operation_id)
                if result.status not in ['notStarted', 'running']:
                    break
                time.sleep(0.8)

            if result.status != OperationStatusCodes.succeeded:
                return False, {"error": f"OCR 失敗: {result.status}"}

            out = {
                "file_path": file_path,
                "timestamp": int(time.time()),
                "total_pages": len(result.analyze_result.read_results),
                "pages": []
            }
            for idx, page in enumerate(result.analyze_result.read_results):
                out["pages"].append(self.process_page(page, idx + 1))

            return True, out
        except Exception as e:
            return False, {"error": str(e)}

class FileManager:
    """儲存與簡單轉換功能"""
    @staticmethod
    def save_results(ocr_result: Dict[str, Any], filename: str = None) -> str:
        if not filename:
            src = ocr_result.get("file_path", "ocr_output")
            base = os.path.splitext(os.path.basename(src))[0]
            filename = f"ocr_output_{base}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(ocr_result, f, ensure_ascii=False, indent=2)
        return filename

    @staticmethod
    def find_files_in_folder(folder: str, extensions: List[str], recursive: bool = True) -> List[str]:
        """在資料夾中尋找支援的檔案（預設遞迴），回傳絕對路徑排序清單"""
        if not folder or not os.path.exists(folder) or not os.path.isdir(folder):
            return []
        # 正規化副檔名（確保以小寫開頭包含 '.'）
        norm_exts = set(e.lower() if e.startswith('.') else f".{e.lower()}" for e in extensions)
        matches: List[str] = []
        if recursive:
            for root, _, files in os.walk(folder):
                for fn in files:
                    if os.path.splitext(fn)[1].lower() in norm_exts:
                        matches.append(os.path.abspath(os.path.join(root, fn)))
        else:
            for fn in os.listdir(folder):
                p = os.path.join(folder, fn)
                if os.path.isfile(p) and os.path.splitext(fn)[1].lower() in norm_exts:
                    matches.append(os.path.abspath(p))
        matches.sort()
        return matches

    @staticmethod
    def convert_to_structured_with_resume_structurer(ocr_json_path: str, output_path: str = None) -> str:
        """若專案有 resume_structurer.py，可呼叫其 structure 函式做更進階結構化"""
        structurer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resume_structurer.py')
        if not os.path.exists(structurer_path):
            raise FileNotFoundError("找不到 resume_structurer.py")
        spec = importlib.util.spec_from_file_location('resume_structurer', structurer_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with open(ocr_json_path, 'r', encoding='utf-8') as f:
            ocr_json = json.load(f)
        structured = mod.structure_resume_from_ocr_json(ocr_json)
        if not output_path:
            base = os.path.basename(ocr_json_path)
            name, _ = os.path.splitext(base)
            output_path = f"resume_structured_{name}.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(structured, f, ensure_ascii=False, indent=2)
        return output_path