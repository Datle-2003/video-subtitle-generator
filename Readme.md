# Video subtitle generator

## Description

This tool generates subtitles for videos by extracting audio, converting it into text (using whisper.cpp), and then translating subtitles (using Gemini API).

## Installation

1. Clone the repository

```bash
git clone https://github.com/Datle-2003/video-subtitle-generator.git
cd Video_Subtitle_Generator
```

2. Install the required packages

```bash
pip install -r requirements.txt
```

3. Install whisper.cpp

```bash
cd speech_to_text
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp
```

- Follow the instructions in the [whisper.cpp repository](https://github.com/ggml-org/whisper.cpp.git)
- Download the appropriate model for your device
  ```bash
  cd whisper.cpp
  sh ./models/download-ggml-model.sh <model_name>
  ```
- Alternatively, you can download model from [Hugging Face](https://huggingface.co/ggerganov/whisper.cpp/tree/main)

- Build the whisper.cpp
  ```bash
  cmake -B build
  cmake --build build --config Release
  ```

4. Set up the Gemini API key

- You can add your Gemini API key in .env file or set it as an environment variable:
  ```bash
  export GEMINI_API_KEY=<your_gemini_api_key>
  ```

## Usage

```bash
python main.py --input_file <video_file> --target_language <target_language> --model <download_model>
```

Required arguments:

- --input_file: Path to the input video file
- --target_language: Language code for the target language (e.g., "en" for English, "vi" for Vietnamese)
- --model: Model name (e.g., "small", "medium", "large")

Optional arguments:

- --output_path: Directory to save the output files (default: current directory)
- --whisper_model_path: Path to whisper.cpp directory (default: "speech_to_text/whisper.cpp/")
- --source_language: Language code of the input file (default: 'auto' for auto-detection)
- --chunk_size: Number of subtitle segments to translate at once (default: 10)

Helper:
- --help: Show help message
- --list-languages: List all supported languages

## Example

```bash
python main.py --input_file "/tests/test.mp4" --target_language vi --model small
```
