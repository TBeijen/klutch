import json
import logging
import math
from datetime import datetime
from typing import Iterable
from typing import List

from kubernetes import client

from klutch.config import Config

logger = logging.getLogger(__name__)


def find_triggers(config: Config) -> List[client.models.v1_config_map.V1ConfigMap]:
    """Find any configmap labeled as trigger and return it. Recent first."""
    resp = client.CoreV1Api().list_namespaced_config_map(
        config.namespace, label_selector="{}={}".format(config.cm_trigger_label_key, config.cm_trigger_label_value,),
    )
    return sorted(resp.items, key=lambda n: n.metadata.creation_timestamp.timestamp(), reverse=True,)


def validate_trigger(config: Config, trigger: client.models.v1_config_map.V1ConfigMap):
    """Evaluate trigger ConfigMap age, returning True if valid."""
    cm_ts = trigger.metadata.creation_timestamp.timestamp()
    now = datetime.now().timestamp()
    return cm_ts + config.trigger_max_age >= now


def delete_trigger(trigger: client.models.v1_config_map.V1ConfigMap):
    return client.CoreV1Api().delete_namespaced_config_map(trigger.metadata.name, trigger.metadata.namespace)


def create_status(config, status: list):
    config_map = client.models.v1_config_map.V1ConfigMap(
        data={"status": json.dumps(status)},
        metadata=client.models.V1ObjectMeta(
            name=config.cm_status_name, labels={config.cm_status_label_key: config.cm_status_label_value},
        ),
    )
    return client.CoreV1Api().create_namespaced_config_map(config.namespace, config_map)


def find_hpas(config: Config,) -> Iterable[client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler]:
    """Find any HorizontalPodAutoscaler having klutch annotation."""
    resp = client.AutoscalingV1Api().list_horizontal_pod_autoscaler_for_all_namespaces()
    return filter(lambda h: config.hpa_annotation_enabled in h.metadata.annotations, resp.items)


def scale_hpa(
    config: Config, hpa: client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler,
) -> client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler:
    """Scale up hpa. Write status in annotation. Return patched hpa."""
    # Raises ValueError or TypeError if value can not pe parsed into int
    scale_perc_of_actual = int(hpa.metadata.annotations.get(config.hpa_annotation_scale_perc_of_actual))
    if hpa.metadata.annotations.get(config.hpa_annotation_status):
        raise ValueError("Can not scale up HPA. Already has been scaled up.")

    # values used in patching and logging
    name = hpa.metadata.name
    namespace = hpa.metadata.namespace
    uid = hpa.metadata.uid
    spec_min_replicas = hpa.spec.min_replicas
    spec_max_replicas = hpa.spec.max_replicas
    target_min_replicas = math.ceil(hpa.status.current_replicas * scale_perc_of_actual / 100)

    if target_min_replicas <= spec_min_replicas:
        raise ValueError("Can not scale up HPA, would decrease minReplicas (deployment not correctly started?).")

    if target_min_replicas > spec_max_replicas:
        logger.warning(
            f"Limiting minReplicas to maxReplicas value of {spec_max_replicas} instead of intended value {target_min_replicas} for HorizontalPodAutoscaler (namespace={namespace}, name={name}, uid={uid})"
        )
        target_min_replicas = hpa.spec.max_replicas

    status = {
        "originalMinReplicas": hpa.spec.min_replicas,
        "originalCurrentReplicas": hpa.status.current_replicas,
        "appliedMinReplicas": target_min_replicas,
        "appliedAt": datetime.now().timestamp(),
    }
    patch = {
        "metadata": {"annotations": {config.hpa_annotation_status: json.dumps(status)}},
        "spec": {"minReplicas": target_min_replicas},
    }
    patched_hpa = client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler(name, namespace, patch,)
    logger.info(
        f"Scaled minReplicas from {spec_min_replicas} to {target_min_replicas} for HorizontalPodAutoscaler (namespace={namespace}, name={name}, uid={uid})"
    )

    return patched_hpa
