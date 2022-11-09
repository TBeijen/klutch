import logging
from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest
from kubernetes import client

from klutch.config import config as klutch_config

REFERENCE_TS = 1500000000


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


@pytest.fixture
def logger():
    return logging.Logger("Test dummy logger")


@pytest.fixture
def frozen(freezer):
    """Use freezer to move current time to REFERENCE_TS."""
    freezer.move_to(datetime.fromtimestamp(REFERENCE_TS))
    return freezer


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
