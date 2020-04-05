import pytest

from klutch.client import get_kubernetes


def test_get_kubernetes_in_cluster(fs, monkeypatch):
    fs.create_file(
        "/var/run/secrets/kubernetes.io/serviceaccount/token", contents="long-secret"
    )
    fs.create_file(
        "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt", contents="cert-data"
    )
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "kubernetest.test.local")
    monkeypatch.setenv("KUBERNETES_SERVICE_PORT", 1234)
    get_kubernetes()


def test_get_kubernetes_out_of_cluster(kubeconfig, monkeypatch):
    monkeypatch.setenv("KUBECONFIG", kubeconfig)
    get_kubernetes()


def test_get_kubernetes_fail(fs):
    """Without in cluster service account or out of cluster kube config, client init should fail."""
    with pytest.raises(expected_exception=BaseException):
        get_kubernetes()
