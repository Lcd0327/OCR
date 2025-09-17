import json


def extract_resume_fields(ocr_json):
    """
    舊版萃取函式，保留原有欄位結構
    """
    page = ocr_json['pages'][0]
    blocks = page.get('text_blocks', [])
    tables = page.get('tables', [])
    result = {}
    basic_info = {}
    for block in blocks:
        for item in block['content']:
            txt = item['text']
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
    for block in blocks:
        for item in block['content']:
            if '應徵職務' in item['text']:
                result['應徵職務'] = item['text']
    for block in blocks:
        for item in block['content']:
            if '語言能力' in item['text'] or '語言程度' in item['text']:
                result['語言能力'] = item['text']
    education = []
    for block in blocks:
        for item in block['content']:
            if '學校' in item['text'] or '科系' in item['text'] or '學位' in item['text']:
                education.append(item['text'])
    if education:
        result['教育背景'] = education
    work_exp = []
    for block in blocks:
        for item in block['content']:
            if '工作經歷' in item['text'] or '工作或社團經歷' in item['text']:
                work_exp.append(item['text'])
    if work_exp:
        result['工作經歷'] = work_exp
    skills = []
    for table in tables:
        if table.get('category') == 'skills':
            for row in table['data']:
                skills.append(row[0])
    if skills:
        result['技能與專長'] = skills
    for block in blocks:
        for item in block['content']:
            if '電腦能力' in item['text'] or '電腦技能' in item['text']:
                result['電腦技能'] = item['text']
    for block in blocks:
        for item in block['content']:
            if '專業證照' in item['text']:
                result['專業證照'] = item['text']
    for block in blocks:
        for item in block['content']:
            if '駕照' in item['text']:
                result['駕照'] = item['text']
    for block in blocks:
        for item in block['content']:
            if '可配合時段' in item['text']:
                result['可配合時段'] = item['text']
    return result


def structure_resume_from_ocr_json(ocr_json):
    """
    新版結構化函式，將 OCR JSON 直接轉成 resume dict
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
    }
    # 基本資料萃取
    for block in blocks:
        for item in block['content']:
            txt = item['text']
            for field, kw_list in keywords.items():
                for kw in kw_list:
                    if kw in txt:
                        # 取出欄位內容
                        value = txt.replace(kw, '').replace(':', '').strip()
                        # 若內容為空，嘗試取下一個 item
                        if not value:
                            idx = block['content'].index(item)
                            if idx + 1 < len(block['content']):
                                next_txt = block['content'][idx+1]['text'].strip()
                                if next_txt and not any(k in next_txt for k in kw_list):
                                    value = next_txt
                        resume[field] = value
    # 技能
    skills = []
    for table in tables:
        if table.get('category') == 'skills':
            for row in table['data']:
                skills.append(row[0])
    if skills:
        resume['skills'] = skills
    # 工作經歷
    work_experience = []
    work_keywords = ['工作經歷', '工作或社團經歷', '經歷', 'experience']
    for block in blocks:
        org, title, period, desc = None, None, None, None
        for item in block['content']:
            txt = item['text']
            if any(kw in txt for kw in ['公司', '組織', '餐廳', '社', 'organization']):
                org = txt
            if any(kw in txt for kw in ['職稱', 'title', '服務生', '活動長']):
                title = txt
            if any(kw in txt for kw in ['年', '月', '日', 'period', '時間', '至']):
                period = txt
            if any(kw in txt for kw in ['負責', '工作內容', '描述', 'desc', 'summary']):
                desc = txt
        if org and title and period:
            work_experience.append({
                'organization': org,
                'title': title,
                'period': period,
                'description': desc or ''
            })
    if work_experience:
        resume['work_experience'] = work_experience
    # 語言能力
    language_keywords = ['語言能力', '語言', 'language']
    for block in blocks:
        for item in block['content']:
            txt = item['text']
            if any(kw in txt for kw in language_keywords):
                langs = [lang for lang in txt.replace('語言能力', '').replace('語言', '').replace(':', '').split('、') if lang]
                resume['languages'] = langs
    # 電腦技能
    computer_keywords = ['電腦能力', '電腦技能', 'computer', 'Excel', 'Word']
    for block in blocks:
        for item in block['content']:
            txt = item['text']
            if any(kw in txt for kw in computer_keywords):
                skills_list = [skill for skill in txt.replace('擅長', '').replace('電腦能力', '').replace('電腦技能', '').replace(':', '').split('、') if skill]
                resume['computer_skills'] = skills_list
    # 證照
    certificate_keywords = ['證照', 'license', 'certificate', '丙級', '蛋糕']
    for block in blocks:
        for item in block['content']:
            txt = item['text']
            if any(kw in txt for kw in certificate_keywords):
                certs = [cert for cert in txt.replace('專業證照', '').replace('證照', '').replace(':', '').split('、') if cert]
                resume['certificates'] = certs
            if '駕照' in txt:
                resume['license'] = [txt.replace('駕照', '').strip()]
    # 可配合時段
    available_times = {}
    days = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
    for block in blocks:
        for item in block['content']:
            txt = item['text']
            for day in days:
                if day in txt:
                    # 嘗試找時間
                    time_str = None
                    for t_item in block['content']:
                        if any(h in t_item['text'] for h in ['10:00', '09:00', '18:00', '19:00']):
                            time_str = t_item['text']
                    available_times[day] = time_str or ''
    if available_times:
        resume['available_times'] = available_times
    return resume

