import google.generativeai as genai
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import os
import re
import logging
from .LLMInterface import LLMInterface
from .gemini import GeminiLLM 
import time

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables. Please set it before running the script.")

genai.configure(api_key=api_key)

models = [
    "gemini-2.5-pro-preview-03-25",
    "gemini-2.5-flash-preview-04-17"
    "gemini-2.0-flash"
]

class Translator:
    def __init__(self, llm_provider: LLMInterface):
        self.llm = llm_provider
        logging.info(f"Translator initialized with LLM: {self.llm.get_model_name()}.")
        # 1\n + hh:mm:ss[,.]SSS + --> + hh:mm:ss[,.]SSS + \n + subtitle text
        # (?=\n\n|\Z): end of block/2 new lines between blocks

        # Group 1: Optional index line (e.g., "1\n")
        # Group 2: Timestamp line (e.g., "00:00:00,000 --> 00:00:03,680\n" or VTT equivalent with styling)
        # Group 3: Subtitle text (one or more lines)
        self.subtitle_block_regex = re.compile(
            r"(\d+\s*\n)?(^\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}\s*$.*?\n)(.+?)(?=\n\n|\Z)",
            re.MULTILINE | re.DOTALL
        )

    def _build_chunk_prompt(self, chunk_content: str, target_language: str, source_language: str = "auto", metadata: Optional[Dict[str, Any]] = None, file_format: str = 'srt'):
        """
        Create a prompt to translate a chunk including multiples transcription blocks.
        """

        prompt_lines = [
            f"You are an expert subtitle translator. Translate the text portions of the following chunk of {file_format} subtitle blocks from '{source_language}' (auto-detect if 'auto') to '{target_language}'.",
        ]

        if metadata:
            prompt_lines.append("\n**Context about the video:**")
            if 'title' in metadata:
                prompt_lines.append(f"- Title: {metadata['title']}")
            if 'duration' in metadata:
                 prompt_lines.append(f"- Duration: {metadata['duration']:.2f} seconds (approx)")
            other_meta = {k: v for k, v in metadata.items() if k not in ['title', 'duration', 'tags'] and v}
            if other_meta:
                 prompt_lines.append(f"- Other Info: {other_meta}")

        prompt_lines.extend([
            f"\n**IMPORTANT INSTRUCTIONS (MUST FOLLOW STRICTLY for {file_format} format):**",
            f"- Translate ONLY the actual subtitle text lines within EACH block into '{target_language}'.",
            "- PRESERVE THE EXACT TIMESTAMPS (e.g., '00:00:20.000 --> 00:00:24.400'). DO NOT ALTER THEM.",
            "- PRESERVE THE ORIGINAL STRUCTURE, including sequence numbers (if present) and the exact blank lines BETWEEN blocks.",
            f"- The output MUST be a valid chunk of {file_format} blocks, maintaining the same number of blocks and structure as the input chunk.",
            "- DO NOT add any explanations, comments, notes, or text outside the required {file_format} structure.",
             "- DO NOT include any backticks (` ``` `) or code block markers in the output.",
            "- Ensure the output starts directly with the first block's index (if present) or timestamp, and ends exactly after the last block's text.",
            f"\n**Original {file_format} Chunk:**",
            chunk_content.strip(),
            f"\n**Translated {file_format} Chunk (only text translated to {target_language}, structure strictly preserved):**"
        ])
        return "\n".join(prompt_lines)
    
    def translate_subtitle_file_by_chunk(self, input_file_path: str, target_language: str, output_file_path: Optional[str] = None, source_language: str = "auto", metadata: Optional[Dict[str, Any]] = None, chunk_size: int = 10, max_retries: int = 2) -> str:

        if not os.path.isfile(input_file_path):
            raise FileNotFoundError(f"Input subtitle file not found: {input_file_path}")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer.")

        # Xác định tên tệp đầu ra
        if output_file_path is None:
            base, ext = os.path.splitext(input_file_path)
            output_file_path = f"{base}.{target_language}{ext}"
        file_format = os.path.splitext(input_file_path)[1].upper().replace(".", "") # SRT hoặc VTT

        logging.info(f"Starting chunk-based translation for '{input_file_path}'")
        logging.info(f"Target: {target_language}, Source: {source_language}, Chunk Size: {chunk_size}")
        logging.info(f"Output file will be: '{output_file_path}'")


        try: 
            with open(input_file_path, "r", encoding="utf-8") as f:
                content = f.read()

                translated_content = []  # used to store translated chunks
                current_chunk_matches: List[re.Match] = [] # group of matches 
                last_match_end = 0 # used to track the end of the last match

            first_match = next(self.subtitle_block_regex.finditer(content), None)
            if first_match:
                preamble = content[:first_match.start()]  # Content before the first block
                if preamble.strip():  # Only add if it's not empty
                    logging.debug("Adding preamble (content before the first block).")
                    translated_content.append(preamble)
                last_match_end = first_match.start()

                def process_chunk(matches_in_chunk: List[re.Match]):
                    """
                    Process a chunks of subtitle blocks and translate them.
                    """
                    nonlocal translated_content, last_match_end

                    if not matches_in_chunk:
                        return

                    chunk_start = matches_in_chunk[0].start()
                    chunk_end = matches_in_chunk[-1].end()
                    chunk_content = content[chunk_start:chunk_end]

                    # keep the original format of the output, like spaces, new lines between blocks
                    non_match_prefix = [last_match_end, chunk_start]
                    if non_match_prefix:
                        translated_content.append(content[non_match_prefix[0]:non_match_prefix[1]])

                    has_text_to_translate = any(match.group(3).strip() for match in matches_in_chunk)
                    if not has_text_to_translate:
                        logging.debug(f"Chunk from {matches_in_chunk[0].group(2).strip()} contains no text. Keeping original.")
                        translated_content.append(chunk_content) # keep the original content
                        last_match_end = chunk_end
                        return
                    
                    final_translated_content = chunk_content # default to original content
                    translation_successful = False
                    
                    for attempt in range(max_retries + 1):
                        prompt = self._build_chunk_prompt(chunk_content, target_language, source_language, metadata, file_format)
                        if attempt > 0:
                            logging.info(f"Retrying translation for chunk (attempt {attempt + 1})...")
                        
                        llm_response = self.llm.generate(prompt, chunk_content, file_format)
                        translated_response_str = llm_response.strip()

                        logging.info(f"Translated response received: \n{translated_response_str}")

                        if self._is_valid_response(translated_response_str, matches_in_chunk):
                            logging.debug(f"Chunk translation successful for chunk starting at {chunk_start}.")
                            translation_successful = True
                            final_translated_content = translated_response_str
                            break
                        
                        logging.warning(
                        f"Invalid LLM response for chunk (Attempt {attempt + 1}/{max_retries + 1}), starting with '{matches_in_chunk[0].group(2).strip()}'."
                        )
                        if attempt < max_retries:
                            logging.info(f"Waiting for a short period before retrying...")
                            time.sleep(1)
                    
                    if not translation_successful:
                        logging.error(f"Failed to translate chunk after {max_retries + 1} attempts. Keeping original content.")
                    
                    translated_content.append(final_translated_content)
                    last_match_end = chunk_end

            for match in self.subtitle_block_regex.finditer(content):
                current_chunk_matches.append(match)
                if len(current_chunk_matches) >= chunk_size:
                    process_chunk(current_chunk_matches)
                    current_chunk_matches = []

            # Process any remaining matches
            if current_chunk_matches:
                process_chunk(current_chunk_matches)

            final_part = content[last_match_end:]
            if final_part:
                translated_content.append(final_part)

            final_output = "".join(translated_content)
            if final_output and not final_output.endswith("\n"):
                final_output += "\n"

            with open(output_file_path, "w", encoding="utf-8") as f:
                f.write(final_output)
                logging.info(f"Translation completed successfully. Output saved to: {output_file_path}")
            
            return output_file_path
        except FileNotFoundError:
            logging.error(f"File not found: {input_file_path}")
            raise
        except Exception as e:
            logging.error(f"An error occurred during translation: {e}")
            raise

    def _is_valid_response(self, translated_response_str: str, original_chunk_matches: List[re.Match]) -> bool:
        
        if not translated_response_str and not original_chunk_matches:
            # both are empty
            return True
        
        if not original_chunk_matches or not translated_response_str:
            # one of them is empty
            logging.error("No original chunk matches found.")
            return False
        
        expected_num_blocks = len(original_chunk_matches)

        translated_block_matches = list(self.subtitle_block_regex.finditer(translated_response_str))

        if len(translated_block_matches) != expected_num_blocks:
            logging.error(f"Mismatch in number of blocks: expected {expected_num_blocks}, got {len(translated_block_matches)}")
            return False
        
        for i, (original_match, translated_match) in enumerate(zip(original_chunk_matches, translated_block_matches)):
            # compare index (group 1)

            original_index_line = (original_match.group(1) or "").strip()
            translated_index_line = (translated_match.group(1) or "").strip()

            if original_index_line != translated_index_line:
                logging.error(f"Index line mismatch at block {i + 1}: original '{original_index_line}', translated '{translated_index_line}'")
                return False
            
            # compare timestamp (group 2)
            original_timestamp_line = (original_match.group(2) or "").strip() # From original chunk
            translated_timestamp_line = (translated_match.group(2) or "").strip() # From translated block

            if not original_timestamp_line or not translated_timestamp_line:
                logging.warning(f"Block {i+1}: Missing timestamp line in original or translation (should not happen).")
                return False

            if original_timestamp_line != translated_timestamp_line:
                logging.warning(
                    f"Block {i+1}: Timestamp mismatch.\nOriginal  : '{original_timestamp_line}'\nTranslated: '{translated_timestamp_line}'"
                )
                return False
            
            # 3. Check for translated text (Group 3)
            translated_text_content = (translated_match.group(3) or "").strip()
            if not translated_text_content:
                original_text_content = (original_match.group(3) or "").strip()
                if original_text_content: # Original had text, translation is empty
                    logging.warning(f"Block {i+1}: Translated text is empty, but original text ('{original_text_content[:30]}...') was not.")
                    return False
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    INPUT_SUBTITLE_FILE = "/home/datle/Documents/WorkSpace/Code/Video_Subtitle_Generator/output/processed_for_whisper.vtt" # Đổi thành .srt hoặc .vtt
    TARGET_LANGUAGE = "vi"
    OUTPUT_SUBTITLE_FILE = None # Tự tạo tên file
    SOURCE_LANGUAGE = "en"
    CHUNK_SIZE = 10

    now = time.time()
    # Đo thời gian thực hiện

    try:

        translator = Translator(llm_provider=GeminiLLM(model_name="gemini-2.0-flash"))
        translated_file = translator.translate_subtitle_file_by_chunk(
            input_file_path=INPUT_SUBTITLE_FILE,
            target_language=TARGET_LANGUAGE,
            output_file_path=OUTPUT_SUBTITLE_FILE,
            source_language=SOURCE_LANGUAGE,
            metadata=None,
            chunk_size=CHUNK_SIZE
        )

        print(f"Successfully translated subtitle file (chunk method) saved to: {translated_file}")

    
    except FileNotFoundError as e:
        logging.error(f"Error: {e}")
    except ValueError as e:
         logging.error(f"Configuration or Value Error: {e}")
    except Exception as e:
        logging.error(f"Translation failed: {e}", exc_info=True)

    time_taken = time.time() - now
    print(f"Time taken for translation: {time_taken:.2f} seconds")
