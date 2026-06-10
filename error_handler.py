"""
错误处理工具模块
提供统一的错误处理和重试机制
"""

import functools
import time
import logging
from typing import Callable, Any, Optional, Type, Tuple
import traceback

logger = logging.getLogger(__name__)


class APIError(Exception):
    """API调用错误"""
    pass


class DataFetchError(Exception):
    """数据获取错误"""
    pass


class RateLimitError(APIError):
    """API限流错误"""
    pass


class TimeoutError(APIError):
    """API超时错误"""
    pass


def retry_on_error(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """重试装饰器
    
    Args:
        max_retries: 最大重试次数
        retry_delay: 初始重试延迟（秒）
        backoff_factor: 退避因子
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = retry_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(f"函数 {func.__name__} 第{attempt + 1}次调用失败: {e}, {delay}秒后重试...")
                        
                        if on_retry:
                            on_retry(attempt, e)
                        
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(f"函数 {func.__name__} 调用失败（已重试{max_retries}次）: {e}")
                        raise
            
            raise last_exception
        
        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    error_message: str = "执行失败",
    log_error: bool = True,
    **kwargs
) -> Any:
    """安全执行函数
    
    Args:
        func: 要执行的函数
        args: 函数参数
        default: 失败时的默认值
        error_message: 错误消息
        log_error: 是否记录错误
        kwargs: 函数关键字参数
    
    Returns:
        函数返回值或默认值
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_error:
            logger.error(f"{error_message}: {e}")
            logger.debug(traceback.format_exc())
        return default


def format_error_message(error: Exception) -> str:
    """格式化错误消息"""
    error_type = type(error).__name__
    error_msg = str(error)
    
    # 常见错误类型映射
    error_messages = {
        'ConnectionError': '网络连接失败',
        'TimeoutError': '请求超时',
        'RateLimitError': 'API调用频率超限',
        'KeyError': '数据字段缺失',
        'ValueError': '数据格式错误',
        'TypeError': '数据类型错误',
        'FileNotFoundError': '文件未找到',
        'PermissionError': '权限不足',
    }
    
    friendly_msg = error_messages.get(error_type, error_msg)
    
    return f"[{error_type}] {friendly_msg}"


def handle_api_error(func):
    """API错误处理装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RateLimitError as e:
            logger.warning(f"API限流: {e}")
            raise
        except TimeoutError as e:
            logger.warning(f"API超时: {e}")
            raise
        except APIError as e:
            logger.error(f"API错误: {e}")
            raise
        except Exception as e:
            logger.error(f"未知错误: {e}")
            logger.debug(traceback.format_exc())
            raise APIError(f"API调用失败: {format_error_message(e)}")
    
    return wrapper


class ErrorContext:
    """错误上下文管理器"""
    
    def __init__(self, operation: str, raise_on_error: bool = False):
        self.operation = operation
        self.raise_on_error = raise_on_error
        self.error = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error = exc_val
            logger.error(f"{self.operation}失败: {format_error_message(exc_val)}")
            
            if not self.raise_on_error:
                return True  # 抑制异常
        
        return False
    
    def __str__(self):
        if self.error:
            return f"{self.operation}: {format_error_message(self.error)}"
        return f"{self.operation}: 成功"


def validate_data(data: Any, data_type: type, min_length: int = 0) -> bool:
    """验证数据有效性"""
    if data is None:
        return False
    
    if not isinstance(data, data_type):
        return False
    
    if hasattr(data, '__len__') and len(data) < min_length:
        return False
    
    return True


def safe_convert(value: Any, target_type: type, default: Any = None) -> Any:
    """安全类型转换"""
    try:
        return target_type(value)
    except (ValueError, TypeError):
        return default


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """截断字符串"""
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, operation: str):
        self.operation = operation
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.duration
        
        if duration > 5:  # 超过5秒记录警告
            logger.warning(f"{self.operation}耗时较长: {duration:.2f}秒")
        else:
            logger.debug(f"{self.operation}完成: {duration:.2f}秒")
        
        return False
    
    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0


def log_function_call(func):
    """函数调用日志装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f"调用函数 {func.__name__}")
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.debug(f"函数 {func.__name__} 执行成功 ({duration:.2f}秒)")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"函数 {func.__name__} 执行失败 ({duration:.2f}秒): {e}")
            raise
    
    return wrapper


# 创建全局错误处理器实例
error_handler = {
    'format_error': format_error_message,
    'validate_data': validate_data,
    'safe_convert': safe_convert,
    'truncate_string': truncate_string,
}
