from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from app.tasks.celery_worker import process_video_task
import shutil
import os
import uuid
from celery.result import AsyncResult
from app.log.logging_config import setup_logging
import logging
from app.utils.common import get_language_from_code
setup_logging("app.log")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Subtitle Generator API is running!"}

@app.post("/generate-subtitle")
async def generate_subtitle(
    file: UploadFile = File(...), 
    target_lang: str = Form("en"),
    source_lang: str = Form("auto"),
    context: str = Form("")
):
    logging.info(f"Receive request with file: {file.filename}, source language: {source_lang}, target language: {target_lang}, context: {context}")

    file_id = str(uuid.uuid4())
    temp_filename = f"/tmp/{file_id}_{file.filename}"

    metadata = {
        "filename": file.filename,
        "context": context,
        "source_lang": source_lang,
    }
    
    try:
        with open(temp_filename, "wb") as f:
            shutil.copyfileobj(file.file, f)
            logging.info(f"File saved to {temp_filename}")  

        # Check audio duration before processing (max 30 minutes)
        MAX_DURATION_SECONDS = 30 * 60  # 30 minutes
        from app.services.transcription_groq import get_audio_duration
        try:
            duration = get_audio_duration(temp_filename)
            logging.info(f"Audio duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
            
            if duration > MAX_DURATION_SECONDS:
                os.remove(temp_filename)
                raise HTTPException(
                    status_code=400, 
                    detail=f"Video too long: {duration/60:.1f} minutes. Maximum allowed: 30 minutes."
                )
        except HTTPException:
            raise
        except Exception as e:
            logging.warning(f"Could not check duration, proceeding anyway: {e}")

        # push task into celery
        # celery client will send task to broker
        target_language = get_language_from_code(target_lang)

        if not target_language:
            raise HTTPException(status_code=400, detail="Invalid target language")

        task = process_video_task.delay(temp_filename, target_language, metadata)
        logging.info(f"Task ID: {task.id} pushed into redis (target: {target_language})") 
    
        return {
            "task_id": task.id,
            "message": "File uploaded successfully. Processing in background."
        }
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
            logging.info(f"Error processing file {temp_filename}: {str(e)}\"")
        return {"error": str(e)}
        

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    task_result = AsyncResult(task_id)
    
    if task_result.state == 'PENDING':
        return {"state": "pending", "progress": 0}
    elif task_result.state == 'PROGRESS':
        return {
            "state": "processing", 
            "progress": task_result.info.get('progress', 0),
            "message": task_result.info.get('message', '')
        }
    elif task_result.state == 'SUCCESS':
        return {
            "state": "completed", 
            "progress": 100,
            "result": task_result.result 
        }
    else:
        return {"state": "failed", "error": str(task_result.info)}