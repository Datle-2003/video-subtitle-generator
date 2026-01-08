from abc import ABC, abstractmethod


class BaseTranslationProvider(ABC):
    @abstractmethod
    def get_model_name(self) -> str:
        """return the model name"""
        pass

    @abstractmethod
    def translate(self, prompt: str, original_chunk_for_fallback, retry_count: int = 2) -> str:
        """return translated string in json format"""
        pass
    
    