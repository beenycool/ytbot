import logging
import hashlib
import json
import time
import random
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import requests
from urllib.parse import urlparse

def setup_logging(log_file: str = 'ytbot.log', level: str = 'INFO') -> logging.Logger:
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def generate_content_hash(title: str, url: str, content: str = "") -> str:
    """Generate unique hash for content deduplication"""
    combined = f"{title.lower().strip()}{url}{content}"
    return hashlib.sha256(combined.encode()).hexdigest()

def clean_filename(filename: str, max_length: int = 100) -> str:
    """Clean filename for safe file system usage"""
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    if len(filename) > max_length:
        filename = filename[:max_length-3] + '...'
    
    return filename.strip()

def is_valid_video_url(url: str) -> bool:
    """Check if URL is a valid video URL"""
    video_domains = [
        'youtube.com', 'youtu.be', 'vimeo.com', 'streamable.com',
        'v.redd.it', 'gfycat.com', 'imgur.com', 'twitter.com',
        'tiktok.com', 'instagram.com'
    ]
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        return any(vid_domain in domain for vid_domain in video_domains)
    except:
        return False

def format_duration(seconds: float) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}TB"

def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for retrying functions on failure"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        raise e
                    
                    logging.warning(f"Attempt {retries} failed: {str(e)}. Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
        return wrapper
    return decorator

def rate_limit(calls_per_minute: int = 60):
    """Decorator for rate limiting function calls"""
    min_interval = 60.0 / calls_per_minute
    last_called = [0.0]
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            
            ret = func(*args, **kwargs)
            last_called[0] = time.time()
            return ret
        return wrapper
    return decorator

def sanitize_text_for_tts(text: str) -> str:
    """Sanitize text for TTS processing"""
    # Remove special characters that might cause TTS issues
    replacements = {
        '&': 'and',
        '@': 'at',
        '#': 'hashtag',
        '$': 'dollars',
        '%': 'percent',
        '+': 'plus',
        '=': 'equals',
        '<': 'less than',
        '>': 'greater than',
        '|': 'pipe',
        '\\': 'backslash',
        '/': 'slash',
        '*': 'star',
        '~': 'tilde',
        '`': 'backtick'
    }
    
    for char, replacement in replacements.items():
        text = text.replace(char, f' {replacement} ')
    
    # Clean up extra spaces
    text = ' '.join(text.split())
    
    return text

def extract_keywords_from_title(title: str) -> List[str]:
    """Extract keywords from title for tagging"""
    # Common stop words to filter out
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'this', 'that', 'these', 'those', 'is', 'are',
        'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do',
        'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
        'can', 'must', 'shall', 'it', 'he', 'she', 'we', 'they', 'i', 'you'
    }
    
    # Extract words and filter
    words = title.lower().split()
    keywords = [word.strip('.,!?;:"()[]{}') for word in words 
                if len(word) > 2 and word.lower() not in stop_words]
    
    return keywords[:10]  # Limit to 10 keywords

def calculate_engagement_score(upvotes: int, comments: int, upvote_ratio: float) -> float:
    """Calculate engagement score for Reddit posts"""
    # Weighted formula for engagement
    score = (
        upvotes * 0.4 +
        comments * 0.3 +
        (upvote_ratio * 100) * 0.3
    )
    
    return round(score, 2)

def get_optimal_posting_time() -> datetime:
    """Get optimal posting time based on current time and schedule"""
    from config.settings import UPLOAD_SCHEDULE_HOURS
    
    now = datetime.now()
    current_hour = now.hour
    
    # Find next optimal hour
    next_hours = [h for h in UPLOAD_SCHEDULE_HOURS if h > current_hour]
    
    if next_hours:
        next_hour = min(next_hours)
        next_time = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
    else:
        # Next day
        next_hour = min(UPLOAD_SCHEDULE_HOURS)
        next_time = (now + timedelta(days=1)).replace(
            hour=next_hour, minute=0, second=0, microsecond=0
        )
    
    return next_time

def validate_api_keys() -> Dict[str, bool]:
    """Validate that all required API keys are configured"""
    from config.settings import (
        REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
        GEMINI_API_KEY, YOUTUBE_CLIENT_ID,
        INSTAGRAM_ACCESS_TOKEN, TIKTOK_CLIENT_KEY
    )
    
    validations = {
        'reddit': bool(REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET),
        'gemini': bool(GEMINI_API_KEY),
        'youtube': bool(YOUTUBE_CLIENT_ID),
        'instagram': bool(INSTAGRAM_ACCESS_TOKEN),
        'tiktok': bool(TIKTOK_CLIENT_KEY)
    }
    
    return validations

def create_backup(data: Dict, backup_dir: str = 'backups') -> str:
    """Create backup of important data"""
    backup_path = Path(backup_dir)
    backup_path.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = backup_path / f"ytbot_backup_{timestamp}.json"
    
    with open(backup_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    return str(backup_file)

def monitor_system_resources() -> Dict[str, Any]:
    """Monitor system resources (CPU, Memory, Disk)"""
    try:
        import psutil
        
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'available_memory_gb': psutil.virtual_memory().available / (1024**3),
            'disk_free_gb': psutil.disk_usage('/').free / (1024**3)
        }
    except ImportError:
        return {'status': 'psutil not available'}

def check_internet_connection(timeout: int = 5) -> bool:
    """Check if internet connection is available"""
    try:
        response = requests.get('https://www.google.com', timeout=timeout)
        return response.status_code == 200
    except:
        return False

def generate_random_delay(min_seconds: int = 30, max_seconds: int = 300) -> float:
    """Generate random delay to avoid being detected as a bot"""
    return random.uniform(min_seconds, max_seconds)

def safe_json_loads(json_string: str, default: Any = None) -> Any:
    """Safely load JSON with fallback"""
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return default

def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def extract_video_metadata(file_path: str) -> Dict[str, Any]:
    """Extract metadata from video file"""
    try:
        import cv2
        
        cap = cv2.VideoCapture(file_path)
        
        if not cap.isOpened():
            return {}
        
        metadata = {
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'duration': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / cap.get(cv2.CAP_PROP_FPS),
            'codec': int(cap.get(cv2.CAP_PROP_FOURCC)),
            'file_size': Path(file_path).stat().st_size
        }
        
        cap.release()
        return metadata
        
    except Exception as e:
        logging.error(f"Error extracting video metadata: {str(e)}")
        return {}

def cleanup_temp_directory(temp_dir: str = 'temp', max_age_hours: int = 24):
    """Clean up temporary directory"""
    try:
        temp_path = Path(temp_dir)
        if not temp_path.exists():
            return
        
        current_time = time.time()
        
        for file_path in temp_path.rglob('*'):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > (max_age_hours * 3600):
                    try:
                        file_path.unlink()
                        logging.info(f"Cleaned up: {file_path}")
                    except Exception as e:
                        logging.warning(f"Could not delete {file_path}: {str(e)}")
                        
    except Exception as e:
        logging.error(f"Error during cleanup: {str(e)}")

def format_performance_report(stats: Dict) -> str:
    """Format performance statistics into readable report"""
    report = []
    report.append("=== YTBot Performance Report ===")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    if 'processing' in stats:
        proc = stats['processing']
        report.append("Processing Statistics:")
        report.append(f"  Total Processed: {proc.get('total_processed', 0)}")
        report.append(f"  Success Rate: {proc.get('success_rate', 0):.1f}%")
        report.append(f"  Avg Processing Time: {format_duration(proc.get('avg_processing_time', 0))}")
        report.append("")
    
    if 'platforms' in stats:
        report.append("Platform Statistics:")
        for platform, data in stats['platforms'].items():
            report.append(f"  {platform.capitalize()}:")
            report.append(f"    Uploads: {data.get('total_uploads', 0)}")
            report.append(f"    Success Rate: {data.get('success_rate', 0):.1f}%")
        report.append("")
    
    return "\n".join(report)