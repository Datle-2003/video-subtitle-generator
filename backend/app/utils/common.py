from app.utils.constants import supported_languages
import os
from typing import List, Dict

def get_language_from_code(lang_code: str) -> str:
    if lang_code in supported_languages:
        return supported_languages[lang_code]
    
    # allow lang_code input is language name
    if lang_code in supported_languages.values():
        return lang_code
    
    return ""


def json_to_srt(json_data: List[Dict]) -> str:
        srt_output = []
        for item in json_data:
            index = item.get("id", "")
            start = item.get("start", "")
            end = item.get("end", "")
            text = item.get("text", "")
            
            # Standard format SRT
            # 1
            # 00:00:01,000 --> 00:00:04,000
            # Hello world
            srt_block = f"{index}\n{start} --> {end}\n{text}\n"
            srt_output.append(srt_block)
        
        return "\n".join(srt_output)