"""Injection de texte via tmux."""

import logging
import subprocess
import os

logger = logging.getLogger(__name__)

# Session tmux cible (configurable)
TMUX_TARGET = os.environ.get("VOICE_TMUX_TARGET", "claude")


def inject_text(text: str, press_enter: bool = True, target: str | None = None) -> bool:
    """
    Injecte du texte dans une session tmux.

    Args:
        text: Texte à taper
        press_enter: Si True, appuie sur Entrée après le texte
        target: Session/fenêtre tmux cible (défaut: $VOICE_TMUX_TARGET ou "claude")

    Returns:
        True si succès
    """
    if not text.strip():
        return False

    target = target or TMUX_TARGET

    try:
        # Nettoyer le texte (enlever les retours à la ligne multiples)
        clean_text = " ".join(text.split())

        # Envoyer le texte via tmux send-keys
        # -l = literal (pas d'interprétation des séquences spéciales)
        subprocess.run(
            ["tmux", "send-keys", "-t", target, "-l", clean_text],
            check=True,
            capture_output=True,
        )

        logger.info(f"Texte injecté dans tmux:{target}: '{clean_text[:50]}...'")

        # Appuyer sur Entrée si demandé
        if press_enter:
            subprocess.run(
                ["tmux", "send-keys", "-t", target, "Enter"],
                check=True,
                capture_output=True,
            )
            logger.debug("Touche Entrée envoyée")

        return True

    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else str(e)
        if "no session" in stderr.lower() or "can't find" in stderr.lower():
            logger.error(f"Session tmux '{target}' non trouvée. Lancez: tmux new -s {target}")
        else:
            logger.error(f"Erreur tmux: {stderr}")
        return False
    except FileNotFoundError:
        logger.error("tmux n'est pas installé")
        return False
    except Exception as e:
        logger.error(f"Erreur injection texte: {e}")
        return False


def check_tmux(target: str | None = None) -> bool:
    """Vérifie que tmux et la session cible sont disponibles."""
    target = target or TMUX_TARGET

    try:
        # Vérifier que tmux est installé
        result = subprocess.run(
            ["tmux", "-V"],
            capture_output=True,
            check=True,
        )
        version = result.stdout.decode().strip()
        logger.info(f"tmux disponible: {version}")

        # Vérifier que la session existe
        result = subprocess.run(
            ["tmux", "has-session", "-t", target],
            capture_output=True,
        )

        if result.returncode != 0:
            logger.warning(f"Session tmux '{target}' non trouvée")
            logger.info(f"Créez-la avec: tmux new -s {target}")
            return False

        logger.info(f"Session tmux '{target}' trouvée")
        return True

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"tmux non disponible: {e}")
        return False


def list_tmux_sessions() -> list[str]:
    """Liste les sessions tmux disponibles."""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            check=True,
        )
        sessions = result.stdout.decode().strip().split("\n")
        return [s for s in sessions if s]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
