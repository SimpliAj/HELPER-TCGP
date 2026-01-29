"""
Utility constants, embed functions, and helper functions for the bot.
"""
import discord
from datetime import timedelta, datetime

# Lokalisierungstexte
LOCALE_TEXT = {
    "bot_started": "Bot started as {bot_name}",
    "embed_title": "Found: {keyword}",
    "embed_link_text": "[Go to original message]({link})",
    "embed_footer": "Forwarded by HELPER ¦ TCGP",
    "embed_author_name": "Save 4 Trade",
}

# Embed-Texte für Filter
CUSTOM_EMBED_TEXT = {
    "one star": "A One Star card was found!",
    "three diamond": "A Three Diamond card was found!",
    "four diamond ex": "A Four Diamond EX card was found!",
    "crown": "A Gold card was found!",
    "god pack": "A GOD pack was found!",
    "invalid god pack": "An Invalid GOD pack was found!",
    "trainer": "A Trainer card was found!",
    "immersive": "An Immersive card was found!",
    "shiny": "A Shiny card was found!",
    "rainbow": "A Rainbow card was found!",
    "full art": "A Two Star Full Art card was found!",
    "gimmighoul": "A Gimmighoul card was found!"
}

# Embed-Author-Texte
CUSTOM_AUTHOR_TEXT = {
    "one star": "Safe 4 Trade",
    "three diamond": "Safe 4 Trade",
    "four diamond ex": "Safe 4 Trade",
    "god pack": "GOD Pack",
    "invalid god pack": "Invalid GOD Pack",
    "trainer": "Safe 4 Trade",
    "immersive": "None Tradeable",
    "shiny": "Safe 4 Trade",
    "rainbow": "Safe 4 Trade",
    "full art": "Safe 4 Trade",
    "crown": "Gold Card",
    "gimmighoul": "HIDDEN QUEST CARD"
}

# Embed-Thumbnails
EMBED_THUMBNAILS = {
    "three diamond": "https://img.game8.co/3995616/740cd3cbff061c16c8e5d8eea939bb59.png/show",
    "four diamond ex": "https://img.game8.co/3995617/622e1c0cca9ffdaa43cdd588b8e18d78.png/show",
    "one star": "https://img.game8.co/3994721/895579e1516f605b7882b0909f329b7e.png/show",
    "crown": "https://img.game8.co/3997607/303598e292a532bcde37ab527a0ac263.png/show",
    "god pack": "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExNW05YmZmM2RkamsyMXd2emtkZzVxZXM2bGE2OHM4MXNyczFzdzF2biZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/vnGlErQHuF9BK/giphy.gif",
    "invalid god pack": "https://img.icons8.com/color/512/cancel.png",
    "trainer": "https://img.game8.co/3995618/7d3d7e80340fe6f678a9fbd34193cae6.png/show",
    "immersive": "https://img.game8.co/3995619/a0d611ce374e3070c530ee8d3fd81efa.png/show",
    "shiny": "https://img.game8.co/4137129/6510d1633ee489b2e8fcba939d7e99cb.png/show",
    "rainbow": "https://img.game8.co/3995618/7d3d7e80340fe6f678a9fbd34193cae6.png/show",
    "full art": "https://img.game8.co/3995618/7d3d7e80340fe6f678a9fbd34193cae6.png/show",
    "gimmighoul": "https://www.pokemon.com/static-assets/content-assets/cms2/img/pokedex/full/999.png"
}

# Embed-Farben
EMBED_COLORS = {
    "three diamond": discord.Color.yellow(),
    "four diamond ex": discord.Color.yellow(),
    "one star": discord.Color.yellow(),
    "god pack": discord.Color.gold(),
    "crown": discord.Color.gold(),
    "invalid god pack": discord.Color.red(),
    "trainer": discord.Color.blurple(),
    "rainbow": discord.Color.magenta(),
    "full art": discord.Color.purple(),
    "shiny": discord.Color.orange(),
    "immersive": discord.Color.dark_teal(),
    "gimmighoul": discord.Color.dark_gold()
}

# Save 4 Trade Keywords (all that should get Traded button)
SAVE4TRADE_KEYWORDS = ["one star", "three diamond", "four diamond ex", "gimmighoul", "shiny", "rainbow", "full art", "trainer"]

# Mapping of old prefix-based names to clean short names
OLD_TO_NEW_CHANNEL_NAMES = {
    # Save 4 Trade
    "save-4-trade-one-star": "one-star",
    "save-4-trade-three-diamond": "three-diamond",
    "save-4-trade-four-diamond-ex": "four-diamond-ex",
    "save-4-trade-gimmighoul": "gimmighoul",
    "save-4-trade-shiny": "shiny",
    "save-4-trade-rainbow": "rainbow",
    "save-4-trade-full-art": "full-art",
    "save-4-trade-trainer": "trainer",
    # God Packs
    "god-packs-god-pack": "god-pack",
    "god-packs-invalid-god-pack": "invalid-god-pack",
    # Detection
    "detection-crown": "crown",
    "detection-immersive": "immersive",
}

# Reverse mapping for lookup
NEW_TO_OLD_CHANNEL_NAMES = {v: k for k, v in OLD_TO_NEW_CHANNEL_NAMES.items()}

# Filter choices für slash commands
FILTER_CHOICES = [discord.app_commands.Choice(name=keyword.title(), value=keyword) for keyword in CUSTOM_EMBED_TEXT.keys()]

# Clear Filters Choices
CLEAR_FILTER_CHOICES = [
    discord.app_commands.Choice(name="Normal Filters", value="normal"),
    discord.app_commands.Choice(name="Pack Filters", value="pack"),
    discord.app_commands.Choice(name="All Filters", value="all")
]


def create_stats_embed(guild_config):
    """Erstelle Stats-Embed für einen Server."""
    validation_buttons_enabled = guild_config.get("validation_buttons_enabled", False)
    stats = guild_config.get("stats", {
        'godpacks': {'total': 0, 'valid': 0, 'invalid': 0},
        'general': {'total': 0, 'valid': 0}
    })

    embed = discord.Embed(
        title="Validation Statistics",
        description="Here are the validation stats for this server. Safe 4 Trade counts all forwarded cards in Save 4 Trade channels:",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url="https://i.imgur.com/pxqjVbO.png")
    
    # God Packs section
    godpacks = stats['godpacks']
    embed.add_field(
        name="God Packs",
        value=f"Total: {godpacks['total']}\nValid: {godpacks['valid']}\nInvalid: {godpacks['invalid']}",
        inline=False
    )

    # Safe 4 Trade section — only show if buttons are enabled
    if validation_buttons_enabled:
        general = stats['general']
        embed.add_field(
            name="Safe 4 Trade",
            value=f"Total: {general['total']}\nTraded: {general['valid']}",
            inline=False
        )

    return embed


def create_detailed_stats_embed(guild_config):
    """Erstelle Detailed Stats-Embed für einen Server."""
    filter_stats = guild_config.get("filter_stats", {})
    
    embed = discord.Embed(
        title="Detailed Filter Statistics",
        description="Here are the number of embeds sent for each filter in this server:",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url="https://i.imgur.com/pxqjVbO.png")
    
    # Kategorien definieren
    god_packs = ["god pack", "invalid god pack"]
    save_for_trade = ["one star", "three diamond", "four diamond ex", "gimmighoul", "shiny", "rainbow", "full art", "trainer"]
    detection = ["crown", "immersive"]

    # GOD PACKS Feld
    god_pack_list = []
    for keyword in god_packs:
        count = filter_stats.get(keyword, 0)
        god_pack_list.append(f"{keyword.title()}: {count} pack{'s' if count != 1 else ''}")
    embed.add_field(
        name="GOD PACKS",
        value="\n".join(god_pack_list) if god_pack_list else "No embeds sent for GOD PACKS yet.",
        inline=False
    )

    # Save 4 Trade Feld
    save_for_trade_list = []
    for keyword in save_for_trade:
        count = filter_stats.get(keyword, 0)
        save_for_trade_list.append(f"{keyword.title()}: {count} card{'s' if count != 1 else ''}")
    embed.add_field(
        name="Save 4 Trade",
        value="\n".join(save_for_trade_list) if save_for_trade_list else "No embeds sent for Save 4 Trade yet.",
        inline=False
    )

    # Detection Feld
    detection_list = []
    for keyword in detection:
        count = filter_stats.get(keyword, 0)
        detection_list.append(f"{keyword.title()}: {count} card{'s' if count != 1 else ''}")
    embed.add_field(
        name="Detection",
        value="\n".join(detection_list) if detection_list else "No embeds sent for Detection yet.",
        inline=False
    )

    return embed


def create_pack_stats_embed(guild_config, series_config):
    """Erstelle Pack Stats-Embed für einen Server."""
    filter_stats = guild_config.get("filter_stats", {})
    
    embed = discord.Embed(
        title="Pack Statistics",
        description="Here are the number of embeds sent for each pack in this server:",
        color=discord.Color.teal()
    )
    embed.set_thumbnail(url="https://i.imgur.com/pxqjVbO.png")
    
    for series_name, packs_in_series in series_config.items():
        series_list = []
        for pack in packs_in_series:
            count = filter_stats.get(pack, 0)
            series_list.append(f"{pack.title()}: {count} pack{'s' if count != 1 else ''}")
        if series_list:
            embed.add_field(
                name=series_name,
                value="\n".join(series_list),
                inline=False
            )

    return embed


def create_heartbeat_embed(guild_config, berlin_tz=None):
    """Erstelle Heartbeat-Embed für einen Server."""
    from zoneinfo import ZoneInfo
    if berlin_tz is None:
        berlin_tz = ZoneInfo("Europe/Berlin")
    
    data = guild_config.get("heartbeat_data", {})
    if not data:
        return discord.Embed(
            title="Heartbeat",
            description="Waiting for first heartbeat...",
            color=discord.Color.orange()
        )

    if "last_update" not in data or not data["last_update"]:
        return discord.Embed(
            title="Heartbeat",
            description="Bot is offline - No heartbeat found.",
            color=discord.Color.red()
        )

    try:
        last_update = datetime.fromisoformat(data["last_update"])
        now = datetime.now(berlin_tz)
        if now - last_update > timedelta(minutes=60):
            return discord.Embed(
                title="Heartbeat",
                description="Bot is offline - No heartbeat found.",
                color=discord.Color.red()
            )
    except ValueError:
        return discord.Embed(
            title="Heartbeat",
            description="Bot is offline - No heartbeat found.",
            color=discord.Color.red()
        )

    embed = discord.Embed(title="Heartbeat", color=discord.Color.green())
    embed.set_thumbnail(url="https://i.imgur.com/pxqjVbO.png")

    if "online" in data:
        online_str = ", ".join(data["online"]) if data["online"] else "None"
        embed.add_field(name="Online", value=online_str, inline=False)

    if all(k in data for k in ["time", "packs", "avg"]):
        stats_str = f"Time: {data['time']} \n Packs: {data['packs']} \n Avg: {data['avg']} packs/min"
        embed.add_field(name="Stats", value=stats_str, inline=False)

    if "type" in data:
        embed.add_field(name="Type", value=data["type"], inline=False)

    if "opening" in data:
        opening_str = ", ".join(data["opening"]) if data["opening"] else "None"
        embed.add_field(name="Opening", value=opening_str, inline=False)

    try:
        last_update_berlin = last_update.astimezone(berlin_tz)
        formatted_time = last_update_berlin.strftime("%d.%m.%Y %H:%M")
        embed.set_footer(text=f"Last updated: {formatted_time}")
    except:
        pass

    return embed


def split_field_value(value, max_len=1024, field_name="Field"):
    """Teile lange Field-Werte in mehrere Fields auf."""
    lines = value.split('\n')
    chunks = []
    current_chunk = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1  # +1 for \n
        if current_len + line_len > max_len and current_chunk:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_len = line_len
        else:
            current_chunk.append(line)
            current_len += line_len
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    return [(field_name, chunk) for chunk in chunks]
