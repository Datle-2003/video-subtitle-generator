"""
Groq Whisper API Transcription Service
Uses Groq's hosted Whisper Large v3 for faster and more accurate transcription.
"""
import os
import logging
from groq import Groq
from typing import Optional, List

from app.log.logging_config import setup_logging
setup_logging("app.log")

from dotenv import load_dotenv
load_dotenv()


class Segment:
    """Segment class compatible with local Whisper output"""
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text

    def __str__(self):
        return f"[{self.start:.2f}s -> {self.end:.2f}s] {self.text}"

    def __repr__(self):
        return self.__str__()


class GroqTranscriber:
    """
    Transcriber using Groq's Whisper API.
    Supports whisper-large-v3 and whisper-large-v3-turbo models.
    """
    
    def __init__(self, model_name: str = "whisper-large-v3"):
        self.api_key = os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set in environment variables")
        
        self.client = Groq(api_key=self.api_key)
        self.model_name = model_name
        logging.info(f"[Groq] Initialized with model: {model_name}")
    
    def transcribe(self, audio_path: str, input_language: Optional[str] = None) -> List[Segment]:
        """
        Transcribe audio file using Groq Whisper API.
        
        Args:
            audio_path: Path to the audio file
            input_language: Language code (e.g., 'vi', 'en') or None for auto-detect
            
        Returns:
            List of Segment objects with start, end, and text
        """
        logging.info(f"[Groq] Transcribing: {audio_path} with language: {input_language or 'auto-detect'}")
        
        try:
            with open(audio_path, "rb") as audio_file:
                # Build transcription parameters
                params = {
                    "file": (os.path.basename(audio_path), audio_file),
                    "model": self.model_name,
                    "response_format": "verbose_json",  # Get timestamps
                    "temperature": 0.0,
                }
                
                # Add language if specified (None = auto-detect)
                if input_language:
                    params["language"] = input_language
                
                # Call Groq API
                transcription = self.client.audio.transcriptions.create(**params)
            
            # Log detected language if available
            if hasattr(transcription, 'language'):
                logging.info(f"[Groq] Detected language: {transcription.language}")
            
            # Parse segments from response
            segment_list = []
            
            if hasattr(transcription, 'segments') and transcription.segments:
                for seg in transcription.segments:
                    segment_list.append(Segment(
                        start=seg.get('start', 0),
                        end=seg.get('end', 0),
                        text=seg.get('text', '').strip()
                    ))
                logging.info(f"[Groq] Transcription complete: {len(segment_list)} segments")
            else:
                # Fallback: if no segments, create one segment with full text
                logging.warning("[Groq] No segments in response, using full text as single segment")
                if hasattr(transcription, 'text') and transcription.text:
                    segment_list.append(Segment(
                        start=0,
                        end=0,
                        text=transcription.text.strip()
                    ))
            
            return segment_list
            
        except Exception as e:
            logging.error(f"[Groq] Transcription failed: {e}")
            raise


def get_audio_duration(audio_path: str) -> float:
    """
    Get the duration of an audio file in seconds.
    Uses ffprobe for accurate duration detection.
    """
    import subprocess
    import json
    
    try:
        result = subprocess.run(
            [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', audio_path
            ],
            capture_output=True,
            text=True
        )
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return duration
    except Exception as e:
        logging.warning(f"Could not get audio duration with ffprobe: {e}")
        # Fallback: estimate from file size (rough estimate)
        file_size = os.path.getsize(audio_path)
        # Assume ~32kbps for mp3 = 4KB/second
        return file_size / 4000
