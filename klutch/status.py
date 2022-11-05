import json
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime

from kubernetes import client  # type: ignore


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

    def dict(self):
        return asdict(self)

    def json(self):
        return json.dumps(self.dict())


def create_hpa_status(
    scale_target_min_replicas: int, hpa: client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler
):
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
