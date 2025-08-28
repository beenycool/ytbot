import cv2
import numpy as np
import logging
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
from moviepy.video.fx import crop, speedx
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json
from config.settings import *

class VideoEditor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.output_dir = Path(OUTPUT_DIR)
        self.output_dir.mkdir(exist_ok=True)
        
    def process_video(self, analysis: Dict) -> Optional[str]:
        """Main video processing pipeline"""
        try:
            video_info = analysis['video_info']
            processing_instructions = analysis['processing_instructions']
            
            input_path = video_info['file_path']
            self.logger.info(f"Starting video processing: {Path(input_path).name}")
            
            # Load video
            clip = VideoFileClip(input_path)
            
            # Apply cuts
            cut_clip = self._apply_cuts(clip, processing_instructions['cutting'])
            
            # Apply cropping
            cropped_clip = self._apply_cropping(cut_clip, processing_instructions['cropping'])
            
            # Apply effects
            effects_clip = self._apply_effects(cropped_clip, processing_instructions['effects'])
            
            # Resize to target resolution
            final_clip = self._resize_video(effects_clip, processing_instructions['quality'])
            
            # Generate output filename
            output_filename = self._generate_output_filename(video_info)
            output_path = self.output_dir / output_filename
            
            # Export video
            final_clip.write_videofile(
                str(output_path),
                fps=processing_instructions['quality']['fps'],
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            # Clean up
            clip.close()
            cut_clip.close()
            cropped_clip.close()
            effects_clip.close()
            final_clip.close()
            
            self.logger.info(f"Video processing complete: {output_filename}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Error processing video: {str(e)}")
            return None
    
    def _apply_cuts(self, clip: VideoFileClip, cutting_instructions: Dict) -> VideoFileClip:
        """Apply cutting based on analysis"""
        try:
            primary_cut = cutting_instructions.get('primary_cut', {})
            segments = cutting_instructions.get('segments', [])
            
            if primary_cut and 'start' in primary_cut and 'end' in primary_cut:
                # Use primary cut
                start_time = max(0, primary_cut['start'])
                end_time = min(clip.duration, primary_cut['end'])
                
                cut_clip = clip.subclip(start_time, end_time)
                self.logger.info(f"Applied primary cut: {start_time:.2f}s - {end_time:.2f}s")
                
            elif segments:
                # Use best segment
                best_segment = segments[0]  # Already sorted by priority
                start_time = max(0, best_segment['start'])
                end_time = min(clip.duration, best_segment['end'])
                
                cut_clip = clip.subclip(start_time, end_time)
                self.logger.info(f"Applied segment cut: {start_time:.2f}s - {end_time:.2f}s")
                
            else:
                # Default: cut to max duration from start
                end_time = min(clip.duration, MAX_VIDEO_DURATION)
                cut_clip = clip.subclip(0, end_time)
                self.logger.info(f"Applied default cut: 0s - {end_time:.2f}s")
            
            return cut_clip
            
        except Exception as e:
            self.logger.error(f"Error applying cuts: {str(e)}")
            return clip
    
    def _apply_cropping(self, clip: VideoFileClip, crop_instructions: Dict) -> VideoFileClip:
        """Apply intelligent cropping to 9:16 aspect ratio"""
        try:
            crop_method = crop_instructions.get('crop_method', 'center')
            original_w, original_h = clip.size
            target_w, target_h = OUTPUT_RESOLUTION
            
            if crop_method == 'horizontal':
                # Crop horizontally (video is too wide)
                crop_x = crop_instructions.get('crop_x', 0)
                crop_width = crop_instructions.get('crop_width', original_w)
                
                # Ensure crop dimensions are valid
                crop_x = max(0, min(crop_x, original_w - crop_width))
                
                cropped_clip = crop(clip, x1=crop_x, x2=crop_x + crop_width)
                self.logger.info(f"Applied horizontal crop: x={crop_x}, width={crop_width}")
                
            elif crop_method == 'vertical':
                # Crop vertically (video is too tall)
                crop_y = crop_instructions.get('crop_y', 0)
                crop_height = crop_instructions.get('crop_height', original_h)
                
                # Ensure crop dimensions are valid
                crop_y = max(0, min(crop_y, original_h - crop_height))
                
                cropped_clip = crop(clip, y1=crop_y, y2=crop_y + crop_height)
                self.logger.info(f"Applied vertical crop: y={crop_y}, height={crop_height}")
                
            else:
                # Center crop
                aspect_ratio = original_w / original_h
                target_aspect = target_w / target_h
                
                if aspect_ratio > target_aspect:
                    # Crop width
                    new_width = int(original_h * target_aspect)
                    crop_x = (original_w - new_width) // 2
                    cropped_clip = crop(clip, x1=crop_x, x2=crop_x + new_width)
                else:
                    # Crop height
                    new_height = int(original_w / target_aspect)
                    crop_y = (original_h - new_height) // 2
                    cropped_clip = crop(clip, y1=crop_y, y2=crop_y + new_height)
                
                self.logger.info("Applied center crop")
            
            return cropped_clip
            
        except Exception as e:
            self.logger.error(f"Error applying cropping: {str(e)}")
            return clip
    
    def _apply_effects(self, clip: VideoFileClip, effects: List[Dict]) -> VideoFileClip:
        """Apply visual effects based on analysis"""
        try:
            processed_clip = clip
            
            for effect in effects:
                effect_type = effect.get('type', '')
                timestamp = effect.get('timestamp', 0)
                
                if effect_type == 'zoom':
                    processed_clip = self._apply_zoom_effect(processed_clip, effect)
                elif effect_type == 'slow_motion':
                    processed_clip = self._apply_slow_motion_effect(processed_clip, effect)
                elif effect_type == 'speed_up':
                    processed_clip = self._apply_speed_effect(processed_clip, effect)
                elif effect_type == 'fade':
                    processed_clip = self._apply_fade_effect(processed_clip, effect)
                
                self.logger.info(f"Applied {effect_type} effect at {timestamp}s")
            
            return processed_clip
            
        except Exception as e:
            self.logger.error(f"Error applying effects: {str(e)}")
            return clip
    
    def _apply_zoom_effect(self, clip: VideoFileClip, effect: Dict) -> VideoFileClip:
        """Apply zoom effect at specific timestamp"""
        try:
            timestamp = effect.get('timestamp', 0)
            intensity = effect.get('intensity', 'medium')
            duration = effect.get('duration', 2.0)
            
            # Define zoom levels
            zoom_levels = {'low': 1.1, 'medium': 1.3, 'high': 1.5}
            zoom_factor = zoom_levels.get(intensity, 1.3)
            
            # Create zoom effect
            def zoom_effect(get_frame, t):
                frame = get_frame(t)
                if timestamp <= t <= timestamp + duration:
                    # Calculate zoom progress
                    progress = (t - timestamp) / duration
                    current_zoom = 1 + (zoom_factor - 1) * progress
                    
                    # Apply zoom
                    h, w = frame.shape[:2]
                    center_x, center_y = w // 2, h // 2
                    
                    new_w, new_h = int(w / current_zoom), int(h / current_zoom)
                    x1 = center_x - new_w // 2
                    y1 = center_y - new_h // 2
                    x2 = x1 + new_w
                    y2 = y1 + new_h
                    
                    # Ensure bounds
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)
                    
                    cropped = frame[y1:y2, x1:x2]
                    return cv2.resize(cropped, (w, h))
                
                return frame
            
            return clip.fl(zoom_effect)
            
        except Exception as e:
            self.logger.error(f"Error applying zoom effect: {str(e)}")
            return clip
    
    def _apply_slow_motion_effect(self, clip: VideoFileClip, effect: Dict) -> VideoFileClip:
        """Apply slow motion effect"""
        try:
            start_time = effect.get('start', 0)
            end_time = effect.get('end', start_time + 2)
            speed_factor = effect.get('speed', 0.5)  # 0.5 = half speed
            
            # Split clip into parts
            before = clip.subclip(0, start_time) if start_time > 0 else None
            slow_part = clip.subclip(start_time, end_time).fx(speedx, speed_factor)
            after = clip.subclip(end_time) if end_time < clip.duration else None
            
            # Concatenate parts
            parts = [part for part in [before, slow_part, after] if part is not None]
            
            if len(parts) > 1:
                return concatenate_videoclips(parts)
            else:
                return parts[0] if parts else clip
                
        except Exception as e:
            self.logger.error(f"Error applying slow motion: {str(e)}")
            return clip
    
    def _apply_speed_effect(self, clip: VideoFileClip, effect: Dict) -> VideoFileClip:
        """Apply speed up effect"""
        try:
            start_time = effect.get('start', 0)
            end_time = effect.get('end', start_time + 2)
            speed_factor = effect.get('speed', 2.0)  # 2.0 = double speed
            
            # Split clip into parts
            before = clip.subclip(0, start_time) if start_time > 0 else None
            fast_part = clip.subclip(start_time, end_time).fx(speedx, speed_factor)
            after = clip.subclip(end_time) if end_time < clip.duration else None
            
            # Concatenate parts
            parts = [part for part in [before, fast_part, after] if part is not None]
            
            if len(parts) > 1:
                return concatenate_videoclips(parts)
            else:
                return parts[0] if parts else clip
                
        except Exception as e:
            self.logger.error(f"Error applying speed effect: {str(e)}")
            return clip
    
    def _apply_fade_effect(self, clip: VideoFileClip, effect: Dict) -> VideoFileClip:
        """Apply fade in/out effect"""
        try:
            fade_type = effect.get('fade_type', 'in')
            duration = effect.get('duration', 1.0)
            
            if fade_type == 'in':
                return clip.fadein(duration)
            elif fade_type == 'out':
                return clip.fadeout(duration)
            else:
                return clip.fadein(duration).fadeout(duration)
                
        except Exception as e:
            self.logger.error(f"Error applying fade effect: {str(e)}")
            return clip
    
    def _resize_video(self, clip: VideoFileClip, quality_settings: Dict) -> VideoFileClip:
        """Resize video to target resolution"""
        try:
            target_resolution = quality_settings.get('resolution', OUTPUT_RESOLUTION)
            target_w, target_h = target_resolution
            
            # Resize maintaining aspect ratio if needed
            resized_clip = clip.resize(newsize=(target_w, target_h))
            
            self.logger.info(f"Resized video to {target_w}x{target_h}")
            return resized_clip
            
        except Exception as e:
            self.logger.error(f"Error resizing video: {str(e)}")
            return clip
    
    def _generate_output_filename(self, video_info: Dict) -> str:
        """Generate unique output filename"""
        post_id = video_info.get('post_id', 'unknown')
        title = video_info.get('title', 'video')
        
        # Clean title for filename
        clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_title = clean_title[:50]  # Limit length
        
        return f"{post_id}_{clean_title}_processed.mp4"
    
    def add_watermark(self, clip: VideoFileClip, watermark_text: str = "YTBot") -> VideoFileClip:
        """Add watermark to video"""
        try:
            # Create text clip
            txt_clip = TextClip(watermark_text, 
                              fontsize=30, 
                              color='white', 
                              font='Arial-Bold',
                              stroke_color='black', 
                              stroke_width=2)
            
            # Position watermark
            txt_clip = txt_clip.set_position(('right', 'bottom')).set_duration(clip.duration)
            
            # Composite
            return CompositeVideoClip([clip, txt_clip])
            
        except Exception as e:
            self.logger.error(f"Error adding watermark: {str(e)}")
            return clip
    
    def create_thumbnail(self, video_path: str, timestamp: float = 2.0) -> Optional[str]:
        """Create thumbnail from video"""
        try:
            clip = VideoFileClip(video_path)
            
            # Extract frame at timestamp
            frame = clip.get_frame(min(timestamp, clip.duration - 1))
            
            # Save as image
            thumbnail_path = str(self.output_dir / f"thumb_{Path(video_path).stem}.jpg")
            clip.save_frame(thumbnail_path, t=timestamp)
            
            clip.close()
            
            self.logger.info(f"Thumbnail created: {thumbnail_path}")
            return thumbnail_path
            
        except Exception as e:
            self.logger.error(f"Error creating thumbnail: {str(e)}")
            return None