import logging
import threading
import time
from datetime import datetime
from queue import Empty
from queue import SimpleQueue
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest
from kubernetes import client

from .conftest import REFERENCE_TS
from klutch.config import config as klutch_config
from klutch.status import SequenceStatus
from klutch.threads import BaseThread
from klutch.threads import ProcessScaler
from klutch.threads import TriggerConfigMap
from klutch.threads import TriggerWebHook


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


class TestProcessScaler:
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
    def test_is_status_duration_expired(self, frozen, creation_timestamp, duration, expected, mock_config):
        mock_config.common.duration = duration

        sequence_status = SequenceStatus(creation_timestamp.timestamp(), [])
        thread = ProcessScaler(SimpleQueue(), threading.Event(), mock_config)
        thread.sequence_status = sequence_status

        assert thread._is_status_duration_expired() == expected
