Threads

* Trigger-ConfigMap

    * Sets trigger var

* Trigger-SQS

    * Sets trigger var

* Trigger-Webhook

    * Sets trigger var

* Scale-loop

    * Starts when trigger found
    * If ongoing, reconcile
    * If not ongoing, check for orphans (can be split of to separate thread, lower freq.)

* Process-orphans-loop

    * Searches for HPA




* https://superfastpython.com/extend-thread-class/
* https://superfastpython.com/interrupt-the-main-thread-in-python/
* https://www.geeksforgeeks.org/python-different-ways-to-kill-a-thread/
* https://blog.miguelgrinberg.com/post/how-to-kill-a-python-thread

* Testing excepthook: https://github.com/pytest-dev/pytest/discussions/9193#discussioncomment-1463715

* k3d e2e tests: https://github.com/marketplace/actions/setup-k3d-k3s


TODO:
* instance key/value on configmap/trigger but also status annotations etc. Allowing multiple klutch to run in same cluster. (Any use case for that?)


Old

```python
import logging
import time

from klutch.exit_handler import ExitHandler
from klutch.old_config import configure_kubernetes
from klutch.old_config import get_config
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

```
