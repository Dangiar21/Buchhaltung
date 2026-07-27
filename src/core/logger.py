import logging
import queue
import sys

class QueueLogHandler(logging.Handler):
    """
    A custom logging handler that pushes formatted log messages to a queue.
    """
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put(msg + '\n')
        except Exception:
            self.handleError(record)

class StreamToLogger:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            if "AFC is enabled" in line:
                continue
            self.logger.log(self.level, line.rstrip('\n'))

    def flush(self):
        pass

class NoAFCFilter(logging.Filter):
    def filter(self, record):
        return "AFC is enabled" not in record.getMessage()

def setup_logger(log_queue, log_file="app.log"):
    """
    Sets up the root logger with a FileHandler (DEBUG) and a QueueHandler (INFO).
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Silence noisy third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("google.api_core").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("absl").setLevel(logging.WARNING)
    logging.getLogger("grpc").setLevel(logging.WARNING)
    
    # Clear existing handlers if any
    if logger.hasHandlers():
        logger.handlers.clear()

    # Redirect sys.stdout and sys.stderr
    sys.stdout = StreamToLogger(logger, logging.INFO)
    sys.stderr = StreamToLogger(logger, logging.ERROR)

    # Formatter
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    gui_formatter = logging.Formatter('%(message)s')
    
    afc_filter = NoAFCFilter()

    # File Handler
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(afc_filter)
        logger.addHandler(file_handler)
    except Exception as e:
        pass

    # Queue Handler (for GUI)
    queue_handler = QueueLogHandler(log_queue)
    queue_handler.setLevel(logging.INFO)
    queue_handler.setFormatter(gui_formatter)
    queue_handler.addFilter(afc_filter)
    logger.addHandler(queue_handler)

    return logger
