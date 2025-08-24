"""
OCR 主程式
"""

import os

from ocr_processor import OCRProcessor, OCRConfig, FileManager
from bullet_resume_parser import BulletResumeParser
from resume_structurer import structure_resume_from_ocr_json


def print_file_info(file_path: str, index: int, total: int):
    """輸出檔案資訊"""
    file_type = "PDF檔案" if file_path.lower().endswith('.pdf') else "圖片檔案"
    print(f"\n[{index}/{total}] 處理{file_type}: {file_path}")


def print_statistics(ocr_result: dict):
    """輸出統計資訊"""
    summary = ocr_result.get('summary', {})
    print(f"\n=== 統計 ===")
    print(f"總頁數: {summary.get('total_pages', 0)}")
    print(f"總行數: {summary.get('total_lines', 0)}")
    print(f"總表格數: {summary.get('total_tables', 0)}")
    print(f"總文字區塊數: {summary.get('total_text_blocks', 0)}")
    print(f"總字符數: {summary.get('total_characters', 0)}")


def process_single_file(processor: OCRProcessor, file_path: str):
    """處理單個檔案"""
    print("正在處理中...")
    
    success, result = processor.process_file(file_path)
    bullet_result = None
    best_layout = "table"
    # 嘗試條列式解析
    if success and result and result["pages"]:
        try:
            parser = BulletResumeParser()
            # 取第一頁所有 text_items（需從 ocr_processor 取得原始 text_items，這裡假設有 result["pages"][0]["text_blocks"]）
            text_blocks = result["pages"][0].get("text_blocks", [])
            # 將所有 text_blocks 的 content 合併
            text_items = []
            for block in text_blocks:
                for c in block.get("content", []):
                    # 模擬 TextItem 結構
                    text_items.append(type("TextItem", (), c)())
            bullet_result = parser.parse(text_items)
        except Exception as e:
            bullet_result = None
    # 比較兩種結果，選擇較佳者（條列區塊數大於1或條列數量大於5就優先條列式）
    if bullet_result and bullet_result.get("sections"):
        bullet_count = sum(len(s["bullets"]) for s in bullet_result["sections"])
        if len(bullet_result["sections"]) > 1 or bullet_count > 5:
            best_layout = "bullet"
    # 輸出
    print("\n=== OCR 結果 (最佳排版: {}型) ===".format("條列" if best_layout=="bullet" else "表格"))
    all_text = ""
    if best_layout == "table":
        for page_data in result["pages"]:
            page_num = page_data["page_number"]
            page_text = page_data["full_text"]
            print(f"\n頁面 {page_num}:")
            print("-" * 50)
            print(page_text)
            all_text += f"=== 頁面 {page_num} ===\n{page_text}\n"
        result["best_layout"] = "table"
        json_filename = FileManager.save_results(result)
    else:
        # 條列式輸出
        for i, section in enumerate(bullet_result["sections"], 1):
            print(f"\n區塊 {i}: {section['title']}")
            print("-" * 30)
            for bullet in section["bullets"]:
                print(f"• {bullet}")
        # 也存成 JSON
        result["best_layout"] = "bullet"
        result["bullet_sections"] = bullet_result["sections"]
        json_filename = FileManager.save_results(result)
    print(f"\n檔案已輸出: {json_filename}")
    print_statistics(result)
    resume_data = structure_resume_from_ocr_json(result)
    print(resume_data)
    if not success:
        error_msg = result.get('error', '未知錯誤')
        print(f"處理失敗: {error_msg}")


def main():
    """主程式"""
    # 初始化處理器
    config = OCRConfig()
    processor = OCRProcessor(config)
    
    assets_folder = "assets"
    
    # 檢查 assets 資料夾
    if not os.path.exists(assets_folder):
        print(f"{assets_folder} 資料夾不存在")
        return
    
    print(f"掃描 {assets_folder} 資料夾中的檔案...")
    
    # 尋找支援的檔案
    files_found = FileManager.find_files_in_folder(
        assets_folder, 
        config.supported_extensions
    )
    
    if not files_found:
        print("未找到支援的檔案格式 (JPEG, PNG, BMP, TIFF, PDF)")
        return
    
    # 顯示找到的檔案
    print(f"找到 {len(files_found)} 個檔案:")
    for file_path in files_found:
        print(f"  - {file_path}")
    
    print("\n開始處理檔案...")
    print("=" * 60)
    
    # 處理每個檔案
    for i, file_path in enumerate(files_found, 1):
        print_file_info(file_path, i, len(files_found))
        process_single_file(processor, file_path)
        print("-" * 60)
    
    print(f"\n處理完成！總共處理了 {len(files_found)} 個檔案")


if __name__ == "__main__":
    main()
