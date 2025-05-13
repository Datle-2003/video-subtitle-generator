from .LLMInterface import LLMInterface
import google.generativeai as genai
import logging
import os



class GeminiLLM(LLMInterface):
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self._model_name = model_name

        self.safety_settings = { # Cấu hình an toàn
            "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
            }
        self.model = genai.GenerativeModel(self._model_name, safety_settings=self.safety_settings)
        logging.info(f"GeminiLLM initialized with model: {self._model_name}")

    def get_model_name(self) -> str:
        return self._model_name

    def generate(self, prompt: str, original_chunk_for_fallback: str, file_format: str) -> str:
        try:
            logging.info(f"Length of prompt: {len(prompt)}")
            response = self.model.generate_content(prompt)
            if not response.candidates or not response.candidates[0].content.parts or \
               (response.prompt_feedback and response.prompt_feedback.block_reason):
                reason = response.prompt_feedback.block_reason if response.prompt_feedback else "No content"
                logging.warning(f"Gemini generation blocked/failed. Reason: {reason}. Keeping original.")
                return original_chunk_for_fallback
            return response.text
        except Exception as e:
            logging.error(f"Gemini API error: {e}. Keeping original chunk.")
            return original_chunk_for_fallback

    async def generate_async(self, prompt: str, original_chunk_for_fallback: str, file_format: str) -> str:
        try:
            response = await self.model.generate_content_async(prompt)
            if not response.candidates or not response.candidates[0].content.parts or \
               (response.prompt_feedback and response.prompt_feedback.block_reason):
                reason = response.prompt_feedback.block_reason if response.prompt_feedback else "No content"
                logging.warning(f"Gemini async generation blocked/failed. Reason: {reason}. Keeping original.")
                return original_chunk_for_fallback
            return response.text
        except Exception as e:
            logging.error(f"Gemini async API error: {e}. Keeping original chunk.")
            return original_chunk_for_fallback
