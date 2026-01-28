# Commande /voice-status

Affiche le statut actuel du service vocal.

## Instructions pour Claude

Lorsque l'utilisateur exécute `/voice-status`:

1. Utilise l'outil MCP `voice_get_status` pour obtenir le statut
2. Affiche les informations de manière claire et concise
3. Indique les actions possibles selon l'état

## Informations affichées

- **État**: stopped, listening, processing, speaking
- **En écoute**: oui/non
- **Voix TTS**: nom de la voix actuelle (siwis/gilles)
- **Dernière transcription**: le dernier texte transcrit (si disponible)

## Exemple de réponse

```
Statut du service vocal:
- État: listening (en écoute)
- Voix: siwis (féminine)
- Dernière transcription: "montre moi le fichier config"
```
