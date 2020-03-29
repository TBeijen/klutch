import logging
from time import sleep

from klutch.exit_handler import ExitHandler
from klutch.kube_client import get_kubernetes

# import pykube
# from klutch.kube_client import get_kube_client


def main():
    """Set up api, logger and trigger control loop."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
    )
    control_loop()


def control_loop():
    handler = ExitHandler()
    while True:
        get_kubernetes()
        # client = get_kube_client()
        # hpa = pykube.HorizontalPodAutoscaler.objects(  # noqa: F841
        #     client, namespace=pykube.all
        # )
        print("Doing things")
        sleep(2)
        print("Finished doing things")

        with handler.safe_exit():
            sleep(5)
