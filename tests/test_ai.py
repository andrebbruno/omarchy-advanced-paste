import json
import sys

import pytest

from oadvpaste import ai


@pytest.fixture
def config(tmp_path, monkeypatch):
    """Point the module at a throwaway config and agent file."""
    cfg = tmp_path / "config.json"
    agent = tmp_path / "agent"
    monkeypatch.setattr(ai, "CONFIG", str(cfg))
    monkeypatch.setattr(ai, "AGENT_FILE", str(agent))
    return cfg, agent


def write_config(cfg, command):
    cfg.write_text(json.dumps({"ai_command": command}), encoding="utf-8")


def test_the_instruction_reaches_the_command(config):
    cfg, _ = config
    write_config(cfg, ["echo", "{prompt}"])
    argv = ai.command_for("make it shout")
    assert argv[0] == "echo"
    assert "make it shout" in argv[1]
    assert "stdin" in argv[1]                      # the system prompt explains the input


def test_the_configured_command_wins_over_the_agent_file(config, monkeypatch):
    cfg, agent = config
    agent.write_text("claude\n", encoding="utf-8")
    write_config(cfg, ["my-own-agent", "{prompt}"])
    assert ai.command_for("x")[0] == "my-own-agent"


def test_the_agent_omarchy_is_set_to_is_used(config, monkeypatch):
    _, agent = config
    agent.write_text("gemini\n", encoding="utf-8")
    monkeypatch.setattr(ai.shutil, "which", lambda name: "/usr/bin/gemini" if name == "gemini" else None)
    assert ai.command_for("x")[:2] == ["gemini", "-p"]


def test_no_agent_at_all_is_an_error_with_advice(config, monkeypatch):
    monkeypatch.setattr(ai.shutil, "which", lambda name: None)
    with pytest.raises(ai.AIError) as e:
        ai.command_for("x")
    assert "omarchy default agent" in str(e.value)


def test_the_text_goes_in_on_stdin_and_the_answer_comes_back(config):
    cfg, _ = config
    # Explicit UTF-8 on both ends: the stub must not inherit the platform's idea of
    # an encoding, which is what a real agent on Linux would use anyway.
    write_config(cfg, [sys.executable, "-c",
                       "import sys; sys.stdout.buffer.write("
                       "sys.stdin.buffer.read().decode('utf-8').upper().encode('utf-8'))"])
    assert ai.transform("ação e paz", "shout") == "AÇÃO E PAZ"


def test_a_failing_agent_never_becomes_the_pasted_text(config):
    """The whole point: 'Not logged in' must not land in the user's document."""
    cfg, _ = config
    write_config(cfg, [sys.executable, "-c",
                       "import sys; print('Not logged in · Please run /login'); sys.exit(1)"])
    with pytest.raises(ai.AIError) as e:
        ai.transform("hello", "anything")
    assert "Not logged in" in str(e.value)


def test_an_empty_answer_is_an_error(config):
    cfg, _ = config
    write_config(cfg, [sys.executable, "-c", "pass"])
    with pytest.raises(ai.AIError):
        ai.transform("hello", "anything")


def test_a_slow_agent_gives_up_instead_of_hanging(config):
    cfg, _ = config
    write_config(cfg, [sys.executable, "-c", "import time; time.sleep(5)"])
    with pytest.raises(ai.AIError) as e:
        ai.transform("hello", "anything", timeout=1)
    assert "longer than" in str(e.value)


def test_a_fenced_answer_is_unwrapped():
    assert ai.strip_fence("```\nhello\n```") == "hello"
    assert ai.strip_fence("```json\n{}\n```") == "{}"


def test_a_fence_inside_the_answer_is_left_alone():
    text = "Here:\n```\ncode\n```\nand more"
    assert ai.strip_fence(text) == text
