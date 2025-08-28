import logging
import os
import json
from typing import Dict, Optional
from pathlib import Path
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from config.settings import *
from .base_uploader import BaseUploader, UploadResult

class YouTubeUploader(BaseUploader):
    def __init__(self):
        super().__init__('youtube')
        self.credentials = None
        self.youtube_service = None
        self.scopes = ['https://www.googleapis.com/auth/youtube.upload']
        self.token_file = 'youtube_token.json'
        self.credentials_file = 'googlecreds.json'
        self._setup_credentials()
        
    def _setup_credentials(self):
        """Setup YouTube API credentials with OAuth flow"""
        try:
            creds = None
            
            # Check if token file exists
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
            
            # If there are no (valid) credentials available, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        self.logger.info("Refreshed existing YouTube credentials")
                    except Exception as e:
                        self.logger.warning(f"Failed to refresh token, starting new OAuth flow: {e}")
                        creds = None
                
                if not creds:
                    creds = self._run_oauth_flow()
                
                # Save the credentials for the next run
                if creds:
                    with open(self.token_file, 'w') as token:
                        token.write(creds.to_json())
                    self.logger.info("Saved YouTube credentials to token file")
            
            self.credentials = creds
            
            # Build YouTube service
            if creds:
                self.youtube_service = self._build_service()
                self.logger.info("YouTube service initialized successfully")
            else:
                self.logger.error("Failed to obtain YouTube credentials")
            
        except Exception as e:
            self.logger.error(f"Error setting up YouTube credentials: {str(e)}")
    
    def _run_oauth_flow(self):
        """Run OAuth flow to get credentials"""
        try:
            if not os.path.exists(self.credentials_file):
                self.logger.error(f"Credentials file not found: {self.credentials_file}")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_file, self.scopes)
            
            if HEADLESS_AUTH:
                self.logger.info("Starting headless OAuth flow")
                
                # Set redirect URI for headless mode
                flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
                
                # Get the auth URL and display instructions
                auth_url, _ = flow.authorization_url(prompt='consent')
                
                print("\n" + "=" * 60)
                print("HEADLESS AUTHENTICATION MODE")
                print("=" * 60)
                print("1. Copy this URL and paste it into your browser:")
                print(f"\n   {auth_url}\n")
                print("2. Complete the authentication process")
                print("3. You'll see an authorization code displayed on the page")
                print("4. Copy the authorization code and paste it back here")
                print("=" * 60)
                
                # Wait for user to paste the authorization code
                auth_code = input("\nPaste the authorization code here: ").strip()
                
                if not auth_code:
                    self.logger.error("No authorization code provided")
                    return None
                
                # Exchange the authorization code for credentials
                try:
                    flow.fetch_token(code=auth_code)
                    creds = flow.credentials
                    
                    self.logger.info("Headless OAuth flow completed successfully")
                    return creds
                    
                except Exception as e:
                    self.logger.error(f"Error processing authorization code: {str(e)}")
                    return None
            
            else:
                self.logger.info("Starting OAuth flow - browser window will open for authentication")
                
                # Run local server for OAuth callback
                creds = flow.run_local_server(port=0, open_browser=True)
                
                self.logger.info("OAuth flow completed successfully")
                return creds
            
        except Exception as e:
            self.logger.error(f"Error in OAuth flow: {str(e)}")
            return None
    
    def _build_service(self):
        """Build YouTube API service"""
        try:
            if not self.credentials:
                self.logger.error("No credentials available for building service")
                return None
            
            # Build service
            service = build('youtube', 'v3', credentials=self.credentials)
            return service
            
        except Exception as e:
            self.logger.error(f"Error building YouTube service: {str(e)}")
            return None
    
    def upload(self, video_path: str, metadata: Dict) -> Optional[str]:
        """Upload video to platform and return URL"""
        return self.upload_short(video_path, metadata)
    
    def upload_short(self, video_path: str, metadata: Dict) -> Optional[str]:
        """Upload video as YouTube Short"""
        try:
            # Validate inputs
            if not self.validate_video_file(video_path):
                return None
            if not self.validate_metadata(metadata):
                return None
            
            self.log_upload_attempt(video_path, metadata)
            
            if not self.youtube_service:
                self.log_upload_failure("YouTube service not available", metadata)
                return None
            
            # Prepare video metadata
            video_metadata = self._prepare_metadata(metadata)
            
            # Create media upload
            media = MediaFileUpload(
                video_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/mp4'
            )
            
            # Upload request
            request = self.youtube_service.videos().insert(
                part='snippet,status',
                body=video_metadata,
                media_body=media
            )
            
            # Execute upload
            response = self._execute_upload(request)
            
            if response:
                video_id = response['id']
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                self.log_upload_success(video_url, metadata)
                return video_url
            else:
                self.log_upload_failure("No response from upload", metadata)
                return None
                
        except Exception as e:
            self.handle_upload_error(e, "upload_short")
            return None
    
    def _prepare_metadata(self, metadata: Dict) -> Dict:
        """Prepare video metadata for YouTube"""
        try:
            title = metadata.get('title', 'Amazing Video!')
            description = self._create_description(metadata)
            tags = self._generate_tags(metadata)
            
            # YouTube Shorts requirements
            video_metadata = {
                'snippet': {
                    'title': title[:100],  # YouTube title limit
                    'description': description,
                    'tags': tags,
                    'categoryId': '24',  # Entertainment category
                    'defaultLanguage': 'en',
                    'defaultAudioLanguage': 'en'
                },
                'status': {
                    'privacyStatus': 'public',
                    'selfDeclaredMadeForKids': False,
                    'madeForKids': False
                }
            }
            
            return video_metadata
            
        except Exception as e:
            self.logger.error(f"Error preparing metadata: {str(e)}")
            return self._get_default_metadata()
    
    def _create_description(self, metadata: Dict) -> str:
        """Create video description with credits"""
        try:
            original_title = metadata.get('original_title', '')
            reddit_url = metadata.get('reddit_url', '')
            subreddit = metadata.get('subreddit', '')
            
            description = f"""
{metadata.get('title', 'Amazing content!')}

🔥 Don't forget to subscribe for daily amazing content!
👍 Like if this blew your mind!
🔔 Turn on notifications so you never miss a video!

📱 Follow us for more:
• YouTube Shorts
• Instagram Reels  
• TikTok

#Shorts #Amazing #Viral #MindBlowing #Incredible

---
Credits:
Original content from r/{subreddit}
{reddit_url}

🤖 Generated with YTBot - Automated content creation
            """.strip()
            
            return description[:5000]  # YouTube description limit
            
        except Exception as e:
            self.logger.error(f"Error creating description: {str(e)}")
            return "Amazing content! Subscribe for more!"
    
    def _generate_hashtags(self, metadata: Dict) -> list:
        """Generate platform-specific hashtags"""
        return self._generate_tags(metadata)
    
    def _generate_tags(self, metadata: Dict) -> list:
        """Generate relevant tags for the video"""
        try:
            base_tags = [
                'shorts', 'viral', 'amazing', 'incredible', 'mindblowing',
                'trending', 'youtube shorts', 'short video', 'viral video'
            ]
            
            # Add tags based on content
            title = metadata.get('title', '').lower()
            subreddit = metadata.get('subreddit', '').lower()
            
            # Content-specific tags
            if 'smart' in title or 'genius' in title:
                base_tags.extend(['smart', 'genius', 'intelligent', 'brilliant'])
            
            if 'science' in title or subreddit == 'interestingasfuck':
                base_tags.extend(['science', 'interesting', 'educational'])
            
            if 'talent' in title or subreddit == 'toptalent':
                base_tags.extend(['talent', 'skill', 'impressive'])
            
            if 'magic' in title or subreddit == 'blackmagicfuckery':
                base_tags.extend(['magic', 'illusion', 'unbelievable'])
            
            # Remove duplicates and limit to 50 tags
            unique_tags = list(set(base_tags))[:50]
            
            return unique_tags
            
        except Exception as e:
            self.logger.error(f"Error generating tags: {str(e)}")
            return ['shorts', 'viral', 'amazing']
    
    def _execute_upload(self, request) -> Optional[Dict]:
        """Execute the upload request with retry logic"""
        try:
            response = None
            retry_count = 0
            max_retries = 3
            
            while response is None and retry_count < max_retries:
                try:
                    status, response = request.next_chunk()
                    
                    if response is not None:
                        if 'id' in response:
                            self.logger.info(f"Upload completed: {response['id']}")
                            return response
                        else:
                            self.logger.error(f"Upload failed: {response}")
                            return None
                            
                except HttpError as e:
                    if e.resp.status in [500, 502, 503, 504]:
                        # Retryable error
                        retry_count += 1
                        self.logger.warning(f"Retryable error: {e}. Retry {retry_count}/{max_retries}")
                    else:
                        # Non-retryable error
                        self.logger.error(f"Non-retryable error: {e}")
                        return None
                        
                except Exception as e:
                    retry_count += 1
                    self.logger.warning(f"Upload error: {e}. Retry {retry_count}/{max_retries}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error executing upload: {str(e)}")
            return None
    
    def _get_default_metadata(self) -> Dict:
        """Get default metadata if preparation fails"""
        return {
            'snippet': {
                'title': 'Amazing Video!',
                'description': 'Check out this amazing content! Subscribe for more!',
                'tags': ['shorts', 'viral', 'amazing'],
                'categoryId': '24'
            },
            'status': {
                'privacyStatus': 'public',
                'selfDeclaredMadeForKids': False
            }
        }
    
    def update_video_thumbnail(self, video_id: str, thumbnail_path: str) -> bool:
        """Update video thumbnail"""
        try:
            if not self.youtube_service or not os.path.exists(thumbnail_path):
                return False
            
            request = self.youtube_service.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            )
            
            response = request.execute()
            
            if response:
                self.logger.info(f"Thumbnail updated for video: {video_id}")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating thumbnail: {str(e)}")
            return False
    
    def get_video_stats(self, video_id: str) -> Optional[Dict]:
        """Get video statistics"""
        try:
            if not self.youtube_service:
                return None
            
            request = self.youtube_service.videos().list(
                part='statistics,snippet',
                id=video_id
            )
            
            response = request.execute()
            
            if response['items']:
                item = response['items'][0]
                return {
                    'views': item['statistics'].get('viewCount', 0),
                    'likes': item['statistics'].get('likeCount', 0),
                    'comments': item['statistics'].get('commentCount', 0),
                    'title': item['snippet'].get('title', ''),
                    'published_at': item['snippet'].get('publishedAt', '')
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting video stats: {str(e)}")
            return None
    
    def delete_video(self, video_id: str) -> bool:
        """Delete video (if needed for cleanup)"""
        try:
            if not self.youtube_service:
                return False
            
            request = self.youtube_service.videos().delete(id=video_id)
            request.execute()
            
            self.logger.info(f"Video deleted: {video_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting video: {str(e)}")
            return False
    
    def check_upload_quota(self) -> Dict:
        """Check upload quota status"""
        try:
            # This is a simplified quota check
            # In production, you'd want to track quota usage
            return {
                'daily_uploads_remaining': 100,  # YouTube allows 100 uploads per day
                'quota_exceeded': False
            }
            
        except Exception as e:
            self.logger.error(f"Error checking quota: {str(e)}")
            return {'daily_uploads_remaining': 0, 'quota_exceeded': True}