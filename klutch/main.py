import logging
from time import sleep

from .exit_handler import ExitHandler


def main():
    """Set up api, logger and trigger control loop."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
    )
    control_loop()


def control_loop():
    handler = ExitHandler()
    while True:
        print("Doing things")
        sleep(2)
        print("Finished doing things")

        with handler.safe_exit():
            sleep(5)
