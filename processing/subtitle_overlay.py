from moviepy.editor import *
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import textwrap
from config.settings import *

class SubtitleOverlay:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.temp_dir = Path(TEMP_DIR) / 'subtitles'
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
    def add_subtitles_to_video(self, video_path: str, analysis: Dict, tts_audio_path: str = None) -> Optional[str]:
        """Add subtitles to video based on analysis and TTS timing"""
        try:
            # Load video
            clip = VideoFileClip(video_path)
            
            # Get subtitle data
            subtitle_timing = analysis.get('subtitle_timing', [])
            transcription = analysis.get('transcription', '')
            tts_script = analysis.get('tts_script', [])
            
            # Create subtitle clips
            subtitle_clips = []
            
            # Add transcription subtitles if available
            if transcription and not subtitle_timing:
                subtitle_clips.extend(self._create_transcription_subtitles(clip, transcription))
            
            # Add emphasis subtitles from analysis
            if subtitle_timing:
                subtitle_clips.extend(self._create_emphasis_subtitles(subtitle_timing))
            
            # Add TTS overlay subtitles
            if tts_script:
                subtitle_clips.extend(self._create_tts_subtitles(tts_script))
            
            if not subtitle_clips:
                self.logger.warning("No subtitles to add")
                return video_path
            
            # Composite video with subtitles
            final_clip = CompositeVideoClip([clip] + subtitle_clips)
            
            # Generate output path
            output_path = str(self.temp_dir / f"subtitled_{Path(video_path).name}")
            
            # Export
            final_clip.write_videofile(
                output_path,
                fps=clip.fps,
                codec='libx264',
                audio_codec='aac',
                verbose=False,
                logger=None
            )
            
            # Cleanup
            clip.close()
            final_clip.close()
            for sub_clip in subtitle_clips:
                sub_clip.close()
            
            self.logger.info(f"Subtitles added successfully: {Path(output_path).name}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error adding subtitles: {str(e)}")
            return None
    
    def _create_transcription_subtitles(self, clip: VideoFileClip, transcription: str) -> List[TextClip]:
        """Create subtitles from transcription"""
        try:
            subtitle_clips = []
            
            # Split transcription into chunks
            words = transcription.split()
            if not words:
                return subtitle_clips
            
            # Calculate timing
            duration = clip.duration
            words_per_second = len(words) / duration
            words_per_subtitle = max(3, min(8, int(words_per_second * 3)))  # 3-second chunks
            
            for i in range(0, len(words), words_per_subtitle):
                chunk_words = words[i:i + words_per_subtitle]
                subtitle_text = ' '.join(chunk_words)
                
                # Calculate timing
                start_time = (i / len(words)) * duration
                end_time = min(((i + words_per_subtitle) / len(words)) * duration, duration)
                subtitle_duration = end_time - start_time
                
                # Create text clip
                txt_clip = self._create_text_clip(
                    subtitle_text,
                    duration=subtitle_duration,
                    style='transcription'
                ).set_start(start_time)
                
                subtitle_clips.append(txt_clip)
            
            return subtitle_clips
            
        except Exception as e:
            self.logger.error(f"Error creating transcription subtitles: {str(e)}")
            return []
    
    def _create_emphasis_subtitles(self, subtitle_timing: List[Dict]) -> List[TextClip]:
        """Create emphasis subtitles from timing data"""
        try:
            subtitle_clips = []
            
            for subtitle_data in subtitle_timing:
                text = subtitle_data.get('text', '').strip()
                start_time = subtitle_data.get('start', 0)
                end_time = subtitle_data.get('end', start_time + 2)
                style = subtitle_data.get('style', 'normal')
                
                if not text:
                    continue
                
                duration = end_time - start_time
                
                # Create text clip with appropriate style
                txt_clip = self._create_text_clip(
                    text,
                    duration=duration,
                    style=style
                ).set_start(start_time)
                
                subtitle_clips.append(txt_clip)
            
            return subtitle_clips
            
        except Exception as e:
            self.logger.error(f"Error creating emphasis subtitles: {str(e)}")
            return []
    
    def _create_tts_subtitles(self, tts_script: List[Dict]) -> List[TextClip]:
        """Create subtitles for TTS overlays"""
        try:
            subtitle_clips = []
            
            for tts_item in tts_script:
                text = tts_item.get('text', '').strip()
                timestamp = tts_item.get('timestamp', 0)
                pause = tts_item.get('pause', 1.0)
                
                if not text:
                    continue
                
                # Estimate duration based on text length and reading speed
                estimated_duration = max(1.0, len(text) / 10)  # ~10 chars per second
                duration = min(estimated_duration + pause, 4.0)  # Max 4 seconds
                
                # Create text clip with TTS style
                txt_clip = self._create_text_clip(
                    text,
                    duration=duration,
                    style='tts'
                ).set_start(timestamp)
                
                subtitle_clips.append(txt_clip)
            
            return subtitle_clips
            
        except Exception as e:
            self.logger.error(f"Error creating TTS subtitles: {str(e)}")
            return []
    
    def _create_text_clip(self, text: str, duration: float, style: str = 'normal') -> TextClip:
        """Create a styled text clip"""
        try:
            # Style configurations
            styles = {
                'normal': {
                    'fontsize': SUBTITLE_FONT_SIZE,
                    'color': SUBTITLE_FONT_COLOR,
                    'stroke_color': SUBTITLE_OUTLINE_COLOR,
                    'stroke_width': SUBTITLE_OUTLINE_WIDTH,
                    'position': ('center', 0.8),
                    'font': 'Arial-Bold'
                },
                'emphasis': {
                    'fontsize': SUBTITLE_FONT_SIZE + 10,
                    'color': 'yellow',
                    'stroke_color': 'red',
                    'stroke_width': 4,
                    'position': ('center', 0.7),
                    'font': 'Arial-Bold'
                },
                'highlight': {
                    'fontsize': SUBTITLE_FONT_SIZE + 15,
                    'color': 'white',
                    'stroke_color': 'black',
                    'stroke_width': 5,
                    'position': ('center', 0.75),
                    'font': 'Arial-Bold'
                },
                'tts': {
                    'fontsize': SUBTITLE_FONT_SIZE - 5,
                    'color': 'cyan',
                    'stroke_color': 'blue',
                    'stroke_width': 2,
                    'position': ('center', 0.9),
                    'font': 'Arial-Bold'
                },
                'transcription': {
                    'fontsize': SUBTITLE_FONT_SIZE - 10,
                    'color': 'white',
                    'stroke_color': 'gray',
                    'stroke_width': 2,
                    'position': ('center', 0.85),
                    'font': 'Arial'
                }
            }
            
            style_config = styles.get(style, styles['normal'])
            
            # Handle long text by wrapping
            wrapped_text = self._wrap_text(text, max_width=30)
            
            # Create text clip
            txt_clip = TextClip(
                wrapped_text,
                fontsize=style_config['fontsize'],
                color=style_config['color'],
                font=style_config['font'],
                stroke_color=style_config['stroke_color'],
                stroke_width=style_config['stroke_width']
            ).set_duration(duration).set_position(style_config['position'])
            
            # Add animation based on style
            if style in ['emphasis', 'highlight']:
                txt_clip = self._add_text_animation(txt_clip, style)
            
            return txt_clip
            
        except Exception as e:
            self.logger.error(f"Error creating text clip: {str(e)}")
            # Fallback to simple text clip
            return TextClip(text, fontsize=40, color='white').set_duration(duration)
    
    def _wrap_text(self, text: str, max_width: int = 30) -> str:
        """Wrap text for better subtitle display"""
        try:
            # Split long text into lines
            words = text.split()
            lines = []
            current_line = []
            current_length = 0
            
            for word in words:
                if current_length + len(word) + 1 <= max_width:
                    current_line.append(word)
                    current_length += len(word) + 1
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = len(word)
            
            if current_line:
                lines.append(' '.join(current_line))
            
            # Limit to 3 lines max
            if len(lines) > 3:
                lines = lines[:3]
                lines[-1] += '...'
            
            return '\n'.join(lines)
            
        except Exception as e:
            self.logger.error(f"Error wrapping text: {str(e)}")
            return text
    
    def _add_text_animation(self, txt_clip: TextClip, style: str) -> TextClip:
        """Add animation effects to text clips"""
        try:
            if style == 'emphasis':
                # Scale animation
                return txt_clip.resize(lambda t: 1 + 0.1 * np.sin(2 * np.pi * t))
            elif style == 'highlight':
                # Fade in animation
                return txt_clip.fadein(0.3).fadeout(0.3)
            else:
                return txt_clip
                
        except Exception as e:
            self.logger.error(f"Error adding text animation: {str(e)}")
            return txt_clip
    
    def create_brainrot_style_subtitles(self, text_items: List[Dict]) -> List[TextClip]:
        """Create brainrot/Gen-Z style subtitles"""
        try:
            subtitle_clips = []
            
            for item in text_items:
                text = item.get('text', '').upper()  # CAPS for emphasis
                timestamp = item.get('timestamp', 0)
                duration = item.get('duration', 2.0)
                
                # Add brainrot styling
                if any(word in text.lower() for word in ['smart', 'insane', 'crazy', 'amazing']):
                    style = 'highlight'
                else:
                    style = 'emphasis'
                
                # Add emojis if not present
                if not any(char in text for char in ['🤯', '🔥', '💯', '😱']):
                    text += ' 🤯'
                
                txt_clip = self._create_text_clip(text, duration, style).set_start(timestamp)
                subtitle_clips.append(txt_clip)
            
            return subtitle_clips
            
        except Exception as e:
            self.logger.error(f"Error creating brainrot subtitles: {str(e)}")
            return []
    
    def add_subtitle_background(self, txt_clip: TextClip, background_type: str = 'box') -> CompositeVideoClip:
        """Add background to subtitle for better readability"""
        try:
            if background_type == 'box':
                # Create a semi-transparent background box
                bg_clip = ColorClip(
                    size=txt_clip.size,
                    color=(0, 0, 0),
                    duration=txt_clip.duration
                ).set_opacity(0.6).set_position(txt_clip.pos)
                
                return CompositeVideoClip([bg_clip, txt_clip])
            else:
                return txt_clip
                
        except Exception as e:
            self.logger.error(f"Error adding subtitle background: {str(e)}")
            return txt_clip
    
    def optimize_subtitles_for_platform(self, subtitle_clips: List[TextClip], platform: str) -> List[TextClip]:
        """Optimize subtitles for specific platform"""
        try:
            platform_configs = {
                'youtube': {
                    'max_lines': 3,
                    'font_size_modifier': 0,
                    'emphasis': True
                },
                'instagram': {
                    'max_lines': 2,
                    'font_size_modifier': 5,
                    'emphasis': True
                },
                'tiktok': {
                    'max_lines': 2,
                    'font_size_modifier': 10,
                    'emphasis': True
                }
            }
            
            config = platform_configs.get(platform, platform_configs['youtube'])
            
            # Apply platform-specific optimizations
            optimized_clips = []
            for clip in subtitle_clips:
                # Adjust font size if needed
                if config['font_size_modifier'] != 0:
                    # This would require recreating the clip with new font size
                    # For now, we'll keep the original
                    pass
                
                optimized_clips.append(clip)
            
            return optimized_clips
            
        except Exception as e:
            self.logger.error(f"Error optimizing subtitles for {platform}: {str(e)}")
            return subtitle_clips
    
    def cleanup_temp_files(self, max_age_hours: int = 24):
        """Clean up temporary subtitle files"""
        try:
            import time
            current_time = time.time()
            
            for file_path in self.temp_dir.iterdir():
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > (max_age_hours * 3600):
                        file_path.unlink()
                        self.logger.info(f"Cleaned up subtitle file: {file_path.name}")
                        
        except Exception as e:
            self.logger.error(f"Error during subtitle cleanup: {str(e)}")