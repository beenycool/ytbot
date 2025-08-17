import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from .base_db import DatabaseBase


class ContentTracker(DatabaseBase):
    """Handles content tracking and deduplication"""
    
    def __init__(self):
        super().__init__()
        self._init_tables()
    
    def _init_tables(self):
        """Initialize content tracking tables"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Processed content table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS processed_content (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        post_id TEXT UNIQUE NOT NULL,
                        title TEXT NOT NULL,
                        subreddit TEXT NOT NULL,
                        original_url TEXT NOT NULL,
                        reddit_permalink TEXT NOT NULL,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processing_time_seconds REAL,
                        success BOOLEAN NOT NULL,
                        upload_results TEXT,  -- JSON
                        analysis_data TEXT,   -- JSON
                        errors TEXT,          -- JSON
                        file_paths TEXT,      -- JSON
                        engagement_score REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Upload statistics table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS upload_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        post_id TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        upload_url TEXT,
                        upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        metadata TEXT,        -- JSON
                        FOREIGN KEY (post_id) REFERENCES processed_content (post_id)
                    )
                ''')
                
                # Content duplicates prevention
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS content_hashes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        post_id TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        url_hash TEXT NOT NULL,
                        title_hash TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(content_hash)
                    )
                ''')
                
                # Create indexes
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_id ON processed_content (post_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_processed_at ON processed_content (processed_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_platform ON upload_stats (platform)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_upload_time ON upload_stats (upload_time)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON content_hashes (content_hash)')
                
                conn.commit()
                self.logger.info("Content tracking tables initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Error initializing content tables: {str(e)}")
            raise
    
    def is_processed(self, post_id: str) -> bool:
        """Check if a post has already been processed"""
        try:
            query = 'SELECT 1 FROM processed_content WHERE post_id = ?'
            result = self.execute_query(query, (post_id,))
            return len(result) > 0
        except Exception as e:
            self.logger.error(f"Error checking if post is processed: {str(e)}")
            return False
    
    def is_duplicate_content(self, title: str, url: str) -> bool:
        """Check if content is duplicate based on title/URL similarity"""
        try:
            # Create hashes
            title_hash = hashlib.md5(title.lower().strip().encode()).hexdigest()
            url_hash = hashlib.md5(url.encode()).hexdigest()
            
            query = 'SELECT 1 FROM content_hashes WHERE title_hash = ? OR url_hash = ?'
            result = self.execute_query(query, (title_hash, url_hash))
            return len(result) > 0
        except Exception as e:
            self.logger.error(f"Error checking duplicate content: {str(e)}")
            return False
    
    def save_processed_content(self, post_id: str, result: Dict) -> bool:
        """Save processed content results to database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Save main record
                cursor.execute('''
                    INSERT OR REPLACE INTO processed_content 
                    (post_id, title, subreddit, original_url, reddit_permalink, 
                     processing_time_seconds, success, upload_results, analysis_data, 
                     errors, file_paths, engagement_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    post_id,
                    result.get('title', ''),
                    result.get('subreddit', ''),
                    result.get('original_url', ''),
                    result.get('reddit_url', ''),
                    result.get('processing_time', 0),
                    result.get('success', False),
                    json.dumps(result.get('uploads', {})),
                    json.dumps(result.get('analysis', {})),
                    json.dumps(result.get('errors', [])),
                    json.dumps(result.get('file_paths', [])),
                    result.get('engagement_score', 0.0)
                ))
                
                # Save upload stats for each platform
                for platform, upload_url in result.get('uploads', {}).items():
                    cursor.execute('''
                        INSERT INTO upload_stats 
                        (post_id, platform, upload_url, success, metadata)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        post_id,
                        platform,
                        upload_url,
                        True,
                        json.dumps({'post_title': result.get('title', '')})
                    ))
                
                # Save content hashes
                self._save_content_hashes(cursor, post_id, result)
                
                conn.commit()
                self.logger.info(f"Saved processed content: {post_id}")
                return True
        except Exception as e:
            self.logger.error(f"Error saving processed content: {str(e)}")
            return False
    
    def _save_content_hashes(self, cursor, post_id: str, result: Dict):
        """Save content hashes for duplicate detection"""
        try:
            title = result.get('title', '')
            url = result.get('original_url', '')
            
            title_hash = hashlib.md5(title.lower().strip().encode()).hexdigest()
            url_hash = hashlib.md5(url.encode()).hexdigest()
            content_hash = hashlib.md5(f"{title}{url}".encode()).hexdigest()
            
            cursor.execute('''
                INSERT OR IGNORE INTO content_hashes 
                (post_id, content_hash, url_hash, title_hash)
                VALUES (?, ?, ?, ?)
            ''', (post_id, content_hash, url_hash, title_hash))
        except Exception as e:
            self.logger.error(f"Error saving content hashes: {str(e)}")
    
    def get_recent_uploads(self, limit: int = 10) -> List[Dict]:
        """Get recent successful uploads"""
        try:
            query = '''
                SELECT pc.title, us.platform, us.upload_url, us.upload_time
                FROM upload_stats us
                JOIN processed_content pc ON us.post_id = pc.post_id
                WHERE us.success = 1
                ORDER BY us.upload_time DESC
                LIMIT ?
            '''
            return self.execute_query(query, (limit,))
        except Exception as e:
            self.logger.error(f"Error getting recent uploads: {str(e)}")
            return []
    
    def get_processed_content_by_date(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get processed content within date range"""
        try:
            query = '''
                SELECT * FROM processed_content 
                WHERE processed_at BETWEEN ? AND ?
                ORDER BY processed_at DESC
            '''
            return self.execute_query(query, (start_date, end_date))
        except Exception as e:
            self.logger.error(f"Error getting content by date: {str(e)}")
            return []
    
    def get_failed_uploads(self, days: int = 7) -> List[Dict]:
        """Get failed uploads from recent days"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = '''
                SELECT pc.title, pc.post_id, pc.errors, pc.processed_at
                FROM processed_content pc
                WHERE pc.success = 0 AND pc.processed_at >= ?
                ORDER BY pc.processed_at DESC
            '''
            return self.execute_query(query, (cutoff_date,))
        except Exception as e:
            self.logger.error(f"Error getting failed uploads: {str(e)}")
            return []