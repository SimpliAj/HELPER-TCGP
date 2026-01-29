# 🔧 Detaillierte Setup-Anleitung

## Schritt 1: Bot auf Discord Developer Portal erstellen

1. Gehe zu [Discord Developer Portal](https://discord.com/developers/applications)
2. Klicke auf "New Application"
3. Gib einen Namen ein (z.B. "TCGP Bot")
4. Akzeptiere die Terms und klicke "Create"

### Bot-User erstellen
1. Gehe zum Tab "Bot"
2. Klicke "Add Bot"
3. Kopiere den **TOKEN** (du wirst ihn später brauchen)
4. Aktiviere diese Intents:
   - Message Content Intent
   - Server Members Intent
   - Guild Members Intent

### Bot zum Server einladen
1. Gehe zum Tab "OAuth2" → "URL Generator"
2. Wähle diese Scopes:
   - `bot`
   - `applications.commands`
3. Wähle diese Permissions:
   - Administrator (oder zumindest: Manage Channels, Send Messages, Embed Links, Read Message History)
4. Kopiere die URL und öffne sie → Bot wird eingeladen

## Schritt 2: Projekt einrichten

### Python-Dependencies installieren
```bash
cd tcgp-v2
pip install -r requirements.txt
```

Falls `requirements.txt` nicht existiert:
```bash
pip install discord.py python-dotenv
```

### .env Datei erstellen
```bash
# Kopiere .env.example
cp .env.example .env

# Öffne .env und setze deinen Discord Token
# DISCORD_TOKEN=dein_token_hier
```

## Schritt 3: Webhooks erstellen

Der Bot benötigt 2 Discord Webhooks für Fehler-Logging:

### Error Webhook
1. Erstelle einen privaten Channel (z.B. #bot-errors)
2. Klicke auf ⚙️ → Webhooks → "Create Webhook"
3. Kopiere die URL → kommt in `bot_config.json` unter `error_webhook_url`

### Permission Warning Webhook
1. Erstelle einen privaten Channel (z.B. #bot-warnings)
2. Klicke auf ⚙️ → Webhooks → "Create Webhook"
3. Kopiere die URL → kommt in `bot_config.json` unter `permission_warning_webhook_url`

## Schritt 4: bot_config.json konfigurieren

```json
{
    "series": {
        "A-Series": [
            "palkia",
            "dialga",
            "arceus",
            "shining",
            "mew",
            "pikachu",
            "charizard",
            "mewtwo",
            "solgaleo",
            "lunala",
            "buzzwole",
            "eevee",
            "hooh",
            "lugia",
            "springs",
            "deluxe"
        ],
        "B-Series": [
            "megagyarados",
            "megaaltaria",
            "megablaziken",
            "crimsonblaze",
            "Parade"
        ]
    },
    "packs": [
        "palkia",
        "dialga",
        "arceus",
        "shining",
        "mew",
        "pikachu",
        "charizard",
        "mewtwo",
        "solgaleo",
        "lunala",
        "buzzwole",
        "eevee",
        "hooh",
        "lugia",
        "springs",
        "deluxe",
        "megagyarados",
        "megaaltaria",
        "megablaziken",
        "crimsonblaze",
        "parade"
    ],
    "error_webhook_url": "https://discord.com/api/webhooks/...",
    "permission_warning_webhook_url": "https://discord.com/api/webhooks/...",
    "owner_id": 774679828594163802,
    "timezone": "Europe/Berlin"
}
```

**WICHTIG:** Passe `owner_id` auf deine Discord-ID an!

Deine Discord-ID findest du:
1. Aktiviere Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Rechtsklick auf deinen Profilnamen → "Copy User ID"

## Schritt 5: Bot starten

```bash
python main.py
```

Der Bot sollte folgende Ausgabe zeigen:
```
Logged in as BotName#0000
Bot is ready!
```

## Schritt 6: Ersten Server Konfigurieren

Gehe in einen Discord-Server wo der Bot Admin-Permissions hat und:

1. Schreib `/setup`
2. Folge dem Guided Setup Wizard:
   - Wähle Pack-Modus (Series oder Pack)
   - Setze Validator-Role
   - Konfiguriere Ping-Rollen
   - Setze Source-Channels
   - Aktiviere/Deaktiviere Features

Das war's! Der Bot sollte jetzt funktionieren.

## Optional: Cron Job für kontinuierlichen Betrieb

### Auf Windows (Task Scheduler)
1. Öffne Task Scheduler
2. Create Basic Task
3. Action: Start a program
4. Program: `python.exe`
5. Arguments: `C:\path\to\tcgp-v2\main.py`
6. Trigger: At startup

### Auf Linux/Mac
```bash
# Crontab bearbeiten
crontab -e

# Addiere diese Zeile (startet Bot bei jedem Reboot):
@reboot cd /path/to/tcgp-v2 && python main.py >> bot.log 2>&1
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'discord'"
```bash
pip install discord.py
```

### "Bot token invalid"
- Überprüfe ob der Token in `.env` korrekt ist
- Token sollte nicht mit Anführungszeichen sein

### "Missing Intents"
Stelle sicher dass folgende Intents im Developer Portal aktiviert sind:
- ✅ Message Content Intent
- ✅ Server Members Intent

### "Cannot find bot_config.json"
Stelle sicher dass `bot_config.json` im gleichen Verzeichnis wie `main.py` ist

### Bot antwortet auf Commands nicht
1. Schreib `/sync` (wenn du Owner bist)
2. Warte 5 Sekunden
3. Versuche den Command wieder

## Weitere Ressourcen

- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [Discord Developer Portal](https://discord.com/developers/applications)
- [Discord API Documentation](https://discord.com/developers/docs)

## Support

Hast du Probleme? Öffne ein Issue mit:
- Python Version (`python --version`)
- Fehlermeldung (kompletter Text)
- `bot_config.json` (ohne Token und Webhook URLs)
- Schritte um das Problem zu reproduzieren
