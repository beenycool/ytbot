import praw
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
from config.settings import *

class RedditContentDiscovery:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )
        self.logger = logging.getLogger(__name__)
        
    def discover_trending_content(self, limit: int = 50) -> List[Dict]:
        """Discover trending video content from target subreddits"""
        all_posts = []
        
        for subreddit_name in TARGET_SUBREDDITS:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                # Ensure each subreddit gets at least 1 post to check
                posts_per_subreddit = max(1, limit // len(TARGET_SUBREDDITS))
                posts = self._get_hot_posts(subreddit, posts_per_subreddit)
                all_posts.extend(posts)
                self.logger.info(f"Found {len(posts)} posts from r/{subreddit_name}")
            except Exception as e:
                self.logger.error(f"Error fetching from r/{subreddit_name}: {str(e)}")
                
        # Sort by engagement score
        sorted_posts = sorted(all_posts, key=lambda x: x['engagement_score'], reverse=True)
        return sorted_posts[:limit]
    
    def _get_hot_posts(self, subreddit, limit: int) -> List[Dict]:
        """Get hot posts from a specific subreddit"""
        posts = []
        
        for submission in subreddit.hot(limit=limit * 2):  # Get more to filter
            if self._is_valid_content(submission):
                post_data = self._extract_post_data(submission)
                if post_data:
                    posts.append(post_data)
                    
        return posts
    
    def _is_valid_content(self, submission) -> bool:
        """Filter posts based on content criteria"""
        # Check age
        post_age = datetime.utcnow() - datetime.utcfromtimestamp(submission.created_utc)
        if post_age > timedelta(hours=CONTENT_AGE_HOURS):
            return False
            
        # Check engagement
        if submission.score < MIN_UPVOTES or submission.num_comments < MIN_COMMENTS:
            return False
            
        # Check if it's a video post
        if not self._has_video_content(submission):
            return False
            
        # Check if it's not removed or deleted
        if submission.removed_by_category or submission.author is None:
            return False
            
        return True
    
    def _has_video_content(self, submission) -> bool:
        """Check if post contains video content"""
        video_domains = [
            'v.redd.it', 'youtube.com', 'youtu.be', 'streamable.com',
            'gfycat.com', 'imgur.com', 'reddit.com/gallery'
        ]
        
        # Check URL
        if hasattr(submission, 'url') and submission.url:
            for domain in video_domains:
                if domain in submission.url.lower():
                    return True
                    
        # Check if it's a video post
        if hasattr(submission, 'is_video') and submission.is_video:
            return True
            
        # Check media
        if hasattr(submission, 'media') and submission.media:
            if 'reddit_video' in str(submission.media):
                return True
                
        return False
    
    def _extract_post_data(self, submission) -> Optional[Dict]:
        """Extract relevant data from Reddit submission"""
        try:
            # Calculate engagement score
            engagement_score = (
                submission.score * 0.7 + 
                submission.num_comments * 0.3 + 
                (submission.upvote_ratio * 100)
            )
            
            # Get video URL
            video_url = self._get_video_url(submission)
            if not video_url:
                return None
                
            post_data = {
                'id': submission.id,
                'title': submission.title,
                'url': submission.url,
                'video_url': video_url,
                'score': submission.score,
                'num_comments': submission.num_comments,
                'upvote_ratio': submission.upvote_ratio,
                'engagement_score': engagement_score,
                'subreddit': submission.subreddit.display_name,
                'author': str(submission.author) if submission.author else '[deleted]',
                'created_utc': submission.created_utc,
                'permalink': f"https://reddit.com{submission.permalink}",
                'nsfw': submission.over_18,
                'spoiler': submission.spoiler
            }
            
            return post_data
            
        except Exception as e:
            self.logger.error(f"Error extracting post data: {str(e)}")
            return None
    
    def _get_video_url(self, submission) -> Optional[str]:
        """Extract video URL from submission"""
        # Reddit video - try fallback URL first, then post URL if needed
        if hasattr(submission, 'is_video') and submission.is_video:
            if hasattr(submission, 'media') and submission.media:
                if 'reddit_video' in submission.media:
                    return submission.media['reddit_video']['fallback_url']
            # Fallback to post URL if media not available
            return f"https://reddit.com{submission.permalink}"
                    
        # Direct video URL
        if hasattr(submission, 'url') and submission.url:
            video_extensions = ['.mp4', '.webm', '.mov', '.avi', '.mkv']
            if any(ext in submission.url.lower() for ext in video_extensions):
                return submission.url
                
        # YouTube, streamable, etc.
        if hasattr(submission, 'url'):
            return submission.url
            
        return None
    
    def get_post_details(self, post_id: str) -> Optional[Dict]:
        """Get detailed information about a specific post"""
        try:
            submission = self.reddit.submission(id=post_id)
            return self._extract_post_data(submission)
        except Exception as e:
            self.logger.error(f"Error getting post details for {post_id}: {str(e)}")
            return None