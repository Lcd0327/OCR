from fastapi import FastAPI, UploadFile, File
from ocr_processor import OCRProcessor, OCRConfig

app = FastAPI()
processor = OCRProcessor(OCRConfig())

@app.post("/ocr")
async def ocr_file(file: UploadFile = File(...)):
    file_path = f"temp_{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    success, result = processor.process_file(file_path)
    return {"success": success, "result": result}