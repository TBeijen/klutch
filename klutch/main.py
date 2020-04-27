import logging
import time

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
    last_orphan_scan = int(time.time())
    while True:
        try:
            # client = get_kubernetes()
            configure_kubernetes()

            logger.info("Starting control loop")

            is_ongoing = process_ongoing(config)
            if not is_ongoing:
                is_ongoing = process_triggers(config)
            if not is_ongoing:
                now = int(time.time())
                if now - last_orphan_scan > config.orphan_scan_interval:
                    last_orphan_scan = now
                    process_orphans(config)
        except Exception as e:
            logger.exception("An error occured: %s", e)

        with handler.safe_exit():
            time.sleep(config.interval)
