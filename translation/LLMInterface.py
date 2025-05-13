from abc import ABC, abstractmethod

class LLMInterface(ABC):
    @abstractmethod
    def get_model_name(self) -> str:
        pass

    @abstractmethod
    def generate(self, prompt: str, original_chunk_for_fallback: str, file_format: str) -> str:
        pass

    @abstractmethod
    async def generate_async(self, prompt: str, original_chunk_for_fallback: str, file_format: str) -> str:
        pass

