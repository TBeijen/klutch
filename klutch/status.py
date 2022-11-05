import json
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict
from typing import List

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

    def dict(self) -> Dict:
        return asdict(self)

    def json(self) -> str:
        return json.dumps(self.dict())


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


def status_list_from_dict(status_data: Dict) -> List[HpaStatus]:
    hpa_status_list = []
    for s in status_data:
        hpa_status_list.append(
            HpaStatus(name=s.get("name"), namespace=s.get("namespace"), status=StatusData(**s.get("status")))
        )
    return hpa_status_list
