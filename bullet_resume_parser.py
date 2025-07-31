"""
條列式履歷解析器
提供條列區塊、分區標題、條目等結構化解析
"""
from typing import List, Dict, Any

class BulletResumeParser:
    def __init__(self, config=None):
        self.config = config

    def parse(self, text_items: List[Any]) -> Dict[str, Any]:
        """
        解析條列式履歷，將分區標題、條列內容結構化
        text_items: List[TextItem] (需有 text, x1, y1, x2, y2)
        """
        # 依據 y1 排序
        items = sorted(text_items, key=lambda x: x.y1)
        # 記錄所有 items 以便計算平均高度
        self._all_items = items
        sections = []
        current_section = None
        for item in items:
            txt = item.text.strip()
            # 判斷是否為分區標題（如全大寫、粗體、或明顯左側、字體較大）
            if self._is_section_title(txt, item):
                if current_section:
                    sections.append(current_section)
                current_section = {"title": txt, "bullets": []}
            elif self._is_bullet(txt):
                if not current_section:
                    current_section = {"title": "", "bullets": []}
                current_section["bullets"].append(txt)
            else:
                # 可能是段落或補充說明
                if current_section:
                    if current_section["bullets"]:
                        current_section["bullets"][-1] += " " + txt
                    else:
                        current_section["bullets"].append(txt)
        if current_section:
            sections.append(current_section)
        return {"sections": sections}

    def _is_section_title(self, txt, item):
        # 判斷標題：全大寫、長度較短、明顯靠左、或字體較大
        # 字體大小推估：高度大於平均高度1.2倍
        if not hasattr(item, 'height'):
            return (txt.isupper() and len(txt) <= 20) or (len(txt) <= 12 and (item.x1 < 100))

        # 動態計算平均高度
        if not hasattr(self, '_avg_height'):
            self._avg_height = None
        if self._avg_height is None:
            try:
                self._avg_height = sum(getattr(i, 'height', 0) for i in getattr(self, '_all_items', [])) / max(1, len(getattr(self, '_all_items', [])))
            except Exception:
                self._avg_height = 0

        is_big_font = False
        if self._avg_height and item.height > self._avg_height * 1.2:
            is_big_font = True

        # 綜合判斷
        if (txt.isupper() and len(txt) <= 20) or (len(txt) <= 12 and (item.x1 < 100)) or is_big_font:
            return True
        return False

    def _is_bullet(self, txt):
        # 判斷條列符號
        return txt.startswith("•") or txt.startswith("·") or txt.startswith("-")
