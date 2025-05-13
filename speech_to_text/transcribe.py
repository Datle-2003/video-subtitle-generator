import subprocess
import os
import logging


supported_languages = {
        "auto": "Auto-detect",  # Special case
        "en": "English",
        "zh": "Chinese",
        "de": "German",
        "es": "Spanish",
        "ru": "Russian",
        "ko": "Korean",
        "fr": "French",
        "ja": "Japanese",
        "pt": "Portuguese",
        "tr": "Turkish",
        "pl": "Polish",
        "ca": "Catalan",
        "nl": "Dutch",
        "ar": "Arabic",
        "sv": "Swedish",
        "it": "Italian",
        "id": "Indonesian",
        "hi": "Hindi",
        "fi": "Finnish",
        "vi": "Vietnamese",
        "he": "Hebrew",
        "uk": "Ukrainian",
        "el": "Greek",
        "ms": "Malay",
        "cs": "Czech",
        "ro": "Romanian",
        "da": "Danish",
        "hu": "Hungarian",
        "ta": "Tamil",
        "no": "Norwegian",
        "th": "Thai",
        "ur": "Urdu",
        "hr": "Croatian",
        "bg": "Bulgarian",
        "lt": "Lithuanian",
        "la": "Latin",
        "mi": "Maori",
        "ml": "Malayalam",
        "cy": "Welsh",
        "sk": "Slovak",
        "te": "Telugu",
        "fa": "Persian",
        "lv": "Latvian",
        "bn": "Bengali",
        "sr": "Serbian",
        "az": "Azerbaijani",
        "sl": "Slovenian",
        "kn": "Kannada",
        "et": "Estonian",
        "mk": "Macedonian",
        "br": "Breton",
        "eu": "Basque",
        "is": "Icelandic",
        "hy": "Armenian",
        "ne": "Nepali",
        "mn": "Mongolian",
        "bs": "Bosnian",
        "kk": "Kazakh",
        "sq": "Albanian",
        "sw": "Swahili",
        "gl": "Galician",
        "mr": "Marathi",
        "pa": "Punjabi",
        "si": "Sinhala",
        "km": "Khmer",
        "sn": "Shona",
        "yo": "Yoruba",
        "so": "Somali",
        "af": "Afrikaans",
        "oc": "Occitan",
        "ka": "Georgian",
        "be": "Belarusian",
        "tg": "Tajik",
        "sd": "Sindhi",
        "gu": "Gujarati",
        "am": "Amharic",
        "yi": "Yiddish",
        "lo": "Lao",
        "uz": "Uzbek",
        "fo": "Faroese",
        "ht": "Haitian Creole",
        "ps": "Pashto",
        "tk": "Turkmen",
        "nn": "Nynorsk",
        "mt": "Maltese",
        "sa": "Sanskrit",
        "lb": "Luxembourgish",
        "my": "Myanmar",
        "bo": "Tibetan",
        "tl": "Tagalog",
        "mg": "Malagasy",
        "as": "Assamese",
        "tt": "Tatar",
        "haw": "Hawaiian",
        "ln": "Lingala",
        "ha": "Hausa",
        "ba": "Bashkir",
        "jw": "Javanese",
        "su": "Sundanese",
        "yue": "Cantonese"
    }

def is_supported_language(language: str) -> bool:
    return language in supported_languages

def get_supported_languages() -> list:
    # key: value
    return [f"{key}: {value}" for key, value in supported_languages.items()]

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
        if not is_supported_language(language):
            raise ValueError(f"Unsupported language: {language}. Supported languages are: {', '.join(supported_languages.keys())}")

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
