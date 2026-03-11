# <img src="https://i.imgur.com/iNJRSxh.png" width="50" alt="TCGP"> Helper - TCGP

> A Discord bot for managing and automating Pokémon Trading Card Game (TCG) pack distributions and validations across Discord servers using Arturo-1212's TCG Pocket Rerolling Bot.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![discord.py 2.0+](https://img.shields.io/badge/discord.py-2.0%2B-blue)](https://github.com/Rapptz/discord.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Production Ready](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](README.md)


 [Invite Discord Bot](https://discord.com/oauth2/authorize?client_id=1389046915928162424&permissions=268437520&integration_type=0&scope=bot)

## ✨ Features

### 🎯 Core Features
- **Automated Setup Wizard** - Interactive step-by-step configuration for servers
- **Keyword & Pack Detection** - Automatic message detection and filtering
- **God Pack Validation** - Approve/reject validation buttons with modal tracking
- **Safe 4 Trade Tracking** - Modal-based card trade documentation
- **Multi-Series Support** - A-Series, B-Series, and infinitely expandable pack management
- **Guild-Specific Configs** - Independent settings per server with auto-recovery
- **Webhook Logging** - Error and warning logging to Discord webhooks
- **Global Statistics** - Aggregated stats tracking across all servers
- **Heartbeat Monitoring** - Real-time status monitoring with auto-updating embeds

### 📊 Functionality
- **26+ Slash Commands** - Modern slash command interface with autocomplete support
- **Automatic Channel Creation** - Auto-create channels by series or by pack with smart fallback logic
- **Role-Based Pings** - Custom pings for God Pack, Invalid God Pack, Safe 4 Trade notifications
- **Background Tasks** - Auto-cleanup, heartbeat monitor, stats updates running continuously
- **Thread-Safe Config** - Synchronized config saves preventing race conditions
- **Auto-Recovery** - Automatic recovery from corrupted guild configs with backup system
- **Configuration Cleanup** - Auto-extraction of stray guild data from global config

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- discord.py 2.0+
- A Discord server for testing
- A Discord bot token

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/HELPER-TCGP.git
   cd HELPER-TCGP
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` with your Discord bot token and settings:
     ```
     TOKEN=your_discord_bot_token_here
     MAIN_DEVELOPER=your_user_id_here
     DEBUG_PACK_LOGS=false
     DEBUG_LIFETIME_STATS=false
     ```

4. **Create bot_config.json**
   - Use the provided template or create with:
     ```json
     {
         "series": {"A-Series": [], "B-Series": []},
         "packs": [],
         "error_webhook_url": "",
         "permission_warning_webhook_url": "",
         "owner_id": YOUR_OWNER_ID,
         "timezone": "Europe/Berlin"
     }
     ```

5. **Start the bot**
   ```bash
   python bot.py
   ```

## 📋 Commands

### 🔧 Setup & Administration

| Command | Description | Permission |
|---------|------------|-----------|
| `/setup` | Automated setup wizard for bot channels, categories, and configurations | Admin |
| `/setfilter` | Configuration of filters for TCGP rerolling keywords | Admin |
| `/setpackfilter` | Configuration of filters for pack channels | Admin |
| `/clearfilters` | Clear all filters of a selected type | Admin |
| `/setpackmode` | Change pack channel mode after setup (series/pack) | Admin |
| `/resetsources` | Set or reset source channels | Admin |
| `/setvalidatorrole` | Set validator role for validation buttons | Admin |
| `/setpingroles` | Set ping roles for god pack, invalid god pack, or safe 4 trade | Admin |
| `/setheartbeat` | Set source and target channels for heartbeat stats | Admin |
| `/setstatus` | Enable/disable traded buttons for Safe 4 Trade embeds | Admin |
| `/createpackcategory` | Create category for a pack with Safe 4 Trade channels | Admin |

### 📦 Pack Management

| Command | Description | Permission |
|---------|------------|-----------|
| `/addseries` | Add new pack series to configuration (auto-creates in all setup guilds) | Owner |
| `/addpack` | Add new pack to list (auto-creates channels in all setup guilds) | Owner |
| `/removepack` | Remove pack from list (deletes channels if in pack mode) | Owner |
| `/removeseries` | Remove series globally and delete all channels/categories in all setup guilds | Owner |

### 📊 Statistics & Info

| Command | Description | Permission |
|---------|------------|-----------|
| `/stats` | Show server validation and trade stats, optionally posts auto-updating embed | Everyone |
| `/detailedstats` | Show detailed statistics for each filter, optionally posts auto-updating embed | Everyone |
| `/packstats` | Show pack statistics for server, optionally posts auto-updating embed | Everyone |
| `/lifetimestats` | Show lifetime statistics across all servers | Owner |
| `/meta` | Show current TCGP meta decks | Everyone |
| `/showfilters` | Show all active filters for server | Everyone |

### 🎮 Utility Commands

| Command | Description | Permission |
|---------|------------|-----------|
| `/removefilter` | Remove a filter from configuration | Admin |
| `/removepackfilter` | Remove pack filter from configuration | Admin |
| `/pick4me` | Let fate decide which card you get! | Everyone |
| `/help` | Show overview of all bot commands | Everyone |
| `/sync` | Synchronize all slash commands | Owner |

## ⚙️ Configuration

### bot_config.json

```json
{
    "series": {
        "A-Series": ["palkia", "dialga", "arceus", ...],
        "B-Series": ["megagyarados", "megaaltaria", ...]
    },
    "packs": ["palkia", "dialga", ...],
    "error_webhook_url": "https://discord.com/api/webhooks/...",
    "permission_warning_webhook_url": "https://discord.com/api/webhooks/...",
    "owner_id": 123456789,
    "timezone": "Europe/Berlin"
}
```

### Guild-Specific Config (guild_configs/)

```json
{
    "pack_channel_mode": "series",
    "keyword_channel_map": {
        "god pack": {"channel_id": 123, "source_channel_ids": [...]}
    },
    "pack_channel_map": {
        "palkia": {"channel_id": 456, "source_channel_ids": [...]}
    },
    "stats": {
        "godpacks": {"total": 10, "valid": 8, "invalid": 2},
        "general": {"total": 100, "valid": 95}
    },
    "validation_buttons_enabled": true,
    "heartbeat_source_channel_id": 789,
    "heartbeat_target_channel_id": 1011
}
```

## 📁 Project Structure

```
HELPER-TCGP/
├── bot.py                       # Main bot file with all commands and logic (5000+ lines)
│   ├── Core bot setup and intents
│   ├── Config management (load/save)
│   ├── Guild config system with auto-recovery
│   ├── 26+ slash commands
│   ├── Event handlers (on_ready, on_guild_join, etc.)
│   ├── Background tasks (cleanup, stats update, lifetime stats)
│   ├── Message handler (keyword/pack detection, forwarding)
│   ├── Validation views (god packs, safe 4 trade, modals)
│   └── Statistics tracking system
│
├── bot_config.json             # Global bot configuration (series, packs, webhooks)
├── guild_configs/              # Guild-specific configurations (auto-created)
│   └── guild_<id>.json
│
├── README.md                   # This file
├── PRIVACY_POLICY.md           # Privacy policy
├── TERMS_OF_SERVICE.md         # Terms of service
└── lifetime_stats_messages.json # Global statistics data (auto-created)
```

## 🔄 Message Handler Logic

The bot monitors all messages in configured servers and:

1. **Keyword Detection** - Scans for configured keywords (e.g., "god pack", "one star") with regex support
2. **Pack Detection** - Searches for pack names using word-boundary matching
3. **Channel Filtering** - Validates message source against configured source channels
4. **Auto-Forwarding** - Forwards matched messages to destination channels
5. **Validation Buttons** - Shows approval/rejection buttons for god pack detections
6. **Traded Tracking** - Displays modal for "Traded" status tracking on Safe 4 Trade embeds
7. **Statistics** - Automatically updates filter and pack statistics

## 🎛️ Background Tasks

| Task | Interval | Function |
|------|----------|---------|
| `auto_cleanup_task()` | 60s | Cleans up guilds the bot has left |
| `update_stats_message()` | On-demand | Updates server validation stats embed |
| `update_detailed_stats_message()` | On-demand | Updates detailed filter statistics embed |
| `update_pack_stats_message()` | On-demand | Updates pack statistics embed |
| `update_heartbeat_message()` | 5min | Updates heartbeat status message |
| `lifetime_stats_update_task()` | 60min | Updates global lifetime statistics |

## 🔐 Permission System

| Level | Commands | Description |
|-------|----------|------------|
| **Everyone** | /stats, /meta, /help, /pick4me | Public commands |
| **Administrator** | /setup, /setfilter, /createpackcategory | Server management |
| **Owner** | /addseries, /addpack, /lifetimestats | Bot administration |

## 🐛 Troubleshooting

### Bot doesn't respond to commands
1. Check if `/sync` was successful
2. Ensure bot.intents is configured correctly
3. Check Discord permissions for the bot

### Filters not working
1. Check channel names in configuration
2. Ensure source channels are saved correctly
3. Check message handler logs

### Stats not updating
1. Check if guild config exists
2. Verify messages are detected correctly
3. Check auto_cleanup_task logs

### Webhook errors
- Check webhook URLs in bot_config.json
- Ensure webhook is still valid
- Check bot permissions for webhook access

## 📊 Statistics & Monitoring

### Available Statistics
- **God Packs** - Total, valid, invalid
- **Safe 4 Trade** - Total, traded
- **Filter Stats** - Per keyword/pack
- **Server Stats** - Per guild
- **Lifetime Stats** - Across all servers

### Auto-Update Feature
Stats embeds can be automatically updated in channels:
```
/stats #channel              # Posts updates every hour
/detailedstats #channel     # Detailed filter breakdown
/lifetimestats #channel     # Global lifetime stats
```

## 🔒 Security & Best Practices

- **Owner ID** - Checked for owner-only commands
- **Admin Check** - Guild admin permissions validated
- **Webhook Logging** - Errors logged in private channels
- **Config Cleanup** - Stale guilds automatically removed
- **Thread Safety** - Config saves synchronized with locks

## 📝 Logs & Debugging

### Webhook Logging
The bot sends errors and warnings to configured webhooks:

```json
{
    "error_webhook_url": "https://discord.com/api/webhooks/...",
    "permission_warning_webhook_url": "https://discord.com/api/webhooks/..."
}
```

### Local Logs
Important events are logged in the console:
- Guild joins/leaves
- Command executions
- Task executions
- Errors & warnings


## 👨‍💼 Support

Having issues or questions?
- 💬 [Discord](https://discord.gg/X5YKZBh9xV)


---
