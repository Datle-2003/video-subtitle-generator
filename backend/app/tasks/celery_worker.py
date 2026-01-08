import os
from app.tasks.celery_config import celery_app
from app.services.translation.manager import Translator
from app.services.translation.providers.gemini import GeminiTranslator
from app.services.translation.providers.openrouter import OpenRouterTranslator
from app.services.transcription import Transcriber
from app.services.transcription_groq import GroqTranscriber, get_audio_duration
from app.services.subtitle_processor import SubtitleProcessor
from celery.signals import worker_process_init

from app.log.logging_config import setup_logging
import logging
setup_logging("app.log")

# Configuration
MAX_VIDEO_DURATION_SECONDS = 30 * 60  # 30 minutes max
GROQ_THRESHOLD_SECONDS = 10 * 60       # Use Groq for videos > 10 minutes

whisper_model = None

@worker_process_init.connect # this function start when worker start
def init_worker(**kwargs):
    global whisper_model
    root_logger = logging.getLogger()
    if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
        fh = logging.FileHandler('app.log')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        root_logger.addHandler(fh)
        root_logger.setLevel(logging.INFO)

    try:
        num_threads = os.cpu_count()
        whisper_model = Transcriber(threads=num_threads)
        logging.info("[Celery] Local Whisper Model loaded successfully!")
    except Exception as e:
        logging.error(f"[Celery] Failed to load local Whisper model: {e}")


def transcribe_with_hybrid(file_path: str, whisper_lang: str = None) -> tuple:
    """
    Returns:
        tuple: (segments_list, audio_duration, transcriber_used)
    """
    global whisper_model
    
    # Get audio duration first
    audio_duration = get_audio_duration(file_path)
    logging.info(f"Audio duration: {audio_duration:.2f} seconds ({audio_duration/60:.1f} minutes)")
    
    # Check max duration limit
    if audio_duration > MAX_VIDEO_DURATION_SECONDS:
        raise ValueError(f"Video too long: {audio_duration/60:.1f} minutes. Maximum allowed: {MAX_VIDEO_DURATION_SECONDS/60:.0f} minutes")
    
    # Try Groq API first (better for cloud deployment - no heavy model loading)
    try:
        logging.info("[Hybrid] Trying Groq Whisper API...")
        groq_transcriber = GroqTranscriber(model_name="whisper-large-v3")
        segments_list = groq_transcriber.transcribe(file_path, input_language=whisper_lang)
        return segments_list, audio_duration, "groq"
    except Exception as e:
        logging.warning(f"[Hybrid] Groq API failed: {e}")
    
    # Fallback to local Whisper if Groq fails
    logging.info("[Hybrid] Falling back to local Whisper Turbo...")
    if whisper_model is None:
        raise RuntimeError("Groq API failed and local Whisper model not available")
    
    segments_list = whisper_model.transcribe(file_path, input_language=whisper_lang)
    return segments_list, audio_duration, "local"


@celery_app.task(name="process_video_task", bind=True)
def process_video_task(self, file_path, target_lang, metadata: dict):
    try:
        logging.info(f"Processing task for file: {file_path}")
        self.update_state(state='PROGRESS', meta={'progress': 5, 'message': 'Analyzing audio...'})
        
        # Get source language from metadata (None = auto-detect)
        source_lang = metadata.get('source_lang', 'auto') if metadata else 'auto'
        whisper_lang = None if source_lang == 'auto' else source_lang
        
        # Use hybrid transcription (Groq for >10min, local for <=10min)
        self.update_state(state='PROGRESS', meta={'progress': 10, 'message': 'Transcribing...'})
        segments_list, total_duration, transcriber_used = transcribe_with_hybrid(file_path, whisper_lang)
        
        logging.info(f"Transcription finished using {transcriber_used}. Duration: {total_duration:.1f}s, Segments: {len(segments_list)}")

        # merge segments if needed to avoid too many segments
        subtitle_processor = SubtitleProcessor()
        segments_list = subtitle_processor.merge_segments(segments_list)
        
        # Generate initial SRT (Source Language)
        source_srt_content = subtitle_processor.create_srt_content(segments_list)
        
        # Save temporary SRT for translation input
        base_name = os.path.splitext(file_path)[0]
        source_srt_path = f"{base_name}_source.srt"
        with open(source_srt_path, "w", encoding="utf-8") as f:
            f.write(source_srt_content)

        all_text = subtitle_processor.get_text_from_segments(segments_list)
        # Disable spaCy NER - title case approach caused too many false positives
        # proper_nouns = subtitle_processor.extract_proper_nouns(all_text)
        # proper_nouns = []  # Empty list = no NER hints in prompt
            
        # 2. Update metadata setup
        if metadata:
            metadata['duration'] = total_duration
            # metadata['proper_nouns'] = proper_nouns

        self.update_state(state='PROGRESS', meta={'progress': 50, 'message': 'Translating...'})
        logging.info("Translating...")
        
        gemini_provider = GeminiTranslator(model_name="gemini-2.5-flash")
        openrouter_provider = OpenRouterTranslator(
            priority_model="xiaomi/mimo-v2-flash:free",
            fallback_model="mistralai/devstral-2512:free"
        )
        
        translator = Translator(llm_provider=openrouter_provider)
        
        translated_srt_path = translator.translate_subtitle_file_by_chunk(
            input_file_path=source_srt_path,
            target_language=target_lang,
            metadata=metadata
        )

        
        
        with open(translated_srt_path, "r", encoding="utf-8") as f:
            final_srt_content = f.read()

        # Cleanup temp srt files
        # if os.path.exists(source_srt_path):
        #     os.remove(source_srt_path)
        # if os.path.exists(translated_srt_path):
        #     os.remove(translated_srt_path)

        # 4. Finish
        return {
            "status": "completed",
            "srt_content": final_srt_content,
            "filename": file_path
        }

    except Exception as e:
        logging.error(f"Task failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        # Cleanup original upload
        if os.path.exists(file_path):
            os.remove(file_path)