import logging
import threading
import time


class TriggerConfigMap(threading.Thread):
    logger = None

    def __init__(self, queue, config, name_suffix=""):
        super().__init__()
        name = self.__class__.__name__ + name_suffix

        self.should_stop = False
        self.name = name
        self.queue = queue
        self.config = config
        self.logger = logging.getLogger(name)
        self.logger.info(f"Started {name}")

    def run(self):
        try:
            while True:
                if self.should_stop:
                    self.logger.info("stopping")
                    return
                self.logger.info("running")
                time.sleep(1)
        finally:
            self.logger.info("ended")

    def stop(self):
        self.logger.info("Received stop()")
        self.should_stop = True
