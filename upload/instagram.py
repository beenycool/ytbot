import requests
import logging
import json
import time
from typing import Dict, Optional
from pathlib import Path
from config.settings import *
from .base_uploader import BaseUploader, UploadResult

class InstagramUploader(BaseUploader):
    def __init__(self):
        super().__init__('instagram')
        self.access_token = INSTAGRAM_ACCESS_TOKEN
        self.user_id = INSTAGRAM_USER_ID
        self.base_url = "https://graph.facebook.com/v18.0"
        
    def upload(self, video_path: str, metadata: Dict) -> Optional[str]:
        """Upload video to platform and return URL"""
        return self.upload_reel(video_path, metadata)
    
    def upload_reel(self, video_path: str, metadata: Dict) -> Optional[str]:
        """Upload video as Instagram Reel"""
        try:
            # Validate inputs
            if not self.validate_video_file(video_path):
                return None
            if not self.validate_metadata(metadata):
                return None
            
            self.log_upload_attempt(video_path, metadata)
            # Step 1: Create media container
            container_id = self._create_media_container(video_path, metadata)
            if not container_id:
                return None
            
            # Step 2: Check upload status
            if not self._wait_for_upload_completion(container_id):
                return None
            
            # Step 3: Publish the reel
            media_id = self._publish_media(container_id)
            if not media_id:
                return None
            
            # Generate Instagram URL
            instagram_url = f"https://www.instagram.com/reel/{media_id}/"
            
            self.log_upload_success(instagram_url, metadata)
            return instagram_url
            
        except Exception as e:
            self.handle_upload_error(e, "upload_reel")
            return None
    
    def _create_media_container(self, video_path: str, metadata: Dict) -> Optional[str]:
        """Create media container for video upload"""
        try:
            # Upload video to a temporary hosting service or use Facebook's upload endpoint
            video_url = self._upload_video_to_facebook(video_path)
            if not video_url:
                return None
            
            # Prepare caption
            caption = self._create_caption(metadata)
            
            # Create container
            url = f"{self.base_url}/{self.user_id}/media"
            
            params = {
                'media_type': 'REELS',
                'video_url': video_url,
                'caption': caption,
                'access_token': self.access_token
            }
            
            response = requests.post(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                container_id = data.get('id')
                self.logger.info(f"Media container created: {container_id}")
                return container_id
            else:
                self.logger.error(f"Failed to create media container: {response.text}")
                return None
                
        except Exception as e:
            self.handle_upload_error(e, "create_media_container")
            return None
    
    def _upload_video_to_facebook(self, video_path: str) -> Optional[str]:
        """Upload video to Facebook's hosting for Instagram"""
        try:
            # This is a simplified version. In production, you'd use Facebook's
            # resumable upload API for large files
            
            url = f"{self.base_url}/{self.user_id}/videos"
            
            with open(video_path, 'rb') as video_file:
                files = {'source': video_file}
                data = {
                    'access_token': self.access_token,
                    'upload_phase': 'start'
                }
                
                response = requests.post(url, files=files, data=data)
                
                if response.status_code == 200:
                    video_data = response.json()
                    video_url = video_data.get('video_url')
                    self.logger.info(f"Video uploaded to Facebook: {video_url}")
                    return video_url
                else:
                    self.logger.error(f"Failed to upload video: {response.text}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error uploading video to Facebook: {str(e)}")
            return None
    
    def _create_caption(self, metadata: Dict) -> str:
        """Create Instagram caption"""
        try:
            return self.create_description_with_credits(metadata, max_length=2200)
        except Exception as e:
            self.logger.error(f"Error creating caption: {str(e)}")
            return "Amazing content! Follow for more! 🔥"
    
    def _wait_for_upload_completion(self, container_id: str, max_wait_time: int = 300) -> bool:
        """Wait for video upload to complete"""
        try:
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                status = self._check_upload_status(container_id)
                
                if status == 'FINISHED':
                    self.logger.info(f"Upload completed for container: {container_id}")
                    return True
                elif status == 'ERROR':
                    self.logger.error(f"Upload failed for container: {container_id}")
                    return False
                elif status == 'IN_PROGRESS':
                    self.logger.info(f"Upload in progress for container: {container_id}")
                    time.sleep(10)  # Wait 10 seconds before checking again
                else:
                    self.logger.warning(f"Unknown status for container {container_id}: {status}")
                    time.sleep(5)
            
            self.logger.error(f"Upload timed out for container: {container_id}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error waiting for upload completion: {str(e)}")
            return False
    
    def _check_upload_status(self, container_id: str) -> str:
        """Check upload status of media container"""
        try:
            url = f"{self.base_url}/{container_id}"
            
            params = {
                'fields': 'status_code',
                'access_token': self.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('status_code', 'UNKNOWN')
            else:
                self.logger.error(f"Failed to check status: {response.text}")
                return 'ERROR'
                
        except Exception as e:
            self.logger.error(f"Error checking upload status: {str(e)}")
            return 'ERROR'
    
    def _publish_media(self, container_id: str) -> Optional[str]:
        """Publish the media container"""
        try:
            url = f"{self.base_url}/{self.user_id}/media_publish"
            
            params = {
                'creation_id': container_id,
                'access_token': self.access_token
            }
            
            response = requests.post(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                media_id = data.get('id')
                self.logger.info(f"Media published successfully: {media_id}")
                return media_id
            else:
                self.logger.error(f"Failed to publish media: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error publishing media: {str(e)}")
            return None
    
    def get_media_insights(self, media_id: str) -> Optional[Dict]:
        """Get insights for published media"""
        try:
            url = f"{self.base_url}/{media_id}/insights"
            
            params = {
                'metric': 'impressions,reach,likes,comments,shares,saves',
                'access_token': self.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                insights = {}
                for item in data.get('data', []):
                    metric_name = item.get('name')
                    metric_value = item.get('values', [{}])[0].get('value', 0)
                    insights[metric_name] = metric_value
                
                return insights
            else:
                self.logger.error(f"Failed to get insights: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting media insights: {str(e)}")
            return None
    
    def delete_media(self, media_id: str) -> bool:
        """Delete published media"""
        try:
            url = f"{self.base_url}/{media_id}"
            
            params = {
                'access_token': self.access_token
            }
            
            response = requests.delete(url, params=params)
            
            if response.status_code == 200:
                self.logger.info(f"Media deleted successfully: {media_id}")
                return True
            else:
                self.logger.error(f"Failed to delete media: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting media: {str(e)}")
            return False
    
    def check_account_status(self) -> Dict:
        """Check Instagram account status and limits"""
        try:
            url = f"{self.base_url}/{self.user_id}"
            
            params = {
                'fields': 'account_type,media_count',
                'access_token': self.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'account_type': data.get('account_type', 'UNKNOWN'),
                    'media_count': data.get('media_count', 0),
                    'status': 'active'
                }
            else:
                self.logger.error(f"Failed to check account status: {response.text}")
                return {'status': 'error'}
                
        except Exception as e:
            self.logger.error(f"Error checking account status: {str(e)}")
            return {'status': 'error'}
    
    def optimize_for_reels(self, metadata: Dict) -> Dict:
        """Optimize metadata specifically for Instagram Reels"""
        try:
            optimized = metadata.copy()
            
            # Optimize title for Instagram
            title = metadata.get('title', '')
            if len(title) > 150:
                title = title[:147] + '...'
            
            # Add Instagram-specific elements
            optimized.update({
                'title': title,
                'hashtags': self._generate_instagram_hashtags(metadata),
                'mention_friends': True,
                'use_trending_audio': True
            })
            
            return optimized
            
        except Exception as e:
            self.logger.error(f"Error optimizing for reels: {str(e)}")
            return metadata
    
    def _prepare_metadata(self, metadata: Dict) -> Dict:
        """Prepare platform-specific metadata"""
        return self.optimize_for_reels(metadata)
    
    def _generate_hashtags(self, metadata: Dict) -> list:
        """Generate platform-specific hashtags"""
        return self._generate_instagram_hashtags(metadata)
    
    def _generate_instagram_hashtags(self, metadata: Dict) -> list:
        """Generate Instagram-specific hashtags"""
        try:
            base_hashtags = [
                '#reels', '#viral', '#fyp', '#explore', '#amazing', 
                '#mindblowing', '#incredible', '#trending', '#wow'
            ]
            
            # Add content-specific hashtags
            title = metadata.get('title', '').lower()
            if 'smart' in title:
                base_hashtags.extend(['#genius', '#intelligent', '#brilliant'])
            if 'science' in title:
                base_hashtags.extend(['#science', '#physics', '#chemistry'])
            if 'art' in title:
                base_hashtags.extend(['#art', '#creative', '#design'])
            
            return base_hashtags[:30]  # Instagram allows up to 30 hashtags
            
        except Exception as e:
            self.logger.error(f"Error generating hashtags: {str(e)}")
            return ['#reels', '#viral', '#amazing']