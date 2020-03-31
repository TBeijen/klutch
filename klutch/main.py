import logging
from time import sleep

from klutch.client import get_kubernetes
from klutch.config import get_args
from klutch.exit_handler import ExitHandler


def main():
    """Set up api, logger and trigger control loop."""
    args = get_args()
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=log_level
    )
    control_loop()


def control_loop():
    handler = ExitHandler()
    while True:
        client = get_kubernetes()

        v1 = client.CoreV1Api()
        print("Listing pods with their IPs:")
        ret = v1.list_pod_for_all_namespaces(watch=False)
        for i in ret.items:
            print(
                "{}\t{}\t{}".format(
                    i.status.pod_ip, i.metadata.namespace, i.metadata.name
                )
            )

        print("Doing things")
        sleep(2)
        print("Finished doing things")

        with handler.safe_exit():
            sleep(5)
