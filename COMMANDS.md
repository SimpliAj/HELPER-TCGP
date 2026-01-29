# 📚 Command-Referenz

## 🔑 Permission Levels

- **Öffentlich** - Kann von jedem genutzt werden
- **Admin** - Benötigt Administrator-Permissions im Server
- **Owner** - Nur Bot-Owner (in `bot_config.json` gespeichert)

---

## 🎯 Setup & Administration Commands

### `/setup`
**Permission:** Admin  
**Beschreibung:** Interaktiver Setup-Wizard für Server-Konfiguration

**Ablauf:**
1. Mode Selection (Series oder Pack)
2. Validator Role Setup
3. Ping Roles Configuration
4. Source Channels Setup
5. Heartbeat Monitoring Setup
6. Feature Activation

**Beispiel:**
```
/setup
→ Wählt "Series Mode"
→ Setzt Validator-Role auf @Validators
→ Setzt Ping Roles für God Pack, Invalid God Pack, Safe 4 Trade
→ Setzt Source Channels
```

---

### `/setfilter`
**Permission:** Admin  
**Parameter:** 
- `filter_keyword` (erforderlich) - Keyword zu konfigurieren
- `channel` (optional) - Ziel-Channel
- `source_channels` (optional) - Quellen-Channels
- `godpack_ping` (optional) - Role für God Pack
- `invgodpack_ping` (optional) - Role für Invalid God Pack
- `safe_trade_ping` (optional) - Role für Safe 4 Trade

**Verfügbare Keywords:**
- `one star`, `three diamond`, `four diamond ex`, `gimmighoul`, `shiny`, `rainbow`, `full art`, `trainer` (Safe 4 Trade)
- `god pack`, `invalid god pack` (God Packs)
- `crown`, `immersive` (Detection)

**Beispiel:**
```
/setfilter god pack #god-packs @GodPackValidators
→ God Pack Nachrichten werden zu #god-packs weitergeleitet
→ @GodPackValidators wird gepingt wenn erkannt
```

---

### `/setpackfilter`
**Permission:** Admin  
**Parameter:**
- `pack` (erforderlich) - Pack-Name
- `channel` (optional) - Ziel-Channel
- `source_channels` (optional) - Quellen-Channels

**Besonderheit:** Respektiert `pack_channel_mode`
- **Series Mode:** Setzt alle Packs in der Serie
- **Pack Mode:** Setzt nur das spezifische Pack

**Beispiel:**
```
/setpackfilter palkia #palkia-pack
→ Alle Palkia-Nachrichten gehen zu #palkia-pack

/setpackfilter dialga (in Series Mode)
→ Alle A-Series Packs werden auf einen Channel konfiguriert
```

---

### `/setpackmode`
**Permission:** Admin  
**Parameter:** `mode` (series | pack)

**Series Mode:**
- Ein Channel pro Serie
- Alle Packs einer Serie teilen sich einen Channel

**Pack Mode:**
- Ein Channel pro Pack
- Jedes Pack hat seinen eigenen Channel

**Beispiel:**
```
/setpackmode series
→ Wechselt zu Series-Mode
→ Vorhandene Pack-Filter werden angepasst
```

---

### `/clearfilters`
**Permission:** Admin  
**Parameter:** `filter_type` (normal | pack | all)

**Beispiel:**
```
/clearfilters all
→ Löscht ALLE Filter (Keyword + Pack)

/clearfilters normal
→ Löscht nur Keyword-Filter (z.B. "god pack")

/clearfilters pack
→ Löscht nur Pack-Filter (z.B. "palkia")
```

---

### `/resetsources`
**Permission:** Admin

Interaktiv wählen:
- **Set New Sources** - Neue Source Channels konfigurieren
- **Reset to All Channels** - Zustand vor Setup wiederherstellen

**Beispiel:**
```
/resetsources
→ Zeigt aktuelle Source Channels
→ Erlaubt neue zu setzen oder alle zurückzusetzen
```

---

### `/setvalidatorrole`
**Permission:** Admin  
**Parameter:** `role` (erforderlich)

Setzt die Role die Validierungs-Buttons nutzen darf

**Beispiel:**
```
/setvalidatorrole @Validators
→ Nur @Validators können God Pack validieren
```

---

### `/setpingroles`
**Permission:** Admin

Interaktiver Ping-Role Setup:
1. Wähle Ping-Typ (God Pack / Invalid God Pack / Safe 4 Trade)
2. Wähle die Role aus

**Beispiel:**
```
/setpingroles
→ Wählt "God Pack"
→ Setzt @GodPackPing
```

---

### `/setheartbeat`
**Permission:** Admin  
**Parameter:**
- `source_channel` (erforderlich) - Überwachter Channel
- `target_channel` (erforderlich) - Ziel für Status-Embed

**Funktion:** Postet Status-Embed mit letztem Activity

**Beispiel:**
```
/setheartbeat #activity-monitor #heartbeat-status
→ Überwacht #activity-monitor
→ Postet Status alle 5 Minuten in #heartbeat-status
```

---

### `/setstatus`
**Permission:** Admin  
**Parameter:** `status` (true | false)

Aktiviert/Deaktiviert "Traded" Buttons bei Safe 4 Trade Nachrichten

**Beispiel:**
```
/setstatus true
→ Safe 4 Trade Nachrichten zeigen "Mark as Traded" Button

/setstatus false
→ Button wird nicht angezeigt
```

---

## 📦 Pack Management Commands

### `/addseries`
**Permission:** Owner  
**Parameter:** `series_name` (erforderlich)

Fügt neue Pack-Serie zur globalen Config hinzu

**Auto-Create:**
- Erstellt Category in ALLEN Servern wo Bot Admin hat
- Aktualisiert globale bot_config.json
- Benachrichtigt Admins in jedem Server

**Beispiel:**
```
/addseries C-Series
→ Neue C-Series wird hinzugefügt
→ Category "C-Series" in allen Servern erstellt
```

---

### `/addpack`
**Permission:** Owner  
**Parameter:**
- `pack_name` (erforderlich)
- `series` (optional, default: "A-Series")

Fügt neues Pack zur globalen Config hinzu

**Auto-Create:**
- Erstellt Pack-Channels in allen SETUP Servern
- Respektiert `pack_channel_mode`
- Aktualisiert Pingen-Rollen Validierung

**Beispiel:**
```
/addpack zacian A-Series
→ Neues Pack "zacian" wird zu A-Series hinzugefügt
→ Channels werden auto-erstellt
```

---

### `/removepack`
**Permission:** Owner  
**Parameter:** `pack_name` (erforderlich)

Entfernt Pack aus globaler Config

**Auto-Delete (im Pack-Mode):**
- Löscht Pack-Channels in allen Servern
- Entfernt aus pack_channel_map
- Bereinigt Statistiken

**Beispiel:**
```
/removepack zacian
→ Pack "zacian" wird entfernt
→ Alle zacian-Channels werden gelöscht
```

---

### `/removeseries`
**Permission:** Owner  
**Parameter:** `series_name` (erforderlich)

Entfernt komplette Serie mit allen Packs

**Auto-Delete:**
- Löscht Serie-Category
- Löscht alle Pack-Channels
- Entfernt aus globaler Config

**Beispiel:**
```
/removeseries C-Series
→ Komplette C-Series wird gelöscht
→ Category + alle Channels gelöscht
```

---

### `/createpackcategory`
**Permission:** Admin  
**Parameter:** `pack` (erforderlich)

Erstellt Category speziell für ein Pack mit allen Save 4 Trade Keywords

**Channels erstellt:**
- one-star
- three-diamond
- four-diamond-ex
- gimmighoul
- shiny
- rainbow
- full-art
- trainer

**Beispiel:**
```
/createpackcategory palkia
→ Category "Palkia - Save 4 Trade" erstellt
→ 8 Channels für jeden Save 4 Trade Filter
→ Automatische Weiterleitung konfiguriert
```

---

## 📊 Statistics Commands

### `/stats`
**Permission:** Öffentlich  
**Parameter:** `channel` (optional)

Zeigt Server-Statistiken:
- Total God Packs (Valid/Invalid)
- Total Trades (Traded/Not Traded)

**Mit Channel:** Postet Auto-Update Embed

**Beispiel:**
```
/stats
→ Zeigt Statistiken als Ephemeral Message

/stats #statistics
→ Postet in #statistics
→ Updates alle 60 Minuten automatisch
```

---

### `/detailedstats`
**Permission:** Öffentlich  
**Parameter:** `channel` (optional)

Detaillierte Statistiken pro Filter:
- Breakdown für jeden Keyword
- Breakdown für jeden Pack
- Safe 4 Trade vs Detection Stats

**Mit Channel:** Postet Auto-Update Embed

**Beispiel:**
```
/detailedstats #stats
→ Zeigt wie viele "one star", "three diamond" etc. gefunden
```

---

### `/packstats`
**Permission:** Öffentlich  
**Parameter:** `channel` (optional)

Pack-spezifische Statistiken:
- Wie viele von jedem Pack gefunden
- Grouped nach Serie

**Mit Channel:** Postet Auto-Update Embed

**Beispiel:**
```
/packstats #pack-stats
→ Zeigt pro Pack die Anzahl gefundener Nachrichten
```

---

### `/lifetimestats`
**Permission:** Owner  
**Parameter:** `channel` (optional)

Globale Lifetime-Statistiken über ALLE Server:
- Total Servers Configured
- Total God Packs (Global)
- Total Trades (Global)
- Pack Breakdown (Global)

**Mit Channel:** Postet in Channel, Updates alle 60 Minuten

**Beispiel:**
```
/lifetimestats
→ Zeigt globale Statistiken ephemeral

/lifetimestats #global-stats
→ Globale Stats in Channel mit Auto-Update
```

---

### `/meta`
**Permission:** Öffentlich

Zeigt Current TCG Meta-Decks

**Beispiel:**
```
/meta
→ Meta-Deck Information
```

---

### `/showfilters`
**Permission:** Öffentlich

Zeigt alle aktiven Filter im Server:
- Keyword-Filter mit Ziel-Channels
- Pack-Filter mit Ziel-Channels
- Source-Channels

**Beispiel:**
```
/showfilters
→ Listet alle Filter auf
```

---

## 🎮 Utility Commands

### `/removefilter`
**Permission:** Admin  
**Parameter:** `filter_keyword` (erforderlich)

Entfernt einen Keyword-Filter

**Beispiel:**
```
/removefilter god pack
→ God Pack Filter wird entfernt
→ Nachrichten werden nicht mehr weitergeleitet
```

---

### `/removepackfilter`
**Permission:** Admin  
**Parameter:** `pack` (erforderlich)

Entfernt einen Pack-Filter

**Beispiel:**
```
/removepackfilter palkia
→ Palkia Pack Filter wird entfernt
```

---

### `/pick4me`
**Permission:** Öffentlich

Zufallsauswahl zwischen 5 Optionen:
- Top Left
- Top Middle
- Top Right
- Bottom Left
- Bottom Right

**Beispiel:**
```
/pick4me
→ > Top Left
```

---

### `/help`
**Permission:** Öffentlich

Zeigt Übersicht aller verfügbaren Commands

**Beispiel:**
```
/help
→ Kategorisierte Command-Liste
```

---

### `/sync`
**Permission:** Owner

Synct alle Slash-Commands mit Discord

**Wann nötig:**
- Nach Code-Deployment
- Nach Command-Änderungen
- Wenn Commands nicht angezeigt werden

**Beispiel:**
```
/sync
→ 26 commands synced
```

---

## 🎛️ Button & Modal Interactions

### God Pack Validation Buttons

**Zeigt:** Wenn "god pack" erkannt wird und Validator-Role gesetzt

**Buttons:**
- ✅ Valid - Aktualisiert Stats als "valid"
- ❌ Invalid - Aktualisiert Stats als "invalid"

**Beispiel:**
```
User schreibt: "Found a god pack!"
Bot: [Embed mit God Pack Icon]
  [✅ Valid] [❌ Invalid]
```

---

### Safe 4 Trade Traded Modal

**Zeigt:** Bei Safe 4 Trade Nachrichten mit aktiviertem Status

**Fields:**
- Traded? (True/False)
- Card Details (optional)

**Beispiel:**
```
User klickt "Mark as Traded"
Modal: [Traded?] [Card Details]
```

---

## ⌚ Auto-Update Feature

Alle Stats-Commands können in Channels gepostet werden:

```
/stats #channel
→ Postet Auto-Update Embed
→ Updates alle 60 Minuten
→ Zeigt "Last updated: HH:MM Berlin Time"
```

Nur ein Update-Embed pro Command pro Channel ist aktiv!

---

## 📝 Command Response Types

### Ephemeral (Nur für Auslöser sichtbar)
- `/sync` - Owner Command Result
- Fehler-Messages
- Confirmation Messages

### Public (Für alle sichtbar)
- `/stats` - ohne Channel parameter
- `/pick4me`
- `/help`
- `/showfilters`

### Channel Post (Mit Auto-Update)
- `/stats #channel`
- `/lifetimestats #channel`
- `/detailedstats #channel`
- `/packstats #channel`

---

## 🔗 Autocomplete Features

Diese Commands haben Autocomplete:

| Command | Autocomplete | Source |
|---------|------------|--------|
| `/setfilter` | Keywords | FILTER_CHOICES |
| `/setpackfilter` | Pack Namen | bot_config.json |
| `/removefilter` | Konfigurierte Filter | Guild Config |
| `/removepackfilter` | Konfigurierte Packs | Guild Config |
| `/addseries` | - | - |
| `/addpack` | Series Namen | bot_config.json |
| `/removepack` | Pack Namen | bot_config.json |
| `/removeseries` | Series Namen | bot_config.json |
| `/createpackcategory` | Pack Namen | bot_config.json |

---

## 💡 Best Practices

1. **Setup zuerst:** Nutze `/setup` für initiale Konfiguration
2. **Source Channels:** Setze Source Channels bevor du Filter konfigurierst
3. **Validator Role:** Setze Validator-Role bevor God Packs gepostet werden
4. **Auto-Update:** Nutze Channel-Parameter für wichtige Stats
5. **Sync nach Updates:** Führe `/sync` aus nach Bot-Restart

---

## 🆘 Häufige Fehler & Lösungen

| Fehler | Ursache | Lösung |
|--------|--------|--------|
| "Missing permissions" | Bot hat nicht genug Rechte | Gib Bot mehr Permissions |
| "Unknown channel" | Channel nicht gültig | Wähle einen existierenden Channel |
| "Cannot find role" | Role wurde gelöscht | Setze Role neu |
| "Cannot create channel" | Guild voll oder Permissions fehlen | Gib Bot Manage Channels Permission |

---

**Alle Commands sind case-insensitive und akzeptieren Autocomplete!**
