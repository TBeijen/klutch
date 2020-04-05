from unittest.mock import MagicMock

import pytest

from klutch.config import get_config


def test_defaults():
    config = get_config(["--namespace=my-namespace"])
    assert config.namespace == "my-namespace"
    assert config.debug is False
    assert config.dry_run is False
    assert config.interval == 10
    assert config.cooldown == 300
    assert config.cm_trigger_label == "klutch.it/trigger"
    assert config.cm_status_label == "klutch.it/status"
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
def test_args(args, exp_debug, exp_dry_run, exp_namespace):
    config = get_config(args)
    assert config.debug == exp_debug
    assert config.dry_run == exp_dry_run
    assert config.namespace == exp_namespace


def test_unknown_arg(monkeypatch):
    mock_exit = MagicMock()
    monkeypatch.setattr("sys.exit", mock_exit)
    get_config(["--foobar", "--namespace=my-namespace"])
    mock_exit.assert_called_once_with(2)


def test_in_cluster_uses_namespace(fs):
    fs.create_file(
        "/var/run/secrets/kubernetes.io/serviceaccount/namespace",
        contents="cluster-namespace",
    )
    config = get_config([])
    assert config.namespace == "cluster-namespace"


def test_in_cluster_override_namespace(fs):
    fs.create_file(
        "/var/run/secrets/kubernetes.io/serviceaccount/namespace",
        contents="cluster-namespace",
    )
    config = get_config(["--namespace=override-namespace"])
    assert config.namespace == "override-namespace"


def test_out_of_cluster_requires_namespace():
    with pytest.raises(FileNotFoundError):
        get_config([])
