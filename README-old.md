

<p align="center">
  <a>
    <img src="https://i.imgur.com/AiKHAMQ.png"></a>
</p>

# TCGP Helper - Discord bot

Discord Support Server: https://discord.gg/2zSUgWJyYJ
<br>
Invite Bot: [Click Here](https://discord.com/oauth2/authorize?client_id=1389046915928162424&permissions=268437520&integration_type=0&scope=bot)<br>
Python: 3.10+,
Discord.py: 2.3+

TCGP Helper is a powerful Pokémon TCG Pocket Discord bot for trading communities. It automatically forwards rare cards, God Packs, and pack openings to dedicated channels with beautiful embeds, validation buttons, real-time stats, and a full setup wizard.

Save time, boost trades, and keep your server organized!

## Key Features

### Auto-Forwarding
- Keyword Filters: Detects "One Star", "Three Diamond", "God Pack", "Shiny", etc.
- Pack Filters: Forwards specific packs (Palkia, Mewtwo, etc.) with series grouping.
- Custom Sources: Only monitor specific channels.

### Validation System
- God Pack Buttons: Valid/Invalid with stats.
- Traded Buttons: Mark Safe 4 Trade cards as traded (with modal).
- Ping Roles: Notify for God Packs, Invalid Packs, or Safe Trades.

### Live Statistics
- Auto-Updating Embeds: Validation, detailed filters, pack counts.
- Heartbeat Monitor: Tracks live pack opening sessions.

### Easy Setup
- One-Command Wizard (/setup): Creates categories, channels, and configs.
- Modes: Series (1 channel per group) or Per-Pack.
- Dynamic Packs: Add/remove packs/series globally with auto-cleanup.
    - This will add/remove also packs/series channels/categories if bot has permissions in discord

### Fun Extras
- /pick4me: Random Wonder Pick helper.
- /meta: Latest TCGP meta decks.


## Quick Start

<details>
<summary>💬 <b>Installation</b></summary>
  
### 1. Installation
git clone https://github.com/ajx00/HELPER-TCGP.git<br>
cd HELPER-TCGP<br>
pip install -r requirements.txt<br>

### requirements.txt
discord.py[voice]==2.3.2<br>
python-dotenv==1.0.0<br>
aiohttp==3.9.1<br>

### 2. Setup
1. Open .env and add the discord bot token<br>
   TOKEN=your_bot_token_here<br>

2. Invite Bot (Discord Developer Portal)
   - Intents: Message Content, Guilds, Members, Reactions
   - Scopes: bot, applications.commands
   - Permissions: Manage Channels, Manage Roles, Send Messages, Embed Links, Add Reactions

3. Run
   python bot.py

### 3. In Your Server
1. Run /setup (Admin only)
2. Follow the wizard!
3. Done! Channels, filters, and stats are ready.

Bot auto-restores setup on restart.
</details>


<details>
<summary>💬 <b>Configuration</b></summary>
  
- bot_config.json (auto-generated): Stores packs, series, guild settings.<br>
  {<br>
    "series": { "A-Series": ["palkia", "dialga", ...] },<br>
    "<guild_id>": { "keyword_channel_map": {}, "pack_channel_map": {}, ... }<br>
  }<br>

- Add Packs/Series (Owner only):
  /addseries "C-Series"
  /addpack "C-Series" "newpack"
</details>

## Commands

### Fun & Meta
- /meta – TCGP meta decks & guides
- /pick4me – Random Wonder Pick!

### Filter Setup (Admin)
- /setup – Full auto-setup wizard
- /setfilter <filter> <channel> – Configure keyword filter
- /setpackfilter <pack> <channel> – Pack filter
- /showfilters – View all active filters

### Validation (Admin)
- /setvalidatorrole <role> – Validator role
- /setstatus <true/false> – Enable traded buttons
- /setpingroles – Set ping roles (God Pack, Invalid, Safe Trade)

### Statistics
- /stats [channel] – Live validation stats
- /detailedstats [channel] – Filter-by-filter
- /packstats [channel] – Pack counts
- /setheartbeat <source> <target> – Live opening monitor

### Dev Commands (Owner only)
- /addseries, /addpack, /removepack, /removeseries, /sync

Full /help in Discord!

## Advanced

### Customizing Packs
 /addseries "B-Series"<br>
 /addpack "B-Series" "mewtwo"<br>
 /removepack "mewtwo"  # Auto-deletes channels!<br>

### Permissions
Bot needs:
- Manage Channels/Roles (setup)
- Send Messages/Embeds
- Manage Messages (stats updates)

### Troubleshooting
- "No channel found": Run /setup or /setpackfilter
- Buttons not working: Check /setvalidatorrole
- Stats not updating: Post in target channel first
- Errors? Check console → Join Support

## Support & Contributing

- Support Server: https://discord.gg/2zSUgWJyYJ
- Issues: https://github.com/ajx00/HELPER-TCGP/issues
- Contribute: Please make suggestions and contribute to this project
