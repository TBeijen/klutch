from datetime import datetime
from unittest.mock import MagicMock

import pytest
from kubernetes import client

from klutch import actions
from klutch.config import get_config

REFERENCE_TS = 1500000000


@pytest.fixture
def mock_client(monkeypatch):
    mock_client = MagicMock(spec=client)
    monkeypatch.setattr("klutch.actions.client", mock_client)
    return mock_client


def test_find_triggers(mock_client):
    mock_cm_new = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm_new.metadata.name = "new"
    mock_cm_new.metadata.creation_timestamp = datetime.fromtimestamp(REFERENCE_TS)
    mock_cm_old = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm_old.metadata.name = "old"
    mock_cm_old.metadata.creation_timestamp = datetime.fromtimestamp(REFERENCE_TS - 100)

    config = get_config(["--namespace=test-ns"])
    config.cm_trigger_label_key = "test-trigger"
    config.cm_trigger_label_value = "yes"

    mock_config_list = MagicMock()
    mock_config_list.items = [mock_cm_old, mock_cm_new]
    mock_client.CoreV1Api().list_namespaced_config_map.return_value = mock_config_list

    found = actions.find_triggers(config)

    assert found == [mock_cm_new, mock_cm_old]  # sorted recent first
    mock_client.CoreV1Api().list_namespaced_config_map.assert_called_once_with(
        "test-ns", label_selector="test-trigger=yes"
    )


@pytest.mark.parametrize(
    "creation_timestamp, trigger_max_age, expected",
    [
        (datetime.fromtimestamp(REFERENCE_TS), 100, True),
        (datetime.fromtimestamp(REFERENCE_TS - 100), 100, True),
        (datetime.fromtimestamp(REFERENCE_TS - 200), 100, False),
        (
            datetime.fromtimestamp(REFERENCE_TS + 100),
            100,
            True,
        ),  # 'future' configmaps should be no problem
    ],
)
def test_validate_trigger(freezer, creation_timestamp, trigger_max_age, expected):
    freezer.move_to(datetime.fromtimestamp(REFERENCE_TS))
    mock_cm = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm.metadata.creation_timestamp = creation_timestamp
    config = get_config(["--namespace=test-ns"])
    config.trigger_max_age = trigger_max_age

    assert actions.validate_trigger(config, mock_cm) == expected


def test_delete_trigger(mock_client):
    mock_cm = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm.metadata.name = "foo-name"
    mock_cm.metadata.namespace = "bar-ns"

    actions.delete_trigger(mock_cm)

    mock_client.CoreV1Api().delete_namespaced_config_map.assert_called_once_with(
        "foo-name", "bar-ns"
    )


def test_find_hpas(mock_client):
    mock_hpa_enabled = MagicMock(
        spec=client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler
    )
    mock_hpa_enabled.metadata.annotations = {"klutch-enabled": "any-value-goes"}
    mock_hpa_disabled = MagicMock(
        spec=client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler
    )
    mock_hpa_disabled.metadata.annotations = {}

    config = get_config(["--namespace=test-ns"])
    config.hpa_annotation_enabled = "klutch-enabled"

    mock_hpa_list = MagicMock()
    mock_hpa_list.items = [mock_hpa_disabled, mock_hpa_enabled]
    mock_client.AutoscalingV1Api().list_horizontal_pod_autoscaler_for_all_namespaces.return_value = (
        mock_hpa_list
    )

    found = actions.find_hpas(config)

    assert list(found) == [mock_hpa_enabled]
