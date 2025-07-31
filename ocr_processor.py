"""
OCR 處理器模組
提供表格檢測、格式化和 JSON 輸出功能
"""

import time
import os
import json
from typing import List, Dict, Any, Tuple
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials


class OCRConfig:
    """OCR 配置類"""
    
    def __init__(self):
        self.subscription_key = "15tkJaax9WyCBdoyOnboz9PDLSD4e0eyKNfMB7f5JMJa965wbPOfJQQJ99BGACYeBjFXJ3w3AAAAACOGOKiL"
        self.endpoint = "https://lcdra0327.services.ai.azure.com/"
        self.supported_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.pdf']
        
        # 表格檢測參數
        self.y_tolerance = 15
        self.alignment_tolerance = 60
        self.column_gap_threshold = 60
        self.max_look_ahead = 15
        self.max_col_width = 40
        self.alignment_ratio = 0.4
        self.max_gap_tolerance = 2
        
        # 分隔詞
        self.separator_keywords = ['工作或社團經歷', '工作技能', '可配合時段', '基本資訊']


class TextItem:
    """文字項目類"""
    
    def __init__(self, text: str, x1: float, y1: float, x2: float, y2: float):
        self.text = text
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.width = x2 - x1
        self.height = y2 - y1
        self.center_x = (x1 + x2) / 2
        self.center_y = (y1 + y2) / 2
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'text': self.text,
            'x1': self.x1, 'y1': self.y1,
            'x2': self.x2, 'y2': self.y2,
            'width': self.width,
            'height': self.height,
            'center_x': self.center_x,
            'center_y': self.center_y
        }


class TableDetector:
    """表格檢測器"""
    
    def __init__(self, config: OCRConfig):
        self.config = config
    
    def group_by_y_coordinate(self, items: List[TextItem]) -> List[List[TextItem]]:
        """按 Y 座標分組"""
        groups = []
        current_group = []
        
        for item in items:
            if not current_group:
                current_group.append(item)
            else:
                avg_y = sum(i.y1 for i in current_group) / len(current_group)
                if abs(item.y1 - avg_y) <= self.config.y_tolerance:
                    current_group.append(item)
                else:
                    groups.append(current_group)
                    current_group = [item]
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def has_separator_keyword(self, group: List[TextItem]) -> bool:
        """檢查是否包含分隔關鍵詞"""
        text_content = ' '.join([item.text for item in group])
        return any(keyword in text_content for keyword in self.config.separator_keywords)
    
    def calculate_alignment(self, positions1: List[float], positions2: List[float]) -> int:
        """計算列對齊數量"""
        alignment_count = 0
        for pos2 in positions2:
            for pos1 in positions1:
                if abs(pos2 - pos1) <= self.config.alignment_tolerance:
                    alignment_count += 1
                    break
        return alignment_count
    
    def detect_tables(self, groups: List[List[TextItem]]) -> List[Dict[str, Any]]:
        """檢測表格結構，遇到分區標題或條列符號比例高的 group 直接略過表格判斷"""
        tables = []
        i = 0
        while i < len(groups):
            current_group = groups[i]
            # 新增：若 group 內有多個分區標題或條列符號比例高，直接略過
            section_title_count = 0
            bullet_count = 0
            for item in current_group:
                txt = getattr(item, 'text', '')
                # 利用 BulletResumeParser 的標題與條列判斷
                from bullet_resume_parser import BulletResumeParser
                parser = BulletResumeParser()
                if parser._is_section_title(txt, item):
                    section_title_count += 1
                if parser._is_bullet(txt):
                    bullet_count += 1
            if section_title_count >= 1 or (len(current_group) > 0 and bullet_count / len(current_group) > 0.4):
                i += 1
                continue

            if len(current_group) >= 1:
                table_rows = [current_group]
                first_row = sorted(current_group, key=lambda x: x.x1)
                column_positions = [item.x1 for item in first_row]

                j = i + 1
                consecutive_matches = 0
                gap_tolerance = 0
                max_look_ahead = min(self.config.max_look_ahead, len(groups) - i)

                # 掃描後續行
                while j < len(groups) and j < i + max_look_ahead:
                    next_group = groups[j]

                    # 新增：若 group 內有多個分區標題或條列符號比例高，直接略過
                    section_title_count2 = 0
                    bullet_count2 = 0
                    for item in next_group:
                        txt = getattr(item, 'text', '')
                        parser = BulletResumeParser()
                        if parser._is_section_title(txt, item):
                            section_title_count2 += 1
                        if parser._is_bullet(txt):
                            bullet_count2 += 1
                    if section_title_count2 >= 1 or (len(next_group) > 0 and bullet_count2 / len(next_group) > 0.4):
                        break

                    if len(next_group) >= 1:
                        next_row = sorted(next_group, key=lambda x: x.x1)
                        next_positions = [item.x1 for item in next_row]

                        # 檢查分隔詞
                        if self.has_separator_keyword(next_group) and len(table_rows) >= 2:
                            break

                        # 計算對齊度
                        alignment_count = self.calculate_alignment(column_positions, next_positions)
                        required_alignment = max(1, len(next_positions) * self.config.alignment_ratio)

                        if alignment_count >= required_alignment:
                            # 更新列位置
                            for next_pos in next_positions:
                                if not any(abs(next_pos - col_pos) <= self.config.alignment_tolerance 
                                         for col_pos in column_positions):
                                    column_positions.append(next_pos)
                            column_positions.sort()

                            table_rows.append(next_group)
                            consecutive_matches += 1
                            gap_tolerance = 0
                            j += 1
                        else:
                            gap_tolerance += 1
                            if gap_tolerance <= self.config.max_gap_tolerance and consecutive_matches > 0:
                                table_rows.append(next_group)
                                j += 1
                            else:
                                break
                    else:
                        if consecutive_matches > 0 and gap_tolerance <= 1:
                            gap_tolerance += 1
                            j += 1
                        else:
                            break

                # 判定是否為表格
                min_rows_required = 2 if len(column_positions) >= 2 else 4
                if len(table_rows) >= min_rows_required:
                    tables.append({
                        'rows': table_rows,
                        'start_index': i,
                        'end_index': j - 1,
                        'column_positions': sorted(column_positions),
                        'column_count': len(column_positions)
                    })
                    i = j
                else:
                    i += 1
            else:
                i += 1
        return tables


class TableFormatter:
    """表格格式化器"""
    
    def __init__(self, config: OCRConfig):
        self.config = config
    
    def find_column_boundaries(self, all_items: List[TextItem]) -> List[float]:
        """找出列邊界 - 改進聚類算法"""
        if not all_items:
            return []
        
        # 收集所有X位置並去重
        x_positions = []
        for item in all_items:
            x_positions.append(item.x1)
        
        # 排序並去除重複值
        unique_x_positions = sorted(list(set(x_positions)))
        
        if len(unique_x_positions) <= 1:
            return unique_x_positions
        
        # 使用自適應閾值找出列邊界
        column_boundaries = [unique_x_positions[0]]
        
        # 計算間距分布，動態調整閾值
        gaps = []
        for i in range(1, len(unique_x_positions)):
            gap = unique_x_positions[i] - unique_x_positions[i-1]
            gaps.append(gap)
        
        # 使用平均間距的一定比例作為閾值
        if gaps:
            avg_gap = sum(gaps) / len(gaps)
            dynamic_threshold = max(self.config.column_gap_threshold, avg_gap * 1.5)
        else:
            dynamic_threshold = self.config.column_gap_threshold
        
        for i in range(1, len(unique_x_positions)):
            gap = unique_x_positions[i] - unique_x_positions[i-1]
            if gap > dynamic_threshold:
                column_boundaries.append(unique_x_positions[i])
        
        return column_boundaries
    
    def assign_cells_to_columns(self, row_items: List[TextItem], 
                               column_boundaries: List[float]) -> List[str]:
        """將單元格分配到列 - 改進邏輯避免內容分割"""
        if not column_boundaries:
            return [' '.join(item.text for item in row_items)]
        
        row_cells = [''] * len(column_boundaries)
        
        # 按X座標排序項目
        sorted_items = sorted(row_items, key=lambda x: x.x1)
        
        for item in sorted_items:
            # 找最適合的列
            best_col = 0
            min_distance = abs(item.x1 - column_boundaries[0])
            
            for col_idx, boundary in enumerate(column_boundaries):
                distance = abs(item.x1 - boundary)
                if distance < min_distance:
                    min_distance = distance
                    best_col = col_idx
            
            # 改進的內容合併邏輯
            if row_cells[best_col]:
                current_content = row_cells[best_col]
                new_content = item.text
                
                # 檢查是否是連續的內容（如日期、時間）
                is_continuous = self._is_continuous_content(current_content, new_content)
                
                if is_continuous:
                    # 對於連續內容，直接連接（如日期範圍）
                    row_cells[best_col] = current_content + new_content
                elif len(current_content) > 30 and len(new_content) > 15:
                    # 長內容分行
                    row_cells[best_col] += '\n' + new_content
                else:
                    # 短內容用空格連接
                    row_cells[best_col] += ' ' + new_content
            else:
                row_cells[best_col] = item.text
        
        return row_cells
    
    def _is_continuous_content(self, current: str, new: str) -> bool:
        """判斷是否為連續內容（如日期範圍）"""
        # 檢查日期範圍模式
        if (current.endswith('-') or current.endswith('.')):
            return True
        
        # 檢查數字連續性
        if current and new:
            if (current[-1].isdigit() and new[0].isdigit()) or \
               (current.endswith('.') and new[0].isdigit()) or \
               (current.endswith('-') and new[0].isdigit()):
                return True
        
        return False
    
    def format_table(self, table_info: Dict[str, Any], table_category: str = None) -> Dict[str, Any]:
        """格式化表格 - 並加上分類資訊，優化排版與內容合併"""
        import copy
        rows = table_info['rows']
        all_items = []
        for row_group in rows:
            all_items.extend(row_group)
        column_boundaries = self.find_column_boundaries(all_items)
        table_data = []
        for i, row_group in enumerate(rows):
            row_items = sorted(row_group, key=lambda x: x.x1)
            row_cells = self.assign_cells_to_columns(row_items, column_boundaries)
            # 補齊欄位數
            if len(row_cells) < len(column_boundaries):
                row_cells += [''] * (len(column_boundaries) - len(row_cells))
            # 合併多行內容
            if i > 0 and self._should_merge_with_previous_row(row_cells, table_data[-1]):
                for col_idx, cell_content in enumerate(row_cells):
                    if cell_content.strip() and col_idx < len(table_data[-1]):
                        if table_data[-1][col_idx].strip():
                            prev_content = table_data[-1][col_idx]
                            if self._is_continuous_content(prev_content, cell_content):
                                table_data[-1][col_idx] = prev_content + cell_content
                            else:
                                table_data[-1][col_idx] = prev_content + '\n' + cell_content
                        else:
                            table_data[-1][col_idx] = cell_content
            else:
                table_data.append(copy.deepcopy(row_cells))
        # 計算每欄最大寬度（考慮多行）
        max_col_widths = []
        for col_idx in range(len(column_boundaries)):
            max_width = 0
            for row in table_data:
                if col_idx < len(row):
                    cell_lines = row[col_idx].split('\n')
                    for line in cell_lines:
                        max_width = max(max_width, len(line))
            max_col_widths.append(min(max_width, self.config.max_col_width))
        # 美化表格排版
        formatted_lines = []
        # 標題行與分隔線
        if table_data:
            header = ' | '.join(cell.ljust(max_col_widths[idx]) for idx, cell in enumerate(table_data[0]))
            formatted_lines.append(header)
            sep_line = '-+-'.join('-' * w for w in max_col_widths)
            formatted_lines.append(sep_line)
        # 內容行
        for row in table_data[1:]:
            # 處理多行內容
            cell_lines = [cell.split('\n') for cell in row]
            max_lines = max(len(lines) for lines in cell_lines)
            for line_idx in range(max_lines):
                line = ''
                for col_idx, lines in enumerate(cell_lines):
                    content = lines[line_idx] if line_idx < len(lines) else ''
                    line += content.ljust(max_col_widths[col_idx])
                    if col_idx < len(cell_lines) - 1:
                        line += ' | '
                formatted_lines.append(line.rstrip())
        return {
            "formatted_text": "\n".join(formatted_lines),
            "raw_data": table_data,
            "column_count": len(column_boundaries),
            "row_count": len(table_data),
            "category": table_category
        }
    
    def _should_merge_with_previous_row(self, current_row: List[str], 
                                       previous_row: List[str]) -> bool:
        """判斷是否應該與上一行合併"""
        # 如果當前行的第一列為空，可能是跨行內容
        if not current_row[0].strip():
            return True
        
        # 如果當前行只有少數列有內容，且內容較短，可能是跨行的一部分
        non_empty_count = sum(1 for cell in current_row if cell.strip())
        if non_empty_count <= 2:
            # 檢查內容長度
            total_length = sum(len(cell) for cell in current_row if cell.strip())
            if total_length < 20:  # 內容較短
                return True
        
        return False
    
    def _create_formatted_output(self, table_data: List[List[str]], 
                                max_col_widths: List[int]) -> List[str]:
        """創建格式化輸出"""
        formatted_lines = []
        
        for row_idx, row in enumerate(table_data):
            line = ""
            for col_idx, cell in enumerate(row):
                if col_idx < len(max_col_widths):
                    # 處理換行內容
                    if '\n' in cell:
                        cell_lines = cell.split('\n')
                        main_content = cell_lines[0]
                        if len(cell_lines) > 1:
                            suffix = f" ({cell_lines[1][:20]}...)" if len(cell_lines[1]) > 20 else f" ({cell_lines[1]})"
                            main_content += suffix
                        cell = main_content
                    
                    # 截斷過長內容
                    if len(cell) > max_col_widths[col_idx]:
                        cell = cell[:max_col_widths[col_idx]-3] + "..."
                    
                    line += cell.ljust(max_col_widths[col_idx])
                    if col_idx < len(row) - 1:
                        line += " | "
            
            formatted_lines.append(line.rstrip())
            
            # 添加分隔線
            if row_idx == 0 or (row_idx > 0 and row_idx % 5 == 0 and row_idx < len(table_data) - 1):
                sep_line = ""
                for col_idx in range(len(max_col_widths)):
                    sep_line += "-" * max_col_widths[col_idx]
                    if col_idx < len(max_col_widths) - 1:
                        sep_line += "-+-"
                formatted_lines.append(sep_line)
        
        return formatted_lines


class OCRProcessor:
    """主 OCR 處理器"""
    
    def __init__(self, config: OCRConfig = None):
        self.config = config or OCRConfig()
        self.client = ComputerVisionClient(
            self.config.endpoint,
            CognitiveServicesCredentials(self.config.subscription_key)
        )
        self.table_detector = TableDetector(self.config)
        self.table_formatter = TableFormatter(self.config)
    
    def is_supported_file(self, file_path: str) -> bool:
        """檢查是否為支援的檔案格式"""
        if not os.path.exists(file_path):
            return False
        
        file_extension = os.path.splitext(file_path)[1].lower()
        return file_extension in self.config.supported_extensions
    
    def extract_text_items(self, page) -> List[TextItem]:
        """從頁面提取文字項目"""
        items = []
        for line in page.lines:
            bbox = line.bounding_box
            x1, y1 = bbox[0], bbox[1]
            x2, y2 = bbox[4], bbox[5]
            items.append(TextItem(line.text, x1, y1, x2, y2))
        
        return sorted(items, key=lambda x: x.y1)
    
    def process_page(self, page, page_number: int) -> Dict[str, Any]:
        """處理單頁，並自動分類表格"""
        text_items = self.extract_text_items(page)
        y_groups = self.table_detector.group_by_y_coordinate(text_items)
        detected_tables = self.table_detector.detect_tables(y_groups)
        table_indices = set()
        for table in detected_tables:
            for idx in range(table['start_index'], table['end_index'] + 1):
                table_indices.add(idx)
        regular_text = [group for i, group in enumerate(y_groups) if i not in table_indices]

        # 分類關鍵字與對應分類
        table_categories = [
            (['基本資訊'], 'basic_info'),
            (['自傳', '簡介'], 'introduction'),
            (['工作或社團經歷', '工作經歷', '社團經歷'], 'work_experience'),
            (['技能', '專長', '能力'], 'skills'),
            (['可配合時段', '時段', '時間'], 'available_time'),
        ]

        def classify_table(table_data):
            joined = ' '.join([' '.join(row) for row in table_data])
            for keywords, cat in table_categories:
                for kw in keywords:
                    if kw in joined:
                        return cat
            return 'other'

        page_result = {
            "page_number": page_number,
            "tables": [],
            "text_blocks": [],
            "statistics": {}
        }

        page_text = ""
        all_content = []
        for table in detected_tables:
            table_y = table['rows'][0][0].y1
            # 先格式化一次取得資料
            preview = self.table_formatter.format_table(table)
            category = classify_table(preview['raw_data'])
            all_content.append(('table', table_y, table, category))
        for text_group in regular_text:
            text_y = text_group[0].y1
            all_content.append(('text', text_y, text_group, None))
        all_content.sort(key=lambda x: x[1])
        prev_y = -1
        for content_type, y_pos, content, category in all_content:
            if prev_y != -1 and y_pos - prev_y > 50:
                page_text += "\n"
            if content_type == 'table':
                table_result = self.table_formatter.format_table(content, table_category=category)
                page_result["tables"].append({
                    "table_id": len(page_result["tables"]) + 1,
                    "position_y": y_pos,
                    "data": table_result["raw_data"],
                    "column_count": table_result["column_count"],
                    "row_count": table_result["row_count"],
                    "formatted_display": table_result["formatted_text"],
                    "category": table_result["category"]
                })
                table_display = f"\n[表格 {len(page_result['tables'])}][分類:{table_result['category']}]\n{table_result['formatted_text']}\n"
                page_text += table_display
            else:
                text_block = []
                for item in content:
                    page_text += item.text + "\n"
                    text_block.append({
                        "text": item.text,
                        "position": {
                            "x1": item.x1, "y1": item.y1,
                            "x2": item.x2, "y2": item.y2
                        }
                    })
                if text_block:
                    page_result["text_blocks"].append({
                        "block_id": len(page_result["text_blocks"]) + 1,
                        "position_y": y_pos,
                        "content": text_block
                    })
            prev_y = y_pos
        page_result.update({
            "statistics": {
                "total_tables": len(page_result["tables"]),
                "total_text_blocks": len(page_result["text_blocks"]),
                "total_lines": len(page.lines),
                "page_text_length": len(page_text)
            },
            "full_text": page_text
        })
        return page_result, page_text
    
    def _process_content(self, tables: List[Dict], text_groups: List[List[TextItem]], 
                        page_result: Dict) -> str:
        """處理頁面內容"""
        all_content = []
        
        # 添加表格
        for table in tables:
            table_y = table['rows'][0][0].y1
            all_content.append(('table', table_y, table))
        
        # 添加文字
        for text_group in text_groups:
            text_y = text_group[0].y1
            all_content.append(('text', text_y, text_group))
        
        # 按Y座標排序
        all_content.sort(key=lambda x: x[1])
        
        # 生成輸出
        page_text = ""
        prev_y = -1
        
        for content_type, y_pos, content in all_content:
            if prev_y != -1 and y_pos - prev_y > 50:
                page_text += "\n"
            
            if content_type == 'table':
                table_result = self.table_formatter.format_table(content)
                
                # 保存到JSON
                page_result["tables"].append({
                    "table_id": len(page_result["tables"]) + 1,
                    "position_y": y_pos,
                    "data": table_result["raw_data"],
                    "column_count": table_result["column_count"],
                    "row_count": table_result["row_count"],
                    "formatted_display": table_result["formatted_text"]
                })
                
                # 添加到頁面文字
                table_display = f"\n[表格 {len(page_result['tables'])}]\n{table_result['formatted_text']}\n"
                page_text += table_display
            
            else:
                # 處理普通文字
                text_block = []
                for item in content:
                    page_text += item.text + "\n"
                    text_block.append({
                        "text": item.text,
                        "position": {
                            "x1": item.x1, "y1": item.y1,
                            "x2": item.x2, "y2": item.y2
                        }
                    })
                
                if text_block:
                    page_result["text_blocks"].append({
                        "block_id": len(page_result["text_blocks"]) + 1,
                        "position_y": y_pos,
                        "content": text_block
                    })
            
            prev_y = y_pos
        
        return page_text
    
    def process_file(self, file_path: str) -> Tuple[bool, Dict[str, Any]]:
        """處理檔案"""
        if not self.is_supported_file(file_path):
            return False, {"error": f"不支援的檔案格式或檔案不存在: {file_path}"}
        
        try:
            # 發送 OCR 請求
            with open(file_path, "rb") as file_stream:
                read_response = self.client.read_in_stream(file_stream, raw=True)
            
            # 等待結果
            operation_location = read_response.headers["Operation-Location"]
            operation_id = operation_location.split("/")[-1]
            
            while True:
                result = self.client.get_read_result(operation_id)
                if result.status not in ['notStarted', 'running']:
                    break
                time.sleep(1)
            
            if result.status != OperationStatusCodes.succeeded:
                return False, {"error": f"OCR 處理失敗: {result.status}"}
            
            # 處理結果
            ocr_result = {
                "file_path": file_path,
                "timestamp": int(time.time()),
                "total_pages": len(result.analyze_result.read_results),
                "pages": []
            }
            
            all_text = ""
            
            for page_idx, page in enumerate(result.analyze_result.read_results):
                page_result, page_text = self.process_page(page, page_idx + 1)
                ocr_result["pages"].append(page_result)
                all_text += f"=== 頁面 {page_idx + 1} ===\n{page_text}\n"
            
            # 添加總統計
            ocr_result["summary"] = {
                "total_pages": len(result.analyze_result.read_results),
                "total_lines": sum(len(page.lines) for page in result.analyze_result.read_results),
                "total_tables": sum(len(page_data["tables"]) for page_data in ocr_result["pages"]),
                "total_text_blocks": sum(len(page_data["text_blocks"]) for page_data in ocr_result["pages"]),
                "total_characters": len(all_text),
                "processing_timestamp": int(time.time())
            }
            
            return True, ocr_result
            
        except Exception as e:
            return False, {"error": f"處理檔案時發生錯誤: {str(e)}"}


class FileManager:
    """檔案管理器"""
    
    @staticmethod
    def save_results(ocr_result: Dict[str, Any], all_text: str = None) -> str:
        """依據來源檔案自動命名 JSON 檔案，若同一檔案則覆蓋"""
        import os
        file_path = ocr_result.get("file_path")
        if file_path:
            base = os.path.basename(file_path)
            name, _ = os.path.splitext(base)
            json_filename = f"ocr_output_{name}.json"
        else:
            json_filename = "ocr_output.json"

        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(ocr_result, f, ensure_ascii=False, indent=2)
        return json_filename
    
    @staticmethod
    def find_files_in_folder(folder_path: str, extensions: List[str]) -> List[str]:
        """在資料夾中尋找支援的檔案"""
        if not os.path.exists(folder_path):
            return []
        
        files_found = []
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                file_extension = os.path.splitext(filename)[1].lower()
                if file_extension in extensions:
                    files_found.append(file_path)
        
        return files_found
