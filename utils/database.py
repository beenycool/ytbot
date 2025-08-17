import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from config.settings import DATABASE_PATH

class ContentTracker:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db_path = Path(DATABASE_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
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
                
                # Platform performance table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS platform_performance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        platform TEXT NOT NULL,
                        upload_url TEXT NOT NULL,
                        views INTEGER DEFAULT 0,
                        likes INTEGER DEFAULT 0,
                        comments INTEGER DEFAULT 0,
                        shares INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                
                # Bot configuration and stats
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS bot_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date DATE NOT NULL,
                        total_processed INTEGER DEFAULT 0,
                        total_uploaded INTEGER DEFAULT 0,
                        total_failed INTEGER DEFAULT 0,
                        platforms_uploaded TEXT,  -- JSON
                        avg_processing_time REAL,
                        errors_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(date)
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_id ON processed_content (post_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_processed_at ON processed_content (processed_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_platform ON upload_stats (platform)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_upload_time ON upload_stats (upload_time)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON content_hashes (content_hash)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON bot_stats (date)')
                
                conn.commit()
                self.logger.info("Database initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Error initializing database: {str(e)}")
            raise
    
    def is_processed(self, post_id: str) -> bool:
        """Check if a post has already been processed"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM processed_content WHERE post_id = ?', (post_id,))
                return cursor.fetchone() is not None
                
        except Exception as e:
            self.logger.error(f"Error checking if post is processed: {str(e)}")
            return False
    
    def is_duplicate_content(self, title: str, url: str) -> bool:
        """Check if content is duplicate based on title/URL similarity"""
        try:
            import hashlib
            
            # Create hashes
            title_hash = hashlib.md5(title.lower().strip().encode()).hexdigest()
            url_hash = hashlib.md5(url.encode()).hexdigest()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT 1 FROM content_hashes WHERE title_hash = ? OR url_hash = ?',
                    (title_hash, url_hash)
                )
                return cursor.fetchone() is not None
                
        except Exception as e:
            self.logger.error(f"Error checking duplicate content: {str(e)}")
            return False
    
    def save_processed_content(self, post_id: str, result: Dict) -> bool:
        """Save processed content results to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
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
                
                # Update daily stats
                self._update_daily_stats(cursor, result)
                
                conn.commit()
                self.logger.info(f"Saved processed content: {post_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error saving processed content: {str(e)}")
            return False
    
    def _save_content_hashes(self, cursor, post_id: str, result: Dict):
        """Save content hashes for duplicate detection"""
        try:
            import hashlib
            
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
    
    def _update_daily_stats(self, cursor, result: Dict):
        """Update daily statistics"""
        try:
            today = datetime.now().date()
            
            # Get current stats
            cursor.execute('SELECT * FROM bot_stats WHERE date = ?', (today,))
            current_stats = cursor.fetchone()
            
            if current_stats:
                # Update existing record
                total_processed = current_stats[2] + 1
                total_uploaded = current_stats[3] + len(result.get('uploads', {}))
                total_failed = current_stats[4] + (0 if result.get('success') else 1)
                
                # Update platforms
                platforms_data = json.loads(current_stats[5] or '{}')
                for platform in result.get('uploads', {}).keys():
                    platforms_data[platform] = platforms_data.get(platform, 0) + 1
                
                cursor.execute('''
                    UPDATE bot_stats 
                    SET total_processed = ?, total_uploaded = ?, total_failed = ?,
                        platforms_uploaded = ?
                    WHERE date = ?
                ''', (total_processed, total_uploaded, total_failed, 
                      json.dumps(platforms_data), today))
            else:
                # Create new record
                platforms_data = {}
                for platform in result.get('uploads', {}).keys():
                    platforms_data[platform] = 1
                
                cursor.execute('''
                    INSERT INTO bot_stats 
                    (date, total_processed, total_uploaded, total_failed, platforms_uploaded)
                    VALUES (?, ?, ?, ?, ?)
                ''', (today, 1, len(result.get('uploads', {})), 
                      0 if result.get('success') else 1, json.dumps(platforms_data)))
                
        except Exception as e:
            self.logger.error(f"Error updating daily stats: {str(e)}")
    
    def get_daily_upload_count(self, date: Optional[datetime] = None) -> int:
        """Get number of uploads for a specific date"""
        try:
            if date is None:
                date = datetime.now().date()
            else:
                date = date.date()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM upload_stats 
                    WHERE DATE(upload_time) = ? AND success = 1
                ''', (date,))
                
                result = cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            self.logger.error(f"Error getting daily upload count: {str(e)}")
            return 0
    
    def get_platform_stats(self, days: int = 30) -> Dict:
        """Get platform performance statistics"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT platform, COUNT(*) as uploads, 
                           SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
                    FROM upload_stats 
                    WHERE upload_time >= ?
                    GROUP BY platform
                ''', (cutoff_date,))
                
                stats = {}
                for row in cursor.fetchall():
                    platform, uploads, successful = row
                    stats[platform] = {
                        'total_uploads': uploads,
                        'successful_uploads': successful,
                        'success_rate': (successful / uploads * 100) if uploads > 0 else 0
                    }
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Error getting platform stats: {str(e)}")
            return {}
    
    def get_recent_uploads(self, limit: int = 10) -> List[Dict]:
        """Get recent successful uploads"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT pc.title, us.platform, us.upload_url, us.upload_time
                    FROM upload_stats us
                    JOIN processed_content pc ON us.post_id = pc.post_id
                    WHERE us.success = 1
                    ORDER BY us.upload_time DESC
                    LIMIT ?
                ''', (limit,))
                
                uploads = []
                for row in cursor.fetchall():
                    title, platform, url, upload_time = row
                    uploads.append({
                        'title': title,
                        'platform': platform,
                        'url': url,
                        'upload_time': upload_time
                    })
                
                return uploads
                
        except Exception as e:
            self.logger.error(f"Error getting recent uploads: {str(e)}")
            return []
    
    def get_processing_stats(self, days: int = 7) -> Dict:
        """Get processing performance statistics"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                           AVG(processing_time_seconds) as avg_time,
                           MIN(processing_time_seconds) as min_time,
                           MAX(processing_time_seconds) as max_time
                    FROM processed_content
                    WHERE processed_at >= ?
                ''', (cutoff_date,))
                
                row = cursor.fetchone()
                if row:
                    total, successful, avg_time, min_time, max_time = row
                    return {
                        'total_processed': total or 0,
                        'successful': successful or 0,
                        'success_rate': (successful / total * 100) if total > 0 else 0,
                        'avg_processing_time': avg_time or 0,
                        'min_processing_time': min_time or 0,
                        'max_processing_time': max_time or 0
                    }
                
                return {}
                
        except Exception as e:
            self.logger.error(f"Error getting processing stats: {str(e)}")
            return {}
    
    def cleanup_old_records(self, days: int = 30):
        """Clean up old records from database"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete old processed content
                cursor.execute('DELETE FROM processed_content WHERE processed_at < ?', (cutoff_date,))
                deleted_content = cursor.rowcount
                
                # Delete old upload stats
                cursor.execute('DELETE FROM upload_stats WHERE upload_time < ?', (cutoff_date,))
                deleted_stats = cursor.rowcount
                
                # Delete old content hashes
                cursor.execute('DELETE FROM content_hashes WHERE created_at < ?', (cutoff_date,))
                deleted_hashes = cursor.rowcount
                
                conn.commit()
                
                self.logger.info(f"Cleaned up database: {deleted_content} content records, "
                               f"{deleted_stats} upload stats, {deleted_hashes} content hashes")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up database: {str(e)}")
    
    def export_data(self, output_path: str, days: int = 30) -> bool:
        """Export data to JSON file"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all data
                cursor.execute('''
                    SELECT * FROM processed_content 
                    WHERE processed_at >= ?
                    ORDER BY processed_at DESC
                ''', (cutoff_date,))
                
                columns = [description[0] for description in cursor.description]
                content_data = [dict(zip(columns, row)) for row in cursor.fetchall()]
                
                # Get upload stats
                cursor.execute('''
                    SELECT * FROM upload_stats 
                    WHERE upload_time >= ?
                    ORDER BY upload_time DESC
                ''', (cutoff_date,))
                
                columns = [description[0] for description in cursor.description]
                upload_data = [dict(zip(columns, row)) for row in cursor.fetchall()]
                
                # Export to JSON
                export_data = {
                    'export_date': datetime.now().isoformat(),
                    'days_included': days,
                    'processed_content': content_data,
                    'upload_stats': upload_data
                }
                
                with open(output_path, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
                
                self.logger.info(f"Data exported to: {output_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error exporting data: {str(e)}")
            return False