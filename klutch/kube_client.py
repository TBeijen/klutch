import logging
import os

import pykube

logger = logging.getLogger(__name__)


def get_kube_client():
    try:
        config = pykube.KubeConfig.from_service_account()
        logger.info("Configured kube_client from ServiceAccount")
    except FileNotFoundError:
        # local testing
        config_file = os.getenv("KUBECONFIG", "~/.kube/config")
        config = pykube.KubeConfig.from_file(config_file)
        logger.info(f"Configured kube_client from config file: {config_file}")
    client = pykube.HTTPClient(config)
    return client
