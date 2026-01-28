# Commande /voice-stop

Arrête l'écoute vocale continue.

## Instructions pour Claude

Lorsque l'utilisateur exécute `/voice-stop`:

1. Utilise l'outil MCP `voice_listen_stop` pour arrêter le service vocal
2. Confirme à l'utilisateur que l'écoute est désactivée
3. Indique que l'utilisateur peut relancer avec `/voice-start`

## Comportement attendu

- Le microphone arrête la capture
- Le service vocal se met en pause
- Les ressources GPU sont préservées (le modèle reste chargé)

## Exemple de réponse

```
Écoute vocale désactivée.
Pour reprendre, utilisez /voice-start.
```
