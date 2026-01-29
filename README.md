# 🎴 TCGP Bot - Trading Card Game Pack Manager

> A Discord bot for managing and automating Pokémon Trading Card Game (TCG) pack distributions and validations across Discord servers using Arturo-1212's TCG Pocket Rerolling Bot.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![discord.py 2.0+](https://img.shields.io/badge/discord.py-2.0%2B-blue)](https://github.com/Rapptz/discord.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Production Ready](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](README.md)

## ✨ Features

### 🎯 Core Features
- **Automatic Setup** - Guided setup wizard for easy configuration
- **Pack Management** - Create, manage, and organize TCG packs
- **Keyword Filtering** - Automatic message forwarding based on keywords
- **God Pack Validation** - Validate "God Packs" with Approval/Rejection buttons
- **Safe 4 Trade Tracking** - Track traded cards with modal input
- **Global Statistics** - Aggregated stats across all servers
- **Heartbeat Monitoring** - Real-time status monitoring

### 📊 Functionality
- **25+ Slash Commands** - Modern slash command structure with autocomplete
- **Guild-Specific Configs** - Different settings per server
- **Automatic Channel Creation** - Smart auto-create with fallback logic
- **Role-Based Pings** - Custom pings for God Pack, Invalid God Pack, Safe 4 Trade
- **Background Tasks** - Auto-cleanup, heartbeat monitor, stats updates
- **Webhook Logging** - Log errors and warnings in Discord channels
- **Multi-Series Support** - A-Series, B-Series, and infinitely expandable

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- discord.py 2.0+
- A Discord server for testing
- A Discord bot token

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/tcgp-bot.git
   cd tcgp-bot/tcgp-v2
   ```

2. **Install dependencies**
   ```bash
   pip install discord.py python-dotenv
   ```

3. **Set up environment variables**
   ```bash
   # Create .env file
   DISCORD_TOKEN=your_bot_token_here
   ```

4. **Configure bot**
   ```bash
   # Customize bot_config.json with your packs and webhooks
   cp bot_config.json.example bot_config.json
   ```

5. **Start the bot**
   ```bash
   python main.py
   ```

## 📋 Commands

### 🔧 Setup & Administration

| Command | Description | Permission |
|---------|------------|-----------|
| `/setup` | Guided setup wizard for server configuration | Admin |
| `/setfilter <keyword> [channel] [sources]` | Configure filters for keywords | Admin |
| `/setpackfilter <pack> [channel] [sources]` | Configure filters for packs | Admin |
| `/clearfilters <type>` | Clear all filters of a type | Admin |
| `/setpackmode <mode>` | Change pack channel mode (series/pack) | Admin |
| `/resetsources` | Reset source channels | Admin |
| `/setvalidatorrole <role>` | Set validator role for buttons | Admin |
| `/setpingroles <type> <role>` | Set ping roles | Admin |
| `/setheartbeat <source> <target>` | Configure heartbeat monitoring | Admin |
| `/setstatus <true/false>` | Enable/Disable traded buttons | Admin |

### 📦 Pack Management

| Command | Description | Permission |
|---------|------------|-----------|
| `/addseries <name>` | Add new pack series | Owner |
| `/addpack <name> [series]` | Add new pack | Owner |
| `/removepack <name>` | Remove pack | Owner |
| `/removeseries <name>` | Remove series (all packs) | Owner |
| `/createpackcategory <pack>` | Create category for pack | Admin |

### 📊 Statistics & Info

| Command | Description | Permission |
|---------|------------|-----------|
| `/stats [channel]` | Display server statistics | Everyone |
| `/detailedstats [channel]` | Display detailed filter statistics | Everyone |
| `/packstats [channel]` | Display pack statistics | Everyone |
| `/lifetimestats [channel]` | Display global lifetime statistics | Owner |
| `/meta` | Show TCGP meta decks | Everyone |
| `/showfilters` | Show all active filters | Everyone |

### 🎮 Utility Commands

| Command | Description | Permission |
|---------|------------|-----------|
| `/removefilter <keyword>` | Remove a filter | Admin |
| `/removepackfilter <pack>` | Remove pack filter | Admin |
| `/pick4me` | Make a random selection | Everyone |
| `/help` | Show all commands | Everyone |
| `/sync` | Sync slash commands | Owner |

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
tcgp-v2/
├── main.py                      # Bot initialization & event handler
├── config.py                    # Config management (global & guild-specific)
├── utils.py                     # Constants, embeds, helper functions
├── webhooks.py                  # Discord webhook logging
│
├── commands/
│   ├── admin.py                # Admin commands (filters, mode, sources)
│   ├── setup.py                # /setup command & wizard
│   ├── stats.py                # Stats commands (/stats, /meta, /setpingroles)
│   ├── utility.py              # Utility commands (help, pick4me, etc.)
│   ├── pack_management.py      # Pack management (add/remove packs & series)
│   └── dev.py                  # Developer commands
│
├── handlers/
│   └── message.py              # Message event handler (forwarding, detection)
│
├── views/
│   ├── validation.py           # Validation views (god pack, traded, modal)
│   └── setup_views.py          # Setup wizard views
│
├── guild_configs/              # Guild-specific configurations
│   └── guild_<id>.json
│
├── bot_config.json             # Global bot configuration
└── README.md                   # This file
```

## 🔄 Message Handler Logic

The bot monitors all messages and:

1. **Keyword Detection** - Detects configured keywords (e.g., "god pack", "one star")
2. **Pack Detection** - Searches for pack names with word-boundary matching
3. **Channel Filtering** - Checks if message is from allowed channel
4. **Validation Buttons** - Shows approval/rejection buttons for god packs
5. **Traded Tracking** - Modal for "Traded" status for safe 4 trade
6. **Statistics** - Updates filter and pack statistics

## 🎛️ Background Tasks

| Task | Interval | Function |
|------|----------|---------|
| `auto_cleanup_task()` | 60s | Cleans up guilds the bot has left |
| `heartbeat_monitor()` | 5min | Updates heartbeat status |
| `lifetime_stats_update_task()` | 60min | Updates global lifetime stats |

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

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a pull request

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## 👨‍💼 Support

Having issues or questions?
- 🐛 [Open an issue](https://github.com/yourusername/tcgp-bot/issues)
- 💬 [Start a discussion](https://github.com/yourusername/tcgp-bot/discussions)
- 📧 Contact the maintainer

---

**Made with ❤️ for the TCG Pokémon Community**

**Version:** 2.0.0 (Full Refactor)  
**Status:** Production Ready ✅  
**Last Updated:** January 2026
- commands/setup.py: /setup command with all views
- commands/admin.py: /clearfilters, /setpackmode, /resetsources
- commands/stats.py: Stats, meta, and monitoring commands
- views/setup_views.py: All setup wizard views
- handlers/message.py: Message forwarding and pack detection
- main.py: Bot initialization and event handling

APPROACH:
---------

Option 1 (RECOMMENDED): Keep using tester.py as-is
- The refactored modules (config, utils, webhooks, views) can be imported into tester.py
- This is a gradual migration approach
- No risk of breaking existing functionality

Option 2: Full Refactoring
- Complete extraction of all 4600+ lines
- Takes significant time and testing
- Better for long-term maintenance

IMPORTS NEEDED:
---------------

If importing from tcgp-v2 modules into tester.py:

```python
from tcgp_v2.config import (
    load_config, save_config, load_guild_config, save_guild_config,
    migrate_configs, extract_and_save_guild_configs, final_cleanup_config
)
from tcgp_v2.utils import (
    CUSTOM_EMBED_TEXT, EMBED_COLORS, EMBED_THUMBNAILS, FILTER_CHOICES,
    create_stats_embed, create_detailed_stats_embed, create_pack_stats_embed,
    create_heartbeat_embed, split_field_value
)
from tcgp_v2.webhooks import log_error_to_webhook, log_permission_warning_to_webhook
from tcgp_v2.views import GodPackValidationView, TradedView, TradedModal
```

NEXT STEPS:
-----------

1. Use config.py + utils.py + webhooks.py in tester.py (import)
2. Gradually refactor commands into commands/ directory
3. Move all views to views/ directory
4. Extract message handler to handlers/message.py
5. Create main.py as entry point
6. Test thoroughly before full migration

This approach allows gradual refactoring while maintaining stability.
"""
