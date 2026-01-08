import logging
from faster_whisper import WhisperModel
import os

from app.log.logging_config import setup_logging
setup_logging("app.log")

class Segment:
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text

    def __str__(self):
        return f"[{self.start:.2f}s -> {self.end:.2f}s] {self.text}"

    def __repr__(self):
        return self.__str__()

class Transcriber:
    def __init__(self, model_name: str = "deepdml/faster-whisper-large-v3-turbo-ct2", threads: int = 2, device: str = "cpu"):
        cores = os.cpu_count() or 1
        if threads > cores:
            logging.warning(f"Requested threads {threads} exceed available CPU cores {cores}. Using {cores} threads instead.")
            threads = cores
        
        self.model_name = model_name
        self.threads = threads
        self.device = device

        logging.info(f"Loading model {model_name} with {threads} threads on {device}...")
        self.model = WhisperModel(
            model_name,
            device=device,
            compute_type="int8",
            cpu_threads=threads
        )


    def transcribe(self, audio_path: str, input_language: str = None):
        segments, info = self.model.transcribe(
            audio_path,
            beam_size=1,
            best_of=1,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            language=input_language,  # None = auto-detect
            condition_on_previous_text=False,
            temperature=0
        )
        
        # Log detected language if auto-detected
        if input_language is None:
            logging.info(f"Auto-detected language: {info.language} (probability: {info.language_probability:.2%})")

        # copy into transcription result
        segment_list = []
        for segment in segments:
            segment_list.append(Segment(segment.start, segment.end, segment.text))
        return segment_list




