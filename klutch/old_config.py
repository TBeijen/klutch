import argparse
import logging
import os

from kubernetes import config  # type: ignore

logger = logging.getLogger(__name__)


class Config:

    debug = False
    interval = 5  # seconds
    duration = 300  # seconds
    trigger_max_age = 300  # seconds
    orphan_scan_interval = 600  # seconds
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
        if args.interval:
            self.interval = int(args.interval)
        if args.duration:
            self.duration = int(args.duration)
        if args.trigger_max_age:
            self.trigger_max_age = int(args.trigger_max_age)
        if args.namespace:
            self.namespace = args.namespace
        else:
            self.namespace = open("/var/run/secrets/kubernetes.io/serviceaccount/namespace").read()


def _get_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug",
        help="Debug mode",
        action="store_true",
    )
    parser.add_argument(
        "--namespace",
        help="Namespace to look for triggers and store status in. By default will use the namespace klutch is deployed in. (Required when running out of cluster)",
    )
    parser.add_argument(
        "--interval",
        help="How frequent to scan for new triggers or ongoing scaling sequences. Default = 5 (seconds).",
    )
    parser.add_argument(
        "--duration",
        help="After this period, HorizontalPodAutoscalers will be restored to their original settings. Default= 300 (seconds).",
    )
    parser.add_argument(
        "--trigger-max-age",
        help="Triggers older than this period will be ignored. Default= 300 (seconds).",
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
