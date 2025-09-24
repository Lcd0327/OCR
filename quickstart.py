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
    if success and result and result["pages"]:
        json_filename = FileManager.save_results(result)
        print(f"\n檔案已輸出: {json_filename}")
    else:
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
