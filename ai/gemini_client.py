import google.generativeai as genai
import logging
import json
import base64
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import cv2
import numpy as np
from config.settings import *

class GeminiClient:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
    def analyze_video(self, video_path: str, title: str, description: str = "") -> Dict:
        """Analyze video using Gemini 2.5 Flash for key moments, transcription, and editing suggestions"""
        try:
            # Extract frames for analysis
            frames = self._extract_key_frames(video_path, max_frames=10)
            if not frames:
                self.logger.error(f"Could not extract frames from {video_path}")
                return {}
            
            # Prepare prompt for video analysis
            prompt = self._create_analysis_prompt(title, description)
            
            # Analyze with Gemini
            response = self.model.generate_content([prompt] + frames)
            
            # Parse response
            analysis = self._parse_analysis_response(response.text)
            
            # Add video-specific metadata
            analysis['video_path'] = video_path
            analysis['original_title'] = title
            
            self.logger.info(f"Successfully analyzed video: {Path(video_path).name}")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing video {video_path}: {str(e)}")
            return {}
    
    def _extract_key_frames(self, video_path: str, max_frames: int = 10) -> List:
        """Extract key frames from video for analysis"""
        try:
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            duration = total_frames / fps if fps > 0 else 0
            
            if duration == 0:
                return []
            
            # Extract frames at regular intervals
            interval = max(1, total_frames // max_frames)
            frames = []
            
            for i in range(0, total_frames, interval):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                
                if ret:
                    # Convert frame to Gemini-compatible format
                    import tempfile
                    import os
                    
                    # Save frame to temporary file
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                        cv2.imwrite(temp_file.name, frame)
                        temp_path = temp_file.name
                    
                    # Upload as file to Gemini
                    uploaded_file = genai.upload_file(temp_path, mime_type='image/jpeg')
                    frames.append(uploaded_file)
                    
                    # Clean up temp file
                    os.unlink(temp_path)
                    
                if len(frames) >= max_frames:
                    break
            
            cap.release()
            return frames
            
        except Exception as e:
            self.logger.error(f"Error extracting frames: {str(e)}")
            return []
    
    
    def _create_analysis_prompt(self, title: str, description: str) -> str:
        """Create comprehensive analysis prompt for Gemini"""
        return f"""
        Analyze this video content for creating engaging short-form content. The original title is: "{title}"
        
        Please provide a JSON response with the following analysis:
        
        1. **Key Moments**: Identify 3-5 most interesting/engaging moments with exact timestamps
        2. **Transcription**: Provide accurate transcription of any speech/audio
        3. **Cutting Suggestions**: Suggest specific cut points to create a 15-60 second engaging clip
        4. **Main Subject**: Identify the main subject/person/object to track for cropping
        5. **Engagement Title**: Rewrite the title to be more engaging for young audiences (include elements like "This person is so smart!", "Wait for it", etc.)
        6. **TTS Script**: Generate text-to-speech script with engagement hooks
        7. **Visual Effects**: Suggest simple visual effects that would enhance engagement
        8. **Subtitle Timing**: Provide timing for key phrases that should be highlighted
        
        Focus on creating content that appeals to Gen Z/Alpha audiences with:
        - High energy and engagement
        - Clear, easy-to-follow content
        - Surprising or educational moments
        - Brainrot-style engagement (sparingly)
        
        Respond ONLY in valid JSON format:
        {{
            "key_moments": [
                {{"timestamp": 0.0, "description": "Opening moment", "importance": "high"}},
                {{"timestamp": 15.2, "description": "Key revelation", "importance": "critical"}}
            ],
            "transcription": "Full transcription here...",
            "cutting_suggestions": {{
                "start_time": 0.0,
                "end_time": 30.0,
                "best_segments": [
                    {{"start": 0.0, "end": 5.0, "reason": "Strong opening"}},
                    {{"start": 15.0, "end": 25.0, "reason": "Main content"}}
                ]
            }},
            "main_subject": {{
                "type": "person|object|action",
                "description": "Description of main subject",
                "tracking_suggestion": "face|center|movement"
            }},
            "engagement_title": "This Will Blow Your Mind! 🤯",
            "tts_script": [
                {{"timestamp": 0.0, "text": "This person is so smart!", "pause": 1.0}},
                {{"timestamp": 10.0, "text": "Wait for the ending!", "pause": 0.5}}
            ],
            "visual_effects": [
                {{"type": "zoom", "timestamp": 5.0, "intensity": "medium"}},
                {{"type": "slow_motion", "start": 20.0, "end": 25.0}}
            ],
            "subtitle_timing": [
                {{"start": 0.0, "end": 3.0, "text": "WATCH THIS!", "style": "emphasis"}},
                {{"start": 15.0, "end": 18.0, "text": "INSANE MOMENT", "style": "highlight"}}
            ]
        }}
        """
    
    def _parse_analysis_response(self, response_text: str) -> Dict:
        """Parse Gemini's JSON response"""
        try:
            # Clean up response text
            response_text = response_text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            # Parse JSON
            analysis = json.loads(response_text)
            
            # Validate required fields
            required_fields = ['key_moments', 'transcription', 'cutting_suggestions', 'engagement_title']
            for field in required_fields:
                if field not in analysis:
                    self.logger.warning(f"Missing field in analysis: {field}")
                    analysis[field] = self._get_default_value(field)
            
            return analysis
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {str(e)}")
            return self._get_fallback_analysis()
        except Exception as e:
            self.logger.error(f"Error parsing analysis response: {str(e)}")
            return self._get_fallback_analysis()
    
    def _get_default_value(self, field: str):
        """Get default values for missing fields"""
        defaults = {
            'key_moments': [],
            'transcription': '',
            'cutting_suggestions': {'start_time': 0.0, 'end_time': 30.0, 'best_segments': []},
            'engagement_title': 'Amazing Video!',
            'tts_script': [{'timestamp': 0.0, 'text': 'Check this out!', 'pause': 1.0}],
            'visual_effects': [],
            'subtitle_timing': [],
            'main_subject': {'type': 'center', 'description': 'Main content', 'tracking_suggestion': 'center'}
        }
        return defaults.get(field, None)
    
    def _get_fallback_analysis(self) -> Dict:
        """Return fallback analysis if parsing fails"""
        return {
            'key_moments': [{'timestamp': 0.0, 'description': 'Video start', 'importance': 'medium'}],
            'transcription': '',
            'cutting_suggestions': {
                'start_time': 0.0,
                'end_time': 30.0,
                'best_segments': [{'start': 0.0, 'end': 30.0, 'reason': 'Full video'}]
            },
            'main_subject': {
                'type': 'center',
                'description': 'Main content',
                'tracking_suggestion': 'center'
            },
            'engagement_title': 'Amazing Video!',
            'tts_script': [
                {'timestamp': 0.0, 'text': 'This is incredible!', 'pause': 1.0}
            ],
            'visual_effects': [],
            'subtitle_timing': []
        }
    
    def generate_engagement_hooks(self, context: str, style: str = "brainrot") -> List[str]:
        """Generate engagement hooks for different parts of the video"""
        try:
            prompt = f"""
            Generate 5 engaging text-to-speech hooks for a short video about: {context}
            
            Style: {style} (should appeal to Gen Z/Alpha but not be too cringe)
            
            Include variations of:
            - Opening hooks ("This person is so smart!", "Wait for it...")
            - Mid-video engagement ("Look what happens next!", "This is insane!")
            - Ending hooks ("Subscribe for more!", "Don't skip this!")
            
            Make them short (3-8 words) and energetic. Return as JSON array:
            ["hook1", "hook2", "hook3", "hook4", "hook5"]
            """
            
            response = self.model.generate_content(prompt)
            hooks = json.loads(response.text)
            
            if isinstance(hooks, list):
                return hooks
            else:
                return ENGAGEMENT_HOOKS[:5]
                
        except Exception as e:
            self.logger.error(f"Error generating engagement hooks: {str(e)}")
            return ENGAGEMENT_HOOKS[:5]
    
    def optimize_title_for_platform(self, title: str, platform: str) -> str:
        """Optimize title for specific platform"""
        try:
            platform_guidelines = {
                'youtube': 'YouTube Shorts (100 chars max, include emojis, trending keywords)',
                'instagram': 'Instagram Reels (125 chars max, use hashtags, engaging)',
                'tiktok': 'TikTok (100 chars max, trending sounds, challenges)'
            }
            
            guideline = platform_guidelines.get(platform, 'Generic short-form content')
            
            prompt = f"""
            Optimize this title for {platform}: "{title}"
            
            Guidelines: {guideline}
            
            Make it engaging for young audiences, include relevant emojis, and ensure it will perform well algorithmically.
            Return only the optimized title, nothing else.
            """
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            self.logger.error(f"Error optimizing title for {platform}: {str(e)}")
            return title