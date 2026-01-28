# Claude Voice Command

Contrôle vocal pour Claude Code avec écoute continue, transcription Whisper et synthèse vocale Piper.

## Fonctionnement

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Microphone    │────►│  Whisper STT    │────►│  tmux send-keys │
│   (PulseAudio)  │     │  (GPU/CUDA)     │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Piper TTS     │◄────│   Claude Code   │◄────│  Terminal tmux  │
│   (Synthèse)    │     │   (via MCP)     │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

1. Vous parlez dans le microphone
2. Silero VAD détecte la parole
3. Whisper transcrit en français (avec vocabulaire technique)
4. Le texte est injecté dans Claude Code via tmux
5. Claude peut répondre vocalement via l'outil MCP `voice_speak`

## Prérequis

- Python 3.11+
- GPU NVIDIA avec CUDA (RTX 3090 recommandé, ~4 Go VRAM)
- WSL2 avec WSLg (pour l'audio sous Windows)
- tmux

## Installation

```bash
cd ~/dev/claude_voice_command

# Environnement virtuel
python3 -m venv .venv
source .venv/bin/activate

# Dépendances
pip install -e .
pip install piper-tts
```

## Utilisation

### 1. Lancer Claude Code dans tmux

```bash
# Créer une session tmux nommée "claude"
tmux new -s claude

# Dans tmux, lancer Claude Code
claude
```

### 2. Lancer le service vocal (autre terminal)

```bash
cd ~/dev/claude_voice_command
source .venv/bin/activate

# Lancer le service vocal ciblant la session tmux "claude"
python -m claude_voice_command.voice_service.main -t claude
```

### 3. Parler

Parlez en français. Le texte sera automatiquement transcrit et envoyé à Claude Code.

### Options du service vocal

```bash
# Cibler une session tmux spécifique
python -m claude_voice_command.voice_service.main -t ma_session

# Mode debug (plus de logs)
python -m claude_voice_command.voice_service.main --debug

# Test sans injection (affiche seulement)
python -m claude_voice_command.voice_service.main --no-inject

# Injection sans appuyer sur Entrée
python -m claude_voice_command.voice_service.main --no-enter
```

## Synthèse vocale (Claude parle)

### Configuration MCP globale

Copiez `mcp.json.example` vers `~/.mcp.json` et ajustez le chemin :

```bash
cp mcp.json.example ~/.mcp.json
# Éditez ~/.mcp.json et remplacez /path/to/ par votre chemin réel
```

### Déclencher la voix

Dans `~/.claude/CLAUDE.md` :
```markdown
Si l'outil MCP voice_speak est disponible :
- Réponds vocalement quand l'utilisateur dit "parle", "dis-moi", "à voix haute"
```

### Voix disponibles

| Nom | Genre | Commande |
|-----|-------|----------|
| siwis | Féminine | `voice_set_voice("siwis")` |
| gilles | Masculine | `voice_set_voice("gilles")` |

### Test manuel

```bash
python -c "
from claude_voice_command.voice_service.synthesizer import PiperSynthesizer
from claude_voice_command.voice_service.config import VoiceConfig
PiperSynthesizer(VoiceConfig()).speak('Bonjour, je suis Claude.')
"
```

## Vocabulaire technique

La transcription Whisper est optimisée pour le vocabulaire de développement :
- Git : commit, push, pull, merge, branch, PR, MR
- Outils : Docker, Kubernetes, API, CI/CD
- Claude : MCP, LLM, prompt

Les corrections automatiques transforment les erreurs courantes :
- "l'APR" → "la PR"
- "committe" → "commit"

## Prononciations TTS

Le TTS prononce correctement les abréviations :
- PR → "pé-air" (pas "professeur")
- API → "a-pé-i"
- JSON → "jay-sonne"
- MCP → "aime-cé-pé"

## Architecture

```
claude_voice_command/
├── voice_service/
│   ├── audio_capture.py   # Capture PulseAudio (WSLg)
│   ├── vad.py             # Silero VAD (détection parole)
│   ├── transcriber.py     # Whisper STT + corrections
│   ├── synthesizer.py     # Piper TTS + prononciations
│   ├── keyboard_inject.py # Injection tmux
│   └── main.py            # Service principal
├── mcp_server/
│   └── server.py          # Serveur MCP pour Claude
└── config.py              # Configuration
```

## Outils MCP

| Outil | Description |
|-------|-------------|
| `voice_speak` | Synthétiser et jouer du texte |
| `voice_set_voice` | Changer la voix (siwis/gilles) |
| `voice_get_status` | Statut du service |
| `voice_listen_start` | Démarrer l'écoute (si utilisé sans tmux) |
| `voice_listen_stop` | Arrêter l'écoute |

## Dépannage

### Pas de son dans WSL2
```bash
export PULSE_SERVER=/mnt/wslg/PulseServer
pactl info
```

### Session tmux non trouvée
```bash
# Lister les sessions
tmux list-sessions

# Créer une session
tmux new -s claude
```

### Transcription incorrecte
- Parlez clairement, évitez les bruits de fond
- Les anglicismes techniques sont gérés (PR, commit, push...)
- Ajoutez des corrections dans `transcriber.py` si nécessaire

## Performances

- Latence STT : ~500ms après fin de parole
- Latence TTS : ~200ms avant lecture
- VRAM : ~4 Go pour Whisper large-v3

## Licence

MIT
