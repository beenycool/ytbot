import cv2
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import json
from .gemini_client import GeminiClient
from config.settings import *

class VideoAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.gemini_client = GeminiClient()
        
    def analyze_and_plan_cuts(self, video_info: Dict, analysis: Dict) -> Dict:
        """Analyze video and create detailed cutting plan"""
        try:
            video_path = video_info['file_path']
            duration = video_info['duration']
            
            # Get basic video metrics
            video_metrics = self._get_video_metrics(video_path)
            
            # Plan optimal cuts based on Gemini analysis
            cut_plan = self._create_cut_plan(analysis, duration, video_metrics)
            
            # Detect main subject for tracking
            subject_info = self._analyze_main_subject(video_path, analysis.get('main_subject', {}))
            
            # Plan cropping strategy
            crop_plan = self._plan_cropping_strategy(video_metrics, subject_info)
            
            complete_analysis = {
                'video_info': video_info,
                'gemini_analysis': analysis,
                'video_metrics': video_metrics,
                'cut_plan': cut_plan,
                'subject_info': subject_info,
                'crop_plan': crop_plan,
                'processing_instructions': self._create_processing_instructions(cut_plan, crop_plan, analysis)
            }
            
            self.logger.info(f"Complete analysis created for {Path(video_path).name}")
            return complete_analysis
            
        except Exception as e:
            self.logger.error(f"Error in video analysis: {str(e)}")
            return {}
    
    def _get_video_metrics(self, video_path: str) -> Dict:
        """Extract detailed video metrics using OpenCV"""
        try:
            cap = cv2.VideoCapture(video_path)
            
            metrics = {
                'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                'fps': cap.get(cv2.CAP_PROP_FPS),
                'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'duration': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / cap.get(cv2.CAP_PROP_FPS),
                'aspect_ratio': cap.get(cv2.CAP_PROP_FRAME_WIDTH) / cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
                'codec': int(cap.get(cv2.CAP_PROP_FOURCC))
            }
            
            # Analyze motion and scene changes
            motion_data = self._analyze_motion_patterns(cap)
            metrics.update(motion_data)
            
            cap.release()
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error getting video metrics: {str(e)}")
            return {}
    
    def _analyze_motion_patterns(self, cap) -> Dict:
        """Analyze motion patterns to identify key moments"""
        try:
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # Sample frames for motion analysis
            sample_interval = max(1, frame_count // 100)  # Sample 100 frames max
            motion_scores = []
            scene_changes = []
            
            prev_frame = None
            for i in range(0, frame_count, sample_interval):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                
                if not ret:
                    break
                    
                # Convert to grayscale for motion detection
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                if prev_frame is not None:
                    # Calculate optical flow
                    flow = cv2.calcOpticalFlowPyrLK(prev_frame, gray, None, None)
                    motion_magnitude = np.mean(np.abs(flow[0])) if flow[0] is not None else 0
                    motion_scores.append({
                        'timestamp': i / fps,
                        'motion': motion_magnitude
                    })
                    
                    # Detect scene changes using histogram comparison
                    hist_prev = cv2.calcHist([prev_frame], [0], None, [256], [0, 256])
                    hist_curr = cv2.calcHist([gray], [0], None, [256], [0, 256])
                    correlation = cv2.compareHist(hist_prev, hist_curr, cv2.HISTCMP_CORREL)
                    
                    if correlation < 0.8:  # Scene change threshold
                        scene_changes.append(i / fps)
                
                prev_frame = gray
            
            return {
                'motion_scores': motion_scores,
                'scene_changes': scene_changes,
                'avg_motion': np.mean([score['motion'] for score in motion_scores]) if motion_scores else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing motion patterns: {str(e)}")
            return {'motion_scores': [], 'scene_changes': [], 'avg_motion': 0}
    
    def _create_cut_plan(self, analysis: Dict, duration: float, metrics: Dict) -> Dict:
        """Create detailed cutting plan based on analysis"""
        try:
            cutting_suggestions = analysis.get('cutting_suggestions', {})
            key_moments = analysis.get('key_moments', [])
            scene_changes = metrics.get('scene_changes', [])
            
            # Determine optimal start and end times
            suggested_start = cutting_suggestions.get('start_time', 0.0)
            suggested_end = cutting_suggestions.get('end_time', min(duration, 30.0))
            
            # Ensure we stay within shorts duration limits
            max_duration = min(MAX_VIDEO_DURATION, 60)
            if suggested_end - suggested_start > max_duration:
                suggested_end = suggested_start + max_duration
            
            # Create segments based on key moments and scene changes
            segments = []
            best_segments = cutting_suggestions.get('best_segments', [])
            
            if best_segments:
                for segment in best_segments:
                    segments.append({
                        'start': max(0, segment['start']),
                        'end': min(duration, segment['end']),
                        'reason': segment.get('reason', 'Key segment'),
                        'priority': self._calculate_segment_priority(segment, key_moments)
                    })
            else:
                # Create default segments if none provided
                segment_duration = min(15, (suggested_end - suggested_start) / 2)
                segments.append({
                    'start': suggested_start,
                    'end': suggested_start + segment_duration,
                    'reason': 'Opening segment',
                    'priority': 'high'
                })
            
            # Sort segments by priority
            segments.sort(key=lambda x: {'high': 3, 'medium': 2, 'low': 1}.get(x['priority'], 1), reverse=True)
            
            cut_plan = {
                'primary_segment': {
                    'start': suggested_start,
                    'end': suggested_end,
                    'duration': suggested_end - suggested_start
                },
                'segments': segments[:5],  # Top 5 segments
                'key_timestamps': [moment['timestamp'] for moment in key_moments],
                'scene_changes': scene_changes,
                'recommended_cuts': self._generate_cut_points(segments, scene_changes)
            }
            
            return cut_plan
            
        except Exception as e:
            self.logger.error(f"Error creating cut plan: {str(e)}")
            return {'primary_segment': {'start': 0, 'end': 30, 'duration': 30}, 'segments': []}
    
    def _calculate_segment_priority(self, segment: Dict, key_moments: List[Dict]) -> str:
        """Calculate priority of a segment based on key moments"""
        start, end = segment['start'], segment['end']
        
        # Count key moments in this segment
        moments_in_segment = sum(1 for moment in key_moments 
                               if start <= moment['timestamp'] <= end)
        
        # Check for critical moments
        critical_moments = sum(1 for moment in key_moments 
                             if start <= moment['timestamp'] <= end 
                             and moment.get('importance') == 'critical')
        
        if critical_moments > 0:
            return 'high'
        elif moments_in_segment >= 2:
            return 'high'
        elif moments_in_segment >= 1:
            return 'medium'
        else:
            return 'low'
    
    def _analyze_main_subject(self, video_path: str, subject_info: Dict) -> Dict:
        """Analyze main subject for tracking and cropping"""
        try:
            cap = cv2.VideoCapture(video_path)
            
            # Get a few sample frames
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            sample_frames = []
            
            for i in range(0, frame_count, frame_count // 5):  # 5 sample frames
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                if ret:
                    sample_frames.append(frame)
            
            cap.release()
            
            if not sample_frames:
                return {'type': 'center', 'tracking_method': 'center', 'regions': []}
            
            # Analyze subject type and position
            subject_type = subject_info.get('type', 'unknown')
            tracking_regions = []
            
            if subject_type == 'person':
                # Use face detection for person tracking
                tracking_regions = self._detect_face_regions(sample_frames)
            elif subject_type == 'object':
                # Use object detection or motion tracking
                tracking_regions = self._detect_object_regions(sample_frames)
            else:
                # Default to center tracking
                height, width = sample_frames[0].shape[:2]
                tracking_regions = [{
                    'x': width // 4,
                    'y': height // 4,
                    'width': width // 2,
                    'height': height // 2,
                    'confidence': 0.5
                }]
            
            return {
                'type': subject_type,
                'tracking_method': subject_info.get('tracking_suggestion', 'center'),
                'regions': tracking_regions,
                'description': subject_info.get('description', 'Main subject')
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing main subject: {str(e)}")
            return {'type': 'center', 'tracking_method': 'center', 'regions': []}
    
    def _detect_face_regions(self, frames: List) -> List[Dict]:
        """Detect face regions in frames"""
        try:
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            regions = []
            
            for frame in frames:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                
                for (x, y, w, h) in faces:
                    regions.append({
                        'x': int(x),
                        'y': int(y),
                        'width': int(w),
                        'height': int(h),
                        'confidence': 0.8
                    })
            
            return regions
            
        except Exception as e:
            self.logger.error(f"Error detecting faces: {str(e)}")
            return []
    
    def _detect_object_regions(self, frames: List) -> List[Dict]:
        """Detect object regions using motion and contours"""
        try:
            regions = []
            
            if len(frames) < 2:
                return regions
            
            # Use frame differencing to detect moving objects
            for i in range(1, len(frames)):
                prev_gray = cv2.cvtColor(frames[i-1], cv2.COLOR_BGR2GRAY)
                curr_gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
                
                # Calculate difference
                diff = cv2.absdiff(prev_gray, curr_gray)
                _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
                
                # Find contours
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Filter contours by area
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > 1000:  # Minimum area threshold
                        x, y, w, h = cv2.boundingRect(contour)
                        regions.append({
                            'x': int(x),
                            'y': int(y),
                            'width': int(w),
                            'height': int(h),
                            'confidence': min(0.9, area / 10000)
                        })
            
            return regions
            
        except Exception as e:
            self.logger.error(f"Error detecting objects: {str(e)}")
            return []
    
    def _plan_cropping_strategy(self, metrics: Dict, subject_info: Dict) -> Dict:
        """Plan cropping strategy to convert to 9:16 aspect ratio"""
        try:
            width = metrics.get('width', 1920)
            height = metrics.get('height', 1080)
            aspect_ratio = metrics.get('aspect_ratio', width / height)
            
            target_aspect = 9/16  # Shorts aspect ratio
            
            crop_plan = {
                'original_dimensions': {'width': width, 'height': height},
                'target_dimensions': OUTPUT_RESOLUTION,
                'crop_method': 'center',
                'tracking_enabled': False
            }
            
            # Determine cropping method based on original aspect ratio
            if aspect_ratio > target_aspect:
                # Video is wider than target - crop horizontally
                new_width = int(height * target_aspect)
                crop_x = (width - new_width) // 2
                
                # Adjust crop position based on subject tracking
                if subject_info.get('regions'):
                    avg_x = np.mean([region['x'] + region['width']//2 for region in subject_info['regions']])
                    crop_x = max(0, min(width - new_width, int(avg_x - new_width//2)))
                
                crop_plan.update({
                    'crop_method': 'horizontal',
                    'crop_x': crop_x,
                    'crop_y': 0,
                    'crop_width': new_width,
                    'crop_height': height,
                    'tracking_enabled': len(subject_info.get('regions', [])) > 0
                })
                
            else:
                # Video is taller or same as target - crop vertically or scale
                new_height = int(width / target_aspect)
                crop_y = max(0, (height - new_height) // 2)
                
                if subject_info.get('regions'):
                    avg_y = np.mean([region['y'] + region['height']//2 for region in subject_info['regions']])
                    crop_y = max(0, min(height - new_height, int(avg_y - new_height//2)))
                
                crop_plan.update({
                    'crop_method': 'vertical',
                    'crop_x': 0,
                    'crop_y': crop_y,
                    'crop_width': width,
                    'crop_height': min(height, new_height),
                    'tracking_enabled': len(subject_info.get('regions', [])) > 0
                })
            
            return crop_plan
            
        except Exception as e:
            self.logger.error(f"Error planning cropping strategy: {str(e)}")
            return {'crop_method': 'center', 'tracking_enabled': False}
    
    def _generate_cut_points(self, segments: List[Dict], scene_changes: List[float]) -> List[Dict]:
        """Generate specific cut points for editing"""
        cut_points = []
        
        for segment in segments:
            start_time = segment['start']
            end_time = segment['end']
            
            # Find scene changes within this segment
            segment_changes = [change for change in scene_changes 
                             if start_time <= change <= end_time]
            
            cut_points.append({
                'start': start_time,
                'end': end_time,
                'duration': end_time - start_time,
                'scene_changes': segment_changes,
                'priority': segment.get('priority', 'medium'),
                'reason': segment.get('reason', 'Key segment')
            })
        
        return cut_points
    
    def _create_processing_instructions(self, cut_plan: Dict, crop_plan: Dict, analysis: Dict) -> Dict:
        """Create comprehensive processing instructions"""
        return {
            'cutting': {
                'primary_cut': cut_plan.get('primary_segment', {}),
                'segments': cut_plan.get('segments', []),
                'method': 'precise'
            },
            'cropping': crop_plan,
            'effects': analysis.get('visual_effects', []),
            'tts': analysis.get('tts_script', []),
            'subtitles': analysis.get('subtitle_timing', []),
            'quality': {
                'resolution': OUTPUT_RESOLUTION,
                'fps': 30,
                'bitrate': 'auto'
            }
        }