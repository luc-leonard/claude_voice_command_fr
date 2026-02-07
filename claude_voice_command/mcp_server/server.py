"""MCP Server pour le service vocal Claude Code."""

import asyncio
import logging
import os
import sys
from typing import Any

# Configurer PULSE_SERVER pour WSLg si disponible
if os.path.exists("/mnt/wslg/PulseServer"):
    os.environ.setdefault("PULSE_SERVER", "/mnt/wslg/PulseServer")

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from ..voice_service import VoiceConfig
from ..voice_service.config import TTSVoice
from ..voice_service.main import ServiceState, VoiceService

logger = logging.getLogger(__name__)

# Instance globale du service vocal
_voice_service: VoiceService | None = None
_transcription_queue: asyncio.Queue[str] = asyncio.Queue()


def _get_service() -> VoiceService:
    """Retourne l'instance du service vocal, la crée si nécessaire."""
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService(VoiceConfig())
        _voice_service.set_transcription_callback(_on_transcription)
    return _voice_service


def _on_transcription(text: str) -> None:
    """Callback appelé lors d'une transcription."""
    try:
        _transcription_queue.put_nowait(text)
    except asyncio.QueueFull:
        logger.warning("Queue de transcription pleine, transcription ignorée")


def create_server() -> Server:
    """Crée et configure le serveur MCP."""
    server = Server("voice-control")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Liste les outils disponibles."""
        return [
            Tool(
                name="voice_listen_start",
                description="Démarre l'écoute vocale continue. Retourne un statut de confirmation.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="voice_listen_stop",
                description="Arrête l'écoute vocale.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="voice_speak",
                description="Synthétise et joue du texte en français.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Le texte à synthétiser et jouer.",
                        },
                    },
                    "required": ["text"],
                },
            ),
            Tool(
                name="voice_get_status",
                description="Retourne le statut actuel du service vocal.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="voice_get_transcription",
                description="Récupère la dernière transcription vocale en attente. Retourne None si aucune transcription disponible.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timeout": {
                            "type": "number",
                            "description": "Timeout en secondes pour attendre une transcription (défaut: 0 = pas d'attente).",
                            "default": 0,
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="voice_set_voice",
                description="Change la voix TTS utilisée.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "voice": {
                            "type": "string",
                            "description": "Nom de la voix: 'feminine_1', 'feminine_2', 'masculine_1', 'masculine_2'.",
                            "enum": ["feminine_1", "feminine_2", "masculine_1", "masculine_2"],
                        },
                    },
                    "required": ["voice"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Exécute un outil."""
        service = _get_service()

        try:
            if name == "voice_listen_start":
                if service.is_listening:
                    return [TextContent(type="text", text="L'écoute vocale est déjà active.")]

                await service.start_listening()
                return [TextContent(type="text", text="Écoute vocale démarrée. Parlez en français.")]

            elif name == "voice_listen_stop":
                if not service.is_listening:
                    return [TextContent(type="text", text="L'écoute vocale n'est pas active.")]

                await service.stop_listening()
                return [TextContent(type="text", text="Écoute vocale arrêtée.")]

            elif name == "voice_speak":
                text = arguments.get("text", "")
                if not text:
                    return [TextContent(type="text", text="Erreur: aucun texte fourni.")]

                success = await service.speak(text)
                if success:
                    return [TextContent(type="text", text=f"Texte prononcé: '{text[:50]}...'")]
                else:
                    return [TextContent(type="text", text="Erreur lors de la synthèse vocale.")]

            elif name == "voice_get_status":
                status = service.get_status()
                return [TextContent(
                    type="text",
                    text=(
                        f"État: {status.state.value}\n"
                        f"En écoute: {status.is_listening}\n"
                        f"Voix: {status.current_voice}\n"
                        f"Dernière transcription: {status.last_transcription or 'Aucune'}"
                    ),
                )]

            elif name == "voice_get_transcription":
                timeout = arguments.get("timeout", 0)

                try:
                    if timeout > 0:
                        text = await asyncio.wait_for(
                            _transcription_queue.get(),
                            timeout=timeout,
                        )
                    else:
                        text = _transcription_queue.get_nowait()

                    return [TextContent(type="text", text=text)]
                except (asyncio.TimeoutError, asyncio.QueueEmpty):
                    return [TextContent(type="text", text="")]

            elif name == "voice_set_voice":
                voice_name = arguments.get("voice", "").lower()
                voice_map = {
                    "feminine_1": TTSVoice.FEMININE_1,
                    "feminine_2": TTSVoice.FEMININE_2,
                    "masculine_1": TTSVoice.MASCULINE_1,
                    "masculine_2": TTSVoice.MASCULINE_2,
                }

                if voice_name not in voice_map:
                    return [TextContent(
                        type="text",
                        text=(
                            f"Erreur: voix inconnue '{voice_name}'. "
                            "Utilisez 'feminine_1', 'feminine_2', 'masculine_1' ou 'masculine_2'."
                        ),
                    )]

                service.set_voice(voice_map[voice_name])
                return [TextContent(type="text", text=f"Voix changée en: {voice_name}")]

            else:
                return [TextContent(type="text", text=f"Outil inconnu: {name}")]

        except Exception as e:
            logger.exception(f"Erreur lors de l'exécution de {name}")
            return [TextContent(type="text", text=f"Erreur: {e!s}")]

    return server


async def run_server() -> None:
    """Lance le serveur MCP via stdio."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    server = create_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Point d'entrée principal."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
