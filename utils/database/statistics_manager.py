import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from .base_db import DatabaseBase


class StatisticsManager(DatabaseBase):
    """Handles analytics and performance statistics"""
    
    def __init__(self):
        super().__init__()
        self._init_tables()
    
    def _init_tables(self):
        """Initialize statistics tables"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
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
                
                # Daily statistics table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS daily_stats (
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
                
                # Performance metrics table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS performance_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        metric_name TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        metric_type TEXT NOT NULL,  -- 'time', 'count', 'percentage', etc.
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT  -- JSON for additional context
                    )
                ''')
                
                # Create indexes
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON daily_stats (date)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_metric_name ON performance_metrics (metric_name)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_recorded_at ON performance_metrics (recorded_at)')
                
                conn.commit()
                self.logger.info("Statistics tables initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Error initializing statistics tables: {str(e)}")
            raise
    
    def update_daily_stats(self, result: Dict):
        """Update daily statistics with processing result"""
        try:
            today = datetime.now().date()
            
            # Get current stats
            query = 'SELECT * FROM daily_stats WHERE date = ?'
            current_stats = self.execute_query(query, (today,))
            
            if current_stats:
                # Update existing record
                stats = current_stats[0]
                total_processed = stats['total_processed'] + 1
                total_uploaded = stats['total_uploaded'] + len(result.get('uploads', {}))
                total_failed = stats['total_failed'] + (0 if result.get('success') else 1)
                
                # Update platforms
                platforms_data = json.loads(stats['platforms_uploaded'] or '{}')
                for platform in result.get('uploads', {}).keys():
                    platforms_data[platform] = platforms_data.get(platform, 0) + 1
                
                update_query = '''
                    UPDATE daily_stats 
                    SET total_processed = ?, total_uploaded = ?, total_failed = ?,
                        platforms_uploaded = ?
                    WHERE date = ?
                '''
                self.execute_update(update_query, (
                    total_processed, total_uploaded, total_failed, 
                    json.dumps(platforms_data), today
                ))
            else:
                # Create new record
                platforms_data = {}
                for platform in result.get('uploads', {}).keys():
                    platforms_data[platform] = 1
                
                insert_query = '''
                    INSERT INTO daily_stats 
                    (date, total_processed, total_uploaded, total_failed, platforms_uploaded)
                    VALUES (?, ?, ?, ?, ?)
                '''
                self.execute_update(insert_query, (
                    today, 1, len(result.get('uploads', {})), 
                    0 if result.get('success') else 1, json.dumps(platforms_data)
                ))
        except Exception as e:
            self.logger.error(f"Error updating daily stats: {str(e)}")
    
    def get_daily_upload_count(self, date: Optional[datetime] = None) -> int:
        """Get number of uploads for a specific date"""
        try:
            if date is None:
                date = datetime.now().date()
            else:
                date = date.date()
            
            query = '''
                SELECT COUNT(*) as count FROM upload_stats 
                WHERE DATE(upload_time) = ? AND success = 1
            '''
            result = self.execute_query(query, (date,))
            return result[0]['count'] if result else 0
        except Exception as e:
            self.logger.error(f"Error getting daily upload count: {str(e)}")
            return 0
    
    def get_platform_stats(self, days: int = 30) -> Dict:
        """Get platform performance statistics"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = '''
                SELECT platform, COUNT(*) as uploads, 
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
                FROM upload_stats 
                WHERE upload_time >= ?
                GROUP BY platform
            '''
            results = self.execute_query(query, (cutoff_date,))
            
            stats = {}
            for row in results:
                platform = row['platform']
                uploads = row['uploads']
                successful = row['successful']
                stats[platform] = {
                    'total_uploads': uploads,
                    'successful_uploads': successful,
                    'success_rate': (successful / uploads * 100) if uploads > 0 else 0
                }
            
            return stats
        except Exception as e:
            self.logger.error(f"Error getting platform stats: {str(e)}")
            return {}
    
    def get_processing_stats(self, days: int = 7) -> Dict:
        """Get processing performance statistics"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = '''
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                       AVG(processing_time_seconds) as avg_time,
                       MIN(processing_time_seconds) as min_time,
                       MAX(processing_time_seconds) as max_time
                FROM processed_content
                WHERE processed_at >= ?
            '''
            results = self.execute_query(query, (cutoff_date,))
            
            if results:
                row = results[0]
                total = row['total'] or 0
                successful = row['successful'] or 0
                return {
                    'total_processed': total,
                    'successful': successful,
                    'success_rate': (successful / total * 100) if total > 0 else 0,
                    'avg_processing_time': row['avg_time'] or 0,
                    'min_processing_time': row['min_time'] or 0,
                    'max_processing_time': row['max_time'] or 0
                }
            return {}
        except Exception as e:
            self.logger.error(f"Error getting processing stats: {str(e)}")
            return {}
    
    def record_performance_metric(self, name: str, value: float, metric_type: str = 'count', metadata: Dict = None):
        """Record a performance metric"""
        try:
            query = '''
                INSERT INTO performance_metrics (metric_name, metric_value, metric_type, metadata)
                VALUES (?, ?, ?, ?)
            '''
            self.execute_update(query, (
                name, value, metric_type, json.dumps(metadata or {})
            ))
        except Exception as e:
            self.logger.error(f"Error recording performance metric: {str(e)}")
    
    def get_performance_trends(self, metric_name: str, days: int = 30) -> List[Dict]:
        """Get performance trends for a specific metric"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = '''
                SELECT metric_value, recorded_at, metadata
                FROM performance_metrics
                WHERE metric_name = ? AND recorded_at >= ?
                ORDER BY recorded_at DESC
            '''
            return self.execute_query(query, (metric_name, cutoff_date))
        except Exception as e:
            self.logger.error(f"Error getting performance trends: {str(e)}")
            return []
    
    def get_daily_summary(self, date: Optional[datetime] = None) -> Dict:
        """Get daily summary statistics"""
        try:
            if date is None:
                date = datetime.now().date()
            else:
                date = date.date()
            
            query = 'SELECT * FROM daily_stats WHERE date = ?'
            results = self.execute_query(query, (date,))
            
            if results:
                return results[0]
            return {
                'date': str(date),
                'total_processed': 0,
                'total_uploaded': 0,
                'total_failed': 0,
                'platforms_uploaded': '{}',
                'avg_processing_time': 0,
                'errors_count': 0
            }
        except Exception as e:
            self.logger.error(f"Error getting daily summary: {str(e)}")
            return {}
    
    def get_weekly_report(self) -> Dict:
        """Generate weekly performance report"""
        try:
            week_ago = datetime.now() - timedelta(days=7)
            
            # Get processing stats
            processing_stats = self.get_processing_stats(days=7)
            
            # Get platform stats
            platform_stats = self.get_platform_stats(days=7)
            
            # Get daily summaries
            daily_summaries = []
            for i in range(7):
                date = datetime.now().date() - timedelta(days=i)
                summary = self.get_daily_summary(date)
                daily_summaries.append(summary)
            
            return {
                'week_ending': datetime.now().date().isoformat(),
                'processing_stats': processing_stats,
                'platform_stats': platform_stats,
                'daily_summaries': daily_summaries,
                'generated_at': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error generating weekly report: {str(e)}")
            return {}