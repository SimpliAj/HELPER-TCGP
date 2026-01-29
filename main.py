"""
main.py - Bot Initialisierung, Events, Background Tasks und Command/Handler Registration
"""
import os
import json
import discord
import asyncio
import time
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Import Config & Utils
from config import load_config, save_config, load_guild_config, save_guild_config, ensure_guild_config_dir, GUILD_CONFIG_DIR, CONFIG_FILE
from utils import (
    create_stats_embed, create_detailed_stats_embed, create_heartbeat_embed, 
    LOCALE_TEXT, CUSTOM_EMBED_TEXT, SAVE4TRADE_KEYWORDS
)
from webhooks import log_error_to_webhook, log_permission_warning_to_webhook
from handlers.message import process_message

# ===== BOT SETUP =====
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = app_commands.CommandTree(bot)

# Global config & timezone
config = None
OWNER_ID = None
BERLIN_TZ = None
PACKS = []

# Global dict for lifetime stats auto-update
LIFETIME_STATS_MESSAGES = {}

# Global dict for missing configs tracking
class BotExt(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.missing_configs = {}
        self.config = None
        self.OWNER_ID = None
        self.BERLIN_TZ = None

bot = BotExt(command_prefix="!", intents=intents)
tree = app_commands.CommandTree(bot)


async def load_cogs():
    """Lade alle Cogs aus commands/ und handlers/."""
    for filename in os.listdir("tcgp-v2/commands"):
        if filename.endswith(".py") and filename != "__init__.py":
            await bot.load_extension(f"tcgp-v2.commands.{filename[:-3]}")
            print(f"✅ Loaded command: {filename}")
    
    # Handlers sind kein Cog, werden direkt in on_message aufgerufen


async def update_stats_message(guild_id):
    """Aktualisiere Stats-Embed in einem Channel."""
    guild_config = load_guild_config(guild_id)
    stats_channel_id = guild_config.get("stats_channel_id")
    stats_message_id = guild_config.get("stats_message_id")
    if stats_channel_id and stats_message_id:
        channel = bot.get_channel(stats_channel_id)
        if channel:
            try:
                message = await channel.fetch_message(stats_message_id)
                embed = create_stats_embed(guild_config)
                await message.edit(embed=embed)
            except discord.NotFound:
                if "stats_channel_id" in guild_config:
                    del guild_config["stats_channel_id"]
                if "stats_message_id" in guild_config:
                    del guild_config["stats_message_id"]
                save_guild_config(guild_id, guild_config)
            except Exception as e:
                print(f"Error updating stats message: {e}")


async def update_detailed_stats_message(guild_id):
    """Aktualisiere Detailed Stats-Embed."""
    guild_config = load_guild_config(guild_id)
    detailed_stats_channel_id = guild_config.get("detailed_stats_channel_id")
    detailed_stats_message_id = guild_config.get("detailed_stats_message_id")
    if detailed_stats_channel_id and detailed_stats_message_id:
        channel = bot.get_channel(detailed_stats_channel_id)
        if channel:
            try:
                message = await channel.fetch_message(detailed_stats_message_id)
                embed = create_detailed_stats_embed(guild_config)
                await message.edit(embed=embed)
            except discord.NotFound:
                if "detailed_stats_channel_id" in guild_config:
                    del guild_config["detailed_stats_channel_id"]
                if "detailed_stats_message_id" in guild_config:
                    del guild_config["detailed_stats_message_id"]
                save_guild_config(guild_id, guild_config)
            except Exception as e:
                print(f"Error updating detailed stats message: {e}")


async def update_pack_stats_message(guild_id):
    """Aktualisiere Pack Stats-Embed."""
    guild_config = load_guild_config(guild_id)
    pack_stats_channel_id = guild_config.get("pack_stats_channel_id")
    pack_stats_message_id = guild_config.get("pack_stats_message_id")
    if pack_stats_channel_id and pack_stats_message_id:
        channel = bot.get_channel(pack_stats_channel_id)
        if channel:
            try:
                message = await channel.fetch_message(pack_stats_message_id)
                
                # Create pack stats embed
                filter_stats = guild_config.get("filter_stats", {})
                series = config.get("series", {})
                
                embed = discord.Embed(
                    title="Pack Statistics",
                    description="Here are the number of embeds sent for each pack:",
                    color=discord.Color.teal()
                )
                embed.set_thumbnail(url="https://i.imgur.com/pxqjVbO.png")
                
                for series_name, packs_in_series in series.items():
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
                
                await message.edit(embed=embed)
            except discord.NotFound:
                if "pack_stats_channel_id" in guild_config:
                    del guild_config["pack_stats_channel_id"]
                if "pack_stats_message_id" in guild_config:
                    del guild_config["pack_stats_message_id"]
                save_guild_config(guild_id, guild_config)
            except Exception as e:
                print(f"Error updating pack stats message: {e}")


async def update_heartbeat_message(guild_id):
    """Aktualisiere Heartbeat-Embed."""
    guild_config = load_guild_config(guild_id)
    heartbeat_channel_id = guild_config.get("heartbeat_target_channel_id")
    heartbeat_message_id = guild_config.get("heartbeat_message_id")
    if heartbeat_channel_id and heartbeat_message_id:
        channel = bot.get_channel(heartbeat_channel_id)
        if channel:
            try:
                message = await channel.fetch_message(heartbeat_message_id)
                embed = create_heartbeat_embed(guild_config, BERLIN_TZ)
                await message.edit(embed=embed)
            except discord.NotFound:
                if "heartbeat_target_channel_id" in guild_config:
                    del guild_config["heartbeat_target_channel_id"]
                if "heartbeat_message_id" in guild_config:
                    del guild_config["heartbeat_message_id"]
                save_guild_config(guild_id, guild_config)
            except Exception as e:
                print(f"Error updating heartbeat message: {e}")


async def auto_cleanup_task():
    """Background task: Auto-cleanup bot_config.json alle 60 Sekunden."""
    await bot.wait_until_ready()
    print("✅ Auto-Cleanup Task started\n")
    
    while not bot.is_closed():
        try:
            await asyncio.sleep(60)
            
            if not os.path.exists(CONFIG_FILE):
                continue
            
            try:
                with open(CONFIG_FILE, "r") as f:
                    current_config = json.load(f)
            except (json.JSONDecodeError, IOError):
                continue
            
            guild_ids_found = []
            for key in list(current_config.keys()):
                if key not in ["series", "packs", "error_webhook_url", "permission_warning_webhook_url", "owner_id", "timezone"]:
                    try:
                        guild_id_int = int(key)
                        if 10**17 <= guild_id_int <= 10**19:
                            guild_ids_found.append(key)
                    except ValueError:
                        pass
            
            if guild_ids_found:
                print(f"\n⚠️ [AUTO-CLEANUP] Found {len(guild_ids_found)} stray guild IDs!")
                
                for guild_id_str in guild_ids_found:
                    try:
                        guild_config = current_config[guild_id_str]
                        if isinstance(guild_config, dict):
                            from config import save_guild_config_sync
                            save_guild_config_sync(guild_id_str, guild_config)
                        del current_config[guild_id_str]
                    except Exception as e:
                        print(f"Error extracting guild {guild_id_str}: {e}")
                
                save_config(current_config)
                print(f"✅ [AUTO-CLEANUP] Removed {len(guild_ids_found)} stray guild IDs\n")
        
        except Exception as e:
            print(f"Error in auto_cleanup_task: {e}")


async def heartbeat_monitor():
    """Background task: Monitor heartbeat status."""
    await bot.wait_until_ready()
    print("✅ Heartbeat Monitor started\n")
    
    while not bot.is_closed():
        try:
            await asyncio.sleep(300)
            
            ensure_guild_config_dir()
            if os.path.exists(GUILD_CONFIG_DIR):
                for config_file in os.listdir(GUILD_CONFIG_DIR):
                    if not config_file.startswith("guild_") or not config_file.endswith(".json"):
                        continue
                    
                    guild_id = config_file.replace("guild_", "").replace(".json", "")
                    guild_config = load_guild_config(guild_id)
                    
                    if "heartbeat_data" in guild_config and "last_update" in guild_config["heartbeat_data"]:
                        try:
                            last_update = datetime.fromisoformat(guild_config["heartbeat_data"]["last_update"])
                            now = datetime.now(BERLIN_TZ)
                            if now - last_update > timedelta(minutes=60):
                                await update_heartbeat_message(guild_id)
                        except Exception as e:
                            await log_error_to_webhook(config, BERLIN_TZ, f"Heartbeat monitor error: {e}", guild_id, "heartbeat_monitor")
        
        except Exception as e:
            print(f"Error in heartbeat_monitor: {e}")


async def lifetime_stats_update_task():
    """Background task: Update lifetime stats every hour."""
    await bot.wait_until_ready()
    print("✅ Lifetime Stats Update Task started\n")
    
    while not bot.is_closed():
        try:
            await asyncio.sleep(3600)
            
            if not LIFETIME_STATS_MESSAGES:
                continue
            
            embed = create_lifetime_stats_embed()
            
            messages_to_remove = []
            for message_key, message_info in list(LIFETIME_STATS_MESSAGES.items()):
                try:
                    channel_id = message_info["channel_id"]
                    message_id = message_info["message_id"]
                    
                    channel = bot.get_channel(channel_id)
                    if not channel:
                        messages_to_remove.append(message_key)
                        continue
                    
                    try:
                        message = await channel.fetch_message(message_id)
                        await message.edit(embed=embed)
                        print(f"✅ Updated lifetime stats in {channel.guild.name}")
                    except discord.NotFound:
                        messages_to_remove.append(message_key)
                
                except Exception as e:
                    print(f"Error updating lifetime stats: {e}")
                    messages_to_remove.append(message_key)
            
            for key in messages_to_remove:
                del LIFETIME_STATS_MESSAGES[key]
        
        except Exception as e:
            print(f"Error in lifetime_stats_update_task: {e}")


def create_lifetime_stats_embed():
    """Erstelle Lifetime Stats Embed aus allen Guild-Configs."""
    total_godpacks = 0
    total_godpacks_valid = 0
    total_godpacks_invalid = 0
    total_trades = 0
    total_traded = 0
    total_filter_stats = {}
    
    guild_count = 0
    active_guild_count = 0
    
    ensure_guild_config_dir()
    if os.path.exists(GUILD_CONFIG_DIR):
        for filename in os.listdir(GUILD_CONFIG_DIR):
            if not filename.startswith("guild_") or not filename.endswith(".json"):
                continue
            
            try:
                guild_id_str = filename.replace("guild_", "").replace(".json", "")
                guild_config = load_guild_config(guild_id_str)
                guild_count += 1
                
                stats = guild_config.get("stats", {})
                filter_stats_guild = guild_config.get("filter_stats", {})
                
                if stats or filter_stats_guild:
                    active_guild_count += 1
                
                godpacks = stats.get("godpacks", {})
                total_godpacks += godpacks.get("total", 0)
                total_godpacks_valid += godpacks.get("valid", 0)
                total_godpacks_invalid += godpacks.get("invalid", 0)
                
                general = stats.get("general", {})
                total_trades += general.get("total", 0)
                total_traded += general.get("valid", 0)
                
                for keyword, count in filter_stats_guild.items():
                    keyword_normalized = keyword.lower().strip()
                    if keyword_normalized in total_filter_stats:
                        total_filter_stats[keyword_normalized] += count
                    else:
                        total_filter_stats[keyword_normalized] = count
            
            except (ValueError, json.JSONDecodeError):
                continue
    
    embed = discord.Embed(
        title="🌍 Lifetime Statistics (All Servers)",
        description=f"Global stats from **{guild_count}** total servers (with data on **{active_guild_count}**)",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url="https://i.imgur.com/pxqjVbO.png")
    
    embed.add_field(
        name="📊 Overall",
        value=f"Total Servers: **{guild_count}**\nActive: **{active_guild_count}**\nTotal Found: **{sum(total_filter_stats.values())}**",
        inline=False
    )
    
    embed.add_field(
        name="🌟 God Packs",
        value=f"Total: **{total_godpacks}**\nValid: **{total_godpacks_valid}**\nInvalid: **{total_godpacks_invalid}**",
        inline=False
    )
    
    embed.add_field(
        name="✅ Safe 4 Trade",
        value=f"Total: **{total_trades}**\nTraded: **{total_traded}**",
        inline=False
    )
    
    embed.set_footer(
        text=f"Last updated: {datetime.now(BERLIN_TZ).strftime('%d.%m.%Y %H:%M:%S')} Berlin Time"
    )
    
    return embed


@bot.event
async def on_ready():
    """Bot startup event."""
    bot.start_time = datetime.now(BERLIN_TZ)
    print(f"✅ Bot ready as {bot.user}")
    await bot.change_presence(status=discord.Status.online, activity=discord.Game("Pokémon TCG Pocket"))
    await tree.sync()
    print("✅ Slash commands synced\n")
    
    # Register persistent views
    bot.add_view(discord.ui.View())
    
    # Start tasks
    if not any(task.get_name() == "auto_cleanup_task" for task in asyncio.all_tasks()):
        asyncio.create_task(auto_cleanup_task(), name="auto_cleanup_task")
    
    if not any(task.get_name() == "heartbeat_monitor" for task in asyncio.all_tasks()):
        asyncio.create_task(heartbeat_monitor(), name="heartbeat_monitor")
    
    if not any(task.get_name() == "lifetime_stats_update_task" for task in asyncio.all_tasks()):
        asyncio.create_task(lifetime_stats_update_task(), name="lifetime_stats_update_task")
    
    await restore_setup_for_all_guilds()


@bot.event
async def on_message(message):
    """Message event handler."""
    if message.guild is None:
        return
    
    # Prefix commands (dev commands)
    if message.content.startswith("-help"):
        if message.author.id != bot.OWNER_ID:
            await message.reply("❌ Owner only!", mention_author=False)
            return
        
        from commands.dev_commands import show_dev_help
        await show_dev_help(message, bot)
        return
    
    # Pack/Filter message processing
    await process_message(message, bot, config, BERLIN_TZ)


async def restore_setup_for_all_guilds():
    """Restore setup für alle Guilds on bot restart."""
    print("🔄 Restoring setup for all guilds...")
    restored_guilds = 0
    
    ensure_guild_config_dir()
    if os.path.exists(GUILD_CONFIG_DIR):
        for config_file in os.listdir(GUILD_CONFIG_DIR):
            if not config_file.startswith("guild_") or not config_file.endswith(".json"):
                continue
            
            guild_id_str = config_file.replace("guild_", "").replace(".json", "")
            guild_config = load_guild_config(guild_id_str)
            
            try:
                guild = bot.get_guild(int(guild_id_str))
                if not guild:
                    continue
                
                # Restore category & channels
                category_configs = {
                    "Save 4 Trade": {"keywords": ["one star", "three diamond", "four diamond ex", "gimmighoul", "shiny", "rainbow", "full art", "trainer"]},
                    "God Packs": {"keywords": ["god pack", "invalid god pack"]},
                    "Detection": {"keywords": ["crown", "immersive"]},
                    "A-Series": {"series": "A-Series"},
                    "B-Series": {"series": "B-Series"}
                }
                
                for cat_name in category_configs.keys():
                    category = discord.utils.get(guild.categories, name=cat_name)
                    if not category:
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(view_channel=True),
                            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                        }
                        await guild.create_category(cat_name, overwrites=overwrites)
                
                restored_guilds += 1
            
            except Exception as e:
                print(f"Error restoring guild {guild_id_str}: {e}")
    
    print(f"✅ Restored {restored_guilds} guilds\n")


# Main startup
async def main():
    """Load config, cogs, and start bot."""
    global config, OWNER_ID, BERLIN_TZ, PACKS
    
    # Load config
    config = load_config()
    OWNER_ID = config.get("owner_id", 774679828594163802)
    timezone_str = config.get("timezone", "Europe/Berlin")
    BERLIN_TZ = ZoneInfo(timezone_str)
    PACKS = [p for sublist in config.get("series", {}).values() for p in sublist]
    
    # Set bot attributes
    bot.config = config
    bot.OWNER_ID = OWNER_ID
    bot.BERLIN_TZ = BERLIN_TZ
    
    # Load cogs
    await load_cogs()
    
    # Run bot
    load_dotenv()
    token = os.getenv("TOKEN")
    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
