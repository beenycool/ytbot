import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from pathlib import Path


class BaseUploader(ABC):
    """Abstract base class for all platform uploaders"""
    
    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.logger = logging.getLogger(f"{__name__}.{platform_name}")
        self.max_retries = 3
        self.retry_delay = 5.0
        
    @abstractmethod
    def upload(self, video_path: str, metadata: Dict) -> Optional[str]:
        """Upload video to platform and return URL"""
        pass
    
    @abstractmethod
    def _prepare_metadata(self, metadata: Dict) -> Dict:
        """Prepare platform-specific metadata"""
        pass
    
    @abstractmethod
    def _generate_hashtags(self, metadata: Dict) -> List[str]:
        """Generate platform-specific hashtags"""
        pass
    
    def validate_video_file(self, video_path: str) -> bool:
        """Validate video file exists and is readable"""
        try:
            if not video_path:
                self.logger.error("Video path is empty")
                return False
                
            video_file = Path(video_path)
            if not video_file.exists():
                self.logger.error(f"Video file not found: {video_path}")
                return False
                
            if not video_file.is_file():
                self.logger.error(f"Path is not a file: {video_path}")
                return False
                
            if video_file.stat().st_size == 0:
                self.logger.error(f"Video file is empty: {video_path}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating video file: {str(e)}")
            return False
    
    def validate_metadata(self, metadata: Dict) -> bool:
        """Validate required metadata fields"""
        try:
            required_fields = ['title']
            optional_fields = ['description', 'tags', 'subreddit', 'reddit_url']
            
            # Check required fields
            for field in required_fields:
                if field not in metadata or not metadata[field]:
                    self.logger.error(f"Missing required metadata field: {field}")
                    return False
            
            # Validate title length (most platforms have limits)
            title = metadata.get('title', '')
            if len(title) > 500:  # Conservative limit
                self.logger.warning(f"Title may be too long ({len(title)} chars): {title[:50]}...")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating metadata: {str(e)}")
            return False
    
    def handle_upload_error(self, error: Exception, context: str = "") -> None:
        """Standardized error handling"""
        error_msg = f"Upload error in {self.platform_name}"
        if context:
            error_msg += f" ({context})"
        error_msg += f": {str(error)}"
        
        self.logger.error(error_msg)
        
        # Log additional context if available
        if hasattr(error, 'response') and hasattr(error.response, 'text'):
            self.logger.error(f"Response details: {error.response.text}")
    
    def retry_on_failure(self, func, *args, **kwargs):
        """Retry logic for API calls"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
                
            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed: {str(e)}"
                )
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    self.handle_upload_error(e, f"Final attempt ({attempt + 1})")
        
        return None
    
    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes"""
        try:
            if file_path and Path(file_path).exists():
                return Path(file_path).stat().st_size
            return 0
        except Exception as e:
            self.logger.error(f"Error getting file size: {str(e)}")
            return 0
    
    def truncate_text(self, text: str, max_length: int, suffix: str = "...") -> str:
        """Truncate text to specified length"""
        if not text:
            return ""
            
        if len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
    
    def sanitize_title(self, title: str, max_length: int = 100) -> str:
        """Sanitize and truncate title for platform"""
        if not title:
            return "Amazing Content!"
        
        # Remove problematic characters
        sanitized = title.replace('\n', ' ').replace('\r', ' ')
        sanitized = ' '.join(sanitized.split())  # Clean up whitespace
        
        return self.truncate_text(sanitized, max_length)
    
    def create_description_with_credits(self, metadata: Dict, max_length: int = 2000) -> str:
        """Create description with proper credits"""
        try:
            title = metadata.get('title', 'Amazing content!')
            reddit_url = metadata.get('reddit_url', '')
            subreddit = metadata.get('subreddit', '')
            
            # Platform-specific description template
            description_parts = [
                title,
                "",
                "🔥 Subscribe for more amazing content!",
                "👍 Like if this amazed you!",
                "🔔 Turn on notifications!",
                "",
                self._get_platform_specific_cta(),
                "",
                self._get_platform_hashtags_string(metadata),
                "",
                "---",
                "Credits:",
                f"Original content from r/{subreddit}" if subreddit else "",
                reddit_url if reddit_url else "",
                "",
                "🤖 Generated with YTBot - Automated content creation"
            ]
            
            # Filter out empty parts
            description_parts = [part for part in description_parts if part]
            description = "\n".join(description_parts)
            
            return self.truncate_text(description, max_length)
            
        except Exception as e:
            self.logger.error(f"Error creating description: {str(e)}")
            return f"{metadata.get('title', 'Amazing content!')} - Subscribe for more!"
    
    def _get_platform_specific_cta(self) -> str:
        """Get platform-specific call-to-action"""
        cta_map = {
            'youtube': '📱 Check out our other platforms for more content!',
            'instagram': '📱 Follow us on all platforms for daily content!',
            'tiktok': '📱 Follow for daily viral content!'
        }
        return cta_map.get(self.platform_name.lower(), '📱 Follow for more content!')
    
    def _get_platform_hashtags_string(self, metadata: Dict) -> str:
        """Get hashtags as formatted string"""
        hashtags = self._generate_hashtags(metadata)
        return ' '.join(hashtags[:20])  # Limit to avoid spam
    
    def log_upload_attempt(self, video_path: str, metadata: Dict) -> None:
        """Log upload attempt details"""
        file_size = self.get_file_size(video_path)
        title = metadata.get('title', 'Unknown')[:50]
        
        self.logger.info(
            f"Starting {self.platform_name} upload: "
            f"'{title}...' ({file_size / (1024*1024):.1f}MB)"
        )
    
    def log_upload_success(self, url: str, metadata: Dict) -> None:
        """Log successful upload"""
        title = metadata.get('title', 'Unknown')[:50]
        self.logger.info(
            f"{self.platform_name} upload successful: '{title}...' -> {url}"
        )
    
    def log_upload_failure(self, error: str, metadata: Dict) -> None:
        """Log failed upload"""
        title = metadata.get('title', 'Unknown')[:50]
        self.logger.error(
            f"{self.platform_name} upload failed: '{title}...' - {error}"
        )


class UploadResult:
    """Standardized upload result"""
    
    def __init__(self, success: bool, url: Optional[str] = None, 
                 error: Optional[str] = None, metadata: Optional[Dict] = None):
        self.success = success
        self.url = url
        self.error = error
        self.metadata = metadata or {}
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'success': self.success,
            'url': self.url,
            'error': self.error,
            'metadata': self.metadata,
            'timestamp': self.timestamp
        }
    
    def __str__(self) -> str:
        if self.success:
            return f"Upload successful: {self.url}"
        else:
            return f"Upload failed: {self.error}"