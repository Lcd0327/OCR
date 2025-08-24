from fastapi import FastAPI, UploadFile, File
from ocr_processor import OCRProcessor, OCRConfig, FileManager
import os

app = FastAPI()
processor = OCRProcessor(OCRConfig())

def format_resume_result(result):
    # 依照 text_blocks、tables 內容分類
    basic_info = {}
    language_skills = []
    education = []
    computer_skills = []
    other_certificates = []
    work_experience = []
    work_skills = {}
    available_time = []

    for page in result.get("pages", []):
        # 基本資料、聯絡方式、學歷
        for block in page.get("text_blocks", []):
            for item in block.get("content", []):
                txt = item.get("text", "")
                # 基本資料
                if "姓名" in txt or "中文姓名" in txt:
                    basic_info["中文姓名"] = txt
                elif "羅馬拼音" in txt:
                    basic_info["羅馬拼音"] = txt
                elif "生日" in txt or "出生日期" in txt:
                    basic_info["生日"] = txt
                elif "年齡" in txt:
                    basic_info["年齡"] = txt
                elif "性別" in txt:
                    basic_info["性別"] = txt
                elif "居住地" in txt or "居住地區" in txt:
                    basic_info["居住地區"] = txt
                elif "兵役" in txt:
                    basic_info["兵役"] = txt
                elif "國籍" in txt:
                    basic_info["國籍"] = txt
                elif "汽機車駕照" in txt or "駕照" in txt:
                    basic_info["汽機車駕照"] = txt
                elif "就業狀態" in txt:
                    basic_info["就業狀態"] = txt
                elif "預定可到職" in txt:
                    basic_info["預定可到職"] = txt
                elif "手機" in txt:
                    basic_info["手機"] = txt
                elif "Email" in txt:
                    basic_info["Email"] = txt
                elif "最高學歷" in txt:
                    basic_info["最高學歷"] = txt
                elif "通訊地址" in txt:
                    basic_info["通訊地址"] = txt

        # 語言程度、教育背景、電腦技能、其他證照、工作經歷、工作技能、可配合時段
        for table in page.get("tables", []):
            cat = table.get("category", "")
            # 語言程度
            if cat == "language" or "語言" in cat:
                for row in table.get("data", []):
                    if len(row) >= 5:
                        language_skills.append({
                            "語言": row[0],
                            "相關證照名稱": row[1],
                            "級別線分數": row[2],
                            "取得年月": row[3],
                            "顧問評價": row[4]
                        })
            # 教育背景
            elif cat == "education" or "教育" in cat:
                for row in table.get("data", []):
                    if len(row) >= 6:
                        education.append({
                            "學位": row[0],
                            "學校": row[1],
                            "科系": row[2],
                            "開始年月": row[3],
                            "結束年月": row[4],
                            "狀況": row[5]
                        })
            # 電腦技能
            elif cat == "computer" or "電腦" in cat or "技能" in cat:
                for row in table.get("data", []):
                    if len(row) >= 2:
                        computer_skills.append({
                            "項目": row[0],
                            "能力": row[1]
                        })
            # 其他證照與資格
            elif cat == "certificate" or "證照" in cat or "資格" in cat:
                for row in table.get("data", []):
                    if len(row) >= 2:
                        other_certificates.append({
                            "名稱": row[0],
                            "取得年月": row[1]
                        })
            # 工作經歷
            elif cat == "work_experience" or "經歷" in cat:
                for row in table.get("data", []):
                    if len(row) >= 4:
                        work_experience.append({
                            "組織名稱": row[0],
                            "職稱": row[1],
                            "時間": row[2],
                            "工作概述": row[3]
                        })
            # 工作技能與專長
            elif cat == "skills" or "技能" in cat or "專長" in cat:
                # 依欄位內容自動分類
                for row in table.get("data", []):
                    if len(row) == 2:
                        if "語言" in row[0]:
                            work_skills["語言能力"] = row[1]
                        elif "電腦" in row[0]:
                            work_skills["電腦能力"] = row[1]
                        elif "專業證照" in row[0]:
                            work_skills["專業證照"] = row[1]
                        elif "駕照" in row[0]:
                            work_skills["駕照"] = row[1]
                # 其他欄位可擴充
            # 可配合時段
            elif cat == "available_time" or "時段" in cat:
                for row in table.get("data", []):
                    available_time.append(row)

    return {
        "基本資料": basic_info,
        "語言程度": language_skills,
        "教育背景": education,
        "電腦技能": computer_skills,
        "其他證照與資格": other_certificates,
        "工作經歷": work_experience,
        "工作技能與專長": work_skills,
        "可配合時段": available_time
    }

@app.post("/ocr")
async def ocr_file(file: UploadFile = File(...)):
    file_path = f"temp_{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    success, result = processor.process_file(file_path)
    if success and result:
        # 自動儲存 JSON 檔案
        json_filename = FileManager.save_results(result)
        formatted = format_resume_result(result)
        return formatted
    else:
        return {"error": "OCR 處理失敗或不支援的檔案格式"}