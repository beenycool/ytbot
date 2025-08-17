#!/usr/bin/env python3
"""
Scheduler for YouTube Shorts Bot
Handles automation, scheduling, and monitoring
"""

import asyncio
import schedule
import time
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List
import argparse
import signal
import sys
from pathlib import Path

from main import YouTubeShortsBot
from utils.database import ContentTracker
from utils.helpers import (
    monitor_system_resources, check_internet_connection,
    get_optimal_posting_time, validate_api_keys, create_backup
)
from utils.error_handling import ErrorHandler, error_handler, ErrorCategory
from config.settings import *

class BotScheduler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_handler = ErrorHandler(__name__)
        self.bot = YouTubeShortsBot()
        self.content_tracker = ContentTracker()
        self.running = False
        self.stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'last_run': None,
            'next_run': None
        }
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        
    def setup_schedule(self):
        """Setup the posting schedule"""
        self.logger.info("Setting up posting schedule...")
        
        # Schedule regular content creation
        for hour in UPLOAD_SCHEDULE_HOURS:
            schedule.every().day.at(f"{hour:02d}:00").do(self._scheduled_run)
            self.logger.info(f"Scheduled daily run at {hour:02d}:00")
        
        # Schedule maintenance tasks
        schedule.every().hour.do(self._hourly_maintenance)
        schedule.every().day.at("03:00").do(self._daily_maintenance)
        schedule.every().sunday.at("02:00").do(self._weekly_maintenance)
        
        # Schedule monitoring
        schedule.every(15).minutes.do(self._system_check)
        
        self.logger.info("Schedule setup complete")
    
    def _scheduled_run(self):
        """Execute scheduled content creation run"""
        try:
            self.logger.info("Starting scheduled content creation run")
            self.stats['total_runs'] += 1
            self.stats['last_run'] = datetime.now()
            
            # Pre-run checks
            if not self._pre_run_checks():
                self.stats['failed_runs'] += 1
                return
            
            # Check daily upload limit
            daily_count = self.content_tracker.get_daily_upload_count()
            if daily_count >= MAX_DAILY_UPLOADS:
                self.logger.info(f"Daily upload limit reached ({daily_count}/{MAX_DAILY_UPLOADS})")
                return
            
            # Run the bot
            result = asyncio.run(self.bot.run_full_pipeline(limit=1))
            
            if result['processed'] > 0:
                self.stats['successful_runs'] += 1
                self.logger.info(f"Scheduled run completed successfully: {result}")
            else:
                self.stats['failed_runs'] += 1
                self.logger.warning(f"Scheduled run completed with no content processed: {result}")
                
        except Exception as e:
            self.stats['failed_runs'] += 1
            self.logger.error(f"Error in scheduled run: {str(e)}")
    
    def _pre_run_checks(self) -> bool:
        """Perform pre-run system checks"""
        try:
            # Check internet connection
            if not check_internet_connection():
                self.logger.error("No internet connection available")
                return False
            
            # Check system resources
            resources = monitor_system_resources()
            if resources.get('cpu_percent', 0) > 90:
                self.logger.warning("High CPU usage, skipping run")
                return False
            
            if resources.get('memory_percent', 0) > 90:
                self.logger.warning("High memory usage, skipping run")
                return False
            
            if resources.get('disk_usage', 0) > 95:
                self.logger.error("Disk space critically low, skipping run")
                return False
            
            # Validate API keys
            api_validations = validate_api_keys()
            if not all(api_validations.values()):
                self.logger.error(f"API key validation failed: {api_validations}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in pre-run checks: {str(e)}")
            return False
    
    def _hourly_maintenance(self):
        """Perform hourly maintenance tasks"""
        try:
            self.logger.debug("Running hourly maintenance")
            
            # Clean up temporary files
            from utils.helpers import cleanup_temp_directory
            cleanup_temp_directory()
            
            # Update next run time
            self._update_next_run_time()
            
        except Exception as e:
            self.logger.error(f"Error in hourly maintenance: {str(e)}")
    
    def _daily_maintenance(self):
        """Perform daily maintenance tasks"""
        try:
            self.logger.info("Running daily maintenance")
            
            # Clean up old downloads
            self.bot.video_downloader.cleanup_old_downloads()
            
            # Clean up TTS files
            self.bot.tts_generator.cleanup_temp_files()
            
            # Clean up subtitle files
            self.bot.subtitle_overlay.cleanup_temp_files()
            
            # Generate daily report
            self._generate_daily_report()
            
        except Exception as e:
            self.logger.error(f"Error in daily maintenance: {str(e)}")
    
    def _weekly_maintenance(self):
        """Perform weekly maintenance tasks"""
        try:
            self.logger.info("Running weekly maintenance")
            
            # Clean up old database records
            self.content_tracker.cleanup_old_records(days=30)
            
            # Create backup
            stats = self.get_comprehensive_stats()
            backup_file = create_backup(stats)
            self.logger.info(f"Weekly backup created: {backup_file}")
            
            # Export data
            export_file = f"exports/ytbot_data_{datetime.now().strftime('%Y%m%d')}.json"
            Path("exports").mkdir(exist_ok=True)
            self.content_tracker.export_data(export_file)
            
        except Exception as e:
            self.logger.error(f"Error in weekly maintenance: {str(e)}")
    
    def _system_check(self):
        """Perform regular system health checks"""
        try:
            resources = monitor_system_resources()
            
            # Log system status
            self.logger.debug(f"System resources: CPU {resources.get('cpu_percent', 0):.1f}%, "
                            f"Memory {resources.get('memory_percent', 0):.1f}%, "
                            f"Disk {resources.get('disk_usage', 0):.1f}%")
            
            # Alert on high resource usage
            if resources.get('cpu_percent', 0) > 80:
                self.logger.warning(f"High CPU usage: {resources.get('cpu_percent', 0):.1f}%")
            
            if resources.get('memory_percent', 0) > 80:
                self.logger.warning(f"High memory usage: {resources.get('memory_percent', 0):.1f}%")
            
            if resources.get('disk_usage', 0) > 90:
                self.logger.warning(f"High disk usage: {resources.get('disk_usage', 0):.1f}%")
            
        except Exception as e:
            self.logger.error(f"Error in system check: {str(e)}")
    
    def _update_next_run_time(self):
        """Update next scheduled run time"""
        try:
            next_time = get_optimal_posting_time()
            self.stats['next_run'] = next_time
            
        except Exception as e:
            self.logger.error(f"Error updating next run time: {str(e)}")
    
    def _generate_daily_report(self):
        """Generate daily performance report"""
        try:
            stats = self.get_comprehensive_stats()
            
            report = []
            report.append("=== Daily YTBot Report ===")
            report.append(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
            report.append("")
            
            # Processing stats
            if 'processing' in stats:
                proc = stats['processing']
                report.append("Processing Statistics:")
                report.append(f"  Total Processed: {proc.get('total_processed', 0)}")
                report.append(f"  Success Rate: {proc.get('success_rate', 0):.1f}%")
                report.append(f"  Avg Processing Time: {proc.get('avg_processing_time', 0):.1f}s")
                report.append("")
            
            # Platform stats
            if 'platforms' in stats:
                report.append("Platform Statistics:")
                for platform, data in stats['platforms'].items():
                    report.append(f"  {platform.capitalize()}:")
                    report.append(f"    Total Uploads: {data.get('total_uploads', 0)}")
                    report.append(f"    Success Rate: {data.get('success_rate', 0):.1f}%")
                report.append("")
            
            # Scheduler stats
            report.append("Scheduler Statistics:")
            report.append(f"  Total Runs: {self.stats['total_runs']}")
            report.append(f"  Successful Runs: {self.stats['successful_runs']}")
            report.append(f"  Failed Runs: {self.stats['failed_runs']}")
            if self.stats['last_run']:
                report.append(f"  Last Run: {self.stats['last_run'].strftime('%Y-%m-%d %H:%M:%S')}")
            if self.stats['next_run']:
                report.append(f"  Next Run: {self.stats['next_run'].strftime('%Y-%m-%d %H:%M:%S')}")
            
            report_text = "\n".join(report)
            
            # Save report
            report_file = Path("reports") / f"daily_report_{datetime.now().strftime('%Y%m%d')}.txt"
            report_file.parent.mkdir(exist_ok=True)
            
            with open(report_file, 'w') as f:
                f.write(report_text)
            
            self.logger.info(f"Daily report generated: {report_file}")
            
        except Exception as e:
            self.logger.error(f"Error generating daily report: {str(e)}")
    
    def get_comprehensive_stats(self) -> Dict:
        """Get comprehensive statistics from all components"""
        try:
            stats = {
                'timestamp': datetime.now().isoformat(),
                'scheduler': self.stats.copy(),
                'processing': self.content_tracker.get_processing_stats(),
                'platforms': self.content_tracker.get_platform_stats(),
                'recent_uploads': self.content_tracker.get_recent_uploads(),
                'system': monitor_system_resources()
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting comprehensive stats: {str(e)}")
            return {}
    
    def run(self):
        """Run the scheduler"""
        try:
            self.logger.info("Starting YTBot Scheduler")
            self.running = True
            
            # Setup schedule
            self.setup_schedule()
            
            # Initial system check
            if not self._pre_run_checks():
                self.logger.error("Initial system checks failed")
                return
            
            self.logger.info("Scheduler is running. Press Ctrl+C to stop.")
            
            # Main scheduler loop
            while self.running:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # Check every minute
                    
                except Exception as e:
                    self.logger.error(f"Error in scheduler loop: {str(e)}")
                    time.sleep(300)  # Wait 5 minutes before retrying
            
            self.logger.info("Scheduler stopped")
            
        except Exception as e:
            self.logger.error(f"Fatal error in scheduler: {str(e)}")
        finally:
            self._cleanup()
    
    def run_once(self):
        """Run the bot once and exit"""
        try:
            self.logger.info("Running bot once")
            
            if not self._pre_run_checks():
                self.logger.error("Pre-run checks failed")
                return
            
            result = asyncio.run(self.bot.run_full_pipeline(limit=3))
            self.logger.info(f"Single run completed: {result}")
            
        except Exception as e:
            self.logger.error(f"Error in single run: {str(e)}")
    
    def status(self):
        """Show current status"""
        try:
            stats = self.get_comprehensive_stats()
            print(json.dumps(stats, indent=2, default=str))
            
        except Exception as e:
            print(f"Error getting status: {str(e)}")
    
    def _cleanup(self):
        """Cleanup resources"""
        try:
            self.logger.info("Cleaning up resources")
            
            # Final cleanup
            from utils.helpers import cleanup_temp_directory
            cleanup_temp_directory()
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")

def main():
    """Main entry point for scheduler"""
    parser = argparse.ArgumentParser(description='YTBot Scheduler')
    parser.add_argument('command', choices=['start', 'once', 'status'], 
                       help='Command to execute')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scheduler.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    scheduler = BotScheduler()
    
    try:
        if args.command == 'start':
            scheduler.run()
        elif args.command == 'once':
            scheduler.run_once()
        elif args.command == 'status':
            scheduler.status()
            
    except KeyboardInterrupt:
        print("\nScheduler stopped by user")
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()