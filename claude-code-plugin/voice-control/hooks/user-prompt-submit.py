#!/usr/bin/env python3
"""Hook de soumission de prompt - traite les transcriptions vocales."""

import json
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

    prompt = hook_input.get("prompt", "")

    # Le hook passe simplement le prompt
    # La logique de transcription vocale est gérée par le MCP server
    result = {
        "status": "ok",
        "prompt": prompt,
        "modified": False,
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
