#!/usr/bin/env python3
"""Hook de démarrage de session - initialise le service vocal si configuré."""

import json
import os
import sys


def main():
    """Point d'entrée du hook."""
    # Lire l'entrée du hook (si disponible)
    hook_input = {}
    if not sys.stdin.isatty():
        try:
            hook_input = json.load(sys.stdin)
        except json.JSONDecodeError:
            pass

    # Vérifier si l'auto-start est activé
    config_path = os.path.expanduser("~/.config/claude-voice/config.json")
    auto_start = False

    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
                auto_start = config.get("auto_start", False)
        except (json.JSONDecodeError, OSError):
            pass

    # Retourner le résultat
    result = {
        "status": "ok",
        "auto_start_enabled": auto_start,
        "message": "Service vocal prêt" if auto_start else "Service vocal disponible (utilisez /voice-start)",
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
