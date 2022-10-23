from unittest.mock import MagicMock

import pytest

from klutch.old_config import configure_kubernetes
from klutch.old_config import get_config


def test_config_defaults():
    config = get_config(["--namespace=my-namespace"])
    assert config.namespace == "my-namespace"
    assert config.debug is False
    assert config.interval == 5
    assert config.duration == 300
    assert config.trigger_max_age == 300
    assert config.orphan_scan_interval == 600
    assert config.cm_trigger_label_key == "klutch.it/trigger"
    assert config.cm_trigger_label_value == "1"
    assert config.cm_status_label_key == "klutch.it/status"
    assert config.cm_status_label_value == "1"
    assert config.hpa_annotation_enabled == "klutch.it/enabled"
    assert config.hpa_annotation_scale_perc_of_actual == "klutch.it/scale-percentage-of-actual"


@pytest.mark.parametrize(
    "args, exp_debug, exp_namespace, exp_interval, exp_duration, exp_trigger_max_age",
    [
        (["--namespace=foo", "--interval=13", "--duration=17", "--trigger-max-age=19"], False, "foo", 13, 17, 19),
        (
            ["--namespace=foo", "--debug", "--interval=13", "--duration=17", "--trigger-max-age=19"],
            True,
            "foo",
            13,
            17,
            19,
        ),
        (
            ["--debug", "--interval=13", "--duration=17", "--trigger-max-age=19", "--namespace=foo"],
            True,
            "foo",
            13,
            17,
            19,
        ),
    ],
)
def test_config_args(args, exp_debug, exp_namespace, exp_interval, exp_duration, exp_trigger_max_age):
    config = get_config(args)
    assert config.debug == exp_debug
    assert config.namespace == exp_namespace
    assert config.interval == exp_interval
    assert config.duration == exp_duration
    assert config.trigger_max_age == exp_trigger_max_age


def test_config_unknown_arg(monkeypatch):
    mock_exit = MagicMock()
    monkeypatch.setattr("sys.exit", mock_exit)
    get_config(["--foobar", "--namespace=my-namespace"])
    mock_exit.assert_called_once_with(2)


def test_config_in_cluster_uses_namespace(fs):
    fs.create_file(
        "/var/run/secrets/kubernetes.io/serviceaccount/namespace",
        contents="cluster-namespace",
    )
    config = get_config([])
    assert config.namespace == "cluster-namespace"


def test_config_in_cluster_override_namespace(fs):
    fs.create_file(
        "/var/run/secrets/kubernetes.io/serviceaccount/namespace",
        contents="cluster-namespace",
    )
    config = get_config(["--namespace=override-namespace"])
    assert config.namespace == "override-namespace"


def test_config_out_of_cluster_requires_namespace():
    with pytest.raises(FileNotFoundError):
        get_config([])


def test_configure_kubernetes_in_cluster(fs, monkeypatch):
    fs.create_file("/var/run/secrets/kubernetes.io/serviceaccount/token", contents="long-secret")
    fs.create_file("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt", contents="cert-data")
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "kubernetest.test.local")
    monkeypatch.setenv("KUBERNETES_SERVICE_PORT", 1234)
    configure_kubernetes()


def test_configure_kubernetes_out_of_cluster(kubeconfig, monkeypatch):
    monkeypatch.setenv("KUBECONFIG", kubeconfig)
    configure_kubernetes()


def test_configure_kubernetes_fail(fs):
    """Without in cluster service account or out of cluster kube config, client init should fail."""
    with pytest.raises(expected_exception=BaseException):
        configure_kubernetes()
