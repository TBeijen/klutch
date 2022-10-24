import logging
import signal
import sys
import time
from argparse import ArgumentParser
from queue import Queue

from nx_config import add_cli_options  # type: ignore
from nx_config import fill_config_from_path  # type: ignore
from nx_config import resolve_config_path  # type: ignore

from klutch.config import config
from klutch.config import configure_kubernetes
from klutch.threads import TriggerConfigMap
from klutch.threads import TriggerWebHook


class ThreadHandler:

    """
    ExitHandler ensures main loop finishes before exiting.

    Class for:
    * Intercepting SIGINT/SIGTERM, preventing exit during main loop execution phase.
    * Providing context handler allowing exit during main loop pause phase.

    See: https://stackoverflow.com/questions/18499497/how-to-process-sigterm-signal-gracefully (sample implementations)
    """

    # should_exit = False
    # safe_to_exit = False

    def __init__(self):
        self.threads = []
        self.timeout = 10
        self.logger = logging.getLogger(self.__class__.__name__)
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

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
        for t in self.threads:
            t.stop()
        while True:
            if not any(t.is_alive() for t in self.threads):
                self.logger.info("All threads stopped. Exiting.")
                sys.exit(0)
            if self.timeout > 0:
                self.logger.info("Waiting for threads to stop.")
                self.timeout -= 1
                time.sleep(1)
            else:
                self.logger.error("Threads failed to stop within timeout. Aborting.")
                sys.exit(1)

        # self.should_exit = True
        # self.exit_if_needed()

    # def exit_if_needed(self):
    #     """Do actual exit, only if needed and safe to do now."""
    #     if self.should_exit and self.safe_to_exit:
    #         logger.info("Safe to exit. Exiting....")
    #         sys.exit(0)

    # @contextlib.contextmanager
    # def safe_exit(self):
    #     """
    #     Context manager for code executionduring which program can safely exit.

    #     Wraps sleep of main loop.
    #     If having caught term. signal during main loop, exit immediately when entering context.

    #     See: https://docs.python.org/3/library/contextlib.html
    #     """
    #     self.safe_to_exit = True
    #     self.exit_if_needed()
    #     yield
    #     self.safe_to_exit = False


# parser = ArgumentParser()
# parser.add_argument("--name")
# add_cli_options(parser, config_t=type(config))
# args = parser.parse_args()

# fill_config_from_path(config, path=resolve_config_path(cli_args=args))


def main():
    """Set up logger and trigger control loop."""
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
    if config.trigger_web_hook.enabled:
        threads.add(TriggerWebHook(trigger_queue, config))
    if config.trigger_config_map.enabled:
        threads.add(TriggerConfigMap(trigger_queue, config))
    threads.start_all()
