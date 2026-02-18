#!/usr/bin/env python3
"""Healthcheck script for the bot container.

Checks if the clawdia bot process is running by scanning /proc.
Works on Linux without requiring procps/pgrep.
"""

import os
import sys


def is_bot_running() -> bool:
    """Check if a process with 'clawdia' in its command line is running."""
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            cmdline_path = f"/proc/{pid}/cmdline"
            with open(cmdline_path, "rb") as f:
                cmdline = f.read().decode(errors="ignore")
                if "clawdia" in cmdline:
                    return True
        except (FileNotFoundError, PermissionError):
            continue
    return False


if __name__ == "__main__":
    sys.exit(0 if is_bot_running() else 1)
