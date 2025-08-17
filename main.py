#!/usr/bin/env python3
"""
YouTube Shorts Bot - Autonomous Content Creation and Upload
Discovers content from Reddit, processes with AI, and uploads to multiple platforms
"""

import asyncio
import logging
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Optional
import argparse
from datetime import datetime
import json

# Import all modules
from config.settings import *
from reddit.discovery import RedditContentDiscovery
from reddit.downloader import VideoDownloader
from ai.gemini_client import GeminiClient
from ai.analysis import VideoAnalyzer
from processing.video_editor import VideoEditor
from processing.tts_generator import TTSGenerator
from processing.subtitle_overlay import SubtitleOverlay
from upload.youtube import YouTubeUploader
from upload.instagram import InstagramUploader
from upload.tiktok import TikTokUploader
from utils.database import ContentTracker
from utils.error_handling import (
    ErrorHandler, ProcessingError, NetworkError, 
    error_handler, ErrorCategory, ErrorSeverity
)

class YouTubeShortsBot:
    def __init__(self):
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        self.error_handler = ErrorHandler(__name__)
        
        # Initialize components
        self.reddit_discovery = RedditContentDiscovery()
        self.video_downloader = VideoDownloader()
        self.gemini_client = GeminiClient()
        self.video_analyzer = VideoAnalyzer()
        self.video_editor = VideoEditor()
        self.tts_generator = TTSGenerator()
        self.subtitle_overlay = SubtitleOverlay()
        
        # Upload clients
        self.youtube_uploader = YouTubeUploader()
        self.instagram_uploader = InstagramUploader()
        self.tiktok_uploader = TikTokUploader()
        
        # Database
        self.content_tracker = ContentTracker()
        
        self.logger.info("YouTube Shorts Bot initialized successfully")
    
    def setup_logging(self):
        """Setup comprehensive logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('ytbot.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    async def run_full_pipeline(self, limit: int = 5) -> Dict:
        """Run the complete content creation pipeline"""
        try:
            self.logger.info(f"Starting full pipeline - processing {limit} posts")
            
            results = {
                'processed': 0,
                'uploaded': 0,
                'failed': 0,
                'videos': []
            }
            
            # Step 1: Discover trending content
            self.logger.info("Step 1: Discovering trending content from Reddit")
            trending_posts = self.reddit_discovery.discover_trending_content(limit=limit * 2)
            
            if not trending_posts:
                self.logger.warning("No trending posts found")
                return results
            
            self.logger.info(f"Found {len(trending_posts)} potential posts")
            
            # Step 2: Process each post
            processed_count = 0
            for post in trending_posts:
                if processed_count >= limit:
                    break
                
                try:
                    # Check if already processed
                    if self.content_tracker.is_processed(post['id']):
                        self.logger.info(f"Post {post['id']} already processed, skipping")
                        continue
                    
                    # Process single post
                    result = await self.process_single_post(post)
                    
                    if result['success']:
                        results['processed'] += 1
                        results['uploaded'] += len(result['uploads'])
                        results['videos'].append(result)
                        processed_count += 1
                        
                        # Save to database
                        self.content_tracker.save_processed_content(post['id'], result)
                        
                        self.logger.info(f"Successfully processed post: {post['title'][:50]}...")
                    else:
                        results['failed'] += 1
                        self.logger.error(f"Failed to process post: {post['title'][:50]}...")
                
                except Exception as e:
                    results['failed'] += 1
                    ytbot_error = self.error_handler.handle_error(e, {
                        'post_id': post['id'],
                        'post_title': post.get('title', '')[:50]
                    })
                    self.logger.error(f"Error processing post {post['id']}: {ytbot_error.message}")
            
            self.logger.info(f"Pipeline completed: {results['processed']} processed, {results['uploaded']} uploaded, {results['failed']} failed")
            return results
            
        except Exception as e:
            ytbot_error = self.error_handler.handle_error(e, {
                'function': 'run_full_pipeline',
                'limit': limit
            })
            self.logger.error(f"Fatal error in pipeline: {ytbot_error.message}")
            return results
    
    async def process_single_post(self, post: Dict) -> Dict:
        """Process a single Reddit post through the complete pipeline"""
        try:
            result = self._initialize_result(post)
            start_time = datetime.now()
            
            self.logger.info(f"Processing post: {post['title'][:50]}...")
            
            # Step 1: Download and validate video
            video_info = await self._download_and_validate(post, result)
            if not video_info:
                return result
            
            # Step 2: Analyze with AI
            analysis_data = await self._analyze_with_ai(post, video_info, result)
            if not analysis_data:
                return result
            
            # Step 3: Process video content
            processed_paths = await self._process_video_content(analysis_data, post, result)
            if not processed_paths:
                return result
            
            # Step 4: Upload to platforms
            await self._upload_to_platforms(processed_paths, analysis_data, post, result)
            
            # Step 5: Cleanup and finalize
            self._cleanup_temp_files(processed_paths.get('temp_files', []))
            result['success'] = len(result['uploads']) > 0
            result['processing_time'] = (datetime.now() - start_time).total_seconds()
            
            return result
            
        except Exception as e:
            ytbot_error = self.error_handler.handle_error(e, {
                'post_id': post.get('id', 'unknown'),
                'function': 'process_single_post'
            })
            return {'success': False, 'post_id': post.get('id', 'unknown'), 'errors': [ytbot_error.message]}
    
    def _initialize_result(self, post: Dict) -> Dict:
        """Initialize processing result structure"""
        return {
            'success': False,
            'post_id': post['id'],
            'title': post['title'],
            'uploads': {},
            'errors': [],
            'processing_time': 0
        }
    
    async def _download_and_validate(self, post: Dict, result: Dict) -> Optional[Dict]:
        """Download video and validate it's processable"""
        try:
            self.logger.info("Downloading video...")
            video_info = self.video_downloader.download_video(post['video_url'], post['id'])
            
            if not video_info:
                result['errors'].append("Failed to download video")
                return None
            
            return video_info
            
        except Exception as e:
            ytbot_error = self.error_handler.handle_error(e, {
                'post_id': post.get('id'),
                'video_url': post.get('video_url')
            })
            result['errors'].append(f"Download error: {ytbot_error.message}")
            return None
    
    async def _analyze_with_ai(self, post: Dict, video_info: Dict, result: Dict) -> Optional[Dict]:
        """Perform AI analysis on video content"""
        try:
            # Step 1: Gemini Analysis
            self.logger.info("Analyzing video with Gemini...")
            gemini_analysis = self.gemini_client.analyze_video(
                video_info['file_path'], 
                post['title'], 
                post.get('description', '')
            )
            
            if not gemini_analysis:
                result['errors'].append("Failed to analyze video")
                return None
            
            # Step 2: Create complete analysis
            self.logger.info("Creating processing plan...")
            complete_analysis = self.video_analyzer.analyze_and_plan_cuts(video_info, gemini_analysis)
            
            if not complete_analysis:
                result['errors'].append("Failed to create processing plan")
                return None
            
            return {
                'gemini_analysis': gemini_analysis,
                'complete_analysis': complete_analysis,
                'video_info': video_info
            }
            
        except Exception as e:
            ytbot_error = self.error_handler.handle_error(e, {
                'post_id': post.get('id'),
                'stage': 'ai_analysis'
            })
            result['errors'].append(f"AI analysis error: {ytbot_error.message}")
            return None
    
    async def _process_video_content(self, analysis_data: Dict, post: Dict, result: Dict) -> Optional[Dict]:
        """Process video content including TTS, editing, and subtitles"""
        try:
            gemini_analysis = analysis_data['gemini_analysis']
            complete_analysis = analysis_data['complete_analysis']
            
            # Step 1: Generate TTS
            self.logger.info("Generating TTS audio...")
            enhanced_tts_script = self.tts_generator.create_engagement_tts(gemini_analysis, post['id'])
            tts_audio_path = await self.tts_generator.generate_tts_audio(enhanced_tts_script, post['id'])
            
            # Step 2: Process video
            self.logger.info("Processing video...")
            processed_video_path = self.video_editor.process_video(complete_analysis)
            
            if not processed_video_path:
                result['errors'].append("Failed to process video")
                return None
            
            # Step 3: Add subtitles
            self.logger.info("Adding subtitles...")
            final_video_path = self.subtitle_overlay.add_subtitles_to_video(
                processed_video_path, 
                gemini_analysis, 
                tts_audio_path
            )
            
            if not final_video_path:
                final_video_path = processed_video_path  # Use video without subtitles
            
            # Step 4: Create thumbnails
            thumbnail_path = self.video_editor.create_thumbnail(final_video_path)
            
            return {
                'final_video_path': final_video_path,
                'thumbnail_path': thumbnail_path,
                'temp_files': [
                    analysis_data['video_info']['file_path'],
                    processed_video_path,
                    final_video_path if final_video_path != processed_video_path else None,
                    tts_audio_path,
                    thumbnail_path
                ]
            }
            
        except Exception as e:
            ytbot_error = self.error_handler.handle_error(e, {
                'post_id': post.get('id'),
                'stage': 'video_processing'
            })
            result['errors'].append(f"Video processing error: {ytbot_error.message}")
            return None
    
    async def _upload_to_platforms(self, processed_paths: Dict, analysis_data: Dict, post: Dict, result: Dict):
        """Upload video to all configured platforms"""
        try:
            final_video_path = processed_paths['final_video_path']
            upload_metadata = self._prepare_upload_metadata(post, analysis_data['gemini_analysis'])
            
            # Upload to YouTube Shorts
            self.logger.info("Uploading to YouTube Shorts...")
            youtube_url = self.youtube_uploader.upload(final_video_path, upload_metadata)
            if youtube_url:
                result['uploads']['youtube'] = youtube_url
            
            # Upload to Instagram Reels
            self.logger.info("Uploading to Instagram Reels...")
            instagram_metadata = self.instagram_uploader.optimize_for_reels(upload_metadata)
            instagram_url = self.instagram_uploader.upload(final_video_path, instagram_metadata)
            if instagram_url:
                result['uploads']['instagram'] = instagram_url
            
            # Upload to TikTok
            self.logger.info("Uploading to TikTok...")
            tiktok_metadata = self.tiktok_uploader.optimize_for_tiktok(upload_metadata)
            tiktok_url = self.tiktok_uploader.upload(final_video_path, tiktok_metadata)
            if tiktok_url:
                result['uploads']['tiktok'] = tiktok_url
                
        except Exception as e:
            ytbot_error = self.error_handler.handle_error(e, {
                'post_id': post.get('id'),
                'stage': 'platform_uploads'
            })
            result['errors'].append(f"Upload error: {ytbot_error.message}")
    
    def _prepare_upload_metadata(self, post: Dict, analysis: Dict) -> Dict:
        """Prepare metadata for uploads"""
        return {
            'title': analysis.get('engagement_title', post['title']),
            'original_title': post['title'],
            'description': post.get('description', ''),
            'subreddit': post['subreddit'],
            'reddit_url': post['permalink'],
            'tags': analysis.get('tags', []),
            'video_path': '',  # Will be set during upload
            'thumbnail_path': ''  # Will be set if available
        }
    
    def _cleanup_temp_files(self, file_paths: List[Optional[str]]):
        """Clean up temporary files"""
        for file_path in file_paths:
            if file_path and Path(file_path).exists():
                try:
                    Path(file_path).unlink()
                    self.logger.debug(f"Cleaned up: {file_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup {file_path}: {str(e)}")
    
    async def run_continuous(self, interval_hours: int = 2):
        """Run bot continuously"""
        self.logger.info(f"Starting continuous mode - checking every {interval_hours} hours")
        
        while True:
            try:
                # Check if we should upload (based on schedule)
                current_hour = datetime.now().hour
                if current_hour in UPLOAD_SCHEDULE_HOURS:
                    # Check daily upload limit
                    daily_count = self.content_tracker.get_daily_upload_count()
                    if daily_count < MAX_DAILY_UPLOADS:
                        await self.run_full_pipeline(limit=1)
                    else:
                        self.logger.info("Daily upload limit reached")
                
                # Wait for next check
                await asyncio.sleep(interval_hours * 3600)
                
            except Exception as e:
                self.logger.error(f"Error in continuous mode: {str(e)}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    def run_single_url(self, url: str) -> Dict:
        """Process a single URL manually"""
        try:
            self.logger.info(f"Processing single URL: {url}")
            
            # Create a mock post object
            post = {
                'id': f"manual_{int(datetime.now().timestamp())}",
                'title': 'Manual Upload',
                'video_url': url,
                'subreddit': 'manual',
                'permalink': url,
                'score': 1000,
                'num_comments': 100
            }
            
            return asyncio.run(self.process_single_post(post))
            
        except Exception as e:
            ytbot_error = self.error_handler.handle_error(e, {
                'function': 'run_single_url',
                'url': url
            })
            return {'success': False, 'errors': [ytbot_error.message]}

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='YouTube Shorts Bot')
    parser.add_argument('--mode', choices=['single', 'batch', 'continuous'], 
                       default='batch', help='Execution mode')
    parser.add_argument('--limit', type=int, default=5, 
                       help='Number of posts to process in batch mode')
    parser.add_argument('--url', type=str, 
                       help='Single URL to process (for single mode)')
    parser.add_argument('--interval', type=int, default=2, 
                       help='Hours between checks in continuous mode')
    
    args = parser.parse_args()
    
    # Initialize bot
    bot = YouTubeShortsBot()
    
    try:
        if args.mode == 'single':
            if not args.url:
                print("Error: --url required for single mode")
                sys.exit(1)
            result = bot.run_single_url(args.url)
            print(json.dumps(result, indent=2))
            
        elif args.mode == 'batch':
            result = asyncio.run(bot.run_full_pipeline(limit=args.limit))
            print(json.dumps(result, indent=2))
            
        elif args.mode == 'continuous':
            asyncio.run(bot.run_continuous(interval_hours=args.interval))
            
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()