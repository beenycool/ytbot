import os
from dotenv import load_dotenv

load_dotenv()

# Reddit API Configuration
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'YTBot/1.0')

# Gemini API Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# YouTube API Configuration
YOUTUBE_CLIENT_ID = os.getenv('YOUTUBE_CLIENT_ID')
YOUTUBE_CLIENT_SECRET = os.getenv('YOUTUBE_CLIENT_SECRET')
YOUTUBE_REFRESH_TOKEN = os.getenv('YOUTUBE_REFRESH_TOKEN')

# Instagram API Configuration
INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN')
INSTAGRAM_USER_ID = os.getenv('INSTAGRAM_USER_ID')

# TikTok API Configuration
TIKTOK_CLIENT_KEY = os.getenv('TIKTOK_CLIENT_KEY')
TIKTOK_CLIENT_SECRET = os.getenv('TIKTOK_CLIENT_SECRET')
TIKTOK_ACCESS_TOKEN = os.getenv('TIKTOK_ACCESS_TOKEN')

# Headless Authentication (for servers without GUI)
HEADLESS_AUTH = os.getenv('HEADLESS_AUTH', 'false').lower() == 'true'

# Content Discovery Settings
TARGET_SUBREDDITS = [
    'interestingasfuck',
    'nextfuckinglevel',
    'blackmagicfuckery',
    'todayilearned',
    'mildlyinteresting',
    'oddlysatisfying',
    'unexpected',
    'damnthatsinteresting',
    'beamazed',
    'toptalent'
]

# Video Processing Settings
MAX_VIDEO_DURATION = 60  # seconds
MIN_VIDEO_DURATION = 5   # seconds
OUTPUT_RESOLUTION = (1080, 1920)  # 9:16 aspect ratio
VIDEO_QUALITY = 'best[height<=1080]'

# Content Filtering
MIN_UPVOTES = 500
MIN_COMMENTS = 25
CONTENT_AGE_HOURS = 72

# TTS Settings
TTS_LANGUAGE = 'en'
TTS_VOICE = 'en-US-AriaNeural'  # Edge-TTS voice
TTS_SPEED = '+10%'

# Engagement Hooks
ENGAGEMENT_HOOKS = [
    "This person is so smart!",
    "Wait for it...",
    "You won't believe what happens next!",
    "This is insane!",
    "Watch this amazing moment!",
    "This will blow your mind!",
    "Don't skip this!",
    "The ending is crazy!"
]

# Subtitle Settings
SUBTITLE_FONT_SIZE = 60
SUBTITLE_FONT_COLOR = 'white'
SUBTITLE_OUTLINE_COLOR = 'black'
SUBTITLE_OUTLINE_WIDTH = 3

# Upload Settings
UPLOAD_SCHEDULE_HOURS = [9, 15, 21]  # Best posting times
MAX_DAILY_UPLOADS = 3

# Database
DATABASE_PATH = 'utils/content_tracker.db'

# Temporary Files
TEMP_DIR = 'temp'
DOWNLOAD_DIR = 'downloads'
OUTPUT_DIR = 'output'