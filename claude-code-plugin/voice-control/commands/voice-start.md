# Commande /voice-start

Démarre l'écoute vocale continue pour contrôler Claude Code par la voix.

## Instructions pour Claude

Lorsque l'utilisateur exécute `/voice-start`:

1. Utilise l'outil MCP `voice_listen_start` pour démarrer le service vocal
2. Confirme à l'utilisateur que l'écoute est active
3. Indique que l'utilisateur peut parler en français
4. Rappelle que `/voice-stop` arrête l'écoute

## Comportement attendu

- Le microphone commence à capturer l'audio
- La détection d'activité vocale (VAD) surveille la parole
- Quand l'utilisateur parle, le texte est transcrit par Whisper
- Les transcriptions sont envoyées à Claude Code comme prompts

## Exemple de réponse

```
Écoute vocale activée. Vous pouvez maintenant parler en français.
Je transcrirai vos paroles et y répondrai.
Pour arrêter, utilisez /voice-stop.
```
