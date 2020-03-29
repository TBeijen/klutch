import logging
import os

import pykube
from kubernetes import client
from kubernetes import config
from kubernetes.config.config_exception import ConfigException

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


def get_kubernetes():
    try:
        config.load_incluster_config()
        logger.info("Configured kube_client from ServiceAccount")
    except ConfigException:
        config.load_kube_config()  # evaluates KUBECONFIG env var if present.
        logger.info("Configured kube_client from config file")

    v1 = client.CoreV1Api()
    print("Listing pods with their IPs:")
    ret = v1.list_pod_for_all_namespaces(watch=False)
    for i in ret.items:
        print(
            "{}\t{}\t{}".format(i.status.pod_ip, i.metadata.namespace, i.metadata.name)
        )
