import os
import json
import logging
import time
from openai import OpenAI
from app.services.translation.providers.provider_interface import BaseTranslationProvider
from app.utils.common import json_to_srt

from app.log.logging_config import setup_logging
setup_logging("app.log")

from dotenv import load_dotenv
load_dotenv()

class OpenRouterTranslator(BaseTranslationProvider):
    def __init__(self, priority_model: str = "xiaomi/mimo-v2-flash:free", fallback_model: str = "mistralai/devstral-2512:free"):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        self.priority_model = priority_model
        self.fallback_model = fallback_model
        self.current_model = priority_model

    def get_model_name(self) -> str:
        return self.current_model

    def translate(self, prompt: str, original_chunk_for_fallback: str, retry_count: int = 2) -> str:
        
        json_instruction = """
        Output the result strictly as a JSON Array of objects. 
        Each object must have these keys: "id" (string), "start" (string timestamp), "end" (string timestamp), "text" (translated string).
        Example: [{"id": "1", "start": "00:00:01,000", "end": "00:00:05,000", "text": "Xin chào"}]
        """
        full_prompt = f"{prompt}\n\n{json_instruction}"

        models_to_try = [self.priority_model, self.fallback_model]
        
        for model in models_to_try:
            self.current_model = model
            extra_body = {}
            if model == "xiaomi/mimo-v2-flash:free":
                extra_body = {"reasoning": {"enabled": True}}

            # Retry logic per model
            for attempt in range(retry_count + 1):
                try:
                    logging.info(f"Translating with {model}, attempt {attempt + 1}")
                    completion = self.client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "user", "content": full_prompt}
                        ],
                        extra_body=extra_body,
                        # temperature=0.1 # Some free models might not support explicit temp or handle it differently, keep it default or low
                    )
                    
                    content = completion.choices[0].message.content

                    logging.info(f"Received response from model {model}")
                    if not content:
                        raise ValueError("Empty response from model")

                    # Parse JSON
                    # Handle potential markdown code blocks ```json ... ```
                    import re
                    match = re.search(r'\[.*\]', content, re.DOTALL)
                    if match:
                        cleaned_content = match.group(0)
                    else:
                         cleaned_content = content.replace("```json", "").replace("```", "").strip()
                    
                    data = json.loads(cleaned_content)
                    if isinstance(data, dict):
                        data = [data]
                        
                    return json_to_srt(data)

                except Exception as e:
                    logging.error(f"Error with model {model} attempt {attempt + 1}: {e}")
                    
                    if "429" in str(e) or "quota" in str(e).lower() or "rate limit" in str(e).lower():
                         if attempt < retry_count:
                             time.sleep(2 ** attempt)
                         else:
                             break # allow fallback to next model
                    else:
                        if attempt < retry_count:
                            time.sleep(1)
                        else:
                            break # allow fallback
            
            # If we are here, retries exhausted for this model. Proceed to next model in outer loop.
            logging.warning(f"Exhausted retries for {model}. Switching to next model if available.")

        logging.error("All models failed.")
        return original_chunk_for_fallback

    