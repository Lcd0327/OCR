# OCR 

## 概述
本次重構將原本的單一檔案拆分為模組化架構，提高代碼的可讀性、維護性和可測試性。

## 套件
```python
pip install azure-cognitiveservices-vision-computervision
pip install msrest
pip install python-dotenv
pip install opencv-python
pip install genai
```
## 架構說明

### 1. `ocr_processor.py` - 核心處理模組
**主要類別：**

#### OCRConfig
- 集中管理所有配置參數
- Azure OCR API 設定
- 表格檢測參數
- 支援的檔案格式

#### TextItem 
- 封裝文字項目及其座標資訊
- 提供計算屬性（寬度、高度、中心點）
- 支援字典轉換

#### TableDetector
- 負責表格檢測邏輯
- Y座標分組功能
- 智能對齊檢測
- 分隔詞識別

#### TableFormatter
- 表格格式化和輸出
- 列邊界檢測
- 單元格分配
- 美化輸出格式

#### OCRProcessor
- 主要的 OCR 處理器
- 統合所有功能
- 檔案驗證和處理
- 結果整合

#### FileManager
- 檔案管理工具
- 結果保存
- 資料夾掃描

### 2. `quickstart.py` - 主程式
- 簡化的主程式邏輯
- 清晰的使用者介面
- 錯誤處理
- 統計資訊顯示


## 使用方式

### 前置設定
```python
from dotenv import load_dotenv
load_dotenv()
    def __init__(self):
        self.subscription_key = os.getenv("AZURE_SUBSCRIPTION_KEY") #create key in .env
        self.endpoint = os.getenv("AZURE_ENDPOINT")#create endpoint in .env
```

### 基本使用
```python
from ocr_processor import OCRProcessor

processor = OCRProcessor()
success, result = processor.process_file("path/to/file.pdf")
```

## 後續改進建議
1. 加入單元測試
2. 支援多執行緒處理
3. 加入進度條顯示
4. 支援更多輸出格式
5. 加入日誌記錄功能

## TODO
1. 影像銳利化
2. 去噪
3. 超分辨率
4. 邊緣對比
