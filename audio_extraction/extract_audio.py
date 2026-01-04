import logging
import os
import ffmpeg
import sys
from typing import Optional, Dict, Any


def get_media_type(file_path):
    if not os.path.isfile(file_path):
        logging.error(f"File not found: {file_path}")
        return None
    
    try:
        probe_info = ffmpeg.probe(file_path)
        streams = probe_info.get('streams', [])

        has_video = any(stream.get('codec_type') == 'video' for stream in streams)
        has_audio = any(stream.get('codec_type') == 'audio' for stream in streams)
        if has_video:
            return 'video'
        elif has_audio:
            return 'audio'
        else:
            logging.warning(f"No video or audio streams found in {file_path}")
            return 'unknown'
    except ffmpeg.Error as e:
        logging.error(f"Error probing file {file_path}: {e}")
        return None


class Media:
    """
    Store the media file information
    This information provides the context for subtiles generation
    """
    def __init__(self, file_path: str):
        if not os.path.isfile(file_path):
            logging.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        
        self.file_path: str = file_path
        self.probe_info: Optional[Dict[str, Any]] = None
        self.format_info: Dict[str, Any] = {}
        self.metadata: Dict[str, str] = {}
        self.duration: Optional[float] = None
        self.media_type: Optional[str] = get_media_type(file_path)
        self._probe_file()
        self._extract_info()


    def _probe_file(self):
        try: 
            logging.info(f"Probing file {self.file_path}")
            self.probe_info = ffmpeg.probe(self.file_path)
        except ffmpeg.Error as e:
            logging.error(f"Error probing file {self.file_path}: {e}")
        
    def _extract_info(self):
        if self.probe_info is None:
            logging.error("Probe information is not available.")
            return

        self.format_info = self.probe_info.get('format', {})
        self.metadata = self.format_info.get('tags', {})
        
        try:
            duration_str = self.format_info.get('duration')
            if duration_str:
                self.duration = float(duration_str)
        except (ValueError, TypeError) as e:
            logging.error(f"Error converting duration to float: {e}")


        streams = self.probe_info.get('streams', [])

        has_video = False
        has_audio = False

        for stream in streams:
            codec_type = stream.get('codec_type')
            if codec_type == 'video':
                has_video = True
            elif codec_type == 'audio':
                has_audio = True

        if has_video:
            self.media_type = 'video'
        elif has_audio:
            self.media_type = 'audio'
        
        logging.info(f"Extracted info for {self.file_path}: Type={self.media_type}, Duration={self.duration:.2f}s (approx)")


    def __str__(self) -> str:
        lines = [
            f"File: {self.file_path}",
            f"Type: {self.media_type}",
            f"Duration: {self.duration:.2f}s" if self.duration is not None else "Duration: Unknown",
            f"Metadata: {self.metadata}",
        ]
        return "\n".join(lines)


class MediaProcessor:
    """
    Take a video/audio file -> process it -> audio file for whisper model
    """

    def __init__(self, media: Media, output_file:str = 'output.wav'):

        if not isinstance(media, Media):
             raise TypeError("Input 'media' must be an instance of the Media class.")

        self.media = media

        if not output_file.lower().endswith('.wav'):
            logging.warning(f"Output file '{output_file}' does not end with .wav. Forcing .wav extension.")
            output_file = os.path.splitext(output_file)[0] + '.wav'

        self.output_file = output_file

        output_dir = os.path.dirname(self.output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"Output directory {output_dir} created")

        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"Output directory {output_dir} created")

    def extract_or_convert_audio(self) -> str:
        if not self.media or not self.media.probe_info:
            logging.error("Media information is not available.")
            raise ValueError("Media information is not available.")


        if self.media.media_type not in ['video', 'audio']:
            msg = f"Input file '{self.media.file_path}' is not a supported media type ('video' or 'audio'). Type found: {self.media.media_type}"
            logging.error(msg)
            raise ValueError(msg)
        
        if self.media.media_type not in ['video', 'audio']:
            msg = f"Input file '{self.media.file_path}' is not a supported media type ('video' or 'audio'). Type found: {self.media.media_type}"
            logging.error(msg)
            raise ValueError(msg)

        logging.info(f"Processing '{self.media.file_path}' ({self.media.media_type}) -> '{self.output_file}' (WAV, 16kHz, mono)")

        try: 
            input_stream = ffmpeg.input(self.media.file_path)

            output_stream = ffmpeg.output(input_stream.audio, self.output_file,
                                       acodec='pcm_s16le',
                                       ar=16000,
                                       ac=1,
                                       format='wav') 

            stdout, stderr = ffmpeg.run(output_stream, cmd='ffmpeg -hide_banner', overwrite_output=True, capture_stdout=True, capture_stderr=True)

            logging.info(f"Successfully created audio file: {self.output_file}")
            if stderr:
                logging.debug(f"FFmpeg stderr:\n{stderr.decode(sys.stderr.encoding or 'utf-8', errors='replace')}")
            if stdout:
                 logging.debug(f"FFmpeg stdout:\n{stdout.decode(sys.stderr.encoding or 'utf-8', errors='replace')}")

            return self.output_file
        except ffmpeg.Error as e:
            logging.error(f"FFmpeg error: {e}")
            raise

    def add_subtitles(self, subtitle_file: str, output_file: Optional[str] = None, 
                  hardcode: bool = False) -> str:
        """
        Add subtitles to a media file using ffmpeg
        """
        if not os.path.exists(subtitle_file):
            raise FileNotFoundError(f"Subtitle file not found: {subtitle_file}")
        
        if not output_file:
            base_name, ext = os.path.splitext(self.media.file_path)
            output_file = f"{base_name}_subtitled{ext}"
        
        try:
            input_stream = ffmpeg.input(self.media.file_path)
            
            if hardcode:
                logging.info(f"Hardcoding subtitles from {subtitle_file} into video...")
                
                # For video files
                if self.media.media_type == 'video':
                    # Apply subtitles filter
                    video = input_stream.video.filter('subtitles', subtitle_file)
                    # Keep the audio stream unchanged
                    audio = input_stream.audio
                    # Combine streams and output
                    output = ffmpeg.output(video, audio, output_file)
                
                # For audio files
                else:
                    # logging.info("Creating audio visualization with subtitles")
                    # video = input_stream.filter('showwaves', s='640x360').filter('subtitles', subtitle_file)
                    # audio = input_stream.audio
                    # output = ffmpeg.output(video, audio, output_file)
                    logging.error("Only video files can be hardcoded with subtitles.")
                    raise ValueError("Only video files can be hardcoded with subtitles.")
                    
            else:
                # Soft-code (add subtitles as a separate stream)
                logging.info(f"Adding subtitles from {subtitle_file} as a separate stream...")
                output = ffmpeg.output(
                    input_stream, 
                    output_file,
                    **{
                        'i': subtitle_file,  # Input subtitle file
                        'c': 'copy',         # Copy all streams
                        'c:s': 'mov_text'    # Convert subtitles to appropriate format
                    }
                )
            
            # Run the ffmpeg command
            stdout, stderr = ffmpeg.run(
                output, 
                cmd='ffmpeg -hide_banner', 
                overwrite_output=True,
                capture_stdout=True, 
                capture_stderr=True
            )
            
            if stderr:
                logging.debug(f"FFmpeg stderr:\n{stderr.decode(sys.stderr.encoding or 'utf-8', errors='replace')}")
                
            logging.info(f"Successfully created subtitled media: {output_file}")
            return output_file
            
        except ffmpeg.Error as e:
            logging.error(f"FFmpeg error adding subtitles: {e}")
            raise