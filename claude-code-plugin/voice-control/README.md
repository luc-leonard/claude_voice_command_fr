# Plugin Voice Control pour Claude Code

Contrôle vocal de Claude Code avec écoute continue et synthèse vocale en français.

## Fonctionnalités

- **Écoute continue** : pas de mot-clé d'activation, parlez naturellement
- **Transcription précise** : Whisper large-v3 sur GPU
- **Synthèse vocale** : Piper TTS avec voix françaises
- **Intégration native** : commandes slash et outils MCP

## Installation

### 1. Installer le service vocal

```bash
cd claude_voice_command
pip install -e .
```

### 2. Installer Piper TTS

```bash
pip install piper-tts
```

### 3. Configurer Claude Code

Ajoutez à votre `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "voice-control": {
      "command": "voice-mcp-server"
    }
  }
}
```

## Utilisation

### Commandes slash

| Commande | Description |
|----------|-------------|
| `/voice-start` | Démarre l'écoute vocale |
| `/voice-stop` | Arrête l'écoute vocale |
| `/voice-status` | Affiche le statut du service |
| `/voice-settings` | Configure les paramètres |

### Changer de voix

```
/voice-settings voice siwis   # Voix féminine
/voice-settings voice gilles  # Voix masculine
```

## Configuration requise

- Python 3.11+
- CUDA compatible GPU (RTX 3090 recommandé)
- ~4 Go VRAM pour Whisper large-v3
- Microphone fonctionnel

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│ Claude Code     │◄──►│ MCP Server      │◄──►│ Service Vocal    │
│                 │    │ voice-control   │    │ - VAD (Silero)   │
│ /voice-start    │    │                 │    │ - STT (Whisper)  │
│ /voice-stop     │    │                 │    │ - TTS (Piper)    │
└─────────────────┘    └─────────────────┘    └──────────────────┘
```

## Outils MCP disponibles

| Outil | Description |
|-------|-------------|
| `voice_listen_start` | Démarre l'écoute |
| `voice_listen_stop` | Arrête l'écoute |
| `voice_speak` | Synthétise et joue du texte |
| `voice_get_status` | Retourne le statut |
| `voice_get_transcription` | Récupère la dernière transcription |
| `voice_set_voice` | Change la voix TTS |

## Performances attendues

- Latence STT : < 500ms après fin de parole
- Latence TTS : < 200ms avant début lecture
- Utilisation GPU : < 4 Go VRAM
