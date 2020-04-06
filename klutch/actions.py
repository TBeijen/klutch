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
