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
            # Create unique filename based on post ID
            file_hash = hashlib.md5(f"{post_id}_{url}".encode()).hexdigest()[:8]
            output_template = str(self.download_dir / f"{post_id}_{file_hash}.%(ext)s")
            
            opts = self.ydl_opts.copy()
            opts['outtmpl'] = output_template
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Extract info first
                info = ydl.extract_info(url, download=False)
                
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
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
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