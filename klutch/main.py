import logging
from time import sleep

from klutch.config import configure_kubernetes
from klutch.config import get_config
from klutch.exit_handler import ExitHandler
from klutch.process import process_ongoing
from klutch.process import process_orphans
from klutch.process import process_triggers

logger = logging.getLogger(__name__)


def main(args=None):
    """Set up logger and trigger control loop."""
    config = get_config(args)
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.DEBUG if config.debug else logging.INFO,
    )
    control_loop(config)


def control_loop(config):
    handler = ExitHandler()
    while True:
        try:
            # client = get_kubernetes()
            configure_kubernetes()

            logger.info("Starting control loop")

            is_ongoing = process_ongoing(config)
            if not is_ongoing:
                is_ongoing = process_triggers(config)
            if not is_ongoing:
                process_orphans(config)
        except Exception as e:
            logger.exception("An error occured: %s", e)

        with handler.safe_exit():
            sleep(config.interval)
