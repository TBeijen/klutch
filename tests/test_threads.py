import logging
import threading
import time
from queue import Empty
from queue import SimpleQueue
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest

from klutch.config import config as klutch_config
from klutch.threads import BaseThread
from klutch.threads import ProcessScaler
from klutch.threads import TriggerConfigMap
from klutch.threads import TriggerWebHook


@pytest.fixture
def mock_config():
    mock_config = Mock(klutch_config)
    mock_config.common.namespace = "test-ns"
    return mock_config


thread_classes = [
    BaseThread,
    ProcessScaler,
    TriggerConfigMap,
    TriggerWebHook,
]


class TestBaseThread:

    """Test number of methods available to all thread subclasses."""

    @pytest.mark.parametrize("thread_class", thread_classes)
    def test_trigger(self, mock_config, thread_class):
        queue = SimpleQueue()

        # Call trigger without actually starting the thread
        thread = thread_class(queue, threading.Event(), mock_config)
        thread._trigger()

        assert queue.get(block=False)

    @pytest.mark.parametrize("thread_class", thread_classes)
    def test_is_active(self, mock_config, thread_class):
        is_active_event = threading.Event()

        # Call trigger without actually starting the thread
        thread = thread_class(SimpleQueue(), is_active_event, mock_config)
        assert not thread._is_active()
        is_active_event.set()
        assert thread._is_active()

    @pytest.mark.parametrize("thread_class", thread_classes)
    def test_stop(self, mock_config, thread_class):
        # Call trigger without actually starting the thread
        thread = thread_class(SimpleQueue(), threading.Event(), mock_config)
        assert not thread.should_stop
        thread.stop()
        assert thread.should_stop
