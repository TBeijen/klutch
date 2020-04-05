import pytest


@pytest.fixture
def kubeconfig(tmpdir):
    """Write test kube config file and return it's location."""
    kubeconfig = tmpdir.join("kubeconfig")
    kubeconfig.write(
        """
apiVersion: v1
kind: Config
clusters:
- cluster:
    server: 'https://kubernetest.test.local:1234'
  name: test
contexts:
- context:
    cluster: test
    user: test
  name: test
current-context: test
users:
- name: test
  user:
    token: secret
    """
    )
    return kubeconfig
