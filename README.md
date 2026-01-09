# Video Subtitle Generator

A tool that automatically generates and translates video subtitles using speech-to-text (Groq API / Faster-Whisper model) and translation (Google Gemini API).

## Features

- Extract audio from video files
- Speech-to-text transcription (Groq API / Faster-Whisper)
- Subtitle translation to multiple languages (Gemini API)
- Background processing with Celery

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Redis server
- API Keys: Groq API, Google Gemini API

### Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Create .env file with your API keys
cat > .env << EOL
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
REDIS_URL=redis://localhost:6379/0
EOL

# Start Celery worker (in a separate terminal)
celery -A app.tasks.celery_worker worker --loglevel=info

# Start FastAPI server
uvicorn app.main:main --reload --host 0.0.0.0 --port 8000
```

You can choose using Faster-Whisper model instead (view `app/services/transcription.py` for more details)

### Frontend Setup

```bash
cd subtitle-web-client

# Install dependencies
npm install

# Create .env file
echo "VITE_API_URL=http://localhost:8000" > .env

# Start development server
npm run dev
```

## Usage

1. **Open the web app** at `http://localhost:5173`

2. **Upload a video file**

3. **Select languages:**
   - Source language (auto-detect or specify)
   - Target language for translation

4. **Add context** (optional): Provide context like names or technical terms for better translation

5. **Click "Generate Subtitles"** and wait for processing

6. **Download** the generated `.srt` subtitle file