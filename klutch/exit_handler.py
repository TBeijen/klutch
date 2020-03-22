import contextlib
import logging
import signal
import sys


class ExitHandler:
    """
    Class for:
    * Intercepting SIGINT/SIGTERM, preventing exit during main loop execution phase.
    * Providing context handler allowing exit during main loop pause phase.
    
    See: https://stackoverflow.com/questions/18499497/how-to-process-sigterm-signal-gracefully (sample implementations)
    """
    should_exit = False
    safe_to_exit = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def handle_signal(self, signum, frame):
        self.should_exit = True
        self.exit_if_needed()

    def exit_if_needed(self):
        """
        Do actual exit, only if needed and safe to do now.
        """
        if self.should_exit and self.safe_to_exit:
            sys.exit(0)

    @contextlib.contextmanager
    def safe_exit(self):
        """
        Wraps sleep of main loop, during which the program can safely be exited.
        If having caught term. signal during main loop, exit immediately

        See: https://docs.python.org/3/library/contextlib.html
        """
        self.safe_to_exit = True
        self.exit_if_needed()
        yield
        self.safe_to_exit = False
