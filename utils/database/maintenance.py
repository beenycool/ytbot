import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from .base_db import DatabaseBase


class DatabaseMaintenance(DatabaseBase):
    """Handles database maintenance, cleanup, and optimization"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def cleanup_old_records(self, days: int = 30) -> Dict[str, int]:
        """Clean up old records from database"""
        cleanup_results = {}
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Delete old processed content
                cursor.execute(
                    'DELETE FROM processed_content WHERE processed_at < ?', 
                    (cutoff_date,)
                )
                cleanup_results['processed_content'] = cursor.rowcount
                
                # Delete old upload stats
                cursor.execute(
                    'DELETE FROM upload_stats WHERE upload_time < ?', 
                    (cutoff_date,)
                )
                cleanup_results['upload_stats'] = cursor.rowcount
                
                # Delete old content hashes
                cursor.execute(
                    'DELETE FROM content_hashes WHERE created_at < ?', 
                    (cutoff_date,)
                )
                cleanup_results['content_hashes'] = cursor.rowcount
                
                # Delete old performance metrics
                cursor.execute(
                    'DELETE FROM performance_metrics WHERE recorded_at < ?', 
                    (cutoff_date,)
                )
                cleanup_results['performance_metrics'] = cursor.rowcount
                
                conn.commit()
                
                self.logger.info(
                    f"Database cleanup completed: "
                    f"{sum(cleanup_results.values())} total records removed"
                )
                
                return cleanup_results
                
        except Exception as e:
            self.logger.error(f"Error during database cleanup: {str(e)}")
            return {}
    
    def vacuum_database(self) -> bool:
        """Optimize database by running VACUUM"""
        try:
            with self.get_connection() as conn:
                conn.execute('VACUUM')
                self.logger.info("Database VACUUM completed successfully")
                return True
        except Exception as e:
            self.logger.error(f"Error during database VACUUM: {str(e)}")
            return False
    
    def analyze_database(self) -> bool:
        """Update database statistics for query optimization"""
        try:
            with self.get_connection() as conn:
                conn.execute('ANALYZE')
                self.logger.info("Database ANALYZE completed successfully")
                return True
        except Exception as e:
            self.logger.error(f"Error during database ANALYZE: {str(e)}")
            return False
    
    def get_database_size(self) -> Dict[str, Any]:
        """Get database size and table information"""
        try:
            db_size = self.db_path.stat().st_size
            
            # Get table sizes
            table_info = {}
            tables = ['processed_content', 'upload_stats', 'content_hashes', 
                     'platform_performance', 'daily_stats', 'performance_metrics']
            
            for table in tables:
                if self.table_exists(table):
                    query = f'SELECT COUNT(*) as count FROM {table}'
                    result = self.execute_query(query)
                    table_info[table] = result[0]['count'] if result else 0
            
            return {
                'database_size_bytes': db_size,
                'database_size_mb': round(db_size / (1024 * 1024), 2),
                'table_counts': table_info,
                'checked_at': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error getting database size: {str(e)}")
            return {}
    
    def export_data(self, output_path: str, days: int = 30) -> bool:
        """Export data to JSON file"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Get all data from main tables
            export_data = {
                'export_metadata': {
                    'export_date': datetime.now().isoformat(),
                    'days_included': days,
                    'cutoff_date': cutoff_date.isoformat()
                }
            }
            
            # Export processed content
            query = '''
                SELECT * FROM processed_content 
                WHERE processed_at >= ?
                ORDER BY processed_at DESC
            '''
            export_data['processed_content'] = self.execute_query(query, (cutoff_date,))
            
            # Export upload stats
            query = '''
                SELECT * FROM upload_stats 
                WHERE upload_time >= ?
                ORDER BY upload_time DESC
            '''
            export_data['upload_stats'] = self.execute_query(query, (cutoff_date,))
            
            # Export daily stats
            query = '''
                SELECT * FROM daily_stats 
                WHERE date >= ?
                ORDER BY date DESC
            '''
            export_data['daily_stats'] = self.execute_query(query, (cutoff_date.date(),))
            
            # Export performance metrics
            query = '''
                SELECT * FROM performance_metrics 
                WHERE recorded_at >= ?
                ORDER BY recorded_at DESC
            '''
            export_data['performance_metrics'] = self.execute_query(query, (cutoff_date,))
            
            # Write to file
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            self.logger.info(f"Data exported successfully to: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting data: {str(e)}")
            return False
    
    def create_backup(self, backup_dir: str = 'backups') -> Optional[str]:
        """Create a complete database backup"""
        try:
            backup_path = Path(backup_dir)
            backup_path.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = backup_path / f"ytbot_db_backup_{timestamp}.db"
            
            # Copy the entire database file
            import shutil
            shutil.copy2(self.db_path, backup_file)
            
            self.logger.info(f"Database backup created: {backup_file}")
            return str(backup_file)
            
        except Exception as e:
            self.logger.error(f"Error creating backup: {str(e)}")
            return None
    
    def restore_from_backup(self, backup_file: str) -> bool:
        """Restore database from backup"""
        try:
            backup_path = Path(backup_file)
            if not backup_path.exists():
                self.logger.error(f"Backup file not found: {backup_file}")
                return False
            
            # Create a backup of current database before restoring
            current_backup = self.create_backup('backups/pre_restore')
            if current_backup:
                self.logger.info(f"Current database backed up to: {current_backup}")
            
            # Replace current database with backup
            import shutil
            shutil.copy2(backup_file, self.db_path)
            
            self.logger.info(f"Database restored from: {backup_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error restoring from backup: {str(e)}")
            return False
    
    def check_database_integrity(self) -> Dict[str, Any]:
        """Check database integrity and report issues"""
        try:
            integrity_results = {}
            
            # Run integrity check
            query = 'PRAGMA integrity_check'
            result = self.execute_query(query)
            integrity_results['integrity_check'] = result
            
            # Check foreign key constraints
            query = 'PRAGMA foreign_key_check'
            result = self.execute_query(query)
            integrity_results['foreign_key_check'] = result
            
            # Get database info
            query = 'PRAGMA database_list'
            result = self.execute_query(query)
            integrity_results['database_info'] = result
            
            # Check for orphaned records
            orphaned_uploads = self.execute_query('''
                SELECT COUNT(*) as count FROM upload_stats us
                LEFT JOIN processed_content pc ON us.post_id = pc.post_id
                WHERE pc.post_id IS NULL
            ''')
            integrity_results['orphaned_upload_stats'] = orphaned_uploads[0]['count'] if orphaned_uploads else 0
            
            return integrity_results
            
        except Exception as e:
            self.logger.error(f"Error checking database integrity: {str(e)}")
            return {'error': str(e)}
    
    def optimize_database(self) -> bool:
        """Perform complete database optimization"""
        try:
            self.logger.info("Starting database optimization...")
            
            # 1. Analyze for query optimization
            if not self.analyze_database():
                return False
            
            # 2. Vacuum to reclaim space
            if not self.vacuum_database():
                return False
            
            # 3. Check integrity
            integrity_results = self.check_database_integrity()
            if integrity_results.get('error'):
                self.logger.error("Database integrity check failed")
                return False
            
            self.logger.info("Database optimization completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during database optimization: {str(e)}")
            return False
    
    def get_maintenance_report(self) -> Dict[str, Any]:
        """Generate comprehensive maintenance report"""
        try:
            report = {
                'generated_at': datetime.now().isoformat(),
                'database_size': self.get_database_size(),
                'integrity_check': self.check_database_integrity(),
                'recommendations': []
            }
            
            # Add recommendations based on database state
            db_size_mb = report['database_size'].get('database_size_mb', 0)
            if db_size_mb > 100:
                report['recommendations'].append(
                    "Database size is large (>100MB). Consider cleaning up old records."
                )
            
            total_records = sum(report['database_size'].get('table_counts', {}).values())
            if total_records > 100000:
                report['recommendations'].append(
                    "High record count. Consider archiving old data."
                )
            
            if not report['recommendations']:
                report['recommendations'].append("Database is in good condition.")
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating maintenance report: {str(e)}")
            return {'error': str(e)}