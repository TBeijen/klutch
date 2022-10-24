import logging
import os
from datetime import timedelta
from typing import Optional

from kubernetes import config as kubernetes_config  # type: ignore
from nx_config import Config  # type: ignore
from nx_config import ConfigSection  # type: ignore
from nx_config import validate  # type: ignore

logger = logging.getLogger(__name__)


class CommonSectionMixin:

    """
    nx_config is quite restrictive in what attributes it allows to be set (None).

    This mixin provides an attribute, not part of config, that can be used to store found in-cluster namespace.
    """

    _in_cluster_namespace: str = ""
    klutch_namespace: str = ""

    @property
    def namespace(self) -> str:
        return self.klutch_namespace or self._in_cluster_namespace


class CommonSection(CommonSectionMixin, ConfigSection):
    debug: bool = False
    # Period (seconds) after which to restore original values
    duration: int = 300
    # Interval (seconds) used to reconcile hpa status
    reconcile_interval: int = 10
    # Interval (seconds) used to scan for orphans
    scan_orphans_duration: int = 600
    # Only needed when running out-of-cluster
    klutch_namespace: str = ""

    # Should not typically need changing: Annotation names used to configure klutch to act on HPAs
    hpa_annotation_enabled: str = "klutch.it/enabled"
    hpa_annotation_scale_perc_of_actual: str = "klutch.it/scale-percentage-of-actual"

    # Should not typically need changing: Annotation name used to store state data while scaling is in progress
    hpa_annotation_status: str = "klutch.it/status"

    # Should not typically need changing: Name and label of configmap klutch uses to store status of ongoing scaling in
    cm_status_name: str = "klutch-status"
    cm_status_label_key: str = "klutch.it/status"
    cm_status_label_value: str = "1"

    @validate
    def validate_reconcile_interval(self):
        if self.reconcile_interval > self.duration:
            raise ValueError("reconconcile_interval cannot be larger than duration")
        print(self._in_cluster_namespace)

    @validate
    def validate_klutch_namespace(self):
        try:
            self._in_cluster_namespace = open("/var/run/secrets/kubernetes.io/serviceaccount/namespace").read()
        except FileNotFoundError:
            self._in_cluster_namespace = None
        if not self._in_cluster_namespace and not self.klutch_namespace:
            raise ValueError("When running out of cluster, klutch_namespace needs to be set")


class TriggerWebHookSection(ConfigSection):
    enabled: bool = True
    address: str = "127.0.0.1"
    port: int = 8123


class TriggerConfigMapSection(ConfigSection):
    enabled: bool = True
    # Interval (seconds) used to scan for trigger configmap
    scan_interval: int = 10
    # Should not typically need changing: Name and label of configmap that can be added as trigger
    cm_trigger_label_key: str = "klutch.it/trigger"
    cm_trigger_label_value: str = "1"


class KlutchConfig(Config):
    common: CommonSection
    trigger_web_hook: TriggerWebHookSection
    trigger_config_map: TriggerConfigMapSection


config = KlutchConfig()


def configure_kubernetes():
    """Configure kubernetes client."""
    try:
        kubernetes_config.load_incluster_config()
        logger.info("Configured kube_client from ServiceAccount")
    except kubernetes_config.ConfigException:
        # Kubernetes SDK evaluates KUBECONFIG, however does so directly in module,
        # which is evaluated on directly on import, making it hard to mock.
        # For that reason evaluating here and passing in via config_file.
        kubernetes_config.load_kube_config(config_file=os.environ.get("KUBECONFIG"))
        logger.info("Configured kube_client from config file")
