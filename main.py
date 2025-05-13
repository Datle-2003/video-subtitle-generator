import argparse
import logging
import sys
import os
import time
from translation.translation import Translator
from audio_extraction.extract_audio import Media, MediaProcessor
from speech_to_text.transcribe import WhisperTranscriber, get_supported_languages
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
        "--output_path",
        type=str,
        required=False,
        help="Path to save the final output file (default: the current directory)",
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
        required=True,
        default="small",
        help="Model to be used for transcription. Options: tiny, base, small, medium, large.",
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
        default="speech_to_text/whisper.cpp",
        help="Path to whisper.cpp directory",
    )
    
    return parser.parse_args()


def remove_temporary_files(file_path):
    # remove the temporary files created during the process
    if os.path.exists(file_path):
        os.remove(file_path)
        logging.info(f"Temporary file removed: {file_path}")



def process_video(args):
    """Main workflow for processing video and generating subtitles"""

    if args.whisper_dir.startswith('/'):
        whisper_dir = args.whisper_dir
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))
        whisper_dir = os.path.join(project_root, args.whisper_dir)
    
    logging.info(f"Using whisper.cpp directory: {whisper_dir}")
    
    start_time = time.time()
    audio_file = None
    subtitle_file = None
    translated_subtitle_file = None
    # Step 1: Extract audio from video
    try:
        logging.info("Step 1/3: Extracting audio from video file...")
        media_info = Media(args.input_file)
        processor = MediaProcessor(media_info)
        audio_file = processor.extract_or_convert_audio()
        logging.info(f"Audio extraction complete: {audio_file}")
    except Exception as e:
        logging.error(f"Audio extraction failed: {e}")
        return False
    
    # Step 2: Transcribe audio to subtitles
    try:
        logging.info("Step 2/3: Transcribing audio to subtitles...")
        model_name = args.model if args.model.startswith("ggml-") else f"ggml-{args.model}.bin"
        
        transcriber = WhisperTranscriber(whisper_dir=whisper_dir, model_name=model_name)
        subtitle_file = transcriber.transcribe(
            audio_wav_path=audio_file,
            language=args.source_language,
            output_format="srt"
        )
        logging.info(f"Transcription complete: {subtitle_file}")
    except Exception as e:
        logging.error(f"Transcription failed: {e}")
        return False
    
    # Step 3: Translate subtitles
    try:
        logging.info("Step 3/3: Translating subtitles...")
        translator = Translator(llm_provider=GeminiLLM(model_name="gemini-2.0-flash"))
        translated_subtitle_file = translator.translate_subtitle_file_by_chunk(
            input_file_path=subtitle_file,
            target_language=args.target_language,
            output_file_path=None,  
            source_language=args.source_language,
            chunk_size=args.chunk_size
        )
        logging.info(f"Translation complete: {translated_subtitle_file}")
    except Exception as e:
        logging.error(f"Translation failed: {e}")
        return False
    
    # Move the translated file to output_path if specified
    if args.output_path:
        if not os.path.exists(args.output_path):
            os.makedirs(args.output_path, exist_ok=True)
            logging.info(f"Created output directory: {args.output_path}")
        
        # Get the filename from the path
        filename = os.path.basename(translated_subtitle_file)
        destination_path = os.path.join(args.output_path, filename)
        
        # Copy the file to destination
        import shutil
        shutil.copy2(translated_subtitle_file, destination_path)
        
        # Update the path
        logging.info(f"Moved translated subtitle file to: {destination_path}")
        translated_subtitle_file = destination_path

    total_time = time.time() - start_time
    logging.info(f"Complete workflow finished in {total_time:.2f} seconds")
    logging.info(f"Final subtitle file: {translated_subtitle_file}")



    # Clean up temporary files
    remove_temporary_files(audio_file)
    remove_temporary_files(subtitle_file)


    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    if "--help" in sys.argv:
        print("Usage: python main.py --input_file <input_file> --target_language <target_language> [options]")
        print("Options:")
        print("  --output_file <output_file>       Path to the final output file")
        print("  --source_language <source_lang>    Language code for the input file (default: 'auto')")
        print("  --model <model>                    Model for transcription (default: 'small')")
        print("  --chunk_size <chunk_size>          Number of subtitle segments to translate at once (default: 10)")
        print("  --whisper_dir <whisper_dir>        Path to whisper.cpp directory (default: 'speech_to_text/whisper.cpp')")
        sys.exit(0)

    if "--list-languages" in sys.argv:
        languages = get_supported_languages()
        print("Supported languages:")
        for lang in languages:
            print(f"  {lang}")
        sys.exit(0)

    args = parse_args()
    success = process_video(args)

    
    
    
    if success:
        logging.info("Video processing completed successfully!")
    else:
        logging.error("Video processing failed.")
        sys.exit(1)