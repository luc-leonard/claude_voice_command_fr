#!/usr/bin/env python3
"""Hook de notification - lit les notifications importantes à voix haute."""

import json
import os
import sys


def main():
    """Point d'entrée du hook."""
    # Lire l'entrée du hook
    hook_input = {}
    if not sys.stdin.isatty():
        try:
            hook_input = json.load(sys.stdin)
        except json.JSONDecodeError:
            pass

    notification = hook_input.get("message", "")
    level = hook_input.get("level", "info")

    # Vérifier si les notifications vocales sont activées
    config_path = os.path.expanduser("~/.config/claude-voice/config.json")
    speak_notifications = False

    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
                speak_notifications = config.get("speak_notifications", False)
        except (json.JSONDecodeError, OSError):
            pass

    result = {
        "status": "ok",
        "should_speak": speak_notifications and level in ("warning", "error"),
        "message": notification,
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
