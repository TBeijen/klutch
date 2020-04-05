import logging
import os

from kubernetes import client
from kubernetes import config
from kubernetes.config.config_exception import ConfigException

logger = logging.getLogger(__name__)


def get_kubernetes():
    try:
        config.load_incluster_config()
        logger.debug("Configured kube_client from ServiceAccount")
    except ConfigException:
        # Kubernetes SDK evaluates KUBECONFIG, however does so directly in module,
        # which is evaluated on directly on import, making it hard to mock.
        # For that reason evaluating here and passing in via config_file.
        config.load_kube_config(config_file=os.environ.get("KUBECONFIG"))
        logger.debug("Configured kube_client from config file")
    return client
