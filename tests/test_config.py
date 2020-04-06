from unittest.mock import MagicMock

import pytest

from klutch.config import configure_kubernetes
from klutch.config import get_config


def test_config_defaults():
    config = get_config(["--namespace=my-namespace"])
    assert config.namespace == "my-namespace"
    assert config.debug is False
    assert config.dry_run is False
    assert config.interval == 10
    assert config.cooldown == 300
    assert config.cm_trigger_label_key == "klutch.it/trigger"
    assert config.cm_trigger_label_value == "1"
    assert config.cm_status_label_key == "klutch.it/status"
    assert config.cm_status_label_value == "1"
    assert config.hpa_annotation_enabled == "klutch.it/enabled"
    assert (
        config.hpa_annotation_scale_perc_of_actual
        == "klutch.it/scale-percentage-of-actual"
    )


@pytest.mark.parametrize(
    "args, exp_debug, exp_dry_run, exp_namespace",
    [
        (["--debug", "--namespace=foo"], True, False, "foo"),
        (["--dry-run", "--namespace=foo"], False, True, "foo"),
        (["--dry-run", "--namespace=foo", "--debug"], True, True, "foo"),
        (["--namespace=foo", "--dry-run"], False, True, "foo"),
    ],
)
def test_config_args(args, exp_debug, exp_dry_run, exp_namespace):
    config = get_config(args)
    assert config.debug == exp_debug
    assert config.dry_run == exp_dry_run
    assert config.namespace == exp_namespace


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
    fs.create_file(
        "/var/run/secrets/kubernetes.io/serviceaccount/token", contents="long-secret"
    )
    fs.create_file(
        "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt", contents="cert-data"
    )
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
