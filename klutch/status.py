import json
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict
from typing import List

from kubernetes import client  # type: ignore

from klutch.config import KlutchConfig


@dataclass
class StatusData:

    """Representation of scaling status, as added to HPA annotation."""

    originalMinReplicas: int
    originalCurrentReplicas: int
    appliedMinReplicas: int
    appliedAt: int


@dataclass
class HpaStatus:

    """Representation of scaled status, as present in status ConfigMap."""

    name: str
    namespace: str
    status: StatusData

    def dict(self) -> Dict:
        return asdict(self)


@dataclass
class SequenceStatus:

    """Representation of ongoing scaling sequence."""

    started_at_ts: int
    status_list: List[HpaStatus]


def create_hpa_status(
    scale_target_min_replicas: int, hpa: client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler
) -> HpaStatus:
    return HpaStatus(
        name=hpa.metadata.name,
        namespace=hpa.metadata.namespace,
        status=StatusData(
            originalMinReplicas=hpa.spec.min_replicas,
            originalCurrentReplicas=hpa.status.current_replicas,
            appliedMinReplicas=scale_target_min_replicas,
            appliedAt=int(datetime.now().timestamp()),
        ),
    )


def sequence_status_from_cm(status_cm: client.models.v1_config_map.V1ConfigMap) -> SequenceStatus:
    cm_ts = status_cm.metadata.creation_timestamp.timestamp()
    hpa_status_list = []
    for s in json.loads(status_cm.data.get("status")):
        hpa_status_list.append(
            HpaStatus(name=s.get("name"), namespace=s.get("namespace"), status=StatusData(**s.get("status")))
        )
    return SequenceStatus(started_at_ts=cm_ts, status_list=hpa_status_list)


def hpa_status_from_annotated_hpa(
    config: KlutchConfig, hpa: client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler
) -> HpaStatus:
    data = json.loads(hpa.metadata.annotations.get(config.common.hpa_annotation_status))
    return HpaStatus(
        name=hpa.metadata.name,
        namespace=hpa.metadata.namespace,
        status=StatusData(**data),
    )
