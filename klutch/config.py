import argparse
import logging
import os

from kubernetes import config

logger = logging.getLogger(__name__)


class Config:

    debug = False
    dry_run = False
    interval = 10  # seconds
    cooldown = 30  # seconds
    trigger_max_age = 300  # seconds
    namespace = None

    cm_trigger_label_key = "klutch.it/trigger"
    cm_trigger_label_value = "1"
    cm_status_name = "klutch-status"
    cm_status_label_key = "klutch.it/status"
    cm_status_label_value = "1"
    hpa_annotation_enabled = "klutch.it/enabled"
    hpa_annotation_status = "klutch.it/status"
    hpa_annotation_scale_perc_of_actual = "klutch.it/scale-percentage-of-actual"

    def __init__(self, args):
        self.debug = args.debug
        self.dry_run = args.dry_run
        if args.namespace:
            self.namespace = args.namespace
        else:
            self.namespace = open("/var/run/secrets/kubernetes.io/serviceaccount/namespace").read()


def _get_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug", help="Debug mode", action="store_true",
    )
    parser.add_argument(
        "--dry-run", help="Do not change anything", action="store_true",
    )
    parser.add_argument(
        "--namespace",
        help="Namespace to store status in. By default will use the namespace klutch is deployed in. (Required when running out of cluster)",
    )
    return parser.parse_args(args)


def get_config(args=None):
    """Return config object, reflecting defaults and optional cli args."""
    return Config(_get_args(args))


def configure_kubernetes():
    """Configure kubernetes client."""
    try:
        config.load_incluster_config()
        logger.debug("Configured kube_client from ServiceAccount")
    except config.ConfigException:
        # Kubernetes SDK evaluates KUBECONFIG, however does so directly in module,
        # which is evaluated on directly on import, making it hard to mock.
        # For that reason evaluating here and passing in via config_file.
        config.load_kube_config(config_file=os.environ.get("KUBECONFIG"))
        logger.debug("Configured kube_client from config file")
