import json
from contextlib import ExitStack as does_not_raise
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


def get_mock_hpa(name="test-hpa", namespace="test-ns", min_repl=2, max_repl=10, current_repl=4, annotations=None):
    mock_hpa = MagicMock(spec=client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler)
    mock_hpa.metadata.name = name
    mock_hpa.metadata.namespace = namespace
    mock_hpa.spec.min_replicas = min_repl
    mock_hpa.spec.max_replicas = max_repl
    mock_hpa.status.current_replicas = current_repl
    if annotations:
        mock_hpa.metadata.annotations = annotations
    return mock_hpa


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
        (datetime.fromtimestamp(REFERENCE_TS + 100), 100, True,),  # 'future' configmaps should be no problem
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

    mock_client.CoreV1Api().delete_namespaced_config_map.assert_called_once_with("foo-name", "bar-ns")


def test_find_status(mock_client):
    mock_cm_new = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm_new.metadata.name = "new"
    mock_cm_new.metadata.creation_timestamp = datetime.fromtimestamp(REFERENCE_TS)
    mock_cm_old = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm_old.metadata.name = "old"
    mock_cm_old.metadata.creation_timestamp = datetime.fromtimestamp(REFERENCE_TS - 100)

    config = get_config(["--namespace=test-ns"])
    config.cm_status_label_key = "test-status"
    config.cm_status_label_value = "yes"

    mock_config_list = MagicMock()
    mock_config_list.items = [mock_cm_old, mock_cm_new]
    mock_client.CoreV1Api().list_namespaced_config_map.return_value = mock_config_list

    found = actions.find_status(config)

    assert found == [mock_cm_new, mock_cm_old]  # sorted recent first
    mock_client.CoreV1Api().list_namespaced_config_map.assert_called_once_with(
        "test-ns", label_selector="test-status=yes"
    )


def test_create_status(mock_client):
    config = get_config(["--namespace=test-ns"])
    config.cm_status_name = "kl-status-name"
    config.cm_status_label_key = "kl-status"
    config.cm_status_label_value = "yes"

    status = [{"foo": "bar"}]
    mock_response = MagicMock()
    mock_client.CoreV1Api().create_namespaced_config_map.return_value = mock_response

    # Prevent models instantiated in sut to be mocks as well
    mock_client.models = client.models

    resp = actions.create_status(config, status)

    call_args = mock_client.CoreV1Api().create_namespaced_config_map.call_args_list
    assert len(call_args) == 1
    assert call_args[0].args[0] == "test-ns"
    assert type(call_args[0].args[1]) == client.models.v1_config_map.V1ConfigMap
    assert call_args[0].args[1].metadata.name == "kl-status-name"
    assert call_args[0].args[1].metadata.labels.get("kl-status") == "yes"
    assert call_args[0].args[1].data.get("status") == json.dumps(status)
    assert resp is mock_response


@pytest.mark.parametrize(
    "creation_timestamp, cooldown, expected",
    [
        (datetime.fromtimestamp(REFERENCE_TS), 300, False),
        (datetime.fromtimestamp(REFERENCE_TS - 300), 300, False),
        (datetime.fromtimestamp(REFERENCE_TS - 301), 300, True),
        (datetime.fromtimestamp(REFERENCE_TS + 100), 300, False,),  # 'future' configmaps should be no problem
    ],
)
def test_evaluate_status_cooldown_expired(freezer, creation_timestamp, cooldown, expected):
    freezer.move_to(datetime.fromtimestamp(REFERENCE_TS))
    mock_cm = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm.metadata.creation_timestamp = creation_timestamp
    config = get_config(["--namespace=test-ns"])
    config.cooldown = cooldown

    assert actions.evaluate_status_cooldown_expired(config, mock_cm) == expected


def test_delete_status(mock_client):
    mock_cm = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm.metadata.name = "foo-name"
    mock_cm.metadata.namespace = "bar-ns"

    actions.delete_status(mock_cm)

    mock_client.CoreV1Api().delete_namespaced_config_map.assert_called_once_with("foo-name", "bar-ns")


def test_find_hpas(mock_client):
    mock_hpa_enabled = MagicMock(spec=client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler)
    mock_hpa_enabled.metadata.annotations = {"klutch-enabled": "any-value-goes"}
    mock_hpa_disabled = MagicMock(spec=client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler)
    mock_hpa_disabled.metadata.annotations = {}

    config = get_config(["--namespace=test-ns"])
    config.hpa_annotation_enabled = "klutch-enabled"

    mock_hpa_list = MagicMock()
    mock_hpa_list.items = [mock_hpa_disabled, mock_hpa_enabled]
    mock_client.AutoscalingV1Api().list_horizontal_pod_autoscaler_for_all_namespaces.return_value = mock_hpa_list

    found = actions.find_hpas(config)

    assert list(found) == [mock_hpa_enabled]


@pytest.mark.parametrize(
    "hpa_min_r, hpa_max_r, hpa_current_r, hpa_scale_perc, expected_min_r, expect_log, expected_exception",
    [
        (2, 10, 3, "200", 6, False, does_not_raise()),  # uses current, not min
        (2, 10, 3, "150", 5, False, does_not_raise()),  # rounds up
        (2, 10, 6, "200", 10, True, does_not_raise()),  # does not exceed maxReplicas
        (2, 10, 0, "200", 0, False, pytest.raises(ValueError)),  # raise when would otherwise decrease
        (2, 10, 2, "foobar", 0, False, pytest.raises(ValueError)),  # raise when not able to parse percentage
        (2, 10, 2, None, 0, False, pytest.raises(TypeError)),  # raise when not able to parse percentage
    ],
)
def test_scale_hpa_patches(
    freezer,
    mock_client,
    hpa_min_r,
    hpa_max_r,
    hpa_current_r,
    hpa_scale_perc,
    expected_min_r,
    expect_log,
    expected_exception,
):
    freezer.move_to(datetime.fromtimestamp(REFERENCE_TS))
    # Setting custom annotation key to test if config is used
    config = get_config(["--namespace=test-ns"])
    config.hpa_annotation_scale_perc_of_actual = "kl-scale-to"
    config.hpa_annotation_status = "kl-status"

    mock_original_hpa = get_mock_hpa(
        name="test-hpa",
        namespace="test-ns",
        min_repl=hpa_min_r,
        max_repl=hpa_max_r,
        current_repl=hpa_current_r,
        annotations={"kl-scale-to": hpa_scale_perc},
    )
    mock_patched_hpa = get_mock_hpa()
    mock_client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler.return_value = mock_patched_hpa

    with expected_exception:
        ret_value = actions.scale_hpa(config, mock_original_hpa)

        expected_patch_body = {
            "metadata": {
                "annotations": {
                    "kl-status": json.dumps(
                        {
                            "originalMinReplicas": hpa_min_r,
                            "originalCurrentReplicas": hpa_current_r,
                            "appliedMinReplicas": expected_min_r,
                            "appliedAt": REFERENCE_TS,
                        }
                    )
                }
            },
            "spec": {"minReplicas": expected_min_r},
        }
        mock_client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler.assert_called_once_with(
            "test-hpa", "test-ns", expected_patch_body
        )
        assert ret_value is mock_patched_hpa


def test_scale_hpa_raises_if_annotation_found(mock_client):
    # Setting custom annotation key to test if config is used
    config = get_config(["--namespace=test-ns"])
    config.hpa_annotation_scale_perc_of_actual = "kl-scale-to"
    config.hpa_annotation_status = "kl-status"

    mock_original_hpa = get_mock_hpa(annotations={"kl-status": "some-json", "kl-scale-to": "200"})

    with pytest.raises(ValueError):
        actions.scale_hpa(config, mock_original_hpa)


def test_reconcile_hpa():
    pass


def test_revert_hpa():
    pass
