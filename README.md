# YTBot - Autonomous YouTube Shorts Creator 🤖

An autonomous bot that discovers trending content from Reddit, processes it with AI, and uploads to YouTube Shorts, Instagram Reels, and TikTok.

## Features

✨ **Autonomous Content Discovery**
- Monitors trending posts from multiple subreddits
- Filters content based on engagement metrics
- Prevents duplicate content processing

🧠 **AI-Powered Processing**
- Gemini 2.5 Flash integration for video analysis
- Intelligent video cutting and cropping
- Smart subject tracking for 9:16 aspect ratio conversion

🎬 **Advanced Video Processing**
- Automatic cropping to vertical format
- Dynamic visual effects (zoom, slow-motion, speed-up)
- Professional subtitle generation
- Text-to-speech with engagement hooks

📱 **Multi-Platform Upload**
- YouTube Shorts with optimized metadata
- Instagram Reels with hashtag optimization
- TikTok with trending elements
- Platform-specific content optimization

🔄 **Full Automation**
- Scheduled posting at optimal times
- Resource monitoring and error handling
- Comprehensive analytics and reporting
- Database tracking for content management

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd ytbot

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### 2. Configuration

Edit `.env` file with your API keys:

```bash
# Reddit API
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret

# Gemini API
GEMINI_API_KEY=your_gemini_api_key

# YouTube API
YOUTUBE_CLIENT_ID=your_youtube_client_id
YOUTUBE_CLIENT_SECRET=your_youtube_client_secret
YOUTUBE_REFRESH_TOKEN=your_refresh_token

# Instagram API
INSTAGRAM_ACCESS_TOKEN=your_instagram_token
INSTAGRAM_USER_ID=your_user_id

# TikTok API
TIKTOK_CLIENT_KEY=your_tiktok_key
TIKTOK_CLIENT_SECRET=your_tiktok_secret
TIKTOK_ACCESS_TOKEN=your_tiktok_token
```

### 3. Run the Bot

```bash
# Process a batch of posts
python main.py --mode batch --limit 5

# Process a single URL
python main.py --mode single --url "https://reddit.com/r/interestingasfuck/..."

# Run continuously (scheduled)
python main.py --mode continuous

# Or use the scheduler
python scheduler.py start
```

## Usage Examples

### Basic Usage

```bash
# Process 3 trending posts
python main.py --mode batch --limit 3

# Run once and exit
python scheduler.py once

# Check status
python scheduler.py status
```

### Advanced Usage

```bash
# Run with custom settings
python main.py --mode continuous --interval 4

# Generate reports
python -c "
from utils.database import ContentTracker
tracker = ContentTracker()
tracker.export_data('my_export.json', days=7)
"
```

## Configuration

### Target Subreddits

Edit `config/settings.py` to customize target subreddits:

```python
TARGET_SUBREDDITS = [
    'interestingasfuck',
    'nextfuckinglevel',
    'blackmagicfuckery',
    'toptalent',
    # Add more...
]
```

### Upload Schedule

Customize posting times:

```python
UPLOAD_SCHEDULE_HOURS = [9, 15, 21]  # Post at 9 AM, 3 PM, 9 PM
MAX_DAILY_UPLOADS = 3
```

### Content Filtering

Adjust content filtering criteria:

```python
MIN_UPVOTES = 1000
MIN_COMMENTS = 50
CONTENT_AGE_HOURS = 24
```

## API Setup Guide

### Reddit API
1. Go to https://www.reddit.com/prefs/apps
2. Create a new application (script type)
3. Copy client ID and secret

### Gemini API
1. Visit https://makersuite.google.com/app/apikey
2. Create API key
3. Copy the key

### YouTube API
1. Go to Google Cloud Console
2. Enable YouTube Data API v3
3. Create OAuth 2.0 credentials
4. Follow OAuth flow to get refresh token

### Instagram API
1. Create Facebook Developer account
2. Set up Instagram Basic Display API
3. Get access token and user ID

### TikTok API
1. Apply for TikTok for Developers
2. Create application
3. Get client key and secret

## Project Structure

```
ytbot/
├── main.py                 # Main orchestration script
├── scheduler.py            # Automation and scheduling
├── config/
│   └── settings.py         # Configuration
├── reddit/
│   ├── discovery.py        # Content discovery
│   └── downloader.py       # Video downloading
├── ai/
│   ├── gemini_client.py    # AI integration
│   └── analysis.py         # Video analysis
├── processing/
│   ├── video_editor.py     # Video processing
│   ├── tts_generator.py    # Text-to-speech
│   └── subtitle_overlay.py # Subtitle generation
├── upload/
│   ├── youtube.py          # YouTube upload
│   ├── instagram.py        # Instagram upload
│   └── tiktok.py          # TikTok upload
└── utils/
    ├── database.py         # Data management
    └── helpers.py          # Utility functions
```

## Key Features Explained

### Intelligent Video Processing

The bot automatically:
- Crops videos to 9:16 aspect ratio for shorts
- Tracks subjects (faces, objects) for optimal framing
- Adds engagement elements (zoom, effects)
- Generates subtitles with brainrot-style formatting

### AI-Powered Analysis

Gemini 2.5 Flash analyzes videos to:
- Identify key moments for cutting
- Generate transcriptions
- Create engaging titles and descriptions
- Suggest visual effects and timing

### Multi-Platform Optimization

Content is optimized for each platform:
- **YouTube**: SEO-optimized titles, proper categories
- **Instagram**: Hashtag optimization, Reels format
- **TikTok**: Trending elements, engagement hooks

### Smart Content Discovery

The bot finds content by:
- Monitoring multiple subreddits
- Filtering by engagement metrics
- Preventing duplicate processing
- Selecting optimal posting times

## Monitoring and Analytics

### Database Tracking

All activity is tracked in SQLite database:
- Processed content history
- Upload success/failure rates
- Platform performance metrics
- Error logging and analysis

### Performance Reports

Generate comprehensive reports:

```bash
# Daily report
python scheduler.py status

# Export data
python -c "
from utils.database import ContentTracker
tracker = ContentTracker()
stats = tracker.get_platform_stats()
print(stats)
"
```

### System Monitoring

Built-in monitoring for:
- CPU and memory usage
- Disk space availability
- Internet connectivity
- API quota limits

## Troubleshooting

### Common Issues

**Video download fails:**
- Check Reddit post URL format
- Verify yt-dlp is up to date
- Ensure sufficient disk space

**Upload failures:**
- Verify API credentials
- Check quota limits
- Review platform-specific requirements

**Processing errors:**
- Monitor system resources
- Check Gemini API quota
- Verify video file formats

### Logs

Check log files for detailed error information:
- `ytbot.log` - Main application logs
- `scheduler.log` - Scheduler logs

### Debug Mode

Run with debug logging:

```bash
python main.py --mode batch --limit 1 --log-level DEBUG
```

## Best Practices

### Content Ethics
- Always credit original creators
- Respect platform community guidelines
- Add transformative elements (effects, commentary)
- Monitor content quality

### API Usage
- Respect rate limits
- Monitor quota usage
- Implement proper error handling
- Use retry mechanisms

### System Resources
- Monitor disk space for downloads
- Clean up temporary files regularly
- Use appropriate upload schedules
- Monitor processing performance

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Update documentation
5. Submit pull request

## Legal Notice

This tool is for educational and research purposes. Users are responsible for:
- Complying with platform terms of service
- Respecting copyright and fair use
- Following content creation best practices
- Monitoring automated uploads

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Support

For issues and questions:
- Check the troubleshooting section
- Review log files for errors
- Open GitHub issues for bugs
- Join community discussions

---

**Disclaimer**: This bot automates content creation from public Reddit posts. Users must ensure compliance with all applicable laws, platform terms of service, and content creation ethics. The authors are not responsible for misuse or violations.