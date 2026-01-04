from LLMInterface import LLMInterface
import logging
import requests
import aiohttp

class CustomLLM(LLMInterface):
    def __init__(self, api_endpoint: str):
        self.api_endpoint = api_endpoint
        self._model_name = f"CustomLLM @ {api_endpoint}"
        logging.info(f"MyCustomLLM initialized for endpoint: {api_endpoint}")

    def get_model_name(self) -> str:
        return self._model_name

    def generate(self, prompt: str, original_chunk_for_fallback: str, file_format: str) -> str:
        logging.info(f"MyCustomLLM (sync) called for format {file_format}. Prompt: {prompt[:100]}...")
        try:
            payload = { "prompt": prompt}
            response = requests.post(self.api_endpoint, json=payload)
            response.raise_for_status()
            translated_text = response.json().get("translated_text", original_chunk_for_fallback)
            return translated_text
        except requests.RequestException as e:
            logging.error(f"CustomLLM API error: {e}. Keeping original chunk.")
            # Fallback to original chunk if API call fails
            return original_chunk_for_fallback

    async def generate_async(self, prompt: str, original_chunk_for_fallback: str, file_format: str) -> str:
        logging.info(f"MyCustomLLM (async) called for format {file_format}. Prompt: {prompt[:100]}...")
        try:
            payload = {"prompt": prompt} # Adjust payload as per your API's requirements
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_endpoint, json=payload) as response:
                    response.raise_for_status() # Raises an ClientResponseError for bad responses
                    # Assuming the API returns JSON with a 'translation' field
                    data = await response.json()
                    translated_text = data.get("translation", original_chunk_for_fallback)
                    return translated_text
        except aiohttp.ClientError as e:
            logging.error(f"Async API request failed: {e}")
            return original_chunk_for_fallback