import threading
import logging

logger = logging.getLogger(__name__)

def process_with_timeout(func, args=(), timeout=30):
    """Ejecutar una función con timeout usando threading"""
    result = [None]
    error = [None]
    
    def worker():
        try:
            if isinstance(args, dict):
                ret = func(**args)
            else:
                ret = func(*args)
            result[0] = ret
        except Exception as e:
            error[0] = e
    
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        logger.error("Timeout en operación")
        raise TimeoutError("Operation timed out")
    
    if error[0] is not None:
        raise error[0]
    
    return result[0] if result else None
