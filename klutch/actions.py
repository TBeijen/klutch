from datetime import datetime
from typing import Iterable
from typing import List

from kubernetes import client

from klutch.config import Config


def find_triggers(config: Config) -> List[client.models.v1_config_map.V1ConfigMap]:
    """Find any configmap labeled as trigger and return it. Recent first."""
    resp = client.CoreV1Api().list_namespaced_config_map(
        config.namespace,
        label_selector="{}={}".format(
            config.cm_trigger_label_key, config.cm_trigger_label_value,
        ),
    )
    return sorted(
        resp.items,
        key=lambda n: n.metadata.creation_timestamp.timestamp(),
        reverse=True,
    )


def validate_trigger(config: Config, trigger: client.models.v1_config_map.V1ConfigMap):
    """Evaluate trigger ConfigMap age, returning True if valid."""
    cm_ts = trigger.metadata.creation_timestamp.timestamp()
    now = datetime.now().timestamp()
    return cm_ts + config.trigger_max_age >= now


def delete_trigger(trigger: client.models.v1_config_map.V1ConfigMap):
    return client.CoreV1Api().delete_namespaced_config_map(
        trigger.metadata.name, trigger.metadata.namespace
    )


def find_hpas(
    config: Config,
) -> Iterable[client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler]:
    """Find any HorizontalPodAutoscaler having klutch annotation."""
    resp = client.AutoscalingV1Api().list_horizontal_pod_autoscaler_for_all_namespaces()
    return filter(
        lambda h: config.hpa_annotation_enabled in h.metadata.annotations, resp.items
    )
