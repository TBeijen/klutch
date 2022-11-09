import json
import logging
import math
from datetime import datetime
from typing import Iterable
from typing import List
from typing import Tuple

from kubernetes import client  # type: ignore

from klutch.config import KlutchConfig
from klutch.status import create_hpa_status
from klutch.status import HpaStatus

logger = logging.getLogger(__name__)


def find_cm_triggers(config: KlutchConfig) -> List[client.models.v1_config_map.V1ConfigMap]:
    """Find any configmap labeled as trigger and return it. Recent first."""
    resp = client.CoreV1Api().list_namespaced_config_map(
        config.common.namespace,
        label_selector="{}={}".format(
            config.trigger_config_map.cm_trigger_label_key,
            config.trigger_config_map.cm_trigger_label_value,
        ),
    )
    return sorted(
        resp.items,
        key=lambda n: n.metadata.creation_timestamp.timestamp(),
        reverse=True,
    )


def validate_cm_trigger(config: KlutchConfig, trigger: client.models.v1_config_map.V1ConfigMap) -> bool:
    """Evaluate trigger ConfigMap age, returning True if valid."""
    cm_ts = trigger.metadata.creation_timestamp.timestamp()
    now = datetime.now().timestamp()
    return cm_ts + config.trigger_config_map.max_age >= now


def delete_cm_trigger(trigger: client.models.v1_config_map.V1ConfigMap):
    return client.CoreV1Api().delete_namespaced_config_map(trigger.metadata.name, trigger.metadata.namespace)


def find_cm_status(config: KlutchConfig) -> List[client.models.v1_config_map.V1ConfigMap]:
    """Find any ConfigMap labeled as status and return it. Recent first."""
    resp = client.CoreV1Api().list_namespaced_config_map(
        config.common.namespace,
        label_selector="{}={}".format(
            config.common.cm_status_label_key,
            config.common.cm_status_label_value,
        ),
    )
    return sorted(
        resp.items,
        key=lambda n: n.metadata.creation_timestamp.timestamp(),
        reverse=True,
    )


def create_cm_status(config: KlutchConfig, status_list: List[HpaStatus]) -> client.models.v1_config_map.V1ConfigMap:
    config_map = client.models.v1_config_map.V1ConfigMap(
        data={"status": json.dumps([s.dict() for s in status_list])},
        metadata=client.models.V1ObjectMeta(
            name=config.common.cm_status_name,
            labels={config.common.cm_status_label_key: config.common.cm_status_label_value},
        ),
    )
    return client.CoreV1Api().create_namespaced_config_map(config.common.namespace, config_map)


def delete_cm_status(status: client.models.v1_config_map.V1ConfigMap):
    return client.CoreV1Api().delete_namespaced_config_map(status.metadata.name, status.metadata.namespace)


def find_hpas(
    config: KlutchConfig,
) -> Iterable[client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler]:
    """Find any HorizontalPodAutoscaler having klutch annotation."""
    resp = client.AutoscalingV1Api().list_horizontal_pod_autoscaler_for_all_namespaces()
    k = config.common.hpa_annotation_enabled_key
    v = config.common.hpa_annotation_enabled_value
    return filter(lambda h: h.metadata.annotations.get(k, None) == v, resp.items)


def scale_hpa(
    config: KlutchConfig,
    hpa: client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler,
    logger: logging.Logger,
) -> Tuple[HpaStatus, client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler]:
    """
    Scale up HPA. Return status as well as patched HPA.

    Raises: ValueError, TypeError
    """

    hpa_repr = _hpa_repr(hpa)
    scale_perc_of_actual = int(hpa.metadata.annotations.get(config.common.hpa_annotation_scale_perc_of_actual))

    if hpa.metadata.annotations.get(config.common.hpa_annotation_status):
        raise ValueError(f"Can not scale up {hpa_repr}. Already has been scaled up.")

    spec_min_replicas = hpa.spec.min_replicas
    spec_max_replicas = hpa.spec.max_replicas

    # Calculate and validate scale target
    scale_target_min_replicas = math.ceil(hpa.status.current_replicas * scale_perc_of_actual / 100)

    if scale_target_min_replicas <= spec_min_replicas:
        raise ValueError(
            f"Can not scale up {hpa_repr}: Would decrease minReplicas (deployment not correctly started?)."
        )

    if scale_target_min_replicas > spec_max_replicas:
        logger.warning(
            f"Limiting minReplicas to maxReplicas value of {spec_max_replicas} instead of intended value {scale_target_min_replicas} for {hpa_repr})"
        )
        scale_target_min_replicas = hpa.spec.max_replicas

    # Patch HPA with scale target and status data
    hpa_status = create_hpa_status(scale_target_min_replicas, hpa)
    patch = {
        "metadata": {
            "annotations": {config.common.hpa_annotation_status: json.dumps(hpa_status.dict().get("status"))}
        },
        "spec": {"minReplicas": scale_target_min_replicas},
    }
    patched_hpa = client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler(
        hpa.metadata.name, hpa.metadata.namespace, patch
    )
    logger.info(f"Scaled minReplicas from {spec_min_replicas} to {scale_target_min_replicas} for {hpa_repr}")

    return hpa_status, patched_hpa


def revert_hpa(
    config: KlutchConfig, hpa_status: HpaStatus, logger: logging.Logger
) -> client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler:
    """Restore minReplicas to original value and remove status annotation."""

    # Load hpa first to determine if annotation hasn't been removed (e.g. by a deployment) which would cause patch to fail
    hpa = client.AutoscalingV1Api().read_namespaced_horizontal_pod_autoscaler(hpa_status.name, hpa_status.namespace)
    patch = [
        {"op": "replace", "path": "/spec/minReplicas", "value": hpa_status.status.originalMinReplicas},
    ]
    if config.common.hpa_annotation_status in hpa.metadata.annotations:
        patch.append(
            {
                "op": "remove",
                "path": "/metadata/annotations/{}".format(config.common.hpa_annotation_status.replace("/", "~1")),
            }
        )

    patched_hpa = client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler(
        hpa_status.name, hpa_status.namespace, patch
    )
    logger.info(
        "Scaled minReplicas from {applied_min_replicas} to {original_min_replicas} for {repr})".format(
            repr=_hpa_repr(patched_hpa),
            applied_min_replicas=hpa_status.status.appliedMinReplicas,
            original_min_replicas=hpa_status.status.originalMinReplicas,
        )
    )
    return patched_hpa


def reconcile_hpa(
    config: KlutchConfig, hpa_status: HpaStatus, logger: logging.Logger
) -> client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler:
    """Examine HPA and ensure minReplicas has overdrive value and annotation is set."""

    # Load hpa first to determine if annotation hasn't been removed (e.g. by a deployment) which would cause patch to fail
    hpa = client.AutoscalingV1Api().read_namespaced_horizontal_pod_autoscaler(hpa_status.name, hpa_status.namespace)
    repr = _hpa_repr(hpa)
    patch = []

    if config.common.hpa_annotation_status not in hpa.metadata.annotations:
        patch.append(
            {
                "op": "add",
                "path": "/metadata/annotations/{}".format(config.common.hpa_annotation_status.replace("/", "~1")),
                "value": json.dumps(hpa_status.dict().get("status")),
            }
        )
    if hpa.spec.min_replicas != hpa_status.status.appliedMinReplicas:
        patch.append({"op": "replace", "path": "/spec/minReplicas", "value": hpa_status.status.appliedMinReplicas})  # type: ignore
    if not patch:
        logger.debug(f"No reconcile needed for {repr})")
        return hpa
    patched_hpa = client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler(
        hpa_status.name, hpa_status.namespace, patch
    )
    logger.info("Reconciled {repr}")
    return patched_hpa


def _hpa_repr(hpa: client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler):
    """Return string representation of HPA for logging purposes."""
    name = hpa.metadata.name
    namespace = hpa.metadata.namespace
    uid = hpa.metadata.uid
    return f"HorizontalPodAutoscaler (namespace={namespace}, name={name}, uid={uid})"
