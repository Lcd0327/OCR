# OCR 重構版本說明

## 概述
本次重構將原本的單一檔案拆分為模組化架構，提高代碼的可讀性、維護性和可測試性。

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

## 重構優勢

### 1. 模組化設計
- **單一職責原則**: 每個類別只負責一個特定功能
- **關注點分離**: 配置、檢測、格式化、檔案管理各自獨立
- **易於測試**: 每個模組可以獨立測試

### 2. 可維護性提升
- **代碼組織**: 相關功能歸類在一起
- **參數集中**: 所有配置參數在 OCRConfig 中統一管理
- **清晰命名**: 類別和方法名稱更具描述性

### 3. 可擴展性
- **配置彈性**: 可以輕鬆調整檢測參數
- **功能擴展**: 新增檢測器或格式化器很容易
- **多種輸出**: 支援不同的輸出格式

### 4. 錯誤處理
- **結構化錯誤**: 統一的錯誤處理機制
- **狀態回傳**: 明確的成功/失敗狀態
- **錯誤資訊**: 詳細的錯誤描述

## 使用方式

### 基本使用
```python
from ocr_processor import OCRProcessor

processor = OCRProcessor()
success, result = processor.process_file("path/to/file.pdf")
```

### 自訂配置
```python
from ocr_processor import OCRProcessor, OCRConfig

config = OCRConfig()
config.y_tolerance = 20  # 調整Y座標容差
config.alignment_tolerance = 80  # 調整對齊容差

processor = OCRProcessor(config)
```

## 原始功能保持
- ✅ 支援圖片和PDF檔案
- ✅ 自動掃描 assets 資料夾
- ✅ 表格檢測和格式化
- ✅ JSON 和文字檔案輸出
- ✅ 統計資訊顯示
- ✅ 中文表格分隔詞識別

## 後續改進建議
1. 加入單元測試
2. 支援多執行緒處理
3. 加入進度條顯示
4. 支援更多輸出格式
5. 加入日誌記錄功能
