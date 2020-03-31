import logging

from kubernetes import client
from kubernetes import config
from kubernetes.config.config_exception import ConfigException

logger = logging.getLogger(__name__)


def get_kubernetes():
    try:
        config.load_incluster_config()
        logger.info("Configured kube_client from ServiceAccount")
    except ConfigException:
        config.load_kube_config()  # evaluates KUBECONFIG env var if present.
        logger.info("Configured kube_client from config file")
    return client
