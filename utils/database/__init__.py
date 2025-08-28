"""
Database package for YTBot
Provides modular database functionality split into focused components
"""

from .base_db import DatabaseBase
from .content_tracker import ContentTracker as _ContentTracker
from .statistics_manager import StatisticsManager
from .maintenance import DatabaseMaintenance

# Legacy compatibility - maintain original interface
class ContentTrackerLegacy(_ContentTracker, StatisticsManager, DatabaseMaintenance):
    """
    Legacy ContentTracker class that combines all database functionality
    Maintains backward compatibility with existing code
    """
    
    def __init__(self):
        _ContentTracker.__init__(self)
        StatisticsManager.__init__(self)
        DatabaseMaintenance.__init__(self)
        
        # Initialize all tables from all components
        self._init_all_tables()
    
    def _init_all_tables(self):
        """Initialize all database tables"""
        try:
            # Tables are already initialized by parent classes
            # This method exists for compatibility
            pass
        except Exception as e:
            self.logger.error(f"Error initializing legacy tables: {str(e)}")
    
    # Alias methods for backward compatibility
    def get_platform_performance(self, days: int = 30) -> dict:
        """Alias for get_platform_stats"""
        return self.get_platform_stats(days)
    
    def get_bot_statistics(self) -> dict:
        """Get comprehensive bot statistics"""
        return {
            'processing_stats': self.get_processing_stats(),
            'platform_stats': self.get_platform_stats(),
            'daily_summary': self.get_daily_summary(),
            'database_info': self.get_database_size()
        }

# For backward compatibility, export the legacy class as ContentTracker
ContentTracker = ContentTrackerLegacy

__all__ = [
    'DatabaseBase',
    'ContentTracker', 
    'StatisticsManager',
    'DatabaseMaintenance'
]