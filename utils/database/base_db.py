import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from config.settings import DATABASE_PATH


class DatabaseBase:
    """Base database class with common functionality"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db_path = Path(DATABASE_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def get_connection(self):
        """Get database connection with proper configuration"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute a SELECT query and return results"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Error executing query: {str(e)}")
            return []
    
    def execute_update(self, query: str, params: tuple = ()) -> bool:
        """Execute an INSERT/UPDATE/DELETE query"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error executing update: {str(e)}")
            return False
    
    def execute_many(self, query: str, params_list: List[tuple]) -> bool:
        """Execute many statements in a transaction"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error executing batch update: {str(e)}")
            return False
    
    def table_exists(self, table_name: str) -> bool:
        """Check if table exists"""
        try:
            query = """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """
            result = self.execute_query(query, (table_name,))
            return len(result) > 0
        except Exception as e:
            self.logger.error(f"Error checking table existence: {str(e)}")
            return False
    
    def get_table_info(self, table_name: str) -> List[Dict]:
        """Get table schema information"""
        try:
            query = f"PRAGMA table_info({table_name})"
            return self.execute_query(query)
        except Exception as e:
            self.logger.error(f"Error getting table info: {str(e)}")
            return []
    
    def backup_table(self, table_name: str, backup_path: str) -> bool:
        """Backup table to file"""
        try:
            with self.get_connection() as conn:
                query = f"SELECT * FROM {table_name}"
                cursor = conn.cursor()
                cursor.execute(query)
                
                import json
                data = [dict(row) for row in cursor.fetchall()]
                
                with open(backup_path, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
                
                return True
        except Exception as e:
            self.logger.error(f"Error backing up table: {str(e)}")
            return False