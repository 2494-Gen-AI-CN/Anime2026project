import logging

class Logger():
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")
        self.console_handler = logging.StreamHandler()
        self.console_handler.setLevel(logging.DEBUG) # Console only prints DEBUG and Above
        self.console_handler.setFormatter(self.formatter)
        self.logger.addHandler(self.console_handler)

    def debug(self, message):
        self.logger.debug(message)
    def info(self, message):
        self.logger.info(message)
    def critical(self, message):
        self.logger.critical(message)
    def warning(self, message):
        self.logger.warning(message)
    def error(self, message):
        self.logger.error(message)
