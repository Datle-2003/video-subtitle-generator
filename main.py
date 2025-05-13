import argparse
import logging
import sys
import os
import time
from translation.translation import Translator
from audio_extraction.extract_audio import Media, MediaProcessor
from speech_to_text.transcribe import WhisperTranscriber
from translation.gemini import GeminiLLM


def parse_args():
    parser = argparse.ArgumentParser(description="Video Subtitle Generator - Extract audio, transcribe, translate, and add subtitles")

    parser.add_argument(
        "--input_file",
        type=str,
        required=True,
        help="Path to the input file (video/audio) to be processed",
    )

    parser.add_argument(
        "--output_file",
        type=str,
        required=False,
        help="Path to the final output file. If not provided, it will be saved in the same directory as input_file",
    )

    parser.add_argument(
        "--source_language",
        type=str,
        required=False,
        default="auto",
        help="Language code for the input file (e.g., 'en' for English). Default is 'auto'",
    )

    parser.add_argument(
        "--target_language",
        type=str,
        required=True,
        help="Language code for translating subtitles (e.g., 'vi' for Vietnamese)",
    )

    parser.add_argument(
        "--model",
        type=str,
        required=False,
        default="small",
        help="Model to be used for transcription. Options: tiny, base, small, medium, large. Default is 'small'",
    )
    
    parser.add_argument(
        "--skip_extract",
        action="store_true",
        help="Skip audio extraction step if you already have a WAV file",
    )
    
    parser.add_argument(
        "--skip_transcribe",
        action="store_true",
        help="Skip transcription step if you already have an SRT file",
    )
    
    parser.add_argument(
        "--skip_translate",
        action="store_true",
        help="Skip translation step if you already have a translated SRT file",
    )
    
    parser.add_argument(
        "--subtitle_file",
        type=str,
        required=False,
        help="Path to existing subtitle file (if skipping extraction/transcription)",
    )
    
    parser.add_argument(
        "--hardcode",
        action="store_true",
        default=True,
        help="Burn subtitles directly into the video (default: add as separate track)",
    )
    
    parser.add_argument(
        "--chunk_size",
        type=int,
        default=10,
        help="Number of subtitle segments to translate at once (default: 10)",
    )
    
    parser.add_argument(
        "--whisper_dir",
        type=str,
        default="/home/datle/Documents/WorkSpace/Code/Video_Subtitle_Generator/speech_to_text/whisper.cpp",
        help="Path to whisper.cpp directory",
    )
    
    return parser.parse_args()


def process_video(args):
    """Main workflow for processing video and generating subtitles"""
    
    start_time = time.time()
    audio_file = None
    subtitle_file = None
    translated_subtitle_file = None
    
    # Step 1: Extract audio from video if needed
    if not args.skip_extract:
        logging.info("Step 1/4: Extracting audio from input file...")
        try:
            media_info = Media(args.input_file)
            processor = MediaProcessor(media_info)
            audio_file = processor.extract_or_convert_audio()
            logging.info(f"Audio extraction complete: {audio_file}")
        except Exception as e:
            logging.error(f"Audio extraction failed: {e}")
            return False
    else:
        if args.subtitle_file:
            logging.info(f"Skipping audio extraction, using existing subtitle file: {args.subtitle_file}")
        else:
            logging.error("Must provide --subtitle_file when using --skip_extract")
            return False
    
    # Step 2: Transcribe audio to subtitles if needed
    if not args.skip_transcribe:
        if not audio_file and not args.subtitle_file:
            logging.error("No audio file available for transcription")
            return False
            
        logging.info("Step 2/4: Transcribing audio to subtitles...")
        try:
            # Add .bin extension if needed
            model_name = args.model if args.model.startswith("ggml-") else f"ggml-{args.model}.bin"
            
            transcriber = WhisperTranscriber(whisper_dir=args.whisper_dir, model_name=model_name)
            subtitle_file = transcriber.transcribe(
                audio_wav_path=audio_file,
                language=args.source_language,
                output_format="srt"
            )
            logging.info(f"Transcription complete: {subtitle_file}")
        except Exception as e:
            logging.error(f"Transcription failed: {e}")
            return False
    else:
        subtitle_file = args.subtitle_file
        if not subtitle_file:
            logging.error("Must provide --subtitle_file when using --skip_transcribe")
            return False
    
    # Step 3: Translate subtitles if needed
    if not args.skip_translate:
        logging.info("Step 3/4: Translating subtitles...")
        try:
            translator = Translator(llm_provider=GeminiLLM(model_name="gemini-2.0-flash"))
            translated_subtitle_file = translator.translate_subtitle_file_by_chunk(
                input_file_path=subtitle_file,
                target_language=args.target_language,
                output_file_path=None,  
                source_language=args.source_language if args.source_language != "auto" else "en",
                chunk_size=args.chunk_size
            )
            logging.info(f"Translation complete: {translated_subtitle_file}")
        except Exception as e:
            logging.error(f"Translation failed: {e}")
            return False
    else:
        translated_subtitle_file = subtitle_file
        logging.info(f"Skipping translation, using subtitle file: {translated_subtitle_file}")
    
    # Step 4: Add subtitles to video
    logging.info("Step 4/4: Adding subtitles to video...")
    try:
        media_info = Media(args.input_file)
        processor = MediaProcessor(media_info)
        
        final_output = processor.add_subtitles(
            subtitle_file=translated_subtitle_file,
            output_file=args.output_file,
            hardcode=args.hardcode
        )
        logging.info(f"Final video with subtitles created: {final_output}")
    except Exception as e:
        logging.error(f"Adding subtitles failed: {e}")
        return False
    
    total_time = time.time() - start_time
    logging.info(f"Complete workflow finished in {total_time:.2f} seconds")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    args = parse_args()
    success = process_video(args)
    
    if success:
        logging.info("Video processing completed successfully!")
    else:
        logging.error("Video processing failed.")
        sys.exit(1)