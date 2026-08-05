"""TerminalBridge just re-emits JS-invoked slots as plain Qt signals."""

from __future__ import annotations

from qtxterm.terminal_bridge import TerminalBridge


def test_send_input_emits_input_received(qtbot) -> None:
    bridge = TerminalBridge()
    with qtbot.waitSignal(bridge.input_received, timeout=1000) as blocker:
        bridge.sendInput("ls -la\n")
    assert blocker.args == ["ls -la\n"]


def test_resize_emits_resize_requested(qtbot) -> None:
    bridge = TerminalBridge()
    with qtbot.waitSignal(bridge.resize_requested, timeout=1000) as blocker:
        bridge.resize(120, 40)
    assert blocker.args == [120, 40]


def test_ready_emits_terminal_ready(qtbot) -> None:
    bridge = TerminalBridge()
    with qtbot.waitSignal(bridge.terminal_ready, timeout=1000) as blocker:
        bridge.ready(80, 24)
    assert blocker.args == [80, 24]
