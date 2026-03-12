
import pdfplumber
import warnings
import json
import os
from difflib import SequenceMatcher
import requests
from bs4 import BeautifulSoup
import pytesseract
from pdf2image import convert_from_path

import logging
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# ====== 設定 TESSDATA_PREFIX 路徑（使用者自訂） ======
os.environ['TESSDATA_PREFIX'] = r'D:\tesseract-5.5.2\tessdata'

def extract_pdf_text(pdf_path):
    text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text.append(page.extract_text() or "")
    return "\n".join(text)

def extract_ocr_text(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return "\n".join(page['page_text'] for page in data['pages'])

def levenshtein_distance(s1, s2):
    matcher = SequenceMatcher(None, s1, s2)
    return int(max(len(s1), len(s2)) - sum(triple.size for triple in matcher.get_matching_blocks()))

def cer(gt, pred):
    dist = levenshtein_distance(gt, pred)
    return dist / max(1, len(gt)), dist, len(gt)

# ====== 新增：自動爬取台灣政府PDF ======
def crawl_gov_pdfs(base_url, dest_folder='assets', max_files=5):
    os.makedirs(dest_folder, exist_ok=True)
    resp = requests.get(base_url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    # 1. 取得所有資料集詳細頁連結
    dataset_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        # 只抓 dataset 詳細頁
        if href.startswith('/dataset/') or href.startswith('https://data.gov.tw/dataset/'):
            # 統一成完整網址
            if not href.startswith('http'):
                href = requests.compat.urljoin(base_url, href)
            if href not in dataset_links:
                dataset_links.append(href)
        if len(dataset_links) >= max_files:
            break
    pdfs = []
    # 2. 進入每個詳細頁抓 PDF 連結
    for detail_url in dataset_links:
        try:
            detail_resp = requests.get(detail_url)
            detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
            for link in detail_soup.find_all('a', href=True):
                pdf_href = link['href']
                if pdf_href.lower().endswith('.pdf'):
                    pdf_url = pdf_href if pdf_href.startswith('http') else requests.compat.urljoin(detail_url, pdf_href)
                    filename = os.path.join(dest_folder, os.path.basename(pdf_url))
                    pdfs.append({'url': pdf_url, 'filename': filename, 'source': detail_url})
                    if len(pdfs) >= max_files:
                        break
            if len(pdfs) >= max_files:
                break
        except Exception as e:
            print(f'錯誤: {detail_url} 解析失敗: {e}')
    # 3. 下載 PDF
    for pdf in pdfs:
        if not os.path.exists(pdf['filename']):
            print(f'下載: {pdf["url"]}')
            r = requests.get(pdf['url'])
            with open(pdf['filename'], 'wb') as f:
                f.write(r.content)
    # 儲存來源對照
    with open(os.path.join(dest_folder, 'pdf_sources.json'), 'w', encoding='utf-8') as f:
        json.dump(pdfs, f, ensure_ascii=False, indent=2)
    return pdfs

# ====== 新增：OCR PDF 儲存為 JSON，支援繁中 ======
def ocr_pdf_to_json(pdf_path, json_path, lang='chi_tra+eng'):
    images = convert_from_path(pdf_path)
    pages = []
    for i, img in enumerate(images):
        text = pytesseract.image_to_string(img, lang=lang)
        pages.append({'page_num': i+1, 'page_text': text})
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({'pages': pages}, f, ensure_ascii=False, indent=2)

# ====== 新增：自動檢查繁中語言包 ======
def check_tesseract_lang(lang_code='chi_tra'):
    tessdata_dir = os.environ.get('TESSDATA_PREFIX')
    if not tessdata_dir:
        tessdata_dir = r'D:\tesseract-5.5.2\tessdata'
    traineddata_path = os.path.join(tessdata_dir, f'{lang_code}.traineddata')
    if not os.path.exists(traineddata_path):
        print(f'警告：找不到 {lang_code}.traineddata，請至 https://github.com/tesseract-ocr/tessdata 下載並放到 {tessdata_dir}')
        return False
    return True

def main():
    # 抑制 pdfplumber/pdfminer 警告
    warnings.filterwarnings("ignore")
    # ====== Tesseract 安裝與路徑說明 ======
    # 若未加到 Path，請手動指定 tesseract.exe 路徑
    # pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
    # 請確認已安裝 chi_tra.traineddata 語言包於 tessdata 目錄
    if not check_tesseract_lang('chi_tra'):
        print('請安裝繁體中文語言包 chi_tra.traineddata 後再執行。')
        return

    # ====== 自動爬取台灣政府PDF ======
    base_url = 'https://data.gov.tw/datasets/search?p=1&size=10&s=_score_desc&rafft=6415'  # 可更換其他政府網站
    print('開始爬取政府PDF...')
    pdfs = crawl_gov_pdfs(base_url, dest_folder='assets', max_files=3)

    # ====== OCR 處理並儲存 JSON ======
    for pdf in pdfs:
        pdf_path = pdf['filename']
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        ocr_json_path = f'ocr_output_{base_name}.json'
        if not os.path.exists(ocr_json_path):
            print(f'OCR: {pdf_path}')
            ocr_pdf_to_json(pdf_path, ocr_json_path, lang='chi_tra+eng')

    # ====== CER 批次測試 ======
    pdf_dir = 'assets'
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print('assets/ 沒有 PDF 檔案')
        return
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_dir, pdf_file)
        base_name = os.path.splitext(pdf_file)[0]
        ocr_json_path = f'ocr_output_{base_name}.json'
        if not os.path.exists(ocr_json_path):
            print(f'找不到對應的 ocr_output 檔案: {ocr_json_path}，略過 {pdf_file}')
            continue
        gt_text = extract_pdf_text(pdf_path)
        if len(gt_text.strip()) < 10:
            print(f'--- {pdf_file} ---')
            print('原始PDF字數過少，可能為圖片型PDF，略過此檔案。')
            print()
            continue
        ocr_text = extract_ocr_text(ocr_json_path)
        error_rate, dist, total = cer(gt_text, ocr_text)
        print(f'--- {pdf_file} ---')
        print(f'原始PDF字數: {total}')
        print(f'OCR字數: {len(ocr_text)}')
        print(f'編輯距離: {dist}')
        print(f'字錯率(CER): {error_rate*100:.2f}%')
        print()

if __name__ == '__main__':
    main()
