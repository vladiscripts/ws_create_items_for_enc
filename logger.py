import sys
import logging
from logging.handlers import TimedRotatingFileHandler

LOG_FORMATTER = logging.Formatter(
    "%(asctime)s %(levelname)s %(name)s (%(filename)s #%(lineno)d %(threadName)s) — %(message)s")
LOG_FILE = "log.txt"


def get_console_handler():
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(LOG_FORMATTER)
    return console_handler


def get_file_handler():
    # my_handler = RotatingFileHandler(logFile, mode='a', maxBytes=5 * 1024 * 1024, backupCount=1, encoding=None, delay=0)
    file_handler = TimedRotatingFileHandler(LOG_FILE, when='W0', backupCount=2)
    file_handler.setFormatter(LOG_FORMATTER)
    return file_handler


def get_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.addHandler(get_console_handler())
    logger.addHandler(get_file_handler())
    # with this pattern, it's rarely necessary to propagate the error up to parent
    # logger.propagate = False

    logger_peewee = logging.getLogger('peewee')
    logger_peewee.addHandler(logging.StreamHandler())
    logger_peewee.setLevel(logging.INFO)

    return logger


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


if __name__ == '__main__':
    import time, sys

    # logger = logging.getLogger(__name__)
    sys.excepthook = handle_exception
    logger = get_logger("my module name")
    logger.info(__file__)

    while True:
        logger.info("data")
        time.sleep(5)
        # raise RuntimeError("Test unhandled")
        # raise 9
