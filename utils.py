import os
import json
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random
import re
import asyncio
import time
import threading
import sys
from collections import deque
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

load_dotenv()

# Debug Logging
DEBUG_PACK_LOGS = os.getenv("DEBUG_PACK_LOGS", "false").lower() == "true"
DEBUG_LIFETIME_STATS = os.getenv("DEBUG_LIFETIME_STATS", "true").lower() == "true"

# Thread-safe lock for config saves
config_save_lock = threading.Lock()

# Bot reference - set in on_ready via set_bot()
_bot = None

def set_bot(bot_instance):
    global _bot
    _bot = bot_instance

# File paths
CONFIG_FILE = "bot_config.json"
LIFETIME_STATS_FILE = "lifetime_stats_messages.json"
GUILD_CONFIG_DIR = "guild_configs"

# Global state
OWNER_ID = None
BERLIN_TZ = None
PACKS = []

# Missing configs tracking
missing_configs = {}

# Lifetime stats tracking
LIFETIME_STATS_MESSAGES = {}
LIFETIME_STATS_TASK_STARTED = False
LIFETIME_STATS_TASK = None


# ============================================================
# CONFIG FUNCTIONS
# ============================================================

def load_config():
    """Load config from bot_config.json. Automatically extracts any guild data to separate files."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)

            guild_ids_found = []
            for key in list(config.keys()):
                if key not in ["series", "packs"]:
                    try:
                        guild_id_int = int(key)
                        if 10**17 <= guild_id_int <= 10**19:
                            guild_ids_found.append(key)
                    except ValueError:
                        pass

            if guild_ids_found:
                print(f"\n⚠️ Found {len(guild_ids_found)} server IDs in bot_config.json that shouldn't be there!")
                print("🔄 Automatically extracting to separate guild config files...\n")
                for guild_id_str in guild_ids_found:
                    try:
                        guild_config = config[guild_id_str]
                        if isinstance(guild_config, dict):
                            save_guild_config_sync(guild_id_str, guild_config)
                            print(f"  ✅ Extracted guild {guild_id_str} to guild_configs/guild_{guild_id_str}.json")
                        del config[guild_id_str]
                    except Exception as e:
                        print(f"  ❌ Error extracting guild {guild_id_str}: {e}")
                save_config(config)
                print(f"\n✅ bot_config.json cleaned - removed {len(guild_ids_found)} server entries\n")

            packs = config.get("packs", [
                "palkia", "dialga", "arceus", "shining", "mew", "pikachu", "charizard",
                "mewtwo", "solgaleo", "lunala", "buzzwole", "eevee", "hooh", "lugia",
                "springs", "deluxe"
            ])
            series = config.get("series", {"A-Series": packs})
            config["series"] = series
            config["packs"] = packs
            update_packs(config)
            return config
        except json.JSONDecodeError as e:
            print(f"\n⚠️ Error parsing {CONFIG_FILE}: {e}")
            if os.path.exists(CONFIG_FILE):
                corrupted_name = f"{CONFIG_FILE}.corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(CONFIG_FILE, corrupted_name)
                print(f"Corrupted config saved to: {corrupted_name}\n")

    print(f"Creating new default configuration...\n")
    default_series = {"A-Series": [
        "palkia", "dialga", "arceus", "shining", "mew", "pikachu", "charizard",
        "mewtwo", "solgaleo", "lunala", "buzzwole", "eevee", "hooh", "lugia",
        "springs", "deluxe"
    ]}
    default_config = {"series": default_series, "packs": sum(default_series.values(), [])}
    save_config(default_config)
    return default_config


def update_packs(cfg):
    global PACKS
    PACKS = [p for sublist in cfg["series"].values() for p in sublist]


def save_config(cfg):
    """Save config to bot_config.json (runs in background thread). Auto-filters out any guild data."""
    import copy

    def _save():
        with config_save_lock:
            try:
                config_copy = copy.deepcopy(cfg)
                keys_to_remove = []
                for key in list(config_copy.keys()):
                    if key not in ["series", "packs"]:
                        try:
                            guild_id_int = int(key)
                            if 10**17 <= guild_id_int <= 10**19:
                                keys_to_remove.append(key)
                                print(f"⚠️ [SAFETY] Removed stray guild ID {key} from save_config()")
                        except ValueError:
                            pass
                for key in keys_to_remove:
                    del config_copy[key]
                with open(CONFIG_FILE, "w") as f:
                    json.dump(config_copy, f, indent=4)
            except Exception as e:
                print(f"Error saving config: {e}")

    threading.Thread(target=_save, daemon=True).start()


def ensure_guild_config_dir():
    if not os.path.exists(GUILD_CONFIG_DIR):
        os.makedirs(GUILD_CONFIG_DIR)


def get_guild_config_path(guild_id):
    return os.path.join(GUILD_CONFIG_DIR, f"guild_{guild_id}.json")


def load_guild_config(guild_id):
    """Load guild config with auto-recovery on corruption."""
    ensure_guild_config_dir()
    config_path = get_guild_config_path(guild_id)

    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"❌ Guild config corrupted for {guild_id}: {e}")

            backup_candidates = [f"{config_path}.backup"]
            backup_dir = os.path.dirname(config_path)
            config_filename = os.path.basename(config_path)
            if os.path.exists(backup_dir):
                for filename in sorted(os.listdir(backup_dir), reverse=True):
                    if filename.startswith(config_filename + ".backup"):
                        backup_candidates.append(os.path.join(backup_dir, filename))

            restored_config = None
            restored_from = None
            for backup_path in backup_candidates:
                if os.path.exists(backup_path):
                    try:
                        with open(backup_path, "r") as f:
                            restored_config = json.load(f)
                        restored_from = backup_path
                        print(f"✅ [RECOVERY] Guild {guild_id}: Successfully restored from backup: {os.path.basename(backup_path)}")
                        break
                    except (json.JSONDecodeError, IOError) as backup_error:
                        print(f"⚠️ Backup {os.path.basename(backup_path)} also corrupted: {backup_error}")
                        continue

            if restored_config:
                try:
                    with open(config_path, "w") as f:
                        json.dump(restored_config, f, indent=4)
                    asyncio.create_task(log_guild_corruption_to_webhook(
                        guild_id,
                        f"Config corrupted. Auto-recovered from backup file.",
                        f"Restored from {os.path.basename(restored_from)}"
                    ))
                    return restored_config
                except Exception as write_error:
                    print(f"❌ Could not write restored config: {write_error}")

            empty_config = {"packs": {}, "filters": {}, "channels": {}}
            corrupted_name = f"{config_path}.corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                os.rename(config_path, corrupted_name)
                print(f"📦 Saved corrupted config to: {corrupted_name}")
                asyncio.create_task(log_guild_corruption_to_webhook(
                    guild_id,
                    f"❌ CRITICAL: Config AND all backup files are corrupted!\nConfig file renamed to:\n`{os.path.basename(corrupted_name)}`\nCreating empty config as fallback.",
                    "Fallback to empty config - ALL BACKUPS CORRUPTED"
                ))
            except Exception as rename_error:
                print(f"⚠️ Could not rename corrupted file: {rename_error}")
                asyncio.create_task(log_guild_corruption_to_webhook(
                    guild_id,
                    f"❌ CRITICAL: Config corrupted AND all backups failed!\nCould not rename corrupted file: {str(rename_error)[:500]}",
                    "Using empty config fallback - CRITICAL ERROR"
                ))

            return empty_config

    return {"packs": {}, "filters": {}, "channels": {}}


def save_guild_config(guild_id, guild_config):
    """Save guild config (thread-safe, async) with backup rotation (max 3)."""
    import copy

    def _save():
        with config_save_lock:
            ensure_guild_config_dir()
            config_path = get_guild_config_path(guild_id)
            try:
                if os.path.exists(config_path):
                    try:
                        with open(config_path, "r") as f:
                            current_data = json.load(f)
                        backup_path = f"{config_path}.backup"
                        max_backups = 3
                        for i in range(max_backups - 1, 0, -1):
                            old_backup = f"{config_path}.backup.{i}"
                            new_backup = f"{config_path}.backup.{i + 1}"
                            if os.path.exists(old_backup):
                                try:
                                    os.remove(new_backup) if os.path.exists(new_backup) else None
                                    os.rename(old_backup, new_backup)
                                except Exception:
                                    pass
                        if os.path.exists(backup_path):
                            try:
                                os.rename(backup_path, f"{config_path}.backup.1")
                            except Exception:
                                pass
                        with open(backup_path, "w") as f:
                            json.dump(current_data, f, indent=4)
                    except Exception as backup_error:
                        print(f"⚠️ Could not create backup rotation for {guild_id}: {backup_error}")

                config_copy = copy.deepcopy(guild_config)
                with open(config_path, "w") as f:
                    json.dump(config_copy, f, indent=4)
            except Exception as e:
                print(f"Error saving guild config for {guild_id}: {e}")

    threading.Thread(target=_save, daemon=True).start()


def save_guild_config_sync(guild_id, guild_config):
    """Save guild config SYNCHRONOUSLY (blocking)."""
    import copy
    with config_save_lock:
        ensure_guild_config_dir()
        config_path = get_guild_config_path(guild_id)
        try:
            config_copy = copy.deepcopy(guild_config)
            with open(config_path, "w") as f:
                json.dump(config_copy, f, indent=4)
        except Exception as e:
            print(f"Error saving guild config for {guild_id}: {e}")


def migrate_configs():
    if not os.path.exists(CONFIG_FILE):
        return
    try:
        with open(CONFIG_FILE, "r") as f:
            old_config = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    guild_configs_data = {}
    for key in list(old_config.keys()):
        if "_" in key:
            parts = key.split("_", 1)
            if parts[0].isdigit():
                guild_id = int(parts[0])
                config_type = parts[1]
                if guild_id not in guild_configs_data:
                    guild_configs_data[guild_id] = {"packs": {}, "filters": {}, "channels": {}}
                if config_type.startswith("pack"):
                    guild_configs_data[guild_id]["packs"] = old_config[key]
                elif config_type.startswith("filter"):
                    guild_configs_data[guild_id]["filters"] = old_config[key]
                elif config_type.startswith("channel"):
                    guild_configs_data[guild_id]["channels"] = old_config[key]

    if guild_configs_data:
        print(f"Migriere {len(guild_configs_data)} Guild-Konfigurationen...")
        for guild_id, guild_config in guild_configs_data.items():
            save_guild_config(guild_id, guild_config)
            print(f"  ✓ Guild {guild_id} migriert")
        global_only_config = {k: v for k, v in old_config.items() if not ("_" in k and k.split("_")[0].isdigit())}
        save_config(global_only_config)
        print("✓ Migration abgeschlossen - bot_config.json bereinigt")


def extract_and_save_guild_configs(cfg):
    ensure_guild_config_dir()
    guilds_extracted = 0
    guild_ids_to_remove = []
    for guild_id_str, guild_config_data in list(cfg.items()):
        if guild_id_str in ["series", "packs"]:
            continue
        if not isinstance(guild_id_str, str) or not guild_id_str.isdigit():
            continue
        guild_id_int = int(guild_id_str)
        if guild_id_int == 0 or not (10**17 <= guild_id_int <= 10**19):
            print(f"⚠️ Skipped invalid guild ID: {guild_id_str}")
            continue
        if isinstance(guild_config_data, dict) and len(guild_config_data) > 0:
            save_guild_config(guild_id_int, guild_config_data)
            guild_ids_to_remove.append(guild_id_str)
            guilds_extracted += 1
    if guild_ids_to_remove:
        for guild_id_str in guild_ids_to_remove:
            del cfg[guild_id_str]
        save_config(cfg)
        print(f"✓ {guilds_extracted} Guild-Konfigurationen extrahiert und aus bot_config.json entfernt")


def final_cleanup_config():
    global config
    ALLOWED_GLOBAL_KEYS = [
        "series", "packs", "error_webhook_url", "permission_warning_webhook_url",
        "guild_corruption_webhook_url", "owner_id", "timezone"
    ]
    keys_to_remove = []
    for key in config.keys():
        if key in ALLOWED_GLOBAL_KEYS:
            continue
        if key.isdigit():
            keys_to_remove.append(key)
    if keys_to_remove:
        print(f"\n🧹 Final Cleanup: Removing {len(keys_to_remove)} stray guild IDs from bot_config.json...")
        for key in keys_to_remove:
            print(f"  ❌ Removing stray Guild ID: {key}")
            del config[key]
        save_config(config)
        print(f"✅ Final cleanup complete - bot_config.json is clean!\n")


def clean_stale_guilds():
    """Remove guild configs from bot_config.json if bot is no longer in that guild."""
    stale_guilds = []
    for guild_id_str in list(config.keys()):
        if guild_id_str in ["series", "packs"]:
            continue
        try:
            guild = _bot.get_guild(int(guild_id_str)) if _bot else None
            if not guild:
                stale_guilds.append(guild_id_str)
        except ValueError:
            continue
    for guild_id_str in stale_guilds:
        del config[guild_id_str]
        print(f"Removed stale guild config for {guild_id_str}")
    if stale_guilds:
        save_config(config)
        print(f"Cleaned {len(stale_guilds)} stale guild configs from bot_config.json")


def clean_config_duplicates():
    """Remove guild configs from bot_config.json if they already exist in guild_configs/."""
    duplicates = []
    for guild_id_str in list(config.keys()):
        if guild_id_str in ["series", "packs"]:
            continue
        try:
            guild_config_file = os.path.join(GUILD_CONFIG_DIR, f"guild_{guild_id_str}.json")
            if os.path.exists(guild_config_file):
                duplicates.append(guild_id_str)
        except Exception:
            continue
    for guild_id_str in duplicates:
        del config[guild_id_str]
        print(f"✓ Removed duplicate guild config {guild_id_str} from bot_config.json")
    if duplicates:
        save_config(config)
        print(f"✅ Cleaned {len(duplicates)} duplicate guild configs from bot_config.json")


# ============================================================
# INITIALIZATION
# ============================================================

migrate_configs()
config = load_config()
extract_and_save_guild_configs(config)

OWNER_ID = config.get("owner_id", 774679828594163802)
timezone_str = config.get("timezone", "Europe/Berlin")
BERLIN_TZ = ZoneInfo(timezone_str)
print(f"✅ Owner ID geladen: {OWNER_ID}")
print(f"✅ Timezone geladen: {timezone_str}")

final_cleanup_config()

PACKS = config["packs"]


# ============================================================
# WEBHOOK LOGGING
# ============================================================

async def log_error_to_webhook(error_message: str, guild_id: str = None, command_name: str = None):
    try:
        webhook_url = config.get("error_webhook_url")
        if not webhook_url:
            print(f"⚠️ Error Webhook URL not configured in bot_config.json")
            return
        if len(error_message) > 1500:
            error_message = error_message[:1500] + "\n... (gekürzt)"
        embed = discord.Embed(
            title="🚨 Bot Error",
            description=error_message,
            color=discord.Color.red(),
            timestamp=datetime.now(BERLIN_TZ)
        )
        if command_name:
            embed.add_field(name="Befehl", value=f"`{command_name}`", inline=True)
        if guild_id:
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
        embed.add_field(name="Zeitstempel", value=f"<t:{int(time.time())}:F>", inline=False)
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json={"embeds": [embed.to_dict()]}) as resp:
                if resp.status not in [200, 204]:
                    print(f"⚠️ Failed to send error to webhook: {resp.status}")
    except Exception as e:
        print(f"❌ Error logging to webhook: {e}")


async def log_permission_warning_to_webhook(error_message: str, guild_id: str = None, command_name: str = None):
    try:
        webhook_url = config.get("permission_warning_webhook_url")
        if not webhook_url:
            await log_error_to_webhook(error_message, guild_id, command_name)
            return
        if len(error_message) > 1500:
            error_message = error_message[:1500] + "\n... (gekürzt)"
        embed = discord.Embed(
            title="⚠️ Permission Warning",
            description=error_message,
            color=discord.Color.orange(),
            timestamp=datetime.now(BERLIN_TZ)
        )
        if command_name:
            embed.add_field(name="Befehl", value=f"`{command_name}`", inline=True)
        if guild_id:
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
        embed.add_field(name="Zeitstempel", value=f"<t:{int(time.time())}:F>", inline=False)
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json={"embeds": [embed.to_dict()]}) as resp:
                if resp.status not in [200, 204]:
                    print(f"⚠️ Failed to send permission warning to webhook: {resp.status}")
    except Exception as e:
        print(f"❌ Error logging permission warning to webhook: {e}")


async def log_config_reset_to_webhook(guild_id: str, guild_name: str, owner: discord.User, channels_count: int):
    try:
        webhook_url = config.get("guild_corruption_webhook_url")
        if not webhook_url:
            return
        embed = discord.Embed(
            title="✅ Guild Config Reinitialized",
            description=f"The guild owner has reinitialized the config for **{guild_name}**.",
            color=discord.Color.green(),
            timestamp=datetime.now(BERLIN_TZ)
        )
        embed.add_field(name="Guild", value=f"{guild_name} (ID: `{guild_id}`)", inline=False)
        embed.add_field(name="Action Performed By", value=f"{owner.mention} (`{owner.id}`)", inline=False)
        embed.add_field(name="Channels Detected & Added", value=f"`{channels_count}` text channel(s)", inline=False)
        embed.add_field(name="Timestamp", value=f"<t:{int(time.time())}:F>", inline=False)
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json={"embeds": [embed.to_dict()]}) as resp:
                if resp.status not in [200, 204]:
                    print(f"⚠️ Failed to send config reset notification to webhook: {resp.status}")
    except Exception as e:
        print(f"❌ Error logging config reset to webhook: {e}")


async def log_guild_corruption_to_webhook(guild_id: str, error_message: str, recovery_action: str = None):
    try:
        webhook_url = config.get("guild_corruption_webhook_url")
        if not webhook_url:
            print(f"⚠️ Guild Corruption Webhook URL not configured in bot_config.json")
        else:
            if len(error_message) > 1000:
                error_message = error_message[:1000] + "\n... (gekürzt)"
            embed = discord.Embed(
                title="🔴 Guild Config Corruption Detected",
                description=error_message,
                color=discord.Color.dark_red(),
                timestamp=datetime.now(BERLIN_TZ)
            )
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
            if recovery_action:
                embed.add_field(name="Recovery Action", value=f"`{recovery_action}`", inline=True)
            embed.add_field(name="Zeitstempel", value=f"<t:{int(time.time())}:F>", inline=False)
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json={"embeds": [embed.to_dict()]}) as resp:
                    if resp.status not in [200, 204]:
                        print(f"⚠️ Failed to send guild corruption warning to webhook: {resp.status}")
    except Exception as e:
        print(f"❌ Error logging guild corruption to webhook: {e}")

    if recovery_action and "ALL BACKUPS CORRUPTED" in recovery_action:
        await notify_guild_owner_corruption(guild_id, error_message, recovery_action)


# ============================================================
# CORRUPTION RECOVERY
# ============================================================

class CorruptionRecoveryView(discord.ui.View):
    """View with button to reinitialize guild config."""
    def __init__(self, guild_id: str, timeout: int = 3600):
        super().__init__(timeout=timeout)
        self.guild_id = guild_id

    @discord.ui.button(label="🔧 Reinitialize Config", style=discord.ButtonStyle.danger)
    async def reset_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        try:
            guild = interaction.client.get_guild(int(self.guild_id))
            if not guild:
                await interaction.followup.send("❌ Server not found!", ephemeral=True)
                return

            source_channel_ids = []
            heartbeat_channel_id = None

            for channel in guild.text_channels:
                if not channel.permissions_for(guild.me).send_messages:
                    continue
                channel_name = channel.name.lower()
                if "source" in channel_name or "feed" in channel_name:
                    source_channel_ids.append(channel.id)

            for channel in guild.text_channels:
                if not channel.permissions_for(guild.me).send_messages:
                    continue
                channel_name = channel.name.lower()
                if "heartbeat" in channel_name or "status" in channel_name or "bot-log" in channel_name:
                    heartbeat_channel_id = channel.id
                    break

            new_config = {
                "packs": {},
                "filters": {},
                "channels": {},
                "default_source_channel_ids": source_channel_ids,
                "heartbeat_target_channel_id": heartbeat_channel_id
            }
            save_guild_config(self.guild_id, new_config)

            confirmation_embed = discord.Embed(
                title="✅ Config Successfully Reinitialized",
                description=f"Essential channels have been detected and restored.",
                color=discord.Color.green(),
                timestamp=datetime.now(BERLIN_TZ)
            )
            confirmation_embed.add_field(
                name="Source Channels",
                value=f"{len(source_channel_ids)} channel(s) detected" if source_channel_ids else "None detected",
                inline=False
            )
            confirmation_embed.add_field(
                name="Heartbeat Channel",
                value=f"<#{heartbeat_channel_id}>" if heartbeat_channel_id else "None detected",
                inline=False
            )
            confirmation_embed.add_field(name="Server ID", value=f"`{self.guild_id}`", inline=False)

            await interaction.followup.send(embed=confirmation_embed, ephemeral=True)
            asyncio.create_task(log_config_reset_to_webhook(
                guild_id=self.guild_id,
                guild_name=guild.name,
                owner=interaction.user,
                channels_count=len(source_channel_ids) + (1 if heartbeat_channel_id else 0)
            ))
        except Exception as e:
            print(f"❌ Error resetting guild config: {e}")
            await interaction.followup.send(f"❌ Error resetting config: {str(e)[:100]}", ephemeral=True)


async def notify_guild_owner_corruption(guild_id: str, error_message: str, recovery_action: str = None):
    try:
        guild = _bot.get_guild(int(guild_id)) if _bot else None
        if not guild:
            print(f"⚠️ Guild {guild_id} not found for corruption notification")
            return
        owner = guild.owner
        if not owner:
            print(f"⚠️ Guild {guild_id} has no owner")
            return

        embed = discord.Embed(
            title="🔴 Guild Config Corruption Detected",
            description=f"The configuration for your server **{guild.name}** has been automatically recovered.",
            color=discord.Color.dark_red(),
            timestamp=datetime.now(BERLIN_TZ)
        )
        embed.add_field(name="What happened?", value="A file corruption was detected and has been automatically recovered.", inline=False)
        if error_message:
            error_short = error_message[:200] + "..." if len(error_message) > 200 else error_message
            embed.add_field(name="Error Message", value=f"`{error_short}`", inline=False)
        if recovery_action:
            embed.add_field(name="Recovery Action", value=f"`{recovery_action}`", inline=False)
        embed.add_field(name="Server", value=f"{guild.name} (ID: `{guild_id}`)", inline=False)
        embed.add_field(name="⚙️ Next Steps", value="You can reinitialize the config - existing channels will be automatically added.", inline=False)

        view = CorruptionRecoveryView(guild_id)
        try:
            await owner.send(embed=embed, view=view)
            print(f"✅ DM sent to owner of guild {guild_id}")
        except discord.Forbidden:
            print(f"⚠️ Could not DM owner of guild {guild_id}")
    except Exception as e:
        print(f"❌ Error notifying guild owner of corruption: {e}")


# ============================================================
# LIFETIME STATS I/O
# ============================================================

def save_lifetime_stats_messages():
    try:
        messages_to_save = {}
        for key, info in LIFETIME_STATS_MESSAGES.items():
            messages_to_save[key] = {
                "channel_id": info["channel_id"],
                "message_id": info["message_id"],
                "guild_id": info["guild_id"],
                "posted_at": info["posted_at"].isoformat() if isinstance(info["posted_at"], datetime) else info["posted_at"]
            }
        with open(LIFETIME_STATS_FILE, "w") as f:
            json.dump(messages_to_save, f, indent=4)
        if DEBUG_LIFETIME_STATS:
            print(f"💾 Saved {len(messages_to_save)} lifetime stats message(s) to {LIFETIME_STATS_FILE}")
    except Exception as e:
        print(f"❌ Error saving lifetime stats messages: {e}")


def load_lifetime_stats_messages():
    global LIFETIME_STATS_MESSAGES
    try:
        LIFETIME_STATS_MESSAGES.clear()
        if os.path.exists(LIFETIME_STATS_FILE):
            with open(LIFETIME_STATS_FILE, "r") as f:
                messages_data = json.load(f)
                for key, info in messages_data.items():
                    LIFETIME_STATS_MESSAGES[key] = {
                        "channel_id": info["channel_id"],
                        "message_id": info["message_id"],
                        "guild_id": info["guild_id"],
                        "posted_at": datetime.fromisoformat(info["posted_at"]) if isinstance(info["posted_at"], str) else info["posted_at"]
                    }
            if DEBUG_LIFETIME_STATS:
                print(f"✅ Loaded {len(LIFETIME_STATS_MESSAGES)} lifetime stats message(s) from {LIFETIME_STATS_FILE}")
        else:
            if DEBUG_LIFETIME_STATS:
                print(f"ℹ️ No lifetime stats messages file found ({LIFETIME_STATS_FILE})")
    except Exception as e:
        print(f"❌ Error loading lifetime stats messages: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# AUTOCOMPLETE & CHECKS
# ============================================================

def get_pack_choices():
    return [app_commands.Choice(name=pack.title(), value=pack) for pack in PACKS[:25]]


async def autocomplete_packs(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    choices = get_pack_choices()
    if not current:
        return choices
    return [c for c in choices if current.lower() in c.value.lower()][:25]


async def autocomplete_series(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    series_names = list(config.get("series", {}).keys())
    if not current:
        return [app_commands.Choice(name=s, value=s) for s in series_names[:25]]
    return [app_commands.Choice(name=s, value=s) for s in series_names if current.lower() in s.lower()][:25]


async def owner_only(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        embed = discord.Embed(
            title="Access Denied",
            description="This command can only be used by the bot developer for updating the bot.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return False
    return True


# ============================================================
# TEXT CONSTANTS
# ============================================================

LOCALE_TEXT = {
    "bot_started": "Bot started as {bot_name}",
    "embed_title": "Found: {keyword}",
    "embed_link_text": "[Go to original message]({link})",
    "embed_footer": "Forwarded by HELPER ¦ TCGP",
    "embed_author_name": "Save 4 Trade",
}

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

SAVE4TRADE_KEYWORDS = ["one star", "three diamond", "four diamond ex", "gimmighoul", "shiny", "rainbow", "full art", "trainer"]

OLD_TO_NEW_CHANNEL_NAMES = {
    "save-4-trade-one-star": "one-star",
    "save-4-trade-three-diamond": "three-diamond",
    "save-4-trade-four-diamond-ex": "four-diamond-ex",
    "save-4-trade-gimmighoul": "gimmighoul",
    "save-4-trade-shiny": "shiny",
    "save-4-trade-rainbow": "rainbow",
    "save-4-trade-full-art": "full-art",
    "save-4-trade-trainer": "trainer",
    "god-packs-god-pack": "god-pack",
    "god-packs-invalid-god-pack": "invalid-god-pack",
    "detection-crown": "crown",
    "detection-immersive": "immersive",
}

NEW_TO_OLD_CHANNEL_NAMES = {v: k for k, v in OLD_TO_NEW_CHANNEL_NAMES.items()}

# Choice constants for commands
FILTER_CHOICES = [app_commands.Choice(name=keyword.title(), value=keyword) for keyword in CUSTOM_EMBED_TEXT.keys()]
CLEAR_FILTER_CHOICES = [
    app_commands.Choice(name="Normal Filters", value="normal"),
    app_commands.Choice(name="Pack Filters", value="pack"),
    app_commands.Choice(name="All Filters", value="all")
]


# ============================================================
# EMBED CREATORS
# ============================================================

def create_stats_embed(guild_config):
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
    embed.set_thumbnail(url="https://i.imgur.com/cqRCftR.png")
    godpacks = stats['godpacks']
    embed.add_field(
        name="God Packs",
        value=f"Total: {godpacks['total']}\nValid: {godpacks['valid']}\nInvalid: {godpacks['invalid']}",
        inline=False
    )
    if validation_buttons_enabled:
        general = stats['general']
        embed.add_field(
            name="Safe 4 Trade",
            value=f"Total: {general['total']}\nTraded: {general['valid']}",
            inline=False
        )
    return embed


def create_detailed_stats_embed(guild_config):
    filter_stats = guild_config.get("filter_stats", {})
    embed = discord.Embed(
        title="Detailed Filter Statistics",
        description="Here are the number of embeds sent for each filter in this server:",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url="https://i.imgur.com/cqRCftR.png")
    god_packs = ["god pack", "invalid god pack"]
    save_for_trade = ["one star", "three diamond", "four diamond ex", "gimmighoul", "shiny", "rainbow", "full art", "trainer"]
    detection = ["crown", "immersive"]

    god_pack_list = []
    for keyword in god_packs:
        count = filter_stats.get(keyword, 0)
        god_pack_list.append(f"{keyword.title()}: {count} pack{'s' if count != 1 else ''}")
    embed.add_field(
        name="GOD PACKS",
        value="\n".join(god_pack_list) if god_pack_list else "No embeds sent for GOD PACKS yet.",
        inline=False
    )

    save_for_trade_list = []
    for keyword in save_for_trade:
        count = filter_stats.get(keyword, 0)
        save_for_trade_list.append(f"{keyword.title()}: {count} card{'s' if count != 1 else ''}")
    embed.add_field(
        name="Save 4 Trade",
        value="\n".join(save_for_trade_list) if save_for_trade_list else "No embeds sent for Save 4 Trade yet.",
        inline=False
    )

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


def create_pack_stats_embed(guild_config):
    filter_stats = guild_config.get("filter_stats", {})
    series = config.get("series", {})
    embed = discord.Embed(
        title="Pack Statistics",
        description="Here are the number of embeds sent for each pack in this server:",
        color=discord.Color.teal()
    )
    embed.set_thumbnail(url="https://i.imgur.com/cqRCftR.png")
    for series_name, packs_in_series in series.items():
        series_list = []
        for pack in packs_in_series:
            count = filter_stats.get(pack, 0)
            series_list.append(f"{pack.title()}: {count} pack{'s' if count != 1 else ''}")
        embed.add_field(
            name=series_name,
            value="\n".join(series_list) if series_list else "No packs yet.",
            inline=False
        )
    return embed


def create_heartbeat_embed(guild_config):
    data = guild_config.get("heartbeat_data", {})
    if not data:
        return discord.Embed(title="Heartbeat", description="Waiting for first heartbeat...", color=discord.Color.orange())
    if "last_update" not in data or not data["last_update"]:
        return discord.Embed(title="Heartbeat", description="Bot is offline - No heartbeat found.", color=discord.Color.red())
    try:
        last_update = datetime.fromisoformat(data["last_update"])
        now = datetime.now(BERLIN_TZ)
        if now - last_update > timedelta(minutes=60):
            return discord.Embed(title="Heartbeat", description="Bot is offline - No heartbeat found.", color=discord.Color.red())
    except ValueError:
        return discord.Embed(title="Heartbeat", description="Bot is offline - No heartbeat found.", color=discord.Color.red())

    embed = discord.Embed(title="Heartbeat", color=discord.Color.green())
    embed.set_thumbnail(url="https://i.imgur.com/cqRCftR.png")
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
    last_update_berlin = last_update.astimezone(BERLIN_TZ)
    formatted_time = last_update_berlin.strftime("%d.%m.%Y %H:%M")
    embed.set_footer(text=f"Last updated: {formatted_time}")
    return embed


def create_lifetime_stats_embed(active_guild_ids=None):
    """Create embed with lifetime stats aggregated from ALL guild config files."""
    if DEBUG_LIFETIME_STATS:
        print(f"🔄 Creating lifetime stats embed...")

    total_godpacks = 0
    total_godpacks_valid = 0
    total_godpacks_invalid = 0
    total_trades = 0
    total_traded = 0
    total_filter_stats = {}

    guild_count = 0
    active_guild_count = 0
    inactive_guild_count = 0

    known_packs = {}
    for series_name, packs_in_series in config.get("series", {}).items():
        for pack in packs_in_series:
            known_packs[pack.lower()] = pack

    ensure_guild_config_dir()
    if os.path.exists(GUILD_CONFIG_DIR):
        for filename in os.listdir(GUILD_CONFIG_DIR):
            if filename.startswith("guild_") and filename.endswith(".json") and not filename.endswith(".bak"):
                try:
                    guild_id_str = filename.replace("guild_", "").replace(".json", "")
                    guild_id = int(guild_id_str)
                    guild_config = load_guild_config(guild_id)
                    guild_count += 1
                    if active_guild_ids is not None and guild_id not in active_guild_ids:
                        inactive_guild_count += 1
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

    if DEBUG_LIFETIME_STATS:
        print(f"  ✓ Loaded {guild_count} guilds, {active_guild_count} active")

    now_berlin = datetime.now(BERLIN_TZ)
    embed = discord.Embed(
        title="🌍 Lifetime Statistics (All Servers)",
        description=f"Global stats aggregated from **{guild_count}** total servers (with data on **{active_guild_count}**)",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url="https://i.imgur.com/cqRCftR.png")
    embed.add_field(
        name="📊 Overall",
        value=f"Total Servers Configured: **{guild_count}**\n"
              f"Servers with Activity: **{active_guild_count}**\n"
              f"Inactive Servers (bot left/kicked): **{inactive_guild_count}**\n"
              f"Total Found: **{sum(total_filter_stats.values())}**",
        inline=False
    )
    embed.add_field(
        name="🌟 God Packs (Global)",
        value=f"Total: **{total_godpacks}**\nValid: **{total_godpacks_valid}** ✅\nInvalid: **{total_godpacks_invalid}** ❌",
        inline=False
    )
    embed.add_field(
        name="✅ Safe 4 Trade (Global)",
        value=f"Total: **{total_trades}**\nTraded: **{total_traded}**",
        inline=False
    )

    filter_list = []
    for keyword in ["one star", "three diamond", "four diamond ex", "gimmighoul", "shiny", "rainbow", "full art", "trainer"]:
        count = total_filter_stats.get(keyword, 0)
        filter_list.append(f"{keyword.title()}: **{count}**")
    if filter_list:
        embed.add_field(name="🎴 Safe 4 Trade Breakdown", value="\n".join(filter_list), inline=False)

    detection_list = []
    for keyword in ["crown", "immersive"]:
        count = total_filter_stats.get(keyword, 0)
        detection_list.append(f"{keyword.title()}: **{count}**")
    if detection_list:
        embed.add_field(name="🔍 Detection", value="\n".join(detection_list), inline=False)

    pack_stats_by_series = {}
    for series_name in config.get("series", {}).keys():
        pack_stats_by_series[series_name] = []
    for series_name, packs_in_series in config.get("series", {}).items():
        for pack in packs_in_series:
            pack_lower = pack.lower()
            count = total_filter_stats.get(pack_lower, 0)
            pack_stats_by_series[series_name].append(f"{pack.title()}: **{count}**")
    for series_name, packs_list in sorted(pack_stats_by_series.items()):
        if packs_list:
            value = "\n".join(packs_list)
            chunks = split_field_value(value, field_name=f"📦 {series_name} Packs")
            for field_name, chunk in chunks:
                embed.add_field(name=field_name, value=chunk, inline=False)

    embed.set_footer(
        text=f"Last updated: {now_berlin.strftime('%d.%m.%Y %H:%M:%S')} Berlin Time",
        icon_url="https://imgur.com/T0KX069.png"
    )
    return embed


# ============================================================
# UPDATE MESSAGE FUNCTIONS
# ============================================================

async def update_stats_message(guild_id):
    guild_config = load_guild_config(guild_id)
    stats_channel_id = guild_config.get("stats_channel_id")
    stats_message_id = guild_config.get("stats_message_id")
    if stats_channel_id and stats_message_id and _bot:
        channel = _bot.get_channel(stats_channel_id)
        if channel:
            try:
                message = await channel.fetch_message(stats_message_id)
                embed = create_stats_embed(guild_config)
                await message.edit(embed=embed)
            except discord.NotFound:
                guild_config.pop("stats_channel_id", None)
                guild_config.pop("stats_message_id", None)
                save_guild_config(guild_id, guild_config)
            except Exception as e:
                print(f"Error updating stats message: {e}")


async def update_detailed_stats_message(guild_id):
    guild_config = load_guild_config(guild_id)
    detailed_stats_channel_id = guild_config.get("detailed_stats_channel_id")
    detailed_stats_message_id = guild_config.get("detailed_stats_message_id")
    if detailed_stats_channel_id and detailed_stats_message_id and _bot:
        channel = _bot.get_channel(detailed_stats_channel_id)
        if channel:
            try:
                message = await channel.fetch_message(detailed_stats_message_id)
                embed = create_detailed_stats_embed(guild_config)
                await message.edit(embed=embed)
            except discord.NotFound:
                guild_config.pop("detailed_stats_channel_id", None)
                guild_config.pop("detailed_stats_message_id", None)
                save_guild_config(guild_id, guild_config)
            except Exception as e:
                print(f"Error updating detailed stats message: {e}")


async def update_pack_stats_message(guild_id):
    guild_config = load_guild_config(guild_id)
    pack_stats_channel_id = guild_config.get("pack_stats_channel_id")
    pack_stats_message_id = guild_config.get("pack_stats_message_id")
    if pack_stats_channel_id and pack_stats_message_id and _bot:
        channel = _bot.get_channel(pack_stats_channel_id)
        if channel:
            try:
                message = await channel.fetch_message(pack_stats_message_id)
                embed = create_pack_stats_embed(guild_config)
                await message.edit(embed=embed)
            except discord.NotFound:
                guild_config.pop("pack_stats_channel_id", None)
                guild_config.pop("pack_stats_message_id", None)
                save_guild_config(guild_id, guild_config)
            except Exception as e:
                print(f"Error updating pack stats message: {e}")


async def update_heartbeat_message(guild_id):
    guild_config = load_guild_config(guild_id)
    heartbeat_channel_id = guild_config.get("heartbeat_target_channel_id")
    heartbeat_message_id = guild_config.get("heartbeat_message_id")
    if heartbeat_channel_id and heartbeat_message_id and _bot:
        channel = _bot.get_channel(heartbeat_channel_id)
        if channel:
            try:
                message = await channel.fetch_message(heartbeat_message_id)
                embed = create_heartbeat_embed(guild_config)
                await message.edit(embed=embed)
            except discord.NotFound:
                guild_config.pop("heartbeat_target_channel_id", None)
                guild_config.pop("heartbeat_message_id", None)
                save_guild_config(guild_id, guild_config)
            except Exception as e:
                print(f"Error updating heartbeat message: {e}")


async def update_lifetime_stats_message():
    try:
        load_lifetime_stats_messages()
        if not LIFETIME_STATS_MESSAGES:
            if DEBUG_LIFETIME_STATS:
                print(f"ℹ️ Lifetime Stats: No messages to update")
            return
        if DEBUG_LIFETIME_STATS:
            print(f"📊 Lifetime Stats: Found {len(LIFETIME_STATS_MESSAGES)} message(s) to update")

        active_guild_ids = {g.id for g in _bot.guilds} if _bot else None
        embed = await asyncio.to_thread(create_lifetime_stats_embed, active_guild_ids)
        messages_to_remove = []

        for message_key, message_info in list(LIFETIME_STATS_MESSAGES.items()):
            try:
                channel_id = message_info["channel_id"]
                message_id = message_info["message_id"]
                guild_id = message_info.get("guild_id")
                guild = _bot.get_guild(int(guild_id)) if _bot and guild_id else None
                if not guild:
                    messages_to_remove.append(message_key)
                    continue
                channel = guild.get_channel(int(channel_id))
                if not channel:
                    messages_to_remove.append(message_key)
                    continue
                try:
                    message = await channel.fetch_message(int(message_id))
                    await message.edit(embed=embed)
                    if DEBUG_LIFETIME_STATS:
                        print(f"  ✅ Successfully updated message")
                except discord.NotFound:
                    messages_to_remove.append(message_key)
                except discord.Forbidden:
                    messages_to_remove.append(message_key)
                except Exception as e:
                    if DEBUG_LIFETIME_STATS:
                        print(f"  ❌ Error editing message: {e}")
                    messages_to_remove.append(message_key)
            except Exception as e:
                if DEBUG_LIFETIME_STATS:
                    print(f"❌ Error processing message {message_key}: {e}")
                messages_to_remove.append(message_key)

        if messages_to_remove:
            for key in messages_to_remove:
                del LIFETIME_STATS_MESSAGES[key]
            save_lifetime_stats_messages()
    except Exception as e:
        if DEBUG_LIFETIME_STATS:
            print(f"❌ Error in update_lifetime_stats_message: {e}")


# ============================================================
# HELPERS
# ============================================================

def split_field_value(value, max_len=1024, field_name="Field"):
    lines = value.split('\n')
    chunks = []
    current_chunk = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1
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


async def notify_admin_of_missing_configs(guild_id, missing_packs, missing_filters):
    try:
        guild = _bot.get_guild(int(guild_id)) if _bot else None
        if not guild or not guild.owner:
            return
        owner = guild.owner
        message_parts = []
        if missing_packs:
            packs_list = ", ".join(sorted(missing_packs))
            message_parts.append(f"**Missing Pack Configs:** {packs_list}")
        if missing_filters:
            filters_list = ", ".join(sorted(missing_filters))
            message_parts.append(f"**Missing Filter Configs:** {filters_list}")
        embed = discord.Embed(
            title="⚠️ Missing Configurations Detected",
            description=f"In **{guild.name}**, the following items have no channel mappings:\n\n" + "\n".join(message_parts),
            color=discord.Color.orange()
        )
        embed.add_field(
            name="How to Fix",
            value="**Packs:** Use `/setpackfilter [pack_name]` to configure\n"
                  "**Filters:** Use `/setfilter [keyword]` to configure\n"
                  "Or re-run `/setup` to auto-configure everything.",
            inline=False
        )
        embed.set_footer(text="These configs are needed to route messages correctly.")
        await owner.send(embed=embed)
        print(f"Sent missing config notification to {owner} ({guild.name})")
    except discord.Forbidden:
        print(f"Could not DM owner of guild {guild_id} (DMs disabled)")
    except Exception as e:
        print(f"Error notifying admin of missing configs: {e}")
