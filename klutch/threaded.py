import logging
import signal
import sys
import time
from queue import Queue

from klutch.config import get_config
from klutch.threads import TriggerConfigMap
from klutch.threads import TriggerWebHook


# logging.basicConfig(
#     format="%(asctime)s %(levelname)s %(name)s: %(message)s",
#     level=logging.DEBUG,
# )
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


def main(args=None):
    """Set up logger and trigger control loop."""
    config = get_config(args)
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.DEBUG if config.debug else logging.INFO,
    )

    # # task executed in a new thread
    # def task():
    #     # block for a moment
    #     sleep(3)
    #     # interrupt the main thread
    #     print('Interrupting main thread now')
    #     interrupt_main()

    # # register the signal handler for this process
    # signal(SIGINT, handle_sigint)

    trigger_queue = Queue()
    threads = ThreadHandler()
    threads.add(TriggerConfigMap(trigger_queue, config, "1"))
    threads.add(TriggerConfigMap(trigger_queue, config, "2"))
    web_thread = TriggerWebHook(trigger_queue, config, "3")
    # web_thread.setDaemon(True)
    threads.add(web_thread)
    threads.start_all()

    # def handle_exit(signalnum, frame):
    #     # terminate
    #     print('Main interrupted! Exiting.')
    #     sys.exit()

    # signal.signal(signal.SIGINT, self.handle_signal)
    # signal.signal(signal.SIGTERM, self.handle_signal)


#     start_all(config)

# def start_all(config):
#     queue = Queue()

#     triggerConfigMap1 = TriggerConfigMap(queue, config, "1")
#     triggerConfigMap2 = TriggerConfigMap(queue, config, "2")
#     triggerConfigMap1.start()
#     triggerConfigMap2.start()

# t_control = threading.Thread(target=control_loop, args=(queue, ))
# t_control.start()

# def start_loop(name, file_name):
#     loop = Loop(queue, name, file_name)
#     loop.start()

# t_loop_1= threading.Thread(target=start_loop, args=("loop1", "loop1.txt"))
# t_loop_1.start()

# t_loop_2= threading.Thread(target=start_loop, args=("loop2", "loop2.txt"))
# t_loop_2.start()
