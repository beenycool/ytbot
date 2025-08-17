import requests
import json
import logging
import time
import hashlib
import hmac
from typing import Dict, Optional
from pathlib import Path
from urllib.parse import urlencode
from config.settings import *
from .base_uploader import BaseUploader, UploadResult

class TikTokUploader(BaseUploader):
    def __init__(self):
        super().__init__('tiktok')
        self.client_key = TIKTOK_CLIENT_KEY
        self.client_secret = TIKTOK_CLIENT_SECRET
        self.access_token = TIKTOK_ACCESS_TOKEN
        self.base_url = "https://open-api.tiktok.com"
        
    def upload(self, video_path: str, metadata: Dict) -> Optional[str]:
        """Upload video to platform and return URL"""
        return self.upload_video(video_path, metadata)
    
    def upload_video(self, video_path: str, metadata: Dict) -> Optional[str]:
        """Upload video to TikTok"""
        try:
            # Validate inputs
            if not self.validate_video_file(video_path):
                return None
            if not self.validate_metadata(metadata):
                return None
            
            self.log_upload_attempt(video_path, metadata)
            # Step 1: Initialize video upload
            upload_url, upload_id = self._initialize_upload(metadata)
            if not upload_url or not upload_id:
                return None
            
            # Step 2: Upload video file
            if not self._upload_video_file(upload_url, video_path):
                return None
            
            # Step 3: Publish video
            video_id = self._publish_video(upload_id, metadata)
            if not video_id:
                return None
            
            # Generate TikTok URL
            tiktok_url = f"https://www.tiktok.com/@username/video/{video_id}"
            
            self.log_upload_success(tiktok_url, metadata)
            return tiktok_url
            
        except Exception as e:
            self.handle_upload_error(e, "upload_video")
            return None
    
    def _initialize_upload(self, metadata: Dict) -> tuple:
        """Initialize video upload and get upload URL"""
        try:
            url = f"{self.base_url}/v2/post/publish/video/init/"
            
            # Prepare video info
            video_info = {
                'source_info': {
                    'source': 'FILE_UPLOAD',
                    'video_size': self._get_file_size(metadata.get('video_path', '')),
                    'chunk_size': 10 * 1024 * 1024,  # 10MB chunks
                    'total_chunk_count': 1
                }
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json; charset=UTF-8'
            }
            
            response = requests.post(url, headers=headers, json=video_info)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('error', {}).get('code') == 'ok':
                    publish_id = data['data']['publish_id']
                    upload_url = data['data']['upload_url']
                    
                    self.logger.info(f"Upload initialized: {publish_id}")
                    return upload_url, publish_id
                else:
                    self.logger.error(f"TikTok API error: {data}")
                    return None, None
            else:
                self.logger.error(f"Failed to initialize upload: {response.text}")
                return None, None
                
        except Exception as e:
            self.logger.error(f"Error initializing upload: {str(e)}")
            return None, None
    
    def _upload_video_file(self, upload_url: str, video_path: str) -> bool:
        """Upload video file to TikTok"""
        try:
            with open(video_path, 'rb') as video_file:
                files = {'video': video_file}
                
                response = requests.put(upload_url, files=files)
                
                if response.status_code == 200:
                    self.logger.info(f"Video file uploaded successfully")
                    return True
                else:
                    self.logger.error(f"Failed to upload video file: {response.text}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error uploading video file: {str(e)}")
            return False
    
    def _publish_video(self, publish_id: str, metadata: Dict) -> Optional[str]:
        """Publish the uploaded video"""
        try:
            url = f"{self.base_url}/v2/post/publish/video/"
            
            # Prepare post info
            post_info = {
                'title': self._create_title(metadata),
                'privacy_level': 'SELF_ONLY',  # Start with private, can be changed later
                'disable_duet': False,
                'disable_comment': False,
                'disable_stitch': False,
                'video_cover_timestamp_ms': 1000
            }
            
            payload = {
                'post_info': post_info,
                'source_info': {
                    'source': 'FILE_UPLOAD',
                    'publish_id': publish_id
                }
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json; charset=UTF-8'
            }
            
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('error', {}).get('code') == 'ok':
                    video_id = data['data']['publish_id']
                    self.logger.info(f"Video published successfully: {video_id}")
                    return video_id
                else:
                    self.logger.error(f"TikTok publish error: {data}")
                    return None
            else:
                self.logger.error(f"Failed to publish video: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error publishing video: {str(e)}")
            return None
    
    def _create_title(self, metadata: Dict) -> str:
        """Create TikTok title with hashtags"""
        try:
            base_title = metadata.get('title', 'Amazing content!')
            
            # TikTok-style title with hashtags
            hashtags = self._generate_tiktok_hashtags(metadata)
            hashtag_string = ' '.join(hashtags[:10])  # Limit hashtags
            
            # TikTok has a 150 character limit for captions
            max_title_length = 150 - len(hashtag_string) - 5  # Buffer for spacing
            
            if len(base_title) > max_title_length:
                base_title = base_title[:max_title_length-3] + '...'
            
            full_title = f"{base_title} {hashtag_string}"
            
            return full_title[:150]  # Ensure we don't exceed limit
            
        except Exception as e:
            self.logger.error(f"Error creating title: {str(e)}")
            return "Amazing content! #fyp #viral"
    
    def _generate_hashtags(self, metadata: Dict) -> list:
        """Generate platform-specific hashtags"""
        return self._generate_tiktok_hashtags(metadata)
    
    def _generate_tiktok_hashtags(self, metadata: Dict) -> list:
        """Generate TikTok-specific hashtags"""
        try:
            base_hashtags = [
                '#fyp', '#viral', '#foryou', '#trending', '#amazing', 
                '#mindblowing', '#wow', '#insane', '#genius', '#smart'
            ]
            
            # Add content-specific hashtags
            title = metadata.get('title', '').lower()
            subreddit = metadata.get('subreddit', '').lower()
            
            if 'science' in title or 'physics' in title:
                base_hashtags.extend(['#science', '#physics', '#chemistry', '#educational'])
            
            if 'art' in title or 'creative' in title:
                base_hashtags.extend(['#art', '#creative', '#artist', '#design'])
            
            if 'talent' in title or subreddit == 'toptalent':
                base_hashtags.extend(['#talent', '#skills', '#impressive', '#amazing'])
            
            if 'funny' in title or 'humor' in title:
                base_hashtags.extend(['#funny', '#comedy', '#humor', '#laugh'])
            
            # TikTok trending hashtags (these change frequently)
            trending_hashtags = [
                '#xyzbca', '#fypシ', '#viralvideo', '#tiktok', '#explore',
                '#discover', '#entertainment', '#satisfying', '#oddlysatisfying'
            ]
            
            base_hashtags.extend(trending_hashtags[:5])
            
            return list(set(base_hashtags))  # Remove duplicates
            
        except Exception as e:
            self.logger.error(f"Error generating hashtags: {str(e)}")
            return ['#fyp', '#viral', '#amazing']
    
    def _get_file_size(self, file_path: str) -> int:
        """Get file size in bytes"""
        return self.get_file_size(file_path)
    
    def get_video_info(self, video_id: str) -> Optional[Dict]:
        """Get video information and stats"""
        try:
            url = f"{self.base_url}/v2/video/query/"
            
            params = {
                'fields': 'id,title,video_description,duration,cover_image_url,share_url,view_count,like_count,comment_count,share_count'
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json; charset=UTF-8'
            }
            
            payload = {
                'filters': {
                    'video_ids': [video_id]
                }
            }
            
            response = requests.post(url, headers=headers, json=payload, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('error', {}).get('code') == 'ok':
                    videos = data.get('data', {}).get('videos', [])
                    if videos:
                        return videos[0]
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting video info: {str(e)}")
            return None
    
    def delete_video(self, video_id: str) -> bool:
        """Delete video from TikTok"""
        try:
            url = f"{self.base_url}/v2/post/publish/video/delete/"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json; charset=UTF-8'
            }
            
            payload = {
                'video_id': video_id
            }
            
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('error', {}).get('code') == 'ok':
                    self.logger.info(f"Video deleted successfully: {video_id}")
                    return True
            
            self.logger.error(f"Failed to delete video: {response.text}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting video: {str(e)}")
            return False
    
    def check_upload_quota(self) -> Dict:
        """Check upload quota and limits"""
        try:
            # TikTok has various limits - this is a simplified check
            return {
                'daily_uploads_remaining': 10,  # TikTok allows limited uploads per day
                'quota_exceeded': False,
                'can_upload': True
            }
            
        except Exception as e:
            self.logger.error(f"Error checking quota: {str(e)}")
            return {'daily_uploads_remaining': 0, 'quota_exceeded': True, 'can_upload': False}
    
    def optimize_for_tiktok(self, metadata: Dict) -> Dict:
        """Optimize metadata specifically for TikTok"""
        try:
            optimized = metadata.copy()
            
            # Optimize title for TikTok
            title = metadata.get('title', '')
            
            # Add TikTok-style engagement elements
            engagement_starters = [
                "POV: ", "Tell me why ", "No one talks about how ", 
                "This is why ", "Wait for it... ", "Plot twist: "
            ]
            
            # Add engagement starter if title doesn't have one
            if not any(starter.lower() in title.lower() for starter in engagement_starters):
                title = f"Wait for it... {title}"
            
            # Ensure title is engaging for TikTok audience
            if len(title) > 100:
                title = title[:97] + '...'
            
            optimized.update({
                'title': title,
                'hashtags': self._generate_tiktok_hashtags(metadata),
                'trending_elements': True,
                'short_attention_span': True
            })
            
            return optimized
            
        except Exception as e:
            self.logger.error(f"Error optimizing for TikTok: {str(e)}")
            return metadata
    
    def get_trending_hashtags(self) -> list:
        """Get current trending hashtags (simplified version)"""
        try:
            # In a real implementation, you'd fetch this from TikTok's trending API
            # or use a third-party service to track trending hashtags
            
            trending = [
                '#fyp', '#viral', '#foryou', '#trending', '#xyzbca',
                '#fypシ', '#viralvideo', '#tiktok', '#amazing', '#wow'
            ]
            
            return trending
            
        except Exception as e:
            self.logger.error(f"Error getting trending hashtags: {str(e)}")
            return ['#fyp', '#viral', '#foryou']
    
    def schedule_video(self, video_id: str, schedule_time: int) -> bool:
        """Schedule video for later publication (if supported)"""
        try:
            # Note: TikTok's scheduling feature may not be available in all regions
            # This is a placeholder for future implementation
            
            self.logger.info(f"Video scheduling not implemented yet for TikTok")
            return False
            
        except Exception as e:
            self.logger.error(f"Error scheduling video: {str(e)}")
            return False