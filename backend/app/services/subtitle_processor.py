import logging

from app.log.logging_config import setup_logging
setup_logging("app.log")

class SubtitleProcessor:
    def __init__(self, max_gap: float = 0.70, max_chars: int = 90, min_chars: int = 20):
        self.max_gap = max_gap
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.end_punctuations = [".", "!", "?", "..."]
        self.nlp = None  # Lazy load spacy

    def _get_attr(self, segment, attr):
        """Helper to get attribute from Segment object or dict."""
        if isinstance(segment, dict):
            return segment.get(attr)
        return getattr(segment, attr, None)

    def merge_segments(self, segments):
        """Merge short segments to create better translation context."""
        if not segments:
            return []

        merged = []

        # Initialize first segment - convert to dict format
        first_seg = segments[0]
        current = {
            "start": self._get_attr(first_seg, "start"),
            "end": self._get_attr(first_seg, "end"),
            "text": (self._get_attr(first_seg, "text") or "").strip()
        }

        for i in range(1, len(segments)):
            next_segment = segments[i]

            next_text = (self._get_attr(next_segment, "text") or "").strip()
            next_start = self._get_attr(next_segment, "start")
            next_end = self._get_attr(next_segment, "end")

            time_gap = next_start - current["end"]
            estimated_length = len(next_text) + len(current["text"]) + 1

            last_char = current["text"][-1] if current["text"] else ""
            end_with_punc = last_char in self.end_punctuations or \
                          any(current["text"].endswith(p) for p in self.end_punctuations)

            should_merge = False

            if time_gap > self.max_gap:
                should_merge = False
            elif estimated_length > self.max_chars:
                should_merge = False
            elif not end_with_punc:
                should_merge = True
            elif len(current["text"]) < self.min_chars:
                should_merge = True
            else:
                should_merge = False

            if should_merge:
                current["text"] += " " + next_text
                current["end"] = next_end
            else:
                merged.append(current)
                current = {
                    "start": next_start,
                    "end": next_end,
                    "text": next_text
                }

        merged.append(current)
        return merged

    def create_srt_content(self, segments):
        """Create SRT content from segments"""
        srt_output = ""
        for i, segment in enumerate(segments):
            start = self.format_timestamp(self._get_attr(segment, "start"))
            end = self.format_timestamp(self._get_attr(segment, "end"))
            text = (self._get_attr(segment, "text") or "").strip()
            srt_output += f"{i + 1}\n{start} --> {end}\n{text}\n\n"
        return srt_output

    def create_srt_file(self, segments, output_path):
        srt_content = self.create_srt_content(segments)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
        
    def get_text_from_segments(self, segments):
        """Extract all text from segments."""
        texts = []
        for segment in segments:
            text = self._get_attr(segment, "text")
            if text:
                texts.append(text.strip())
        return "\n".join(texts)
    
    def extract_proper_nouns(self, text: str) -> list:
        """Extract proper nouns (names, places, organizations) using spaCy NER."""
        if not text:
            return []
        
        # Lazy load spacy
        if self.nlp is None:
            try:
                import spacy
                self.nlp = spacy.load("en_core_web_sm")
                logging.info("SpaCy NER model loaded.")
            except OSError:
                logging.warning("SpaCy model not found. Attempting to download...")
                try:
                    from spacy.cli import download
                    download("en_core_web_sm")
                    import spacy
                    self.nlp = spacy.load("en_core_web_sm")
                except Exception as e:
                    logging.error(f"Failed to load SpaCy: {e}")
                    return []
            except Exception as e:
                logging.error(f"Failed to load SpaCy: {e}")
                return []
        
        # Title case the text to help spaCy detect proper nouns
        # Whisper often outputs lowercase text which confuses NER
        text_for_ner = text.title()
        doc = self.nlp(text_for_ner)
        
        proper_nouns = set()
        for ent in doc.ents:
            # PERSON: People names (Taylor Swift)
            # ORG: Organizations (Google, NASA)
            # GPE: Geo-political entities (Vietnam, Hanoi)
            # PRODUCT: Products (iPhone, Windows)
            # WORK_OF_ART: Titles of works
            if ent.label_ in ["PERSON", "ORG", "GPE", "PRODUCT", "WORK_OF_ART"]:
                proper_nouns.add(ent.text)
        
        if proper_nouns:
            logging.info(f"Extracted proper nouns: {list(proper_nouns)}")
        else:
            logging.info("No proper nouns detected (text may be lowercase)")
        
        return list(proper_nouns)
    
    @staticmethod
    def format_timestamp(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
