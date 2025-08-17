import logging
import traceback
import functools
from typing import Any, Callable, Dict, Optional, Union
from datetime import datetime
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better classification"""
    NETWORK = "network"
    API = "api"
    FILE_IO = "file_io"
    PROCESSING = "processing"
    VALIDATION = "validation"
    DATABASE = "database"
    UPLOAD = "upload"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


class YTBotError(Exception):
    """Base exception class for YTBot"""
    
    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.UNKNOWN, 
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM, context: Dict = None):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        """Convert error to dictionary for logging/storage"""
        return {
            'message': self.message,
            'category': self.category.value,
            'severity': self.severity.value,
            'context': self.context,
            'timestamp': self.timestamp.isoformat(),
            'type': self.__class__.__name__
        }


class NetworkError(YTBotError):
    """Network-related errors"""
    def __init__(self, message: str, context: Dict = None):
        super().__init__(message, ErrorCategory.NETWORK, ErrorSeverity.MEDIUM, context)


class APIError(YTBotError):
    """API-related errors"""
    def __init__(self, message: str, status_code: int = None, context: Dict = None):
        context = context or {}
        if status_code:
            context['status_code'] = status_code
        super().__init__(message, ErrorCategory.API, ErrorSeverity.HIGH, context)


class FileIOError(YTBotError):
    """File I/O related errors"""
    def __init__(self, message: str, file_path: str = None, context: Dict = None):
        context = context or {}
        if file_path:
            context['file_path'] = file_path
        super().__init__(message, ErrorCategory.FILE_IO, ErrorSeverity.MEDIUM, context)


class ProcessingError(YTBotError):
    """Video/audio processing errors"""
    def __init__(self, message: str, context: Dict = None):
        super().__init__(message, ErrorCategory.PROCESSING, ErrorSeverity.HIGH, context)


class ValidationError(YTBotError):
    """Data validation errors"""
    def __init__(self, message: str, context: Dict = None):
        super().__init__(message, ErrorCategory.VALIDATION, ErrorSeverity.LOW, context)


class DatabaseError(YTBotError):
    """Database operation errors"""
    def __init__(self, message: str, context: Dict = None):
        super().__init__(message, ErrorCategory.DATABASE, ErrorSeverity.HIGH, context)


class UploadError(YTBotError):
    """Upload-related errors"""
    def __init__(self, message: str, platform: str = None, context: Dict = None):
        context = context or {}
        if platform:
            context['platform'] = platform
        super().__init__(message, ErrorCategory.UPLOAD, ErrorSeverity.HIGH, context)


class ConfigurationError(YTBotError):
    """Configuration-related errors"""
    def __init__(self, message: str, context: Dict = None):
        super().__init__(message, ErrorCategory.CONFIGURATION, ErrorSeverity.CRITICAL, context)


class ErrorHandler:
    """Centralized error handling and logging"""
    
    def __init__(self, logger_name: str = None):
        self.logger = logging.getLogger(logger_name or __name__)
        self.error_stats = {
            'total_errors': 0,
            'errors_by_category': {},
            'errors_by_severity': {}
        }
    
    def handle_error(self, error: Union[Exception, YTBotError], context: Dict = None) -> YTBotError:
        """Handle and log an error"""
        # Convert regular exceptions to YTBotError
        if not isinstance(error, YTBotError):
            ytbot_error = YTBotError(
                str(error),
                self._categorize_error(error),
                ErrorSeverity.MEDIUM,
                context
            )
        else:
            ytbot_error = error
            if context:
                ytbot_error.context.update(context)
        
        # Update statistics
        self._update_error_stats(ytbot_error)
        
        # Log the error
        self._log_error(ytbot_error)
        
        return ytbot_error
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Automatically categorize errors based on type and message"""
        error_type = type(error).__name__.lower()
        error_message = str(error).lower()
        
        # Network-related errors
        if any(keyword in error_type for keyword in ['connection', 'timeout', 'network']):
            return ErrorCategory.NETWORK
        if any(keyword in error_message for keyword in ['connection', 'timeout', 'network']):
            return ErrorCategory.NETWORK
        
        # File I/O errors
        if any(keyword in error_type for keyword in ['file', 'io', 'permission']):
            return ErrorCategory.FILE_IO
        if any(keyword in error_message for keyword in ['file not found', 'permission denied']):
            return ErrorCategory.FILE_IO
        
        # API errors
        if any(keyword in error_message for keyword in ['api', 'http', 'status code']):
            return ErrorCategory.API
        
        # Database errors
        if any(keyword in error_type for keyword in ['database', 'sqlite']):
            return ErrorCategory.DATABASE
        
        return ErrorCategory.UNKNOWN
    
    def _update_error_stats(self, error: YTBotError):
        """Update error statistics"""
        self.error_stats['total_errors'] += 1
        
        # Update category stats
        category = error.category.value
        self.error_stats['errors_by_category'][category] = \
            self.error_stats['errors_by_category'].get(category, 0) + 1
        
        # Update severity stats
        severity = error.severity.value
        self.error_stats['errors_by_severity'][severity] = \
            self.error_stats['errors_by_severity'].get(severity, 0) + 1
    
    def _log_error(self, error: YTBotError):
        """Log error with appropriate level"""
        error_dict = error.to_dict()
        
        # Choose log level based on severity
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"CRITICAL ERROR: {error.message}", extra=error_dict)
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(f"ERROR: {error.message}", extra=error_dict)
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"WARNING: {error.message}", extra=error_dict)
        else:
            self.logger.info(f"INFO: {error.message}", extra=error_dict)
        
        # Log stack trace for debugging
        if error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self.logger.debug(f"Stack trace for {error.category.value} error:", 
                            exc_info=True)
    
    def get_error_stats(self) -> Dict:
        """Get current error statistics"""
        return self.error_stats.copy()
    
    def reset_stats(self):
        """Reset error statistics"""
        self.error_stats = {
            'total_errors': 0,
            'errors_by_category': {},
            'errors_by_severity': {}
        }


def error_handler(category: ErrorCategory = ErrorCategory.UNKNOWN, 
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 reraise: bool = True):
    """Decorator for automatic error handling"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except YTBotError:
                # Re-raise YTBotErrors as-is
                if reraise:
                    raise
                return None
            except Exception as e:
                # Convert to YTBotError and handle
                handler = ErrorHandler(func.__module__)
                ytbot_error = YTBotError(str(e), category, severity, {
                    'function': func.__name__,
                    'args': str(args)[:100],  # Truncate for logging
                    'kwargs': str(kwargs)[:100]
                })
                handler.handle_error(ytbot_error)
                
                if reraise:
                    raise ytbot_error
                return None
        return wrapper
    return decorator


def retry_on_error(max_retries: int = 3, 
                  retry_categories: list = None,
                  delay: float = 1.0,
                  backoff_factor: float = 2.0):
    """Decorator for retrying operations on specific error types"""
    if retry_categories is None:
        retry_categories = [ErrorCategory.NETWORK, ErrorCategory.API]
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except YTBotError as e:
                    last_error = e
                    
                    # Check if we should retry this error category
                    if e.category not in retry_categories:
                        raise
                    
                    # Don't retry on last attempt
                    if attempt == max_retries:
                        raise
                    
                    # Wait before retrying
                    import time
                    wait_time = delay * (backoff_factor ** attempt)
                    time.sleep(wait_time)
                    
                    logging.getLogger(func.__module__).warning(
                        f"Retrying {func.__name__} (attempt {attempt + 2}/{max_retries + 1}) "
                        f"after {wait_time:.1f}s due to {e.category.value} error: {e.message}"
                    )
                except Exception as e:
                    # Convert to YTBotError and apply same logic
                    handler = ErrorHandler(func.__module__)
                    ytbot_error = handler.handle_error(e)
                    last_error = ytbot_error
                    
                    if ytbot_error.category not in retry_categories:
                        raise ytbot_error
                    
                    if attempt == max_retries:
                        raise ytbot_error
                    
                    import time
                    wait_time = delay * (backoff_factor ** attempt)
                    time.sleep(wait_time)
            
            # This should never be reached, but just in case
            if last_error:
                raise last_error
                
        return wrapper
    return decorator


# Global error handler instance
global_error_handler = ErrorHandler("ytbot.global")


def handle_error(error: Exception, context: Dict = None) -> YTBotError:
    """Global error handling function"""
    return global_error_handler.handle_error(error, context)


def get_global_error_stats() -> Dict:
    """Get global error statistics"""
    return global_error_handler.get_error_stats()