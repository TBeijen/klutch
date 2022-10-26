import logging
import signal
import sys
import threading
import time
from argparse import ArgumentParser
from queue import Queue

from nx_config import add_cli_options  # type: ignore
from nx_config import fill_config_from_path  # type: ignore
from nx_config import resolve_config_path  # type: ignore

from klutch.config import config
from klutch.config import configure_kubernetes
from klutch.threads import ProcessScaler
from klutch.threads import TriggerConfigMap
from klutch.threads import TriggerWebHook


class ThreadHandler:

    """
    ThreadHandler.

    - Starts multiple threads
    - Traps SIGINT/SIGTERM and gracefully stops threads before ending program
    - Registers exception_hook to attempt graceful shutdown when unhandled exception is raised in thread
    """

    def __init__(self):
        self.threads = []
        self.timeout = 10
        self.logger = logging.getLogger(self.__class__.__name__)
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
        self._setup_excepthook()

    def add(self, thread):
        self.threads.append(thread)

    def start_all(self):
        for t in self.threads:
            t.start()
        for t in self.threads:
            t.join()

    def handle_signal(self, signum, frame):
        self.logger.info(
            "Received termination signal {sig_name} ({signum})".format(
                sig_name=signal.Signals(signum).name, signum=signum
            )
        )
        self._stop_program()

    def _stop_program(self):
        """
        Will stop all threads gracefully.

        If one of threads raised an exception caught by excepthook, this thread will
        not join, remain alive and program will exit with exit code 1.
        """
        for t in self.threads:
            t.stop()
        while True:
            if not any(t.is_alive() for t in self.threads):
                self.logger.info("All threads stopped. Exiting.")
                sys.exit(0)
            if self.timeout > 0:
                self.logger.debug("Waiting for threads to stop.")
                self.timeout -= 1
                time.sleep(1)
            else:
                self.logger.error("Threads failed to stop within timeout. Aborting.")
                sys.exit(1)

    def _setup_excepthook(self):
        _self = self

        def hook(args: threading.ExceptHookArgs):
            print(args)
            _self._stop_program()

        threading.excepthook = hook


def main():
    """Set up logger, configure application and start threads."""
    parser = ArgumentParser()
    add_cli_options(parser, config_t=type(config))
    args = parser.parse_args()

    fill_config_from_path(config, path=resolve_config_path(cli_args=args))

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.DEBUG if config.common.debug else logging.INFO,
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Config: {config}")
    configure_kubernetes()
    logger.info(f"Initializing")

    trigger_queue = Queue()
    threads = ThreadHandler()
    threads.add(ProcessScaler(trigger_queue, config))
    if config.trigger_web_hook.enabled:
        threads.add(TriggerWebHook(trigger_queue, config))
    if config.trigger_config_map.enabled:
        threads.add(TriggerConfigMap(trigger_queue, config))
    threads.start_all()
