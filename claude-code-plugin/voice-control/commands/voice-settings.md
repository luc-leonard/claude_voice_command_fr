# Commande /voice-settings

Configure les paramètres du service vocal.

## Instructions pour Claude

Lorsque l'utilisateur exécute `/voice-settings [option] [valeur]`:

### Sans arguments
Affiche les paramètres actuels et les options disponibles.

### Avec arguments

#### Changer la voix TTS
`/voice-settings voice siwis` - Voix féminine
`/voice-settings voice gilles` - Voix masculine

1. Utilise l'outil MCP `voice_set_voice` avec la voix choisie
2. Confirme le changement

## Voix disponibles

| Nom | Genre | Description |
|-----|-------|-------------|
| siwis | Féminine | Voix française claire et naturelle |
| gilles | Masculine | Voix française masculine |

## Exemple de réponses

### Sans arguments
```
Paramètres vocaux actuels:
- Voix: siwis (féminine)

Options disponibles:
- /voice-settings voice siwis  - Voix féminine
- /voice-settings voice gilles - Voix masculine
```

### Changement de voix
```
Voix changée en: gilles (masculine)
```
