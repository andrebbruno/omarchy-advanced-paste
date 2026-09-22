"""Transform the clipboard with whatever coding agent Omarchy is already set up with.

PowerToys' Advanced Paste sends the clipboard to an OpenAI key you have to supply.
Omarchy users already have an agent CLI installed and logged in, so this reuses it:
no second credential, no network code of our own.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                      "omarchy-advanced-paste", "config.json")
AGENT_FILE = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                          "omarchy", "defaults", "agent")

# Agents that take a prompt on the command line and print the answer to stdout.
# The clipboard goes in on stdin, so its size is not a shell argument limit.
KNOWN = {
    "claude": ["claude", "-p", "{prompt}"],
    "gemini": ["gemini", "-p", "{prompt}"],
    "codex": ["codex", "exec", "{prompt}"],
    "opencode": ["opencode", "run", "{prompt}"],
    "crush": ["crush", "run", "{prompt}"],
}

SYSTEM = (
    "You transform a piece of text. The text to transform arrives on stdin. "
    "Reply with the transformed text and nothing else: no preamble, no explanation, "
    "no markdown fence around the whole answer, no quotes around it. "
    "Keep the original language unless the instruction says otherwise.\n\n"
    "Instruction: {instruction}"
)


class AIError(Exception):
    pass


def _config() -> dict:
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def command_for(instruction: str) -> list[str]:
    """The argv to run, with the instruction already substituted."""
    cfg = _config()
    template = cfg.get("ai_command")
    if not template:
        agent = ""
        try:
            with open(AGENT_FILE, encoding="utf-8") as f:
                agent = f.read().strip()
        except OSError:
            pass
        if agent in KNOWN and shutil.which(agent):
            template = KNOWN[agent]
        else:
            for name, cmd in KNOWN.items():
                if shutil.which(name):
                    template = cmd
                    break
    if not template:
        raise AIError("no AI agent found — set one with `omarchy default agent`, "
                      f"or put an \"ai_command\" in {CONFIG}")
    prompt = SYSTEM.format(instruction=instruction)
    return [arg.replace("{prompt}", prompt) for arg in template]


def transform(text: str, instruction: str, timeout: int = 180) -> str:
    cmd = command_for(instruction)
    if shutil.which(cmd[0]) is None:
        raise AIError(f"{cmd[0]} is not installed")
    try:
        r = subprocess.run(cmd, input=text.encode("utf-8"), capture_output=True,
                           timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        raise AIError(f"{cmd[0]} took longer than {timeout}s") from e
    out = r.stdout.decode("utf-8", "replace").strip()
    if r.returncode != 0:
        # An agent that failed still prints something ("Not logged in · Please run
        # /login"), and pasting that into the user's document would be worse than
        # saying nothing. Anything but a clean exit is an error, never a result.
        detail = (out or r.stderr.decode("utf-8", "replace")).strip().splitlines()
        raise AIError(f"{cmd[0]}: {detail[-1][:200]}" if detail
                      else f"{cmd[0]} exited {r.returncode}")
    if not out:
        raise AIError(f"{cmd[0]} returned nothing")
    return strip_fence(out)


def strip_fence(text: str) -> str:
    """Agents like wrapping an answer in ``` even when asked not to."""
    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])
    return text
