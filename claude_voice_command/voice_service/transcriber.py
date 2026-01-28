"""Transcription vocale avec faster-whisper."""

import logging
from dataclasses import dataclass

import numpy as np
from faster_whisper import WhisperModel

from .config import VoiceConfig

logger = logging.getLogger(__name__)

# Prompt initial pour guider Whisper vers le vocabulaire technique
TECHNICAL_PROMPT = """
Transcription d'un développeur français parlant de code et programmation.
Termes fréquents: créer une PR, faire un commit, push sur la branch, merge la PR,
ouvrir une issue, fix le bug, run les tests, deploy en prod, check le status.
Git: commit, push, pull, merge, branch, checkout, repository, repo, clone, fork.
GitHub: pull request, PR, issue, review, approve, merge request, MR.
Code: function, class, method, variable, const, import, export, async, await.
Outils: Docker, Kubernetes, API, REST, GraphQL, JSON, YAML, CI/CD, pipeline.
Languages: Python, JavaScript, TypeScript, React, Node, npm, pip.
Claude: Claude Code, Anthropic, MCP, LLM, prompt, completion.
Terminal: bash, zsh, tmux, vim, grep, curl, ssh.
"""

# Corrections post-transcription pour les erreurs courantes
POST_CORRECTIONS = {
    # PR / pull request
    "l'APR": "la PR",
    "l'apr": "la PR",
    "LAPR": "la PR",
    "lapr": "la PR",
    "un APR": "une PR",
    "le PR": "la PR",
    "les APR": "les PR",
    # Autres corrections courantes
    "committe": "commit",
    "commite": "commit",
    "pouche": "push",
    "poush": "push",
    "merge error": "merger",
    "pulpe": "pull",
    "branche": "branch",
    "Claude code": "Claude Code",
    "cloud code": "Claude Code",
    "MCP serveur": "MCP server",
}


def _apply_corrections(text: str) -> str:
    """Applique les corrections post-transcription."""
    result = text
    for wrong, correct in POST_CORRECTIONS.items():
        # Remplacement insensible à la casse mais préserve le contexte
        import re
        pattern = re.compile(re.escape(wrong), re.IGNORECASE)
        result = pattern.sub(correct, result)
    return result


@dataclass
class TranscriptionResult:
    """Résultat d'une transcription."""
    text: str
    language: str
    language_probability: float
    duration: float
    segments: list[dict]


class WhisperTranscriber:
    """Transcripteur vocal utilisant faster-whisper."""

    def __init__(self, config: VoiceConfig):
        self.config = config
        self._model: WhisperModel | None = None

    def _load_model(self) -> None:
        """Charge le modèle Whisper."""
        if self._model is not None:
            return

        logger.info(
            f"Chargement du modèle Whisper {self.config.whisper_model} "
            f"sur {self.config.whisper_device}..."
        )

        self._model = WhisperModel(
            self.config.whisper_model,
            device=self.config.whisper_device,
            compute_type=self.config.whisper_compute_type,
            download_root=str(self.config.models_dir / "whisper"),
        )

        logger.info("Modèle Whisper chargé")

    def transcribe(self, audio: np.ndarray) -> TranscriptionResult | None:
        """
        Transcrit un segment audio.

        Args:
            audio: Audio float32 normalisé [-1, 1] à 16kHz

        Returns:
            TranscriptionResult ou None si échec
        """
        self._load_model()

        if len(audio) < self.config.sample_rate * 0.1:  # Moins de 100ms
            return None

        try:
            segments, info = self._model.transcribe(
                audio,
                language=self.config.whisper_language,
                beam_size=self.config.whisper_beam_size,
                vad_filter=self.config.whisper_vad_filter,
                vad_parameters={
                    "min_silence_duration_ms": self.config.min_silence_duration_ms,
                },
                initial_prompt=TECHNICAL_PROMPT,
            )

            # Collecter tous les segments
            segment_list = []
            full_text_parts = []

            for segment in segments:
                segment_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                })
                full_text_parts.append(segment.text.strip())

            full_text = " ".join(full_text_parts).strip()

            if not full_text:
                return None

            # Appliquer les corrections post-transcription
            full_text = _apply_corrections(full_text)

            duration = len(audio) / self.config.sample_rate

            logger.debug(f"Transcription: '{full_text}' ({duration:.2f}s)")

            return TranscriptionResult(
                text=full_text,
                language=info.language,
                language_probability=info.language_probability,
                duration=duration,
                segments=segment_list,
            )

        except Exception as e:
            logger.error(f"Erreur de transcription: {e}")
            return None

    def unload_model(self) -> None:
        """Libère le modèle de la mémoire."""
        if self._model is not None:
            del self._model
            self._model = None
            logger.info("Modèle Whisper déchargé")
