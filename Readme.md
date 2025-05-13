# Video subtitle generator

## Description

This tool will generate subtitles for a video by extracting audio, convert it into text(using whisper), and then generate subtitles (using Gemini API)

## Requirements

- Python 3.12 or higher
- whisper.cpp
- Gemini API key

## Installation

1. Clone the repository

2. Install the required packages

3. Install whisper.cpp

   - Follow the instructions in the [whisper.cpp repository]
   - you can also download model from [here](https://huggingface.co/ggerganov/whisper.cpp/tree/main)

4. Set up the Gemini API key

## Usage

1. Run the script with the video file as an argument:
   ```bash
   python generate_subtitles.py <video_file> --format <format> --target-language <language>
   ```
2. The generated subtitles will be saved in the same directory as the video file.

## Example

```bash
python generate_subtitles.py video.mp4 --format srt --target-language en
```

## License

This project is licensed under the MIT License. See the LICENSE file for details.
