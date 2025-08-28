import yt_dlp
import os
import logging
from typing import Optional, Dict
import hashlib
from pathlib import Path
from config.settings import *

class VideoDownloader:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.download_dir = Path(DOWNLOAD_DIR)
        self.download_dir.mkdir(exist_ok=True)
        
        self.ydl_opts = {
            'format': VIDEO_QUALITY,
            'outtmpl': str(self.download_dir / '%(title)s.%(ext)s'),
            'noplaylist': True,
            'extractaudio': False,
            'audioformat': 'mp3',
            'embedsubs': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'ignoreerrors': True,
        }
    
    def download_video(self, url: str, post_id: str) -> Optional[Dict]:
        """Download video from URL and return file info"""
        try:
            # Check if this is a Reddit DASH URL that needs special handling
            if 'v.redd.it' in url and 'DASH_' in url:
                return self._download_reddit_dash_video(url, post_id)
            
            # Create unique filename based on post ID
            file_hash = hashlib.md5(f"{post_id}_{url}".encode()).hexdigest()[:8]
            output_template = str(self.download_dir / f"{post_id}_{file_hash}.%(ext)s")
            
            opts = self.ydl_opts.copy()
            opts['outtmpl'] = output_template
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Extract info first
                info = ydl.extract_info(url, download=False)
                
                # Check if extraction failed
                if info is None:
                    self.logger.warning(f"Could not extract video info from URL: {url}")
                    return None
                
                # Validate video before downloading
                if not self._is_suitable_video(info):
                    self.logger.warning(f"Video not suitable for processing: {url}")
                    return None
                
                # Download the video
                ydl.download([url])
                
                # Find downloaded file
                downloaded_file = self._find_downloaded_file(post_id, file_hash)
                if not downloaded_file:
                    self.logger.error(f"Could not find downloaded file for {post_id}")
                    return None
                
                # Extract metadata
                video_info = {
                    'file_path': str(downloaded_file),
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'width': info.get('width', 0),
                    'height': info.get('height', 0),
                    'fps': info.get('fps', 30),
                    'filesize': downloaded_file.stat().st_size,
                    'format': info.get('ext', 'mp4'),
                    'original_url': url,
                    'post_id': post_id,
                    'description': info.get('description', ''),
                    'uploader': info.get('uploader', 'Unknown')
                }
                
                self.logger.info(f"Successfully downloaded video: {downloaded_file.name}")
                return video_info
                
        except Exception as e:
            self.logger.error(f"Error downloading video from {url}: {str(e)}")
            return None
    
    def _download_reddit_dash_video(self, url: str, post_id: str) -> Optional[Dict]:
        """Download Reddit DASH video using direct HTTP request"""
        try:
            import requests
            import cv2
            from urllib.parse import urlparse
            
            # Create unique filename
            file_hash = hashlib.md5(f"{post_id}_{url}".encode()).hexdigest()[:8]
            output_file = self.download_dir / f"{post_id}_{file_hash}.mp4"
            
            # Download the video file
            self.logger.info(f"Downloading Reddit video: {url}")
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Save the video
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Get video metadata using cv2
            cap = cv2.VideoCapture(str(output_file))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            cap.release()
            
            # Validate video - allow slightly longer videos for testing
            max_duration = MAX_VIDEO_DURATION if MAX_VIDEO_DURATION > 70 else 90
            if duration < MIN_VIDEO_DURATION or duration > max_duration:
                self.logger.warning(f"Video duration {duration}s not suitable (allowed: {MIN_VIDEO_DURATION}-{max_duration}s)")
                output_file.unlink()  # Delete the file
                return None
            
            if width < 480 or height < 480:
                self.logger.warning(f"Video resolution {width}x{height} too low")
                output_file.unlink()  # Delete the file
                return None
            
            video_info = {
                'file_path': str(output_file),
                'title': f'Reddit Video {post_id}',
                'duration': duration,
                'width': width,
                'height': height,
                'fps': fps,
                'filesize': output_file.stat().st_size,
                'format': 'mp4',
                'original_url': url,
                'post_id': post_id,
                'description': '',
                'uploader': 'Reddit'
            }
            
            self.logger.info(f"Successfully downloaded Reddit video: {output_file.name}")
            return video_info
            
        except Exception as e:
            self.logger.error(f"Error downloading Reddit DASH video: {str(e)}")
            if 'output_file' in locals() and output_file.exists():
                output_file.unlink()  # Clean up partial download
            return None
    
    def _is_suitable_video(self, info: Dict) -> bool:
        """Check if video meets criteria for processing"""
        duration = info.get('duration', 0)
        
        # Check duration
        if duration and (duration < MIN_VIDEO_DURATION or duration > MAX_VIDEO_DURATION):
            return False
        
        # Check if it's actually a video
        if info.get('vcodec') == 'none':
            return False
            
        # Check dimensions
        width = info.get('width', 0)
        height = info.get('height', 0)
        
        if width == 0 or height == 0:
            return False
            
        # Prefer videos that can be processed
        if width < 480 or height < 480:
            return False
            
        return True
    
    def _find_downloaded_file(self, post_id: str, file_hash: str) -> Optional[Path]:
        """Find the downloaded file by post ID and hash"""
        pattern = f"{post_id}_{file_hash}.*"
        
        for file_path in self.download_dir.glob(pattern):
            if file_path.is_file():
                # Skip subtitle files
                if file_path.suffix in ['.vtt', '.srt', '.json']:
                    continue
                return file_path
                
        return None
    
    def download_reddit_video(self, reddit_video_url: str, post_id: str) -> Optional[Dict]:
        """Download Reddit-hosted video with audio"""
        try:
            # Reddit videos often have separate audio tracks
            # Try to get the audio URL
            audio_url = reddit_video_url.replace('DASH_', 'DASH_audio')
            
            # Use ffmpeg to combine video and audio if needed
            opts = self.ydl_opts.copy()
            opts['format'] = 'best[ext=mp4]'
            
            return self.download_video(reddit_video_url, post_id)
            
        except Exception as e:
            self.logger.error(f"Error downloading Reddit video: {str(e)}")
            return None
    
    def get_video_metadata(self, url: str) -> Optional[Dict]:
        """Get video metadata without downloading"""
        try:
            # For Reddit DASH URLs, we need to download and check the file
            if 'v.redd.it' in url and 'DASH_' in url:
                return self._get_reddit_dash_metadata(url)
            
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    return None
                    
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'width': info.get('width', 0),
                    'height': info.get('height', 0),
                    'fps': info.get('fps', 30),
                    'description': info.get('description', ''),
                    'uploader': info.get('uploader', 'Unknown'),
                    'thumbnail': info.get('thumbnail', ''),
                }
        except Exception as e:
            self.logger.error(f"Error extracting metadata from {url}: {str(e)}")
            return None
    
    def _get_reddit_dash_metadata(self, url: str) -> Optional[Dict]:
        """Get metadata for Reddit DASH video by downloading temporarily"""
        try:
            import requests
            import cv2
            import tempfile
            
            # Download to a temporary file
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                temp_path = temp_file.name
            
            # Get metadata using cv2
            cap = cv2.VideoCapture(temp_path)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            cap.release()
            
            # Clean up temp file
            import os
            os.unlink(temp_path)
            
            return {
                'title': 'Reddit Video',
                'duration': duration,
                'width': width,
                'height': height,
                'fps': fps,
                'description': '',
                'uploader': 'Reddit',
                'thumbnail': '',
            }
            
        except Exception as e:
            self.logger.error(f"Error getting Reddit DASH metadata: {str(e)}")
            return None
    
    def cleanup_old_downloads(self, max_age_hours: int = 24):
        """Clean up old downloaded files"""
        try:
            import time
            current_time = time.time()
            
            for file_path in self.download_dir.iterdir():
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > (max_age_hours * 3600):
                        file_path.unlink()
                        self.logger.info(f"Cleaned up old file: {file_path.name}")
                        
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
    
    def get_available_formats(self, url: str) -> list:
        """Get available formats for a video URL"""
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                
                available_formats = []
                for fmt in formats:
                    available_formats.append({
                        'format_id': fmt.get('format_id'),
                        'ext': fmt.get('ext'),
                        'width': fmt.get('width'),
                        'height': fmt.get('height'),
                        'fps': fmt.get('fps'),
                        'filesize': fmt.get('filesize'),
                        'vcodec': fmt.get('vcodec'),
                        'acodec': fmt.get('acodec')
                    })
                
                return available_formats
                
        except Exception as e:
            self.logger.error(f"Error getting formats for {url}: {str(e)}")
            return []