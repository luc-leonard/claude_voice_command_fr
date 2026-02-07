#!/bin/bash
# Script d'installation pour Claude Voice Command

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installation de Claude Voice Command ==="

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo "Erreur: Python 3 n'est pas installé"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

# Vérifier CUDA (requis pour Kyutai DSM-TTS)
if command -v nvidia-smi &> /dev/null; then
    echo "CUDA disponible:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

    # Vérifier la VRAM disponible (Kyutai DSM-TTS nécessite ~8-12 Go)
    VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | tr -d ' ')
    if [ "$VRAM_MB" -lt 8000 ]; then
        echo "Attention: VRAM insuffisante (${VRAM_MB} Mo). Kyutai DSM-TTS nécessite ~8-12 Go de VRAM."
        echo "Le modèle pourrait ne pas se charger correctement."
    else
        echo "VRAM suffisante (${VRAM_MB} Mo) pour Kyutai DSM-TTS."
    fi
else
    echo "ERREUR: CUDA non détecté. Kyutai DSM-TTS nécessite un GPU NVIDIA avec CUDA."
    echo "Whisper fonctionnera sur CPU mais sera plus lent."
fi

# Vérifier WSLg
if [ -S "/mnt/wslg/PulseServer" ]; then
    echo "WSLg PulseAudio détecté"
    export PULSE_SERVER=/mnt/wslg/PulseServer
else
    echo "Attention: WSLg non détecté. Vérifiez votre configuration audio."
fi

# Créer un environnement virtuel
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "Création de l'environnement virtuel..."
    python3 -m venv "$SCRIPT_DIR/.venv"
fi

source "$SCRIPT_DIR/.venv/bin/activate"
echo "Environnement virtuel activé"

# Vérifier libpulse
if ! ldconfig -p 2>/dev/null | grep -q "libpulse-simple"; then
    echo "Installation des dépendances système requises..."
    echo "Exécutez: sudo apt-get install libpulse0 pulseaudio-utils"
fi

# Installer les dépendances Python
echo "Installation des dépendances Python..."
pip install -e "$SCRIPT_DIR"

# moshi (Kyutai DSM-TTS) est installé automatiquement via pyproject.toml

# Vérifier l'installation
echo ""
echo "=== Vérification de l'installation ==="

python3 -c "
import os
if os.path.exists('/mnt/wslg/PulseServer'):
    os.environ['PULSE_SERVER'] = '/mnt/wslg/PulseServer'

from claude_voice_command.voice_service.pulse_bindings import PULSE_AVAILABLE
from claude_voice_command.mcp_server.server import create_server

print(f'PulseAudio: {\"OK\" if PULSE_AVAILABLE else \"NON DISPONIBLE\"}')

server = create_server()
print(f'Serveur MCP: OK ({server.name})')

print('Installation réussie!')
"

# Instructions
echo ""
echo "=== Configuration ==="
echo ""
echo "1. Pour utiliser le service vocal avec Claude Code dans tmux:"
echo ""
echo "   # Terminal 1: Claude Code dans tmux"
echo "   tmux new -s claude"
echo "   claude"
echo ""
echo "   # Terminal 2: Service vocal"
echo "   source $SCRIPT_DIR/.venv/bin/activate"
echo "   python -m claude_voice_command.voice_service.main -t claude"
echo ""
echo "2. Pour que Claude puisse parler, copiez mcp.json.example vers ~/.mcp.json"
echo "   et ajustez les chemins."
echo ""
echo "=== Installation terminée ==="
