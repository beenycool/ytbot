import edge_tts
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional
import random
from gtts import gTTS
import io
from pydub import AudioSegment
from config.settings import *

class TTSGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.output_dir = Path(TEMP_DIR) / 'tts'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    async def generate_tts_audio(self, tts_script: List[Dict], post_id: str) -> Optional[str]:
        """Generate TTS audio from script using Edge-TTS"""
        try:
            audio_segments = []
            
            for i, tts_item in enumerate(tts_script):
                text = tts_item.get('text', '').strip()
                pause_duration = tts_item.get('pause', 0.5)
                
                if not text:
                    continue
                
                # Generate audio for this text
                audio_data = await self._generate_edge_tts(text, post_id, i)
                if audio_data:
                    # Load as audio segment
                    audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
                    audio_segments.append(audio_segment)
                    
                    # Add pause if specified
                    if pause_duration > 0:
                        silence = AudioSegment.silent(duration=int(pause_duration * 1000))
                        audio_segments.append(silence)
            
            if not audio_segments:
                self.logger.warning("No audio segments generated")
                return None
            
            # Combine all audio segments
            final_audio = sum(audio_segments)
            
            # Save combined audio
            output_filename = f"tts_{post_id}.mp3"
            output_path = self.output_dir / output_filename
            
            final_audio.export(str(output_path), format="mp3", bitrate="128k")
            
            self.logger.info(f"TTS audio generated: {output_filename}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Error generating TTS audio: {str(e)}")
            return None
    
    async def _generate_edge_tts(self, text: str, post_id: str, segment_id: int) -> Optional[bytes]:
        """Generate TTS using Edge-TTS"""
        try:
            voice = TTS_VOICE
            rate = TTS_SPEED
            
            # Create TTS communication
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            
            # Generate audio data
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            return audio_data
            
        except Exception as e:
            self.logger.error(f"Error with Edge-TTS: {str(e)}")
            # Fallback to gTTS
            return self._generate_gtts_fallback(text)
    
    def _generate_gtts_fallback(self, text: str) -> Optional[bytes]:
        """Fallback TTS using Google TTS"""
        try:
            tts = gTTS(text=text, lang=TTS_LANGUAGE, slow=False)
            
            # Save to bytes
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            
            return fp.read()
            
        except Exception as e:
            self.logger.error(f"Error with gTTS fallback: {str(e)}")
            return None
    
    def create_engagement_tts(self, analysis: Dict, post_id: str) -> List[Dict]:
        """Create TTS script with engagement hooks"""
        try:
            # Get original TTS script from analysis
            original_script = analysis.get('tts_script', [])
            
            # If no script provided, create one based on key moments
            if not original_script:
                original_script = self._create_default_tts_script(analysis)
            
            # Enhance script with engagement elements
            enhanced_script = self._enhance_with_engagement(original_script, analysis)
            
            return enhanced_script
            
        except Exception as e:
            self.logger.error(f"Error creating engagement TTS: {str(e)}")
            return self._get_fallback_tts_script()
    
    def _create_default_tts_script(self, analysis: Dict) -> List[Dict]:
        """Create default TTS script from analysis"""
        script = []
        
        # Opening hook
        opening_hooks = [
            "This person is so smart!",
            "Wait for it...",
            "You won't believe this!",
            "This is incredible!",
            "Watch this amazing moment!"
        ]
        
        script.append({
            'timestamp': 0.0,
            'text': random.choice(opening_hooks),
            'pause': 1.0
        })
        
        # Mid-video engagement based on key moments
        key_moments = analysis.get('key_moments', [])
        if key_moments:
            mid_moment = key_moments[len(key_moments)//2]
            mid_hooks = [
                "Look what happens next!",
                "This is insane!",
                "Don't skip this part!",
                "The best part is coming!"
            ]
            
            script.append({
                'timestamp': mid_moment['timestamp'],
                'text': random.choice(mid_hooks),
                'pause': 0.5
            })
        
        # Ending hook (if video is long enough)
        cutting_suggestions = analysis.get('cutting_suggestions', {})
        end_time = cutting_suggestions.get('end_time', 30)
        
        if end_time > 20:
            ending_hooks = [
                "Subscribe for more!",
                "Like if you're amazed!",
                "Follow for daily content!",
                "More amazing videos coming!"
            ]
            
            script.append({
                'timestamp': end_time - 3,
                'text': random.choice(ending_hooks),
                'pause': 0.5
            })
        
        return script
    
    def _enhance_with_engagement(self, script: List[Dict], analysis: Dict) -> List[Dict]:
        """Enhance TTS script with brainrot-style engagement"""
        enhanced_script = []
        
        for item in script:
            text = item['text']
            
            # Add emphasis and excitement
            enhanced_text = self._add_emphasis(text)
            
            # Update item
            enhanced_item = item.copy()
            enhanced_item['text'] = enhanced_text
            enhanced_script.append(enhanced_item)
        
        return enhanced_script
    
    def _add_emphasis(self, text: str) -> str:
        """Add emphasis to TTS text"""
        # Add SSML-like emphasis for supported TTS engines
        emphasis_words = ['amazing', 'incredible', 'insane', 'smart', 'crazy']
        
        for word in emphasis_words:
            if word.lower() in text.lower():
                text = text.replace(word, f"<emphasis level='strong'>{word}</emphasis>")
        
        return text
    
    def _get_fallback_tts_script(self) -> List[Dict]:
        """Fallback TTS script if all else fails"""
        return [
            {
                'timestamp': 0.0,
                'text': 'This is amazing!',
                'pause': 1.0
            },
            {
                'timestamp': 10.0,
                'text': 'Subscribe for more!',
                'pause': 0.5
            }
        ]
    
    def generate_hook_variations(self, base_hook: str, count: int = 5) -> List[str]:
        """Generate variations of engagement hooks"""
        try:
            variations = [base_hook]
            
            # Simple variations
            if "smart" in base_hook.lower():
                variations.extend([
                    "This person is genius!",
                    "So intelligent!",
                    "Big brain moment!",
                    "This guy gets it!"
                ])
            elif "wait" in base_hook.lower():
                variations.extend([
                    "Hold up...",
                    "Wait for the magic!",
                    "Patience pays off!",
                    "The best part is coming!"
                ])
            elif "subscribe" in base_hook.lower():
                variations.extend([
                    "Hit that subscribe button!",
                    "Follow for daily content!",
                    "More videos like this!",
                    "Join the community!"
                ])
            
            return variations[:count]
            
        except Exception as e:
            self.logger.error(f"Error generating hook variations: {str(e)}")
            return [base_hook]
    
    def adjust_timing_for_video(self, tts_script: List[Dict], video_duration: float) -> List[Dict]:
        """Adjust TTS timing to fit video duration"""
        try:
            adjusted_script = []
            
            for item in tts_script:
                timestamp = item['timestamp']
                
                # Ensure timestamp is within video duration
                if timestamp < video_duration - 2:  # Leave 2 seconds buffer
                    adjusted_script.append(item)
                else:
                    # Move to earlier in video
                    new_timestamp = max(0, video_duration - 5)
                    adjusted_item = item.copy()
                    adjusted_item['timestamp'] = new_timestamp
                    adjusted_script.append(adjusted_item)
            
            # Sort by timestamp
            adjusted_script.sort(key=lambda x: x['timestamp'])
            
            return adjusted_script
            
        except Exception as e:
            self.logger.error(f"Error adjusting TTS timing: {str(e)}")
            return tts_script
    
    def optimize_for_platform(self, tts_script: List[Dict], platform: str) -> List[Dict]:
        """Optimize TTS for specific platform"""
        try:
            platform_optimizations = {
                'youtube': {
                    'max_hooks': 3,
                    'subscribe_hook': True,
                    'emphasis_level': 'medium'
                },
                'instagram': {
                    'max_hooks': 2,
                    'subscribe_hook': False,
                    'emphasis_level': 'high'
                },
                'tiktok': {
                    'max_hooks': 4,
                    'subscribe_hook': False,
                    'emphasis_level': 'high'
                }
            }
            
            settings = platform_optimizations.get(platform, platform_optimizations['youtube'])
            
            # Limit number of hooks
            optimized_script = tts_script[:settings['max_hooks']]
            
            # Adjust subscribe mentions
            if not settings['subscribe_hook']:
                optimized_script = [item for item in optimized_script 
                                 if 'subscribe' not in item['text'].lower()]
            
            return optimized_script
            
        except Exception as e:
            self.logger.error(f"Error optimizing TTS for {platform}: {str(e)}")
            return tts_script
    
    def cleanup_temp_files(self, max_age_hours: int = 24):
        """Clean up temporary TTS files"""
        try:
            import time
            current_time = time.time()
            
            for file_path in self.output_dir.iterdir():
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > (max_age_hours * 3600):
                        file_path.unlink()
                        self.logger.info(f"Cleaned up TTS file: {file_path.name}")
                        
        except Exception as e:
            self.logger.error(f"Error during TTS cleanup: {str(e)}")