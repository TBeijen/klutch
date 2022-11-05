import json
import logging
from contextlib import ExitStack as does_not_raise
from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest
from kubernetes import client

from klutch import actions
from klutch.config import config as klutch_config
from klutch.status import HpaStatus
from klutch.status import StatusData

REFERENCE_TS = 1500000000


dummy_logger = logging.Logger("test dummy")


@pytest.fixture
def mock_client(monkeypatch):
    mock_client = MagicMock(spec=client)
    monkeypatch.setattr("klutch.actions.client", mock_client)
    return mock_client


@pytest.fixture
def mock_config():
    mock_config = Mock(klutch_config)
    mock_config.common.namespace = "test-ns"
    return mock_config


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


def test_find_cm_triggers(mock_client, mock_config):
    mock_cm_new = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm_new.metadata.name = "new"
    mock_cm_new.metadata.creation_timestamp = datetime.fromtimestamp(REFERENCE_TS)
    mock_cm_old = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm_old.metadata.name = "old"
    mock_cm_old.metadata.creation_timestamp = datetime.fromtimestamp(REFERENCE_TS - 100)

    mock_config.trigger_config_map.cm_trigger_label_key = "test-trigger"
    mock_config.trigger_config_map.cm_trigger_label_value = "yes"

    mock_cm_list = MagicMock()
    mock_cm_list.items = [mock_cm_old, mock_cm_new]
    mock_client.CoreV1Api().list_namespaced_config_map.return_value = mock_cm_list

    found = actions.find_cm_triggers(mock_config)

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
def test_validate_cm_trigger(freezer, creation_timestamp, trigger_max_age, expected, mock_config):
    freezer.move_to(datetime.fromtimestamp(REFERENCE_TS))
    mock_cm = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm.metadata.creation_timestamp = creation_timestamp

    mock_config.trigger_config_map.max_age = trigger_max_age

    assert actions.validate_cm_trigger(mock_config, mock_cm) == expected


def test_delete_cm_trigger(mock_client):
    mock_cm = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm.metadata.name = "foo-name"
    mock_cm.metadata.namespace = "bar-ns"

    actions.delete_cm_trigger(mock_cm)

    mock_client.CoreV1Api().delete_namespaced_config_map.assert_called_once_with("foo-name", "bar-ns")


def test_find_cm_status(mock_client, mock_config):
    mock_cm_new = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm_new.metadata.name = "new"
    mock_cm_new.metadata.creation_timestamp = datetime.fromtimestamp(REFERENCE_TS)
    mock_cm_old = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm_old.metadata.name = "old"
    mock_cm_old.metadata.creation_timestamp = datetime.fromtimestamp(REFERENCE_TS - 100)

    mock_config.common.cm_status_label_key = "test-status"
    mock_config.common.cm_status_label_value = "yes"

    mock_config_list = MagicMock()
    mock_config_list.items = [mock_cm_old, mock_cm_new]
    mock_client.CoreV1Api().list_namespaced_config_map.return_value = mock_config_list

    found = actions.find_cm_status(mock_config)

    assert found == [mock_cm_new, mock_cm_old]  # sorted recent first
    mock_client.CoreV1Api().list_namespaced_config_map.assert_called_once_with(
        "test-ns", label_selector="test-status=yes"
    )


def test_create_cm_status(mock_client, mock_config):
    mock_config.common.cm_status_name = "kl-status-name"
    mock_config.common.cm_status_label_key = "kl-status"
    mock_config.common.cm_status_label_value = "yes"

    status_list = [
        HpaStatus(
            name="foo",
            namespace="ns",
            status=StatusData(
                originalMinReplicas=1,
                originalCurrentReplicas=1,
                appliedMinReplicas=2,
                appliedAt=int(datetime.now().timestamp()),
            ),
        )
    ]
    mock_response = MagicMock()
    mock_client.CoreV1Api().create_namespaced_config_map.return_value = mock_response

    # Prevent models instantiated in sut to be mocks as well
    mock_client.models = client.models

    resp = actions.create_cm_status(mock_config, status_list)

    call_args = mock_client.CoreV1Api().create_namespaced_config_map.call_args_list
    assert len(call_args) == 1
    assert call_args[0].args[0] == "test-ns"
    assert type(call_args[0].args[1]) == client.models.v1_config_map.V1ConfigMap
    assert call_args[0].args[1].metadata.name == "kl-status-name"
    assert call_args[0].args[1].metadata.labels.get("kl-status") == "yes"
    assert json.loads(call_args[0].args[1].data.get("status")) == [s.dict() for s in status_list]
    assert resp is mock_response


@pytest.mark.parametrize(
    "creation_timestamp, duration, expected",
    [
        (datetime.fromtimestamp(REFERENCE_TS), 300, False),
        (datetime.fromtimestamp(REFERENCE_TS - 300), 300, False),
        (datetime.fromtimestamp(REFERENCE_TS - 301), 300, True),
        (
            datetime.fromtimestamp(REFERENCE_TS + 100),
            300,
            False,
        ),  # 'future' configmaps should be no problem
    ],
)
def test_is_status_duration_expired(freezer, creation_timestamp, duration, expected, mock_config):
    freezer.move_to(datetime.fromtimestamp(REFERENCE_TS))
    mock_cm = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm.metadata.creation_timestamp = creation_timestamp
    mock_config.common.duration = duration

    assert actions.is_status_duration_expired(mock_config, mock_cm) == expected


def test_delete_cm_status(mock_client):
    mock_cm = MagicMock(spec=client.models.v1_config_map.V1ConfigMap)
    mock_cm.metadata.name = "foo-name"
    mock_cm.metadata.namespace = "bar-ns"

    actions.delete_cm_status(mock_cm)

    mock_client.CoreV1Api().delete_namespaced_config_map.assert_called_once_with("foo-name", "bar-ns")


@pytest.mark.parametrize(
    "annotation_key, annotation_value, should_be_included",
    [
        ("proper_annotation_key", "1", True),
        ("proper_annotation_key", "0", False),
        ("proper_annotation_key", "foobar", False),
        ("incorrect_annotation_key", "1", False),
    ],
)
def test_find_hpas(mock_client, mock_config, annotation_key, annotation_value, should_be_included):
    # This one should never be included
    mock_hpa1 = MagicMock(spec=client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler)
    mock_hpa1.metadata.annotations = {"proper_annotation_key": "1"}
    # This one should be included based on test parameters
    mock_hpa2 = MagicMock(spec=client.models.v1_horizontal_pod_autoscaler.V1HorizontalPodAutoscaler)
    mock_hpa2.metadata.annotations = {annotation_key: annotation_value}

    mock_config.common.hpa_annotation_enabled_key = "proper_annotation_key"
    mock_config.common.hpa_annotation_enabled_value = "1"

    mock_hpa_list = MagicMock()
    mock_hpa_list.items = [mock_hpa1, mock_hpa2]
    mock_client.AutoscalingV1Api().list_horizontal_pod_autoscaler_for_all_namespaces.return_value = mock_hpa_list

    found = actions.find_hpas(mock_config)
    found = list(found)

    assert mock_hpa1 in found
    assert (mock_hpa2 in found) is should_be_included


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
    mock_config,
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
    mock_config.common.hpa_annotation_scale_perc_of_actual = "kl-scale-to"
    mock_config.common.hpa_annotation_status = "kl-status"

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

    expected_hpa_status = HpaStatus(
        name="test-hpa",
        namespace="test-ns",
        status=StatusData(
            originalMinReplicas=hpa_min_r,
            originalCurrentReplicas=hpa_current_r,
            appliedMinReplicas=expected_min_r,
            appliedAt=REFERENCE_TS,
        ),
    )

    expected_patch_body = {
        "metadata": {"annotations": {"kl-status": json.dumps(expected_hpa_status.dict().get("status"))}},
        "spec": {"minReplicas": expected_min_r},
    }

    with expected_exception:
        returned_status, returned_hpa = actions.scale_hpa(mock_config, mock_original_hpa, dummy_logger)

        mock_client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler.assert_called_once_with(
            "test-hpa", "test-ns", expected_patch_body
        )
        assert returned_status == expected_hpa_status
        assert returned_hpa is mock_patched_hpa


def test_scale_hpa_raises_if_annotation_found(mock_client, mock_config):
    # Setting custom annotation key to test if config is used
    mock_config.common.hpa_annotation_scale_perc_of_actual = "kl-scale-to"
    mock_config.common.hpa_annotation_status = "kl-status"

    mock_original_hpa = get_mock_hpa(annotations={"kl-status": "some-json", "kl-scale-to": "200"})

    with pytest.raises(ValueError):
        actions.scale_hpa(mock_config, mock_original_hpa, dummy_logger)


@pytest.mark.parametrize("has_patch_annotation", [True, False])
def test_revert_hpa_patches(mock_client, mock_config, has_patch_annotation):
    mock_config.common.hpa_annotation_status = "kl/status"  # testing replacing of / by ~1

    hpa_annot = {"kl/status": "some-json"} if has_patch_annotation else None
    mock_read_hpa = get_mock_hpa(annotations=hpa_annot)
    mock_patched_hpa = get_mock_hpa()
    mock_client.AutoscalingV1Api().read_namespaced_horizontal_pod_autoscaler.return_value = mock_read_hpa
    mock_client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler.return_value = mock_patched_hpa

    hpa_status = HpaStatus(
        name="test-name",
        namespace="test-ns",
        status=StatusData(
            originalMinReplicas=4,
            originalCurrentReplicas=5,
            appliedMinReplicas=8,
            appliedAt=REFERENCE_TS,
        ),
    )
    ret_value = actions.revert_hpa(mock_config, hpa_status, dummy_logger)

    # should have loaded hpa using name and ns
    mock_client.AutoscalingV1Api().read_namespaced_horizontal_pod_autoscaler.assert_called_once_with(
        "test-name", "test-ns"
    )
    # should have patched hpa with proper patch
    assert len(mock_client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler.call_args_list) == 1
    assert ret_value is mock_patched_hpa
    args = mock_client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler.call_args_list[0].args
    assert args[0] == "test-name"
    assert args[1] == "test-ns"
    assert {"op": "replace", "path": "/spec/minReplicas", "value": 4} in args[2]
    assert len(args[2]) == 2 if has_patch_annotation else 1
    if has_patch_annotation:
        assert {"op": "remove", "path": "/metadata/annotations/kl~1status"} in args[2]


@pytest.mark.parametrize(
    "has_patch_annotation, hpa_min_replicas, should_patch",
    [
        (True, 4, False),
        (True, 2, True),
        (False, 4, True),
        (False, 2, True),
        (False, 6, True),  # Also reconcile if for some odd reason minReplicas is higher than appliedMinReplicas
    ],
)
def test_reconcile_hpa_patches(mock_client, mock_config, has_patch_annotation, hpa_min_replicas, should_patch):
    mock_config.common.hpa_annotation_status = "kl/status"  # testing replacing of / by ~1

    hpa_annot = {"kl/status": "some-json"} if has_patch_annotation else None
    mock_read_hpa = get_mock_hpa(annotations=hpa_annot, min_repl=hpa_min_replicas)
    mock_patched_hpa = get_mock_hpa()
    mock_client.AutoscalingV1Api().read_namespaced_horizontal_pod_autoscaler.return_value = mock_read_hpa
    mock_client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler.return_value = mock_patched_hpa

    hpa_status = HpaStatus(
        name="test-name",
        namespace="test-ns",
        status=StatusData(
            originalMinReplicas=2,
            originalCurrentReplicas=2,
            appliedMinReplicas=4,
            appliedAt=REFERENCE_TS,
        ),
    )
    ret_value = actions.reconcile_hpa(mock_config, hpa_status, dummy_logger)

    patch_annot = {"op": "add", "path": "/metadata/annotations/kl~1status", "value": '{"appliedMinReplicas": 4}'}
    patch_spec = {"op": "replace", "path": "/spec/minReplicas", "value": 4}

    if not should_patch:
        mock_client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler.assert_not_called()
        assert ret_value is mock_read_hpa
    else:
        assert len(mock_client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler.call_args_list) == 1
        assert ret_value is mock_patched_hpa
        args = mock_client.AutoscalingV1Api().patch_namespaced_horizontal_pod_autoscaler.call_args_list[0].args
        assert args[0] == "test-name"
        assert args[1] == "test-ns"
        # Finding the spec and annotation patch components in the arg to patch the hpa
        patch_element_spec = [p for p in args[2] if p.get("op") == "replace"]
        patch_element_annot = [p for p in args[2] if p.get("op") == "add"]
        # Only if original hpa not yet had annotation, the expected annotation should be included in the patch
        if not has_patch_annotation:
            assert patch_element_annot[0]["path"] == "/metadata/annotations/kl~1status"
            assert json.loads(patch_element_annot[0]["value"]) == hpa_status.dict().get("status")
        # Only if HPA min replicas differs from what has been applied as scale target, should spec be included in the patch
        if not (hpa_min_replicas == 4):
            assert patch_element_spec[0]["path"] == "/spec/minReplicas"
            assert patch_element_spec[0]["value"] == 4
