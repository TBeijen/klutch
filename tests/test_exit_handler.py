import signal
from unittest.mock import MagicMock

from klutch.exit_handler import ExitHandler


def test_initial_state():
    handler = ExitHandler()
    assert not handler.safe_to_exit
    assert not handler.should_exit


def test_traps_signals(monkeypatch):
    mock_signal = MagicMock()
    monkeypatch.setattr("signal.signal", mock_signal)
    handler = ExitHandler()
    assert len(mock_signal.call_args_list) == 2
    assert {c[0][0] for c in mock_signal.call_args_list} == {
        signal.SIGTERM,
        signal.SIGINT,
    }
    assert all(c[0][1] == handler.handle_signal for c in mock_signal.call_args_list)


def test_delays_exit(monkeypatch):
    mock_exit = MagicMock()
    monkeypatch.setattr("sys.exit", mock_exit)
    handler = ExitHandler()
    handler.handle_signal(signal.SIGTERM, 0)
    # should not exit outside safe_exit context
    assert handler.should_exit
    assert not handler.safe_to_exit
    mock_exit.assert_not_called()
    # should immediately exit when entering safe_exit context
    with handler.safe_exit():
        assert handler.safe_to_exit
        mock_exit.assert_called_once_with(0)


def test_immediately_exits_if_safe(monkeypatch):
    mock_exit = MagicMock()
    monkeypatch.setattr("sys.exit", mock_exit)
    handler = ExitHandler()
    # when in safe_exit context, should immediately exit when receiving signal
    with handler.safe_exit():
        handler.handle_signal(signal.SIGTERM, 0)
        mock_exit.assert_called_once_with(0)
