"""notify() must not let attacker-controlled message text execute as AppleScript."""

from unittest.mock import patch

from wnflow.notify import notify


def test_notify_passes_message_as_argv_not_in_script_body() -> None:
    """The osascript invocation should pass title/message as `-- argv`,
    so quotes inside the message can't break out into shell-script land."""
    with patch("wnflow.notify.subprocess.run") as mock_run:
        notify("Flow", 'evil"; do shell script "rm -rf ~"; --')

    assert mock_run.called
    args, _ = mock_run.call_args
    cmd = args[0]
    # The injection string must appear as an argv element, never inside -e.
    injection = 'evil"; do shell script "rm -rf ~"; --'
    assert injection in cmd, "message lost from argv"
    e_idx = cmd.index("-e")
    script_body = cmd[e_idx + 1]
    assert injection not in script_body, \
        "message body interpolated into the AppleScript (= injection!)"
