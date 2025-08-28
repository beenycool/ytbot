# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the Bot
```bash
# Process a batch of posts (recommended for testing)
python main.py --mode batch --limit 5

# Process a single URL manually
python main.py --mode single --url "https://reddit.com/r/interestingasfuck/..."

# Run continuously (production mode)
python main.py --mode continuous

# Use the scheduler (recommended for production)
python scheduler.py start    # Start automated scheduling
python scheduler.py once     # Run once and exit
python scheduler.py status   # Check current status
```

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Setup environment variables (copy .env.example to .env first)
# Required: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, GEMINI_API_KEY
# Optional: YOUTUBE_*, INSTAGRAM_*, TIKTOK_* (for uploads)
# Headless mode: HEADLESS_AUTH=true (for servers without GUI)
```

### Headless Authentication (Server Mode)
For environments without GUI (servers, Docker containers, etc.):

1. Set `HEADLESS_AUTH=true` in your .env file
2. When running the bot, if YouTube authentication is needed, you'll see:
   - A URL to copy and paste into your browser
   - Instructions to complete authentication manually
   - A prompt to paste back the redirect URL containing the auth code

```bash
# Example headless authentication flow:
export HEADLESS_AUTH=true
python main.py --mode batch --limit 1

# Follow the on-screen instructions:
# 1. Copy the provided URL to your browser
# 2. Complete authentication 
# 3. Copy the localhost redirect URL (even if it shows 404)
# 4. Paste it back into the terminal
```

Alternatively, you can use the export BROWSER=echo workaround:
```bash
export BROWSER=echo && python3 main.py --mode batch --limit 1
```

### Testing and Validation
```bash
# Test API connections
python -c "from utils.helpers import validate_api_keys; print(validate_api_keys())"

# Check system resources
python -c "from utils.helpers import monitor_system_resources; print(monitor_system_resources())"

# Validate database
python -c "from utils.database import ContentTracker; ContentTracker().get_processing_stats()"
```

### Database Operations
```bash
# Export data for the last 7 days
python -c "
from utils.database import ContentTracker
tracker = ContentTracker()
tracker.export_data('export.json', days=7)
"

# Get platform statistics
python -c "
from utils.database import ContentTracker
tracker = ContentTracker()
print(tracker.get_platform_stats())
"
```

## Architecture Overview

### Core Pipeline Flow
1. **Content Discovery** (`reddit/discovery.py`) - Monitors subreddits for trending posts
2. **Video Download** (`reddit/downloader.py`) - Downloads videos using yt-dlp
3. **AI Analysis** (`ai/gemini_client.py` + `ai/analysis.py`) - Gemini 2.5 Flash analyzes content
4. **Video Processing** (`processing/video_editor.py`) - Crops to 9:16, adds effects
5. **TTS Generation** (`processing/tts_generator.py`) - Creates engaging narration
6. **Subtitle Overlay** (`processing/subtitle_overlay.py`) - Adds styled subtitles
7. **Multi-Platform Upload** (`upload/`) - YouTube Shorts, Instagram Reels, TikTok

### Key Components

**Main Orchestrator** (`main.py`)
- `YouTubeShortsBot` class coordinates the entire pipeline
- Handles error recovery and resource cleanup
- Manages async operations and batch processing

**Scheduler** (`scheduler.py`)
- `BotScheduler` handles automation and monitoring
- Manages posting schedules and system health checks
- Performs daily/weekly maintenance tasks

**Database System** (`utils/database/`)
- Content tracking to prevent duplicates
- Performance analytics and statistics
- Configurable data retention policies

**Configuration** (`config/settings.py`)
- Target subreddits and content filtering criteria
- Video processing settings (resolution, duration limits)
- Upload schedules and platform-specific settings

### Module Relationships
- `main.py` imports and orchestrates all processing modules
- `scheduler.py` wraps `main.py` with automation logic
- All modules use centralized configuration from `config/settings.py`
- Database tracking spans the entire pipeline via `utils/database/`
- Error handling is centralized through `utils/error_handling.py`

### Data Flow
1. Reddit API → Content discovery → Database check for duplicates
2. Video URL → yt-dlp download → Temporary storage
3. Video file → Gemini API → Analysis metadata
4. Analysis + Video → OpenCV processing → 9:16 crop + effects
5. Analysis → Edge-TTS → Audio generation
6. Video + Audio + Analysis → FFmpeg → Final output with subtitles
7. Final video → Platform APIs → Upload confirmation → Database logging

### External Dependencies
- **Reddit API** - Content discovery (requires client credentials)
- **Gemini 2.5 Flash** - Video analysis and content generation
- **yt-dlp** - Video downloading from Reddit/external sources
- **FFmpeg** - Video processing and format conversion
- **Edge-TTS** - Text-to-speech generation
- **Platform APIs** - YouTube Data API, Instagram Basic Display, TikTok for Developers

### File Organization Patterns
- Each major module has its own directory (`reddit/`, `ai/`, `processing/`, `upload/`)
- Utility functions are centralized in `utils/`
- Configuration is environment-based via `.env` and centralized in `config/`
- Temporary files use structured paths: `temp/`, `downloads/`, `output/`

### Error Handling Strategy
- Centralized error handling with categorization and severity levels
- Graceful degradation (e.g., proceed without subtitles if TTS fails)
- Comprehensive logging to both file and console
- Automatic cleanup of resources on failure

### Content Safety
- Filters content by engagement metrics (upvotes, comments)
- Respects content age limits to avoid stale content
- Tracks processed content to prevent duplicates
- Implements rate limiting for API calls