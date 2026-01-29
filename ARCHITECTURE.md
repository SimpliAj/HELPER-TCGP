# 🏗️ Projekt-Architektur

## Übersicht

TCGP Bot ist ein modularer Discord-Bot mit Cog-basierter Architektur für einfache Erweiterbarkeit und Wartung.

```
┌─────────────────────────────────────┐
│        Discord API (discord.py)     │
└──────────────┬──────────────────────┘
               │
       ┌───────▼────────┐
       │   main.py      │
       │ (Bot Kernel)   │
       └───────┬────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼──┐  ┌────▼────┐  ┌──▼────┐
│Config│  │Handlers │  │Commands│
│System│  │(Message)│  │(Cogs)  │
└──┬───┘  └─────────┘  └──┬─────┘
   │                       │
┌──▼───────────────────────▼──┐
│       Guild Configs          │
│    (guild_configs/*.json)    │
└──────────────────────────────┘
```

## 📦 Module-Struktur

### **main.py** - Bot Kernel
**Verantwortung:**
- Bot-Initialisierung (Intents, Cogs laden)
- Event Handler (on_ready, on_message)
- Task Scheduling
- Guild Management

**Key Functions:**
```python
async def main()                    # Bot starten
async def load_cogs()               # Commands dynamisch laden
async def on_ready()                # Bot bereit
async def on_message(message)       # Nachricht verarbeitet
async def auto_cleanup_task()       # Cleanup jede 60s
async def heartbeat_monitor()       # Status alle 5min
async def lifetime_stats_update_task()  # Stats alle 60min
```

**Dependencies:**
- config.py
- webhooks.py
- handlers/message.py
- Alle commands/

---

### **config.py** - Konfiguration Manager
**Verantwortung:**
- Global bot_config.json laden/speichern
- Guild-spezifische Configs verwalten
- Migrations & Upgrades
- Thread-Safe Operationen

**Key Functions:**
```python
def load_config()                   # bot_config.json laden
def save_config(config)             # Config speichern
def load_guild_config(guild_id)     # Guild Config laden
def save_guild_config(guild_id, config)  # Guild Config speichern
def migrate_configs()               # Alte Configs updaten
def final_cleanup_config(config)    # Aufräumen
```

**Config-Struktur:**
```
Global (bot_config.json):
├── series: {name: [packs]}
├── packs: [list]
├── webhooks: {urls}
└── owner_id, timezone

Guild-Specific (guild_configs/guild_*.json):
├── pack_channel_mode: "series" | "pack"
├── keyword_channel_map: {keyword: config}
├── pack_channel_map: {pack: config}
├── stats: {categories}
├── roles: {role_ids}
└── channels: {channel_ids}
```

---

### **utils.py** - Utilities & Constants
**Verantwortung:**
- Globale Constants definieren
- Embed-Generierungsfunktionen
- Helper-Funktionen

**Key Content:**
```python
# Constants
SAVE4TRADE_KEYWORDS     # Keyword Liste
FILTER_CHOICES          # Für Command Autocomplete
CUSTOM_EMBED_TEXT       # Embed-Beschreibungen
EMBED_COLORS            # Color Mapping
EMBED_THUMBNAILS        # Thumbnail URLs

# Functions
def create_stats_embed()
def create_detailed_stats_embed()
def create_pack_stats_embed()
def create_heartbeat_embed()
def split_field_value()
```

---

### **webhooks.py** - Error Logging
**Verantwortung:**
- Fehler zu Discord Webhooks loggen
- Permission Warnings tracken

**Key Functions:**
```python
async def log_error_to_webhook(config, berlin_tz, msg, guild_id, command)
async def log_permission_warning_to_webhook(config, berlin_tz, msg, guild_id, command)
```

---

## 🎯 Commands Module

### **commands/setup.py** - Setup Wizard
**Commands:**
- `/setup` - Interaktiver Setup mit 6 Steps

**Features:**
- Mode Selection (Series/Pack)
- Validator Role Setup
- Ping Roles (God Pack, Invalid, Safe 4 Trade)
- Source Channels
- Heartbeat Configuration

**Views:**
- ModeView (Series/Pack Buttons)
- ValidatorView (Role Selection)
- PingSetupView (3 Ping Roles)
- SourceModal (Channel Input)
- ValidationSetupView (Validation Toggle)
- HeartbeatSetupView (Heartbeat Config)

---

### **commands/admin.py** - Admin Commands
**Commands:**
- `/clearfilters` - Filter löschen
- `/setpackmode` - Mode wechseln
- `/resetsources` - Sources zurücksetzen
- `/setfilter` - Keyword-Filter konfigurieren
- `/setpackfilter` - Pack-Filter konfigurieren
- `/setvalidatorrole` - Validator-Role setzen

**Features:**
- Auto-Channel-Erstellung
- Source Channel Parsing
- Role Ping Mapping
- Config Persistence

---

### **commands/stats.py** - Statistics Commands
**Commands:**
- `/stats` - Server Stats
- `/meta` - Meta Information
- `/setpingroles` - Ping Roles (alternative)

**Features:**
- Embed Generation
- Auto-Update Messages
- Guild Config Aggregation

---

### **commands/utility.py** - Utility Commands
**Commands:**
- `/removefilter` - Filter entfernen
- `/removepackfilter` - Pack-Filter entfernen
- `/showfilters` - Filter anzeigen
- `/detailedstats` - Detaillierte Stats
- `/packstats` - Pack Stats
- `/setheartbeat` - Heartbeat konfigurieren
- `/setstatus` - Traded Buttons
- `/pick4me` - Random Picker
- `/lifetimestats` - **NEU** Globale Stats
- `/createpackcategory` - **NEU** Pack Category
- `/help` - Command Help
- `/sync` - Command Sync

---

### **commands/pack_management.py** - Pack Commands
**Commands:**
- `/addseries` - Serie hinzufügen
- `/addpack` - Pack hinzufügen
- `/removepack` - Pack entfernen
- `/removeseries` - Serie entfernen

**Features:**
- Global Config Update
- Auto-Create in allen Servern
- Guild Config Update
- Error Tracking

---

### **commands/dev.py** - Dev Commands
**Commands:**
- Dev-only Utilities

---

## 🔄 Handlers Module

### **handlers/message.py** - Message Processing
**Verantwortung:**
- Keyword Detection
- Pack Detection
- Message Forwarding
- Validation Views
- Statistics Tracking

**Flow:**
```
Message → Check Source Channels
          ↓
       Keyword Detection (Priority: "invalid god pack" before "god pack")
          ↓
       Pack Detection (Word-Boundary Regex)
          ↓
       Route Message
          ↓
       Add Buttons (if enabled)
          ↓
       Update Stats
          ↓
       Check Heartbeat
```

**Key Functions:**
```python
async def process_message(message, bot, config, BERLIN_TZ)
    # Keyword & Pack Detection
    # Message Forwarding
    # Statistics Update
    # Validation Buttons
```

---

## 👁️ Views Module

### **views/validation.py** - Interaction Views
**Classes:**
```python
class GodPackValidationView(discord.ui.View)
    ├── valid_button() → Aktualisiert Stats
    └── invalid_button() → Aktualisiert Stats

class TradedView(discord.ui.View)
    ├── traded_button() → Öffnet Modal
    └── TradedModal() → Speichert Trade

class GodPackWithoutValidationView(discord.ui.View)
    └── traded_button() → Trade tracking ohne Validierung
```

---

### **views/setup_views.py** - Setup Wizard Views
**Classes:**
```python
class ModeView(discord.ui.View)
    ├── series_mode() → Creates A/B Series Categories
    └── pack_mode() → Creates Pack Categories

class ValidatorView(discord.ui.View)
    └── role_callback() → Role Selection

class PingSetupView(discord.ui.View)
    ├── godpack_ping()
    ├── invgodpack_ping()
    ├── safe_trade_ping()
    ├── skip_pings()
    └── set_ping_role()

class SourceModal(discord.ui.Modal)
    └── on_submit() → Speichert Source Channels

class ValidationSetupView(discord.ui.View)
    ├── enable_validation()
    └── disable_validation()

class HeartbeatSetupView(discord.ui.View)
    ├── enable_heartbeat()
    └── Nested Select Menus
```

---

## 🔄 Data Flow Examples

### **Setup Flow**
```
User: /setup
  ↓
Setup.setup() (in setup.py)
  ↓
Send ModeView Buttons
  ↓
series_mode() OR pack_mode()
  ↓
Send ValidatorView
  ↓
Create Categories (Save4Trade, GodPacks, Detection, Series)
  ↓
Send PingSetupView
  ↓
Send SourceModal
  ↓
Send ValidationSetupView
  ↓
Send HeartbeatSetupView
  ↓
Save Guild Config
```

### **Message Processing Flow**
```
User posts message
  ↓
on_message() in main.py
  ↓
process_message() in handlers/message.py
  ↓
Check source_channel_ids
  ↓
Detect Keywords (with priority check)
  ↓
Detect Packs (word-boundary regex)
  ↓
Look up channel_id in config maps
  ↓
Create Embed
  ↓
Forward to target channel
  ↓
Add Validation/Traded Buttons (if enabled)
  ↓
Update filter_stats & pack_stats
  ↓
Update heartbeat tracking
```

### **Command Execution Flow**
```
User: /setfilter god pack #channel
  ↓
setfilter() in admin.py (Cog Method)
  ↓
Check Admin Permissions
  ↓
Validate keyword & channel
  ↓
Auto-create channel if missing
  ↓
Parse source_channels (regex)
  ↓
Load Guild Config
  ↓
Update keyword_channel_map
  ↓
Save Guild Config (thread-safe with lock)
  ↓
Send Success Embed
```

---

## 🎛️ Task System

### **auto_cleanup_task()**
- **Interval:** 60 seconds
- **Function:** Entfernt Guilds wo Bot nicht mehr ist
- **Implementation:** Vergleicht Guild-Configs mit Discord Guilds

### **heartbeat_monitor()**
- **Interval:** 5 minutes
- **Function:** Aktualisiert Heartbeat Status
- **Implementation:** Liest letzte Message aus source_channel

### **lifetime_stats_update_task()**
- **Interval:** 60 minutes
- **Function:** Aktualisiert globale Stats
- **Implementation:** Aggregiert alle Guild-Config Stats

---

## 🔒 Permission System

```
Öffentlich Commands:
  /stats, /meta, /showfilters, /help, /pick4me

Admin Commands:
  /setup, /setfilter, /setpackfilter, /clearfilters
  /setpackmode, /resetsources, /setvalidatorrole
  /setpingroles, /setheartbeat, /setstatus
  /createpackcategory, /removefilter, /removepackfilter

Owner Commands:
  /addseries, /addpack, /removepack, /removeseries
  /lifetimestats, /sync
```

**Implementation:**
```python
# Admin Check
if not interaction.user.guild_permissions.administrator:
    await interaction.followup.send(embed=error_embed)
    return

# Owner Check
if interaction.user.id != self.OWNER_ID:
    await interaction.followup.send("Owner only")
    return
```

---

## 🗄️ Storage Model

### **Hierarchie:**
```
bot_config.json (Global)
├── Series + Pack Definitions
├── Webhook URLs
├── Owner ID
└── Timezone

guild_configs/ (Per-Guild)
├── guild_<id>.json
│   ├── Configuration
│   ├── Statistics
│   ├── Channel Mappings
│   └── Role IDs
```

### **Thread Safety:**
```python
config_save_lock = asyncio.Lock()

async def save_guild_config():
    async with config_save_lock:
        # Safe file write
```

---

## 🚀 Extension Points

### **Neue Commands hinzufügen:**
1. Datei in `commands/` erstellen
2. Cog-Klasse definieren
3. `async def setup(bot)` am Ende
4. `load_cogs()` lädt automatisch

### **Neue Views hinzufügen:**
1. Datei in `views/` erstellen
2. View-Klasse definieren
3. In relevant Command importieren

### **Neue Handler hinzufügen:**
1. Funktion in `handlers/message.py` definieren
2. Von `process_message()` aufrufen
3. oder Event-Handler in `main.py` hinzufügen

---

## 📊 Performance Considerations

- **Config Caching:** Guild Configs werden on-demand geladen
- **Task Intervals:** 60s, 5min, 60min - optimiert für Server-Last
- **Async Operations:** Alle I/O ist async
- **Thread Safety:** Locks für kritische Config-Operationen
- **Cleanup:** Stale Guilds entfernt automatisch

---

## 🔄 Update & Migration Strategy

1. **Config Migration:** `migrate_configs()` in config.py
2. **Backward Compatibility:** Alte Format wird automatisch konvertiert
3. **Graceful Degradation:** Missing Keys haben sane Defaults
4. **Cleanup:** `final_cleanup_config()` vor dem Speichern

---

**Dieses Design ermöglicht:**
✅ Einfache Erweiterbarkeit  
✅ Klare Verantwortlichkeiten  
✅ Wiederverwendbarer Code  
✅ Testbarkeit  
✅ Wartbarkeit  
✅ Skalierbarkeit
│
├── commands/
│   ├── __init__.py
│   ├── setup.py           # /setup command + SetupView
│   ├── admin.py           # Admin commands (clearfilters, setpackmode, etc.)
│   ├── stats.py           # Stats commands (/stats, /meta, /setpingroles)
│   ├── utility.py         # Utility commands (help, sync, etc.)
│   └── dev.py             # Developer commands (prefix-based)
│
├── handlers/
│   ├── __init__.py
│   └── message.py         # on_message event handler with pack/filter processing
│
├── views/
│   ├── __init__.py
│   ├── validation.py      # GodPackValidationView, TradedView, TradedModal
│   └── setup_views.py     # ModeView, ValidatorView, PingSetupView, etc.
│
└── README.md
```

## 🚀 Setup & Running

### Prerequisites
- Python 3.11+
- discord.py 2.0+
- python-dotenv

### Installation

1. **Install dependencies:**
   ```bash
   pip install discord.py python-dotenv aiohttp
   ```

2. **Create `.env` file in project root:**
   ```env
   TOKEN=your_bot_token_here
   ```

3. **Create `bot_config.json` (optional, will be auto-created):**
   ```json
   {
     "series": {
       "A-Series": ["palkia", "dialga", "arceus", "shining", "mew", "pikachu", "charizard", "mewtwo", "solgaleo", "lunala", "buzzwole", "eevee", "hooh", "lugia", "springs", "deluxe"]
     },
     "packs": ["palkia", "dialga", "arceus", "shining", "mew", "pikachu", "charizard", "mewtwo", "solgaleo", "lunala", "buzzwole", "eevee", "hooh", "lugia", "springs", "deluxe"],
     "owner_id": 774679828594163802,
     "timezone": "Europe/Berlin",
     "error_webhook_url": "your_error_webhook_url",
     "permission_warning_webhook_url": "your_permission_webhook_url"
   }
   ```

### Running the Bot

```bash
# From project root
python tcgp-v2/main.py
```

## 📋 Key Features

### Configuration System
- **Global Config** (`bot_config.json`): Series, packs, webhooks, owner settings
- **Guild Configs** (`guild_configs/guild_<id>.json`): Per-server settings, filters, stats
- **Thread-safe** config saves with background worker threads
- **Auto-cleanup**: Prevents guild data from polluting global config

### Commands
- `/setup` - Full guided setup wizard
- `/stats` - Server validation statistics
- `/meta` - Current TCGP meta decks
- `/setfilter` - Configure individual filters
- `/setpackfilter` - Configure pack channels
- `/setpingroles` - Set ping roles for god packs, etc.
- `/showfilters` - View all configured filters
- `/clearfilters` - Remove filters by type
- `/help` - Show command overview
- `-help` - Developer menu (owner only)

### Background Tasks
- **auto_cleanup_task()** - Monitors and cleans bot_config.json every 60 seconds
- **heartbeat_monitor()** - Checks heartbeat status every 5 minutes
- **lifetime_stats_update_task()** - Updates global stats every hour

### Validation System
- God Pack validation (Valid/Invalid buttons)
- Traded card tracking with modal
- Role-based permission checks
- Automatic stats incrementing

## 🔌 Integration

### Adding New Commands
1. Create new file in `commands/` folder
2. Implement as `commands.Cog` class with `async def setup(bot)` function
3. Bot will auto-load on startup

### Adding New Views
Add to `views/` folder and import as needed in command files

### Error Handling
Errors are logged to Discord webhooks (if configured):
- `error_webhook_url` - General errors
- `permission_warning_webhook_url` - Permission-related errors

## 📊 Config Files Structure

### bot_config.json
```json
{
  "series": {
    "A-Series": ["pack1", "pack2"],
    "B-Series": []
  },
  "packs": ["pack1", "pack2"],
  "owner_id": 123456789,
  "timezone": "Europe/Berlin",
  "error_webhook_url": "https://...",
  "permission_warning_webhook_url": "https://..."
}
```

### guild_configs/guild_<id>.json
```json
{
  "pack_channel_mode": "series",
  "keyword_channel_map": {
    "god pack": {
      "channel_id": 123456789,
      "source_channel_ids": []
    }
  },
  "pack_channel_map": {
    "palkia": {
      "channel_id": 987654321,
      "source_channel_ids": []
    }
  },
  "stats": {
    "godpacks": {"total": 0, "valid": 0, "invalid": 0},
    "general": {"total": 0, "valid": 0}
  },
  "filter_stats": {},
  "validator_role_id": 111111111,
  "validation_buttons_enabled": true,
  "heartbeat_source_channel_id": 222222222,
  "heartbeat_target_channel_id": 333333333
}
```

## 🛠️ Development

### Code Organization Principles
- **Separation of Concerns**: Config, utils, webhooks, handlers, views, commands
- **No Circular Imports**: Lazy imports in event handlers where needed
- **Async-First**: All blocking operations run in threads or async functions
- **Thread-Safe**: Config saves protected by threading locks

### Key Functions
- `load_guild_config(guild_id)` - Load guild-specific config
- `save_guild_config(guild_id, config)` - Save guild config (async)
- `create_stats_embed(guild_config)` - Generate stats embed
- `process_message(message, bot, config, BERLIN_TZ)` - Main message handler

## 🔐 Permissions
- Admin commands require `guild.administrator` permission
- Owner commands check against `OWNER_ID`
- Validation buttons check role membership

## 📝 Notes
- Bot requires Manage Channels, Manage Roles permissions for full functionality
- All times use Berlin timezone (configurable)
- Message processing supports both keywords and pack names
- Auto-update embeds stored in config for persistence on bot restart

---

**Created for TCGP Community**
