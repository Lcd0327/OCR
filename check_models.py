from google import genai
import os
from dotenv import load_dotenv

load_dotenv("azure.env")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("錯誤: 未設定 GEMINI_API_KEY，請檢查 azure.env 檔案")
else:
    try:
        client = genai.Client(api_key=api_key)
        print("正在取得可用模型清單...\n")
        
        # 由於新舊版 SDK 方法不同，這裡嘗試列出模型
        # 新版 google-genai SDK
        for m in client.models.list():
            print(f"- {m.name}")
                
    except Exception as e:
        print(f"發生錯誤: {e}")
        print("\n如果出現 AttributeError，可能是 SDK 版本差異，請嘗試升級套件：")
        print("pip install --upgrade google-genai")
