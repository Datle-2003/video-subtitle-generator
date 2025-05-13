import subprocess
import os
import logging

class WhisperTranscriber:
    def __init__(self, whisper_dir: str, model_name: str = "ggml-small.bin"):
        self.whisper_dir = os.path.abspath(whisper_dir)
        self.executable_path = os.path.join(self.whisper_dir, "build", "bin", "whisper-cli")
        self.model_path = os.path.join(self.whisper_dir, "models", model_name)

        if not os.path.isfile(self.executable_path):
            raise FileNotFoundError(
                f"whisper-cli not found: {self.executable_path}. "
                f"Ensure you have compiled the whisper.cpp project and the executable is in the correct path."
            )
        if not os.path.isfile(self.model_path):
            raise FileNotFoundError(
                f"Model file not found: {self.model_path}. "
                f"Ensure the model file is in the correct path."
            )
        
        logging.info(f"Whisper executable found at: {self.executable_path}")

    def transcribe(self, audio_wav_path: str, language: str = "auto", output_format: str = "txt") -> str:
        audio_wav_path = os.path.abspath(audio_wav_path)
        if not os.path.isfile(audio_wav_path):
            raise FileNotFoundError(f"Audio file not found: {audio_wav_path}")
        
        output_file_path = f"{audio_wav_path}.{output_format}"
        
        # -m: model path
        # -f: input audio
        # -l: language
        # -nt: do not print timestamps
        # -osrt: output in a srt file
        # -otxt: output in a txt file
        # -ovtt: output in a vtt file
        command = [
            self.executable_path,
            "-m", self.model_path,
            "-f", audio_wav_path,
            "-l", language,
        ]

        if output_format == "srt":
            command.append("-osrt")
        elif output_format == "vtt":
            command.append("-ovtt")
        else:
            command.append("-otxt")

        try:

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8',
            )

            logging.info(f"Command executed: {' '.join(command)}")
            logging.info(f"Transcription completed successfully. Output: {result.stdout}")

            if os.path.exists(output_file_path):
                logging.info(f"Output file created at: {output_file_path}")
                return output_file_path
            else:
                raise FileNotFoundError(f"Expected output file {output_file_path} was not created")
    
        except subprocess.CalledProcessError as e:
            logging.error(f"Error when running whisper-cli: {e}")
            raise RuntimeError(f"Whisper-cli error: {e.stderr.strip()}") from e
        except Exception as e:
            logging.error(f"Unexpected error during transcription: {e}")
            raise RuntimeError(f"Unexpected error: {e}") from e



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    WHISPER_CPP_PROJECT_DIR = "/home/datle/Documents/WorkSpace/Code/Video_Subtitle_Generator/speech_to_text/whisper.cpp"
    INPUT_AUDIO_FILE = "/home/datle/Documents/WorkSpace/Code/Video_Subtitle_Generator/output.wav"
    MODEL = "ggml-small.bin"
    LANGUAGE = "auto"
    OUTPUT_FORMAT = "srt"

    try:
        transcriber = WhisperTranscriber(whisper_dir=WHISPER_CPP_PROJECT_DIR, model_name=MODEL)
        transcript = transcriber.transcribe(INPUT_AUDIO_FILE, language=LANGUAGE, output_format=OUTPUT_FORMAT)

    except Exception as e:
        logging.error(f"Error: {e}")