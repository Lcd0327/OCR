import json
import spacy
nlp = spacy.load("zh_core_web_sm")

def extract_entities(text):
    doc = nlp(text)
    entities = [(ent.text, ent.label_) for ent in doc.ents]
    return entities


def extract_resume_fields(ocr_json):
    """
    萃取函式，將 OCR JSON 轉成 resume dict，僅萃取常見欄位
    """
    page = ocr_json['pages'][0]
    blocks = page.get('text_blocks', [])
    tables = page.get('tables', [])
    result = {}
    basic_info = {}

    for block in blocks:
        for item in block['content']:
            txt = item.get('value') or item.get('text') or ''

            if '姓名' in txt or '中文姓名' in txt:
                basic_info['姓名'] = txt
            elif '羅馬拼音' in txt:
                basic_info['羅馬拼音'] = txt
            elif '性別' in txt:
                basic_info['性別'] = txt
            elif '生日' in txt or '出生日期' in txt:
                basic_info['生日'] = txt
            elif '年齡' in txt:
                basic_info['年齡'] = txt
            elif '手機' in txt:
                basic_info['手機'] = txt
            elif 'Email' in txt:
                basic_info['Email'] = txt
            elif '最高學歷' in txt:
                basic_info['最高學歷'] = txt
            elif '學校' in txt:
                basic_info['學校'] = txt
            elif '科系' in txt:
                basic_info['科系'] = txt
            elif '通訊地址' in txt or '居住地區' in txt:
                basic_info['地址'] = txt
            elif '就業狀態' in txt:
                basic_info['就業狀態'] = txt
            elif '預定可到職' in txt:
                basic_info['預定可到職'] = txt
    if basic_info:
        result['基本資料'] = basic_info
    return result


def structure_resume_from_ocr_json(ocr_json):
    """
    新版結構化函式，將 OCR JSON 直接轉成 resume dict，支援 key-value 配對
    """
    page = ocr_json['pages'][0]
    blocks = page.get('text_blocks', [])
    tables = page.get('tables', [])
    resume = {}
    # 關鍵字定義
    keywords = {
        'name': ['姓名', '中文姓名', 'name'],
        'phone': ['手機', '電話', 'phone', 'tel'],
        'email': ['Email', 'E-mail', 'email', 'mail'],
        'address': ['通訊地址', '居住地', '地址', 'address'],
        'birth_date': ['出生日期', '生日', 'birth', '出生'],
        'education': ['最高學歷', '學歷', '學校', '科系', 'education', 'degree'],
        'job_title': ['應徵職務', '職稱', 'job', 'title', '申請職位'],
        'gender': ['性別', 'gender'],
        'age': ['年齡', 'age'],
        'language': ['語言能力', '語言', 'language'],
        'license': ['駕照', 'license'],
        'certificate': ['證照', 'certificate', '專業證照'],
        'available_time': ['可配合時段', '時段', '時間'],
        'self_intro': ['自傳', '簡介', '自我介紹'],
        'work_experience': ['工作經歷', '工作或社團經歷', '經歷', 'experience'],
        'skills': ['技能', '專長', '能力'],
        'computer_skills': ['電腦能力', '電腦技能', 'computer', 'Excel', 'Word'],
    }

    # NLP 分析重點
    all_text = []
    for block in blocks:
        for item in block.get('content', []):
            key = item.get('key', '')
            value = item.get('value', '')
            if key:
                all_text.append(key)
            if value:
                all_text.append(value)
    for table in tables:
        for row in table.get('data', []):
            all_text.extend(row)
    full_text = '\n'.join(all_text)
    doc = nlp(full_text)
    key_points = []
    for ent in doc.ents:
        key_points.append({'text': ent.text, 'label': ent.label_})

    # 基本資料萃取（用 key 來判斷）
    for block in blocks:
        for item in block.get('content', []):
            key = item.get('key', '')
            value = item.get('value', '')
            for field, kw_list in keywords.items():
                if any(kw in key for kw in kw_list):
                    # 多欄位支援（如多個語言、證照等）
                    if field in ['language', 'certificate', 'skills', 'computer_skills']:
                        if value:
                            resume.setdefault(field, []).append(value)
                    elif field == 'work_experience':
                        resume.setdefault(field, []).append(value)
                    else:
                        resume[field] = value

    # 技能（表格）
    skills = []
    for table in tables:
        if table.get('category') == 'skills':
            for row in table.get('data', []):
                if row and row[0]:
                    skills.append(row[0])
    if skills:
        resume.setdefault('skills', []).extend(skills)

    # 工作經歷（表格）
    work_exp = []
    for table in tables:
        if table.get('category') == 'work_experience':
            for row in table.get('data', []):
                work_exp.append(row)
    if work_exp:
        resume['work_experience_table'] = work_exp

    # 語言能力（表格）
    languages = []
    for table in tables:
        if table.get('category') == 'language':
            for row in table.get('data', []):
                languages.append(row)
    if languages:
        resume['languages_table'] = languages

    # 電腦技能（表格）
    computer_skills = []
    for table in tables:
        if table.get('category') == 'computer_skills':
            for row in table.get('data', []):
                computer_skills.append(row)
    if computer_skills:
        resume['computer_skills_table'] = computer_skills

    # 證照（表格）
    certificates = []
    for table in tables:
        if table.get('category') == 'certificate':
            for row in table.get('data', []):
                certificates.append(row)
    if certificates:
        resume['certificates_table'] = certificates

    # 可配合時段（表格）
    available_times = {}
    days = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
    for block in blocks:
        for item in block.get('content', []):
            key = item.get('key', '')
            value = item.get('value', '')
            for day in days:
                if day in key:
                    available_times[day] = value
    if available_times:
        resume['available_times'] = available_times

    # 自傳/自我介紹
    intros = []
    for block in blocks:
        for item in block.get('content', []):
            key = item.get('key', '')
            value = item.get('value', '')
            if any(kw in key for kw in keywords['self_intro']):
                intros.append(value)
    if intros:
        resume['self_intro'] = '\n'.join(intros)

    # 加入 NLP 分析重點
    if key_points:
        resume['key_points'] = key_points

    return resume
