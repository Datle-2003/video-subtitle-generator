import google.generativeai as genai
import os
import json
import logging
from app.services.translation.providers.provider_interface import BaseTranslationProvider
from app.utils.common import json_to_srt

from app.log.logging_config import setup_logging
setup_logging("app.log")

from dotenv import load_dotenv
load_dotenv()


class GeminiTranslator(BaseTranslationProvider):
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self.api_key = os.environ.get("GEMINI_API_KEY") 
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY is not set")
        
        genai.configure(api_key=self.api_key) 
        self._model_name = model_name
        self.safety_settings = {
            "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
        }
        self.generation_config = genai.GenerationConfig(
            temperature=0.1,
            response_mime_type="application/json"
        )
        self.model = genai.GenerativeModel(model_name, safety_settings=self.safety_settings, generation_config=self.generation_config)

    def get_model_name(self) -> str:
        return self._model_name

    def translate(self, prompt: str, original_chunk_for_fallback: str, retry_count: int = 2) -> str:
        import time
        
        json_instruction = """
        Output the result strictly as a JSON Array of objects. 
        Each object must have these keys: "id" (string), "start" (string timestamp), "end" (string timestamp), "text" (translated string).
        Example: [{"id": "1", "start": "00:00:01,000", "end": "00:00:05,000", "text": "Xin chào"}]
        """
        full_prompt = f"{prompt}\n\n{json_instruction}"

        for attempt in range(retry_count + 1):
            try:
                response = self.model.generate_content(full_prompt)
                
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    logging.warning(f"Blocked: {response.prompt_feedback.block_reason}")
                    return original_chunk_for_fallback

                json_text = response.text
                
                try:
                    data = json.loads(json_text)
                    if isinstance(data, dict): 
                        data = [data]
                    return json_to_srt(data)
                except json.JSONDecodeError:
                    logging.warning(f"JSON Parse Error at attempt {attempt+1}")
            except Exception as e:
                logging.error(f"Gemini API Error attempt {attempt+1}: {e}")
                
                if "429" in str(e) or "quota" in str(e).lower():
                    wait_time = min(60, 10 * (attempt + 1))  
                    logging.info(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                elif attempt < retry_count:
                    time.sleep(2 ** attempt)  # 1, 2, 4, ... seconds
                
                if attempt == retry_count:
                    break
        
        return original_chunk_for_fallback


