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

# Lade .env Datei
load_dotenv()

# Debug Logging Control
DEBUG_PACK_LOGS = os.getenv("DEBUG_PACK_LOGS", "false").lower() == "true"
DEBUG_LIFETIME_STATS = os.getenv("DEBUG_LIFETIME_STATS", "true").lower() == "true"

# Thread-safe lock for config saves
config_save_lock = threading.Lock()

# Intents und Bot-Initialisierung
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Pfad zur Konfigurationsdatei
CONFIG_FILE = "bot_config.json"
LIFETIME_STATS_FILE = "lifetime_stats_messages.json"

# OWNER_ID und BERLIN_TZ werden später aus Config geladen
OWNER_ID = None
BERLIN_TZ = None

# Funktion zum Laden der Konfiguration
def load_config():
    """Load config from bot_config.json. Automatically extracts any guild data to separate files."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                
                # AUTO-CLEANUP: Extract any guild IDs that shouldn't be here
                guild_ids_found = []
                for key in list(config.keys()):
                    if key not in ["series", "packs"]:
                        try:
                            guild_id_int = int(key)
                            # Valid Discord ID format (18-19 digits)
                            if 10**17 <= guild_id_int <= 10**19:
                                guild_ids_found.append(key)
                        except ValueError:
                            pass
                
                # If guild IDs found, extract them to separate files
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
                    
                    # Save cleaned config
                    save_config(config)
                    print(f"\n✅ bot_config.json cleaned - removed {len(guild_ids_found)} server entries\n")
                
                # Lade Packs und Series aus Config (Fallback auf Standard-Liste in A-Series)
                packs = config.get("packs", [
                    "palkia", "dialga", "arceus", "shining", "mew", "pikachu", "charizard",
                    "mewtwo", "solgaleo", "lunala", "buzzwole", "eevee", "hooh", "lugia",
                    "springs", "deluxe"
                ])
                series = config.get("series", {"A-Series": packs})
                config["series"] = series
                config["packs"] = packs  # Backward compat
                update_packs(config)
                return config
        except json.JSONDecodeError as e:
            print(f"\n⚠️ Error parsing {CONFIG_FILE}: {e}")
            print(f"Corrupted config file detected. Creating backup and initializing new config...\n")
            
            # Backup the corrupted file
            if os.path.exists(CONFIG_FILE):
                corrupted_name = f"{CONFIG_FILE}.corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(CONFIG_FILE, corrupted_name)
                print(f"Corrupted config saved to: {corrupted_name}\n")
    
    # Create default config
    print(f"Creating new default configuration...\n")
    default_series = {"A-Series": [
        "palkia", "dialga", "arceus", "shining", "mew", "pikachu", "charizard",
        "mewtwo", "solgaleo", "lunala", "buzzwole", "eevee", "hooh", "lugia",
        "springs", "deluxe"
    ]}
    default_config = {"series": default_series, "packs": sum(default_series.values(), [])}
    save_config(default_config)
    return default_config

def update_packs(config):
    global PACKS
    PACKS = [p for sublist in config["series"].values() for p in sublist]

# Funktion zum Speichern der Konfiguration (nicht-blockierend)
def save_config(config):
    """Save config to bot_config.json (runs in background thread). Auto-filters out any guild data."""
    import copy
    
    def _save():
        # Use lock to prevent multiple threads from saving simultaneously
        with config_save_lock:
            try:
                # DEEP COPY to prevent race conditions from concurrent modifications
                config_copy = copy.deepcopy(config)
                
                # AUTO-FILTER: Remove any guild IDs before saving (SAFETY NET)
                keys_to_remove = []
                for key in list(config_copy.keys()):
                    if key not in ["series", "packs"]:
                        try:
                            guild_id_int = int(key)
                            # Valid Discord ID format (18-19 digits)
                            if 10**17 <= guild_id_int <= 10**19:
                                keys_to_remove.append(key)
                                print(f"⚠️ [SAFETY] Removed stray guild ID {key} from save_config()")
                        except ValueError:
                            pass
                
                # Remove the identified guild keys
                for key in keys_to_remove:
                    del config_copy[key]
                
                # Write directly to config file
                with open(CONFIG_FILE, "w") as f:
                    json.dump(config_copy, f, indent=4)
                
            except Exception as e:
                print(f"Error saving config: {e}")
    
    # Run in background thread to not block event loop
    threading.Thread(target=_save, daemon=True).start()

# Guild-Config System - Neue Funktionen für Pro-Server Configs
GUILD_CONFIG_DIR = "guild_configs"

def ensure_guild_config_dir():
    """Stelle sicher, dass der guild_configs Ordner existiert."""
    if not os.path.exists(GUILD_CONFIG_DIR):
        os.makedirs(GUILD_CONFIG_DIR)

def get_guild_config_path(guild_id):
    """Gib den Pfad zur Config-Datei eines Servers zurück."""
    return os.path.join(GUILD_CONFIG_DIR, f"guild_{guild_id}.json")

def load_guild_config(guild_id):
    """Lade die Config für einen spezifischen Server mit Auto-Recovery bei Korruption."""
    ensure_guild_config_dir()
    config_path = get_guild_config_path(guild_id)
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"❌ Guild config corrupted for {guild_id}: {e}")
            
            # Versuche Backup-Dateien nacheinander (letzte zuerst)
            backup_candidates = [
                f"{config_path}.backup",  # Haupt-Backup
            ]
            
            # Suche auch nach nummerierten Backups (.backup.1, .backup.2, etc.)
            backup_dir = os.path.dirname(config_path)
            config_filename = os.path.basename(config_path)
            if os.path.exists(backup_dir):
                for filename in sorted(os.listdir(backup_dir), reverse=True):
                    if filename.startswith(config_filename + ".backup"):
                        backup_candidates.append(os.path.join(backup_dir, filename))
            
            # Versuche jeden Backup nacheinander
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
                # Restore from the working backup
                try:
                    with open(config_path, "w") as f:
                        json.dump(restored_config, f, indent=4)
                    
                    # Webhook logging (asynchron - im Hintergrund)
                    asyncio.create_task(log_guild_corruption_to_webhook(
                        guild_id, 
                        f"Config corrupted. Auto-recovered from backup file.",
                        f"Restored from {os.path.basename(restored_from)}"
                    ))
                    
                    return restored_config
                except Exception as write_error:
                    print(f"❌ Could not write restored config: {write_error}")
            
            # Wenn ALLE Backups auch korrupt sind, erstelle leere Config
            empty_config = {"packs": {}, "filters": {}, "channels": {}}
            
            # Rename die korrupte Datei als Backup
            corrupted_name = f"{config_path}.corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                os.rename(config_path, corrupted_name)
                print(f"📦 Saved corrupted config to: {corrupted_name}")
                
                # Webhook logging - CRITICAL: ALL BACKUPS FAILED
                asyncio.create_task(log_guild_corruption_to_webhook(
                    guild_id,
                    f"❌ CRITICAL: Config AND all backup files are corrupted!\nConfig file renamed to:\n`{os.path.basename(corrupted_name)}`\nCreating empty config as fallback.\nPlease check the corrupted files manually!",
                    "Fallback to empty config - ALL BACKUPS CORRUPTED"
                ))
            except Exception as rename_error:
                print(f"⚠️ Could not rename corrupted file: {rename_error}")
                
                # Webhook logging
                asyncio.create_task(log_guild_corruption_to_webhook(
                    guild_id,
                    f"❌ CRITICAL: Config corrupted AND all backups failed!\nCould not rename corrupted file: {str(rename_error)[:500]}",
                    "Using empty config fallback - CRITICAL ERROR"
                ))
            
            return empty_config
    
    # Neue Server bekommen leere Config
    return {"packs": {}, "filters": {}, "channels": {}}

def save_guild_config(guild_id, guild_config):
    """Speichere die Config für einen spezifischen Server (thread-safe, asynchron) mit Backup-Rotation (max 3 Backups)."""
    import copy
    
    def _save():
        with config_save_lock:
            ensure_guild_config_dir()
            config_path = get_guild_config_path(guild_id)
            
            try:
                # Erstelle Backup-Rotation: .backup → .backup.1 → .backup.2 → .backup.3 (max 3 halten)
                if os.path.exists(config_path):
                    try:
                        with open(config_path, "r") as f:
                            current_data = json.load(f)
                        
                        # Rotate existing backups
                        backup_path = f"{config_path}.backup"
                        max_backups = 3
                        
                        # Schiebe alte Backups um eins nach oben
                        for i in range(max_backups - 1, 0, -1):
                            old_backup = f"{config_path}.backup.{i}"
                            new_backup = f"{config_path}.backup.{i + 1}"
                            if os.path.exists(old_backup):
                                try:
                                    os.remove(new_backup) if os.path.exists(new_backup) else None
                                    os.rename(old_backup, new_backup)
                                except Exception:
                                    pass
                        
                        # Hauptbackup zu .backup.1
                        if os.path.exists(backup_path):
                            try:
                                os.rename(backup_path, f"{config_path}.backup.1")
                            except Exception:
                                pass
                        
                        # Speichere aktuelle Config als neues Hauptbackup
                        with open(backup_path, "w") as f:
                            json.dump(current_data, f, indent=4)
                    except Exception as backup_error:
                        print(f"⚠️ Could not create backup rotation for {guild_id}: {backup_error}")
                
                # Speichere die neue Config
                config_copy = copy.deepcopy(guild_config)
                with open(config_path, "w") as f:
                    json.dump(config_copy, f, indent=4)
            except Exception as e:
                print(f"Error saving guild config for {guild_id}: {e}")
    
    threading.Thread(target=_save, daemon=True).start()

def save_guild_config_sync(guild_id, guild_config):
    """Speichere die Config für einen spezifischen Server SYNCHRON (blocking)."""
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
    """Migriere alte bot_config.json mit Guild-Daten in separate Guild-Config-Dateien."""
    if not os.path.exists(CONFIG_FILE):
        return
    
    try:
        with open(CONFIG_FILE, "r") as f:
            old_config = json.load(f)
    except (json.JSONDecodeError, IOError):
        return
    
    # Checke ob es Guild-spezifische Configs in der alten Datei gibt
    guild_configs_data = {}
    
    # Suche nach Guild-IDs in den Keys (z.B. "123456789_setup", "987654321_filters")
    for key in list(old_config.keys()):
        if "_" in key:
            parts = key.split("_", 1)
            if parts[0].isdigit():  # Ist der erste Teil eine Zahl (Guild-ID)?
                guild_id = int(parts[0])
                config_type = parts[1]
                
                if guild_id not in guild_configs_data:
                    guild_configs_data[guild_id] = {"packs": {}, "filters": {}, "channels": {}}
                
                # Sortiere die Daten in die richtige Kategorie
                if config_type.startswith("pack"):
                    guild_configs_data[guild_id]["packs"] = old_config[key]
                elif config_type.startswith("filter"):
                    guild_configs_data[guild_id]["filters"] = old_config[key]
                elif config_type.startswith("channel"):
                    guild_configs_data[guild_id]["channels"] = old_config[key]
    
    # Speichere die migrierten Guild-Configs
    if guild_configs_data:
        print(f"Migriere {len(guild_configs_data)} Guild-Konfigurationen...")
        for guild_id, guild_config in guild_configs_data.items():
            save_guild_config(guild_id, guild_config)
            print(f"  ✓ Guild {guild_id} migriert")
        
        # Entferne die Guild-Daten aus der bot_config.json (behalte nur globale Settings)
        global_only_config = {k: v for k, v in old_config.items() if not ("_" in k and k.split("_")[0].isdigit())}
        save_config(global_only_config)
        print("✓ Migration abgeschlossen - bot_config.json bereinigt")

def extract_and_save_guild_configs(config):
    """Extrahiere Guild-Konfigurationen aus der globalen config und speichere sie als separate Dateien."""
    ensure_guild_config_dir()
    
    guilds_extracted = 0
    guild_ids_to_remove = []
    
    # Iteration durch alle Keys in der Config
    for guild_id_str, guild_config in list(config.items()):
        # Skip globale Keys explizit
        if guild_id_str in ["series", "packs"]:
            continue
        
        # Skip wenn es keine numerische Guild-ID ist
        if not isinstance(guild_id_str, str) or not guild_id_str.isdigit():
            continue
        
        # Extra-Sicherheit: Nur wenn es ein valides Discord Guild-ID Format ist (18-19 Ziffern)
        # und nicht leer ist
        guild_id_int = int(guild_id_str)
        if guild_id_int == 0 or not (10**17 <= guild_id_int <= 10**19):  # Valider Discord ID Range
            print(f"⚠️ Skipped invalid guild ID: {guild_id_str}")
            continue
        
        guild_id = guild_id_int
        
        # Speichere ALLE Guild-Konfigurationen (unabhängig vom Inhalt)
        # Nur wenn es ein Dict ist und nicht leer
        if isinstance(guild_config, dict) and len(guild_config) > 0:
            save_guild_config(guild_id, guild_config)
            guild_ids_to_remove.append(guild_id_str)
            guilds_extracted += 1
    
    # Entferne die extrahierten Guild-Daten aus der bot_config.json
    if guild_ids_to_remove:
        for guild_id_str in guild_ids_to_remove:
            del config[guild_id_str]
        save_config(config)
        print(f"✓ {guilds_extracted} Guild-Konfigurationen extrahiert und aus bot_config.json entfernt")


# Konfiguration initialisieren
migrate_configs()  # Migriere alte Config-Format zu Pro-Server Configs
config = load_config()
extract_and_save_guild_configs(config)  # Extrahiere und speichere Guild-Configs sofort nach dem Laden

# OWNER_ID und BERLIN_TZ aus Config laden
OWNER_ID = config.get("owner_id", 774679828594163802)  # Fallback zu Hardcoded ID wenn nicht in Config
timezone_str = config.get("timezone", "Europe/Berlin")  # Fallback zu Standard-Timezone
BERLIN_TZ = ZoneInfo(timezone_str)  # Erstelle ZoneInfo Objekt aus String
print(f"✅ Owner ID geladen: {OWNER_ID}")
print(f"✅ Timezone geladen: {timezone_str}")

# Final cleanup: Stelle sicher dass bot_config.json NUR noch globale Daten hat
def final_cleanup_config():
    """Final synchrone Cleanup um sicherzustellen dass nur globale Daten bleiben."""
    global config
    
    # Globale Config-Keys die behalten werden sollen
    ALLOWED_GLOBAL_KEYS = ["series", "packs", "error_webhook_url", "permission_warning_webhook_url", "guild_corruption_webhook_url", "owner_id", "timezone"]
    
    keys_to_remove = []
    for key in config.keys():
        # Keep only global keys
        if key in ALLOWED_GLOBAL_KEYS:
            continue
        
        # Nur Guild-IDs (numerische Keys) entfernen - alles andere behalten
        if key.isdigit():
            keys_to_remove.append(key)
    
    if keys_to_remove:
        print(f"\n🧹 Final Cleanup: Removing {len(keys_to_remove)} stray guild IDs from bot_config.json...")
        for key in keys_to_remove:
            print(f"  ❌ Removing stray Guild ID: {key}")
            del config[key]
        
        save_config(config)
        print(f"✅ Final cleanup complete - bot_config.json is clean!\n")

# Führe final cleanup aus
final_cleanup_config()

# === ERROR LOGGING TO WEBHOOK ===
async def log_error_to_webhook(error_message: str, guild_id: str = None, command_name: str = None):
    """Sende Fehler an Discord Webhook als Embed."""
    try:
        webhook_url = config.get("error_webhook_url")
        if not webhook_url:
            print(f"⚠️ Error Webhook URL not configured in bot_config.json")
            return
        
        # Kürze lange Nachrichten
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

# === PERMISSION WARNING LOGGING TO SEPARATE WEBHOOK ===
async def log_permission_warning_to_webhook(error_message: str, guild_id: str = None, command_name: str = None):
    """Sende Permission-Warnungen an separaten Discord Webhook als Embed."""
    try:
        webhook_url = config.get("permission_warning_webhook_url")
        if not webhook_url:
            # Fallback to regular error webhook if permission webhook not configured
            await log_error_to_webhook(error_message, guild_id, command_name)
            return
        
        # Kürze lange Nachrichten
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

# === GUILD CONFIG CORRUPTION - DM TO OWNER WITH RESET BUTTON ===
class CorruptionRecoveryView(discord.ui.View):
    """View mit Button zum Neu-Initialisieren der Guild Config."""
    def __init__(self, guild_id: str, timeout: int = 3600):
        super().__init__(timeout=timeout)
        self.guild_id = guild_id
    
    @discord.ui.button(label="🔧 Reinitialize Config", style=discord.ButtonStyle.danger)
    async def reset_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reset der Guild Config mit essentiellen Channels (Source + Heartbeat)."""
        await interaction.response.defer(thinking=True)
        
        try:
            guild = bot.get_guild(int(self.guild_id))
            if not guild:
                await interaction.followup.send("❌ Server not found!", ephemeral=True)
                return
            
            # Sammle NUR essentiellen Channels
            source_channel_ids = []
            heartbeat_channel_id = None
            
            # Suche nach Source Channels (von denen der Bot Messages liest)
            for channel in guild.text_channels:
                if not channel.permissions_for(guild.me).send_messages:
                    continue
                # Heuristic: Source Channels sind oft "source" oder "feed" im Namen
                channel_name = channel.name.lower()
                if "source" in channel_name or "feed" in channel_name:
                    source_channel_ids.append(channel.id)
            
            # Suche nach Heartbeat Channel
            for channel in guild.text_channels:
                if not channel.permissions_for(guild.me).send_messages:
                    continue
                # Heartbeat Channel ist oft "heartbeat", "status", oder "bot-log" im Namen
                channel_name = channel.name.lower()
                if "heartbeat" in channel_name or "status" in channel_name or "bot-log" in channel_name:
                    heartbeat_channel_id = channel.id
                    break
            
            # Erstelle neue Config mit essentiellen Channels
            new_config = {
                "packs": {},
                "filters": {},
                "channels": {},
                "default_source_channel_ids": source_channel_ids,
                "heartbeat_target_channel_id": heartbeat_channel_id
            }
            
            # Speichere die neue Config
            save_guild_config(self.guild_id, new_config)
            
            # Bestätigungs-Nachricht
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
            confirmation_embed.add_field(
                name="Server ID",
                value=f"`{self.guild_id}`",
                inline=False
            )
            
            await interaction.followup.send(embed=confirmation_embed, ephemeral=True)
            print(f"✅ Guild {self.guild_id} Config wurde neu initialisiert - Source: {len(source_channel_ids)}, Heartbeat: {heartbeat_channel_id}")
            
            # Benachrichtige Webhook über den Button-Click und Config-Reset
            asyncio.create_task(log_config_reset_to_webhook(
                guild_id=self.guild_id,
                guild_name=guild.name,
                owner=interaction.user,
                channels_count=len(source_channel_ids) + (1 if heartbeat_channel_id else 0)
            ))
            
        except Exception as e:
            print(f"❌ Error resetting guild config: {e}")
            await interaction.followup.send(
                f"❌ Error resetting config: {str(e)[:100]}",
                ephemeral=True
            )

async def notify_guild_owner_corruption(guild_id: str, error_message: str, recovery_action: str = None):
    """Sende DM an Guild Owner mit Button zum Neu-Initialisieren der Config."""
    try:
        guild = bot.get_guild(int(guild_id))
        if not guild:
            print(f"⚠️ Guild {guild_id} not found for corruption notification")
            return
        
        owner = guild.owner
        if not owner:
            print(f"⚠️ Guild {guild_id} has no owner")
            return
        
        # Erstelle Embed für die DM
        embed = discord.Embed(
            title="🔴 Guild Config Corruption Detected",
            description=f"The configuration for your server **{guild.name}** has been automatically recovered.",
            color=discord.Color.dark_red(),
            timestamp=datetime.now(BERLIN_TZ)
        )
        
        embed.add_field(
            name="What happened?",
            value=f"A file corruption was detected and has been automatically recovered.",
            inline=False
        )
        
        if error_message:
            error_short = error_message[:200] + "..." if len(error_message) > 200 else error_message
            embed.add_field(
                name="Error Message",
                value=f"`{error_short}`",
                inline=False
            )
        
        if recovery_action:
            embed.add_field(
                name="Recovery Action",
                value=f"`{recovery_action}`",
                inline=False
            )
        
        embed.add_field(
            name="Server",
            value=f"{guild.name} (ID: `{guild_id}`)",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Next Steps",
            value="You can reinitialize the config - existing channels will be automatically added.",
            inline=False
        )
        
        # Sende DM mit Button
        view = CorruptionRecoveryView(guild_id)
        try:
            await owner.send(embed=embed, view=view)
            print(f"✅ DM sent to owner of guild {guild_id}")
        except discord.Forbidden:
            print(f"⚠️ Could not send DM to owner of guild {guild_id} (DMs disabled)")
        
    except Exception as e:
        print(f"❌ Error notifying guild owner of corruption: {e}")

async def log_config_reset_to_webhook(guild_id: str, guild_name: str, owner: discord.User, channels_count: int):
    """Sende Webhook-Benachrichtigung wenn Guild Owner Config neu initialisiert hat."""
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
        
        embed.add_field(
            name="Guild",
            value=f"{guild_name} (ID: `{guild_id}`)",
            inline=False
        )
        
        embed.add_field(
            name="Action Performed By",
            value=f"{owner.mention} (`{owner.id}`)",
            inline=False
        )
        
        embed.add_field(
            name="Channels Detected & Added",
            value=f"`{channels_count}` text channel(s)",
            inline=False
        )
        
        embed.add_field(
            name="Timestamp",
            value=f"<t:{int(time.time())}:F>",
            inline=False
        )
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json={"embeds": [embed.to_dict()]}) as resp:
                if resp.status not in [200, 204]:
                    print(f"⚠️ Failed to send config reset notification to webhook: {resp.status}")
                else:
                    print(f"✅ Webhook notification sent for guild {guild_id} config reset")
    except Exception as e:
        print(f"❌ Error logging config reset to webhook: {e}")

async def log_guild_corruption_to_webhook(guild_id: str, error_message: str, recovery_action: str = None):
    """Sende Guild Config Korruptions-Warnungen an Discord Webhook als Embed. Sende DM nur bei CRITICAL."""
    try:
        webhook_url = config.get("guild_corruption_webhook_url")
        if not webhook_url:
            print(f"⚠️ Guild Corruption Webhook URL not configured in bot_config.json")
        else:
            # Kürze lange Nachrichten
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
    
    # Benachrichtige Guild Owner per DM NUR bei CRITICAL (ALL BACKUPS CORRUPTED)
    if recovery_action and "ALL BACKUPS CORRUPTED" in recovery_action:
        await notify_guild_owner_corruption(guild_id, error_message, recovery_action)

# AUTO-CLEANUP Background Task - läuft kontinuierlich und überprüft bot_config.json
async def auto_cleanup_task():
    """Background task that runs every 60 seconds and auto-cleans bot_config.json if guild IDs appear."""
    await bot.wait_until_ready()
    print("✅ Auto-Cleanup Task started - monitoring bot_config.json for stray guild IDs...\n")
    
    while not bot.is_closed():
        try:
            await asyncio.sleep(60)  # Check every 60 seconds
            
            if not os.path.exists(CONFIG_FILE):
                continue
            
            try:
                with open(CONFIG_FILE, "r") as f:
                    current_config = json.load(f)
            except (json.JSONDecodeError, IOError):
                continue
            
            # Check for any guild IDs that shouldn't be here
            guild_ids_found = []
            for key in list(current_config.keys()):
                if key not in ["series", "packs"]:
                    try:
                        guild_id_int = int(key)
                        # Valid Discord ID format (18-19 digits)
                        if 10**17 <= guild_id_int <= 10**19:
                            guild_ids_found.append(key)
                    except ValueError:
                        pass
            
            # If guild IDs found, auto-extract them
            if guild_ids_found:
                print(f"\n⚠️ [AUTO-CLEANUP] Found {len(guild_ids_found)} server IDs in bot_config.json!")
                print("🔄 Automatically extracting to separate guild config files...\n")
                
                for guild_id_str in guild_ids_found:
                    try:
                        guild_config = current_config[guild_id_str]
                        if isinstance(guild_config, dict):
                            save_guild_config_sync(guild_id_str, guild_config)
                            print(f"  ✅ [AUTO-CLEANUP] Extracted guild {guild_id_str} to guild_configs/guild_{guild_id_str}.json")
                        del current_config[guild_id_str]
                    except Exception as e:
                        print(f"  ❌ [AUTO-CLEANUP] Error extracting guild {guild_id_str}: {e}")
                
                # Save cleaned config
                save_config(current_config)
                print(f"\n✅ [AUTO-CLEANUP] bot_config.json cleaned - removed {len(guild_ids_found)} server entries\n")
        
        except Exception as e:
            print(f"Error in auto_cleanup_task: {e}")

# Global dictionary to store lifetime stats messages for auto-update
LIFETIME_STATS_MESSAGES = {}

# Flag to track if lifetime stats task has been started
LIFETIME_STATS_TASK_STARTED = False
LIFETIME_STATS_TASK = None

# Funktionen zum Speichern/Laden von Lifetime Stats Messages
def save_lifetime_stats_messages():
    """Speichert alle Lifetime Stats Messages in eine JSON-Datei."""
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
    """Lädt Lifetime Stats Messages aus JSON-Datei."""
    global LIFETIME_STATS_MESSAGES
    try:
        LIFETIME_STATS_MESSAGES.clear()  # Clear existing entries first
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
                for key, info in LIFETIME_STATS_MESSAGES.items():
                    print(f"   - Guild {info['guild_id']} | Channel {info['channel_id']} | Message {info['message_id']}")
        else:
            if DEBUG_LIFETIME_STATS:
                print(f"ℹ️ No lifetime stats messages file found ({LIFETIME_STATS_FILE})")
    except Exception as e:
        print(f"❌ Error loading lifetime stats messages: {e}")
        import traceback
        traceback.print_exc()

# AUTO-UPDATE Background Task for Lifetime Stats - MUST BE BEFORE on_ready()!
async def lifetime_stats_update_task():
    """Background task that updates lifetime stats embeds every minute."""
    try:
        # Wait a bit for bot to be ready
        await asyncio.sleep(2)
        
        print("✅ Lifetime Stats Update Task started - updating every 60 seconds\n")
        load_lifetime_stats_messages()
        
        cycle_count = 0
        while not bot.is_closed():
            try:
                cycle_count += 1
                if DEBUG_LIFETIME_STATS:
                    print(f"[Lifetime Stats #{cycle_count}] Update at {datetime.now(BERLIN_TZ).strftime('%H:%M:%S')} - Tracked: {len(LIFETIME_STATS_MESSAGES)} message(s)")
                
                await update_lifetime_stats_message()
                await asyncio.sleep(60)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Error in lifetime_stats_update_task cycle: {e}")
                await asyncio.sleep(10)
    except Exception as e:
        print(f"❌ Critical error in lifetime_stats_update_task: {e}")

# Starte Auto-Cleanup Task (merged into the actual on_ready at line 4294)

# Dynamische PACKS-Liste (aus Config geladen)
PACKS = config["packs"]

# Funktion für dynamische Pack-Choices (jetzt für Autocomplete)
def get_pack_choices():
    return [app_commands.Choice(name=pack.title(), value=pack) for pack in PACKS[:25]]  # Max 25, wie Discord es erlaubt

# Neue Autocomplete-Funktion für dynamische Packs
async def autocomplete_packs(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    choices = get_pack_choices()
    if not current:
        return choices
    # Filtere nach aktueller Eingabe (case-insensitive)
    filtered = [choice for choice in choices if current.lower() in choice.value.lower()]
    return filtered[:25]  # Max 25

# Neue Autocomplete-Funktion für Series
async def autocomplete_series(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    series_names = list(config.get("series", {}).keys())
    if not current:
        return [app_commands.Choice(name=s, value=s) for s in series_names[:25]]
    # Filtere nach aktueller Eingabe (case-insensitive)
    filtered = [app_commands.Choice(name=s, value=s) for s in series_names if current.lower() in s.lower()]
    return filtered[:25]  # Max 25

# Check-Funktion für Owner-only Commands
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

# === NEW: Mapping of old prefix-based names to clean short names ===
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
    embed.set_thumbnail(url="https://i.imgur.com/pxqjVbO.png")
    
    # God Packs section (unchanged)
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

# Funktion zum Erstellen des Detailed Stats-Embeds (ohne Packs)
def create_detailed_stats_embed(guild_config):
    filter_stats = guild_config.get("filter_stats", {})
    
    embed = discord.Embed(
        title="Detailed Filter Statistics",
        description="Here are the number of embeds sent for each filter in this server:",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url="https://i.imgur.com/pxqjVbO.png")  # Ersetze durch deine Bild-URL
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

# Funktion zum Erstellen des Pack Stats-Embeds (jetzt gruppiert nach Series)
def create_pack_stats_embed(guild_config):
    filter_stats = guild_config.get("filter_stats", {})
    global_config = config  # Globale Series aus config
    series = global_config.get("series", {})
    
    embed = discord.Embed(
        title="Pack Statistics",
        description="Here are the number of embeds sent for each pack in this server:",
        color=discord.Color.teal()
    )

    # Thumbnail hinzufügen (konsistent mit anderen Embeds)
    embed.set_thumbnail(url="https://i.imgur.com/pxqjVbO.png")
    
    # Gruppiere nach Series
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

# Funktion zum Erstellen des Heartbeat-Embeds
def create_heartbeat_embed(guild_config):
    data = guild_config.get("heartbeat_data", {})
    if not data:
        return discord.Embed(
            title="Heartbeat",
            description="Waiting for first heartbeat...",
            color=discord.Color.orange()
        )

    # Prüfe auf Offline-Status basierend auf last_update (erwarte ISO-String mit TZ)
    if "last_update" not in data or not data["last_update"]:
        return discord.Embed(
            title="Heartbeat",
            description="Bot is offline - No heartbeat found.",
            color=discord.Color.red()
        )

    try:
        last_update = datetime.fromisoformat(data["last_update"])
        now = datetime.now(BERLIN_TZ)
        if now - last_update > timedelta(minutes=60):
            return discord.Embed(
                title="Heartbeat",
                description="Bot is offline - No heartbeat found.",
                color=discord.Color.red()
            )
    except ValueError:
        # Fallback bei ungültigem Timestamp
        return discord.Embed(
            title="Heartbeat",
            description="Bot is offline - No heartbeat found.",
            color=discord.Color.red()
        )

    # Normale Online-Stats (grün)
    embed = discord.Embed(title="Heartbeat", color=discord.Color.green())
    
    # Thumbnail hinzufügen (wie in create_stats_embed)
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

    # Footer mit letztem Update hinzufügen (in Berlin-Zeit)
    last_update_berlin = last_update.astimezone(BERLIN_TZ)
    formatted_time = last_update_berlin.strftime("%d.%m.%Y %H:%M")
    embed.set_footer(text=f"Last updated: {formatted_time}")

    return embed

# Funktion zum Updaten der Stats-Nachricht
async def update_stats_message(guild_id):
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

# Funktion zum Updaten der Detailed Stats-Nachricht
async def update_detailed_stats_message(guild_id):
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

# Funktion zum Updaten der Pack Stats-Nachricht
async def update_pack_stats_message(guild_id):
    guild_config = load_guild_config(guild_id)
    pack_stats_channel_id = guild_config.get("pack_stats_channel_id")
    pack_stats_message_id = guild_config.get("pack_stats_message_id")
    if pack_stats_channel_id and pack_stats_message_id:
        channel = bot.get_channel(pack_stats_channel_id)
        if channel:
            try:
                message = await channel.fetch_message(pack_stats_message_id)
                embed = create_pack_stats_embed(guild_config)
                await message.edit(embed=embed)
            except discord.NotFound:
                if "pack_stats_channel_id" in guild_config:
                    del guild_config["pack_stats_channel_id"]
                if "pack_stats_message_id" in guild_config:
                    del guild_config["pack_stats_message_id"]
                save_guild_config(guild_id, guild_config)
            except Exception as e:
                print(f"Error updating pack stats message: {e}")

# Funktion zum Updaten der Heartbeat-Nachricht
async def update_heartbeat_message(guild_id):
    guild_config = load_guild_config(guild_id)
    heartbeat_channel_id = guild_config.get("heartbeat_target_channel_id")
    heartbeat_message_id = guild_config.get("heartbeat_message_id")
    if heartbeat_channel_id and heartbeat_message_id:
        channel = bot.get_channel(heartbeat_channel_id)
        if channel:
            try:
                message = await channel.fetch_message(heartbeat_message_id)
                embed = create_heartbeat_embed(guild_config)
                await message.edit(embed=embed)
            except discord.NotFound:
                if "heartbeat_target_channel_id" in guild_config:
                    del guild_config["heartbeat_target_channel_id"]
                if "heartbeat_message_id" in guild_config:
                    del guild_config["heartbeat_message_id"]
                save_guild_config(guild_id, guild_config)
            except Exception as e:
                print(f"Error updating heartbeat message: {e}")

# Funktion zum Updaten der Lifetime Stats-Nachricht
async def update_lifetime_stats_message():
    """Updates all lifetime stats messages across all servers."""
    try:
        # Reload from file to get latest
        load_lifetime_stats_messages()
        
        if not LIFETIME_STATS_MESSAGES:
            if DEBUG_LIFETIME_STATS:
                print(f"ℹ️ Lifetime Stats: No messages to update")
            return
        
        if DEBUG_LIFETIME_STATS:
            print(f"📊 Lifetime Stats: Found {len(LIFETIME_STATS_MESSAGES)} message(s) to update")
        
        embed = await asyncio.to_thread(create_lifetime_stats_embed)
        messages_to_remove = []
        
        for message_key, message_info in list(LIFETIME_STATS_MESSAGES.items()):
            try:
                channel_id = message_info["channel_id"]
                message_id = message_info["message_id"]
                guild_id = message_info.get("guild_id")
                
                if DEBUG_LIFETIME_STATS:
                    print(f"🔄 Lifetime Stats: Updating message {message_id} in channel {channel_id} (Guild: {guild_id})")
                
                # Get the guild first
                guild = bot.get_guild(int(guild_id)) if guild_id else None
                if not guild:
                    if DEBUG_LIFETIME_STATS:
                        print(f"  ❌ Guild {guild_id} not found in cache")
                    messages_to_remove.append(message_key)
                    continue
                
                # Get channel from guild
                channel = guild.get_channel(int(channel_id))
                if not channel:
                    if DEBUG_LIFETIME_STATS:
                        print(f"  ❌ Channel {channel_id} not found in guild {guild.name}")
                    messages_to_remove.append(message_key)
                    continue
                
                if DEBUG_LIFETIME_STATS:
                    print(f"  ✓ Found channel: {guild.name} #{channel.name}")
                
                # Fetch and edit message
                try:
                    message = await channel.fetch_message(int(message_id))
                    await message.edit(embed=embed)
                    if DEBUG_LIFETIME_STATS:
                        print(f"  ✅ Successfully updated message")
                except discord.NotFound:
                    if DEBUG_LIFETIME_STATS:
                        print(f"  ❌ Message {message_id} not found")
                    messages_to_remove.append(message_key)
                except discord.Forbidden:
                    if DEBUG_LIFETIME_STATS:
                        print(f"  ❌ No permission to edit message")
                    messages_to_remove.append(message_key)
                except Exception as e:
                    if DEBUG_LIFETIME_STATS:
                        print(f"  ❌ Error editing message: {e}")
                    messages_to_remove.append(message_key)
            
            except Exception as e:
                if DEBUG_LIFETIME_STATS:
                    print(f"❌ Error processing message {message_key}: {e}")
                    import traceback
                    traceback.print_exc()
                messages_to_remove.append(message_key)
        
        # Remove messages that couldn't be updated
        if messages_to_remove:
            if DEBUG_LIFETIME_STATS:
                print(f"\n🗑️ Removing {len(messages_to_remove)} failed message(s)...")
            for key in messages_to_remove:
                del LIFETIME_STATS_MESSAGES[key]
            save_lifetime_stats_messages()
    
    except Exception as e:
        if DEBUG_LIFETIME_STATS:
            print(f"❌ Error in update_lifetime_stats_message: {e}")
            import traceback
            traceback.print_exc()

# View für God Pack Validierung
class GodPackValidationView(discord.ui.View):
    def __init__(self, embed: discord.Embed, original_message: discord.Message = None, guild_id: str = None):
        super().__init__(timeout=None)
        self.embed = embed
        self.original_message = original_message
        self.disabled = False
        self.guild_id = guild_id
        self.allowed_role_id = load_guild_config(guild_id).get("validator_role_id")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not hasattr(member, "roles"):
            await interaction.followup.send("⛔ Error during role check.", ephemeral=True)
            return False

        if not self.allowed_role_id:
            await interaction.followup.send("⛔ No validator role configured for this server. Please set one using /setvalidatorrole.", ephemeral=True)
            return False

        if not any(role.id == self.allowed_role_id for role in member.roles):
            await interaction.followup.send("⛔ You do not have permission for this.", ephemeral=True)
            return False

        if self.disabled:
            await interaction.followup.send("❌ This action has already been completed.", ephemeral=True)
            return False

        return True

    async def disable_all_buttons(self, interaction: discord.Interaction):
        self.disabled = True
        for child in self.children:
            child.disabled = True
        await self.original_message.edit(embed=self.embed, view=self)

    @discord.ui.button(label="✅ Valid", style=discord.ButtonStyle.success, custom_id="godpack_valid")
    async def valid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.embed.color = discord.Color.green()
        await self.disable_all_buttons(interaction)
        await interaction.followup.send("✅ Marked as valid.", ephemeral=True)
        guild_config = load_guild_config(self.guild_id)
        if 'stats' not in guild_config:
            guild_config['stats'] = {
                'godpacks': {'total': 0, 'valid': 0, 'invalid': 0},
                'general': {'total': 0, 'valid': 0, 'invalid': 0}
            }
        guild_config['stats']['godpacks']['valid'] += 1
        save_guild_config(self.guild_id, guild_config)
        await update_stats_message(self.guild_id)
        if "validation_messages" in guild_config and str(self.original_message.id) in guild_config["validation_messages"]:
            del guild_config["validation_messages"][str(self.original_message.id)]
            save_guild_config(self.guild_id, guild_config)

    @discord.ui.button(label="❌ Invalid", style=discord.ButtonStyle.danger, custom_id="godpack_invalid")
    async def invalid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.embed.color = discord.Color.red()
        await self.disable_all_buttons(interaction)
        await interaction.followup.send("❌ Marked as invalid.", ephemeral=True)
        guild_config = load_guild_config(self.guild_id)
        if 'stats' not in guild_config:
            guild_config['stats'] = {
                'godpacks': {'total': 0, 'valid': 0, 'invalid': 0},
                'general': {'total': 0, 'valid': 0, 'invalid': 0}
            }
        guild_config['stats']['godpacks']['invalid'] += 1
        save_guild_config(self.guild_id, guild_config)
        await update_stats_message(self.guild_id)
        if "validation_messages" in guild_config and str(self.original_message.id) in guild_config["validation_messages"]:
            del guild_config["validation_messages"][str(self.original_message.id)]
            save_guild_config(self.guild_id, guild_config)

# Modal for Traded Card Details
class TradedModal(discord.ui.Modal, title="Mark as Traded - Enter Card Details"):
    card_input = discord.ui.TextInput(
        label="Traded Card",
        style=discord.TextStyle.short,
        placeholder="e.g., Pikachu VMAX",
        required=True,
        max_length=100
    )

    def __init__(self):
        super().__init__()
        self.original_message = None
        self.guild_id = None
        self.view = None

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Update the embed with traded card details
        embed = self.original_message.embeds[0]  # Assume first embed
        embed.add_field(
            name="✅ Traded Card",
            value=self.card_input.value,
            inline=False
        )
        embed.color = discord.Color.green()

        # Disable the view
        self.view.disabled = True
        for child in self.view.children:
            child.disabled = True

        # Edit the original message
        await self.original_message.edit(embed=embed, view=self.view)

        # Increment stats
        guild_config = load_guild_config(self.guild_id)
        if 'stats' not in guild_config:
            guild_config['stats'] = {
                'godpacks': {'total': 0, 'valid': 0, 'invalid': 0},
                'general': {'total': 0, 'valid': 0, 'invalid': 0}
            }
        guild_config['stats']['general']['valid'] += 1
        save_guild_config(self.guild_id, guild_config)
        await update_stats_message(self.guild_id)

        # Remove from validation messages
        if "validation_messages" in guild_config and str(self.original_message.id) in guild_config["validation_messages"]:
            del guild_config["validation_messages"][str(self.original_message.id)]
            save_guild_config(self.guild_id, guild_config)

        # Ephemeral confirmation
        await interaction.followup.send("✅ Marked as traded with card details added to embed.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(f"Traded modal error: {error}")
        await interaction.followup.send("An error occurred during traded submission.", ephemeral=True)

# View für Traded Button (für alle Save 4 Trade)
class TradedView(discord.ui.View):
    def __init__(self, embed: discord.Embed, original_message: discord.Message = None, guild_id: str = None):
        super().__init__(timeout=None)
        self.embed = embed
        self.original_message = original_message
        self.disabled = False
        self.guild_id = guild_id
        self.allowed_role_id = load_guild_config(guild_id).get("validator_role_id")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not hasattr(member, "roles"):
            await interaction.followup.send("⛔ Error during role check.", ephemeral=True)
            return False

        if not self.allowed_role_id:
            await interaction.followup.send("⛔ No validator role configured for this server. Please set one using /setvalidatorrole.", ephemeral=True)
            return False

        if not any(role.id == self.allowed_role_id for role in member.roles):
            await interaction.followup.send("⛔ You do not have permission for this.", ephemeral=True)
            return False

        if self.disabled:
            await interaction.followup.send("❌ This action has already been completed.", ephemeral=True)
            return False

        return True

    async def disable_all_buttons(self, interaction: discord.Interaction):
        self.disabled = True
        for child in self.children:
            child.disabled = True
        await self.original_message.edit(embed=self.embed, view=self)

    @discord.ui.button(label="✅ Traded", style=discord.ButtonStyle.success, custom_id="traded")
    async def traded_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Create and configure modal
        modal = TradedModal()
        modal.original_message = self.original_message
        modal.guild_id = self.guild_id
        modal.view = self

        # Show the modal
        await interaction.response.send_modal(modal)

# Vordefinierte Filter-Optionen für Slash-Commands
FILTER_CHOICES = [app_commands.Choice(name=keyword.title(), value=keyword) for keyword in CUSTOM_EMBED_TEXT.keys()]

# Clear Filters Choices
CLEAR_FILTER_CHOICES = [
    app_commands.Choice(name="Normal Filters", value="normal"),
    app_commands.Choice(name="Pack Filters", value="pack"),
    app_commands.Choice(name="All Filters", value="all")
]

# Helper function to split long field values into multiple fields (without split counters)
def split_field_value(value, max_len=1024, field_name="Field"):
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
    # Return without the " (1/2)" suffix—use plain field_name for all chunks
    return [(field_name, chunk) for chunk in chunks]

# Updated /setup command (now ensures pack channels are created in mode views, no empties)
@tree.command(name="setup", description="Automated setup for bot channels, categories, and configurations (Admin only)")
async def setup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    # KORREKT: Prüfe Berechtigungen über den Member im Guild
    member = interaction.guild.get_member(interaction.user.id)
    if member is None:
        embed = discord.Embed(
            title="Error",
            description="Unable to fetch your member information. Please try again.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    if not member.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error",
            description="You need administrator permissions to use this command.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    guild = interaction.guild
    guild_id = str(guild.id)

    # Embed explaining permissions (unchanged)
    embed = discord.Embed(
        title="🚀 Bot Setup Wizard",
        description=(
            "This will create categories and channels for your TCGP server:\n"
            "**Categories & Channels:**\n"
            "• **Save 4 Trade** (individual channels for each filter: #one-star, etc.)\n"
            "• **God Packs** (#god-pack, #invalid-god-pack)\n"
            "• **Detection** (#crown, #immersive)\n"
            "• **A-Series** / **B-Series** (all pack channels created based on your mode choice—no empties!)\n\n"
            "**Required Bot Permissions:** Manage Channels, Manage Roles\n\n"
            "Click **✅ Agree** to start. This is irreversible—backup your server if needed!"
        ),
        color=discord.Color.orange()
    )
    embed.set_thumbnail(url="https://i.imgur.com/T0KX069.png")

    # View with Agree button (updated to create keyword channels, packs after mode)
    class SetupView(discord.ui.View):
        def __init__(self, original_user):
            super().__init__(timeout=300)
            self.original_user = original_user

        @discord.ui.button(label="✅ Agree & Setup", style=discord.ButtonStyle.success, emoji="✅")
        async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.original_user:
                await interaction.followup.send("Only the command issuer can proceed.", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            try:
                # Initialize guild config
                guild_config = load_guild_config(guild_id)

                # Ensure B-Series exists if not present (unchanged)
                if "B-Series" not in config["series"]:
                    config["series"]["B-Series"] = []
                    update_packs(config)
                    config["packs"] = PACKS
                    save_config(config)

                # Define category_configs (unchanged)
                category_configs = {
                    "Save 4 Trade": {
                        "keywords": ["one star", "three diamond", "four diamond ex", "gimmighoul", "shiny", "rainbow", "full art", "trainer"],
                        "channel_prefix": "save-4-trade-"
                    },
                    "God Packs": {
                        "keywords": ["god pack", "invalid god pack"],
                        "channel_prefix": "god-packs-"
                    },
                    "Detection": {
                        "keywords": ["crown", "immersive"],
                        "channel_prefix": "detection-"
                    },
                    "A-Series": {
                        "series": "A-Series",
                        "channel_name": "a-series"
                    },
                    "B-Series": {
                        "series": "B-Series",
                        "channel_name": "b-series"
                    }
                }

                # Create categories first
                created_channels = {}
                for cat_name, cfg in category_configs.items():
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                    }
                    category = discord.utils.get(guild.categories, name=cat_name)
                    if not category:
                        category = await guild.create_category(cat_name, overwrites=overwrites)
                    created_channels[cat_name] = category

                # Create individual channels for keyword-based categories (use short names)
                keyword_channel_map = {}
                created_keyword_channels = 0
                for cat_name, cfg in category_configs.items():
                    if "keywords" in cfg:
                        category = created_channels[cat_name]
                        for keyword in cfg["keywords"]:
                            clean_name = keyword.lower().replace(" ", "-").replace("invalid god pack", "invalid-god-pack")
                            old_channel_name = f"{cfg['channel_prefix']}{clean_name}"
                            channel_name = OLD_TO_NEW_CHANNEL_NAMES.get(old_channel_name, clean_name)
                            existing_channel = discord.utils.get(category.text_channels, name=channel_name)
                            if not existing_channel:
                                overwrites = {
                                    guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                                }
                                existing_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                                print(f"Created keyword channel '{channel_name}' in '{cat_name}'")
                                created_keyword_channels += 1
                            # Check if old name exists and rename
                            old_channel = discord.utils.get(category.text_channels, name=old_channel_name)
                            if old_channel:
                                await old_channel.edit(name=channel_name)
                                print(f"Renamed '{old_channel_name}' to '{channel_name}' in '{cat_name}'")
                            keyword_channel_map[keyword.lower()] = {
                                "channel_id": existing_channel.id,
                                "source_channel_ids": []
                            }

                # Save keyword_channel_map
                if keyword_channel_map:
                    guild_config["keyword_channel_map"] = keyword_channel_map
                    save_guild_config(guild_id, guild_config)

                # UPDATED: Pre-create default pack channels (series mode) to avoid empties; mode will override
                created_pack_channels = 0
                for cat_name, cfg in category_configs.items():
                    if "series" in cfg:
                        category = created_channels[cat_name]
                        series_name = cfg["series"]
                        global_series_packs = config.get("series", {}).get(series_name, [])
                        if global_series_packs:
                            # Default to series mode channel
                            channel_name = f"{series_name.lower().replace(' ', '-')}-packs"
                            existing_channel = discord.utils.get(category.text_channels, name=channel_name)
                            if not existing_channel:
                                overwrites = {
                                    guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                                }
                                existing_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                                print(f"Pre-created default pack channel '{channel_name}' in '{cat_name}'")
                                created_pack_channels += 1
                            # Temp map for defaults
                            if "pack_channel_map" not in guild_config:
                                guild_config["pack_channel_map"] = {}
                            for pack in global_series_packs:
                                guild_config["pack_channel_map"][pack.lower()] = {
                                    "channel_id": existing_channel.id,
                                    "source_channel_ids": []
                                }

                save_guild_config(guild_id, guild_config)

                # Now send Mode Choice View (updated embed to note pre-creation)
                mode_embed = discord.Embed(
                    title="✅ Keyword Channels Created! – Step 1: Choose Pack Channel Mode",
                    description=f"Created {created_keyword_channels} filter channels + {created_pack_channels} default pack channels.\n\n"
                                "Select mode to finalize/override pack channels (no empties left):\n\n"
                                "**One Channel per Series:** Uses the pre-created #a-series-packs, etc.\n"
                                "**One Channel per Pack:** Creates individual #palkia-pack, etc. (overrides defaults).",
                    color=discord.Color.orange()
                )
                mode_view = ModeView(self.original_user, guild_id, created_channels)
                await interaction.followup.send(embed=mode_embed, view=mode_view)

                # Initial response (updated)
                setup_embed = discord.Embed(
                    title="✅ Setup In Progress!",
                    description=f"Categories & {created_keyword_channels} filter channels created. {created_pack_channels} default pack channels ready. Finalizing packs next.",
                    color=discord.Color.green()
                )
                await interaction.edit_original_response(embed=setup_embed, view=None)

            except discord.Forbidden:
                error_msg = "Bot lacks 'Manage Channels' permission. Grant it and try again."
                error_embed = discord.Embed(
                    title="❌ Permission Error",
                    description=error_msg,
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                await log_permission_warning_to_webhook(error_msg, guild_id=str(guild.id), command_name="setup")
            except Exception as e:
                print(f"Setup error: {e}")
                error_msg = f"An error occurred: {str(e)}"
                error_embed = discord.Embed(
                    title="❌ Setup Failed",
                    description=error_msg,
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                await log_error_to_webhook(error_msg, guild_id=str(guild.id), command_name="setup")

    view = SetupView(interaction.user)
    await interaction.followup.send(embed=embed, view=view)

# Reset/Set Source Channels Command
@tree.command(name="resetsources", description="Set or reset source channels (Admin only)")
async def resetsources(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    # Check admin permissions
    member = interaction.guild.get_member(interaction.user.id)
    if member is None or not member.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error",
            description="You need administrator permissions to use this command.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)
    guild_config = load_guild_config(guild_id)
    
    # Check if sources are set and show options
    has_sources = "default_source_channel_ids" in guild_config and guild_config["default_source_channel_ids"]
    
    # Create view with buttons
    class SourceOptionsView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
        
        @discord.ui.button(label="Set New Sources", style=discord.ButtonStyle.primary)
        async def set_sources(self, interaction: discord.Interaction, button: discord.ui.Button):
            modal = SourceModal()
            modal.guild_id = guild_id
            modal.original_user = interaction.user
            await interaction.response.send_modal(modal)
        
        @discord.ui.button(label="Reset to All Channels", style=discord.ButtonStyle.danger)
        async def reset_sources(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=True)
            
            guild_config = load_guild_config(guild_id)
            old_sources = guild_config.get("default_source_channel_ids", [])
            guild_config["default_source_channel_ids"] = []
            
            # Also reset in all filter maps
            if "keyword_channel_map" in guild_config:
                for kw, cfg in guild_config["keyword_channel_map"].items():
                    cfg["source_channel_ids"] = []
            if "pack_channel_map" in guild_config:
                for pack, cfg in guild_config["pack_channel_map"].items():
                    cfg["source_channel_ids"] = []
            
            save_guild_config(guild_id, guild_config)
            
            sources_mention = ', '.join([f'<#{sid}>' for sid in old_sources]) if old_sources else "None"
            embed = discord.Embed(
                title="✅ Sources Reset",
                description=f"Source channels have been reset.\n\n**Previous Sources:** {sources_mention}\n**New Sources:** All channels",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Show options
    if has_sources:
        current_sources = guild_config.get("default_source_channel_ids", [])
        sources_mention = ', '.join([f'<#{sid}>' for sid in current_sources])
        embed = discord.Embed(
            title="📡 Manage Source Channels",
            description=f"**Current Sources:** {sources_mention}\n\nWhat do you want to do?",
            color=discord.Color.blue()
        )
    else:
        embed = discord.Embed(
            title="📡 Manage Source Channels",
            description="No source channels currently set (monitoring all channels).\n\nWhat do you want to do?",
            color=discord.Color.blue()
        )
    
    view = SourceOptionsView()
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

# Updated ModeView (now overrides pre-created defaults if needed, ensures no empties)
class ModeView(discord.ui.View):
    def __init__(self, original_user, guild_id, created_categories):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id
        self.created_categories = created_categories
        self.guild_config = load_guild_config(guild_id)

    @discord.ui.button(label="One Channel per Series", style=discord.ButtonStyle.primary, custom_id="series_mode")
    async def series_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.followup.send("Only the command issuer can proceed.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        self.guild_config["pack_channel_mode"] = "series"

        # Override/create channels for series mode (uses pre-created if exist)
        global_series = config.get("series", {})
        created_in_mode = 0
        for series_name, packs_in_series in global_series.items():
            if not packs_in_series:
                continue
            cat = self.created_categories.get(series_name)
            if not cat:
                continue
            channel_name = f"{series_name.lower().replace(' ', '-')}-packs"
            channel = discord.utils.get(cat.text_channels, name=channel_name)
            if not channel:  # Only create if missing (pre-create should have it)
                overwrites = {
                    interaction.guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                }
                channel = await cat.create_text_channel(channel_name, overwrites=overwrites)
                created_in_mode += 1
            for pack in packs_in_series:
                if "pack_channel_map" not in self.guild_config:
                    self.guild_config["pack_channel_map"] = {}
                self.guild_config["pack_channel_map"][pack.lower()] = {
                    "channel_id": channel.id,
                    "source_channel_ids": self.guild_config.get("default_source_channel_ids", [])
                }
                print(f"Set {pack} to {channel_name} in series mode")

        save_guild_config(self.guild_id, self.guild_config)

        # Proceed to Validator (updated embed)
        val_embed = discord.Embed(
            title="✅ Series Mode Set! – Step 2: Validator Role",
            description=f"Pack channels finalized (no empties). Select validator role next.",
            color=discord.Color.green()
        )
        val_view = ValidatorView(self.original_user, self.guild_id, interaction.guild)
        await interaction.followup.send(embed=val_embed, view=val_view)
        self.stop()

    @discord.ui.button(label="One Channel per Pack", style=discord.ButtonStyle.secondary, custom_id="pack_mode")
    async def pack_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.followup.send("Only the command issuer can proceed.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        self.guild_config["pack_channel_mode"] = "pack"

        # Create individual channels (override pre-created series channels)
        global_series = config.get("series", {})
        created_in_mode = 0
        for series_name, packs_in_series in global_series.items():
            if not packs_in_series:
                continue
            cat = self.created_categories.get(series_name)
            if not cat:
                continue
            for pack in packs_in_series:
                channel_name = f"{pack.lower()}-pack"
                channel = discord.utils.get(cat.text_channels, name=channel_name)
                if not channel:
                    overwrites = {
                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                        interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                    }
                    channel = await cat.create_text_channel(channel_name, overwrites=overwrites)
                    created_in_mode += 1
                    print(f"Created individual pack channel '{channel_name}' in pack mode")
                if "pack_channel_map" not in self.guild_config:
                    self.guild_config["pack_channel_map"] = {}
                self.guild_config["pack_channel_map"][pack.lower()] = {
                    "channel_id": channel.id,
                    "source_channel_ids": self.guild_config.get("default_source_channel_ids", [])
                }

        # Clean up pre-created series channels if they exist and mode is pack (optional: delete them?)
        # For now, leave them as extras; user can delete manually

        save_guild_config(self.guild_id, self.guild_config)

        # Proceed to Validator (updated)
        val_embed = discord.Embed(
            title="✅ Pack Mode Set! – Step 2: Validator Role",
            description=f"Created {created_in_mode} individual pack channels (no empties). Select validator role next.",
            color=discord.Color.green()
        )
        val_view = ValidatorView(self.original_user, self.guild_id, interaction.guild)
        await interaction.followup.send(embed=val_embed, view=val_view)
        self.stop()

# Validator View (updated to chain to PingSetupView)
class ValidatorView(discord.ui.View):
    def __init__(self, original_user, guild_id, guild):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id
        self.guild = guild
        # Fallback: Create a string select with top 25 roles (sorted by position)
        roles = sorted(guild.roles, key=lambda r: r.position, reverse=True)[:25]  # Exclude @everyone
        if guild.default_role in roles:
            roles.remove(guild.default_role)
        self.select = discord.ui.Select(
            placeholder="Select Validator Role...",
            options=[discord.SelectOption(label=role.name, value=str(role.id)) for role in roles]
        )
        self.select.callback = self.role_callback
        self.add_item(self.select)

    async def role_callback(self, inter: discord.Interaction):
        if inter.user != self.original_user:
            await inter.response.send_message("Only the command issuer can proceed.", ephemeral=True)
            return
        role_id = int(self.select.values[0])
        guild_config = load_guild_config(self.guild_id)
        guild_config["validator_role_id"] = role_id
        save_guild_config(self.guild_id, guild_config)

        # Step 3: Ping Setup View
        ping_embed = discord.Embed(
            title="Step 3: Optional Ping Roles",
            description="Select which ping roles to configure (optional). You can skip and set them later with /setpingroles.",
            color=discord.Color.green()
        )
        ping_view = PingSetupView(self.original_user, self.guild_id, inter.guild)
        await inter.response.send_message(embed=ping_embed, view=ping_view, ephemeral=True)
        self.stop()

# Ping Setup View
class PingSetupView(discord.ui.View):
    def __init__(self, original_user, guild_id, guild):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id
        self.guild = guild
        self.current_step = 0
        self.ping_types = ["godpack", "invgodpack", "safe_trade"]
        self.ping_labels = {"godpack": "God Pack Ping", "invgodpack": "Invalid God Pack Ping", "safe_trade": "Safe for Trade Ping"}

    @discord.ui.button(label="Set God Pack Ping", style=discord.ButtonStyle.primary)
    async def godpack_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        await interaction.response.defer(ephemeral=True)
        await self.set_ping_role(interaction, "godpack")

    @discord.ui.button(label="Set Invalid God Pack Ping", style=discord.ButtonStyle.primary)
    async def invgodpack_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        await interaction.response.defer(ephemeral=True)
        await self.set_ping_role(interaction, "invgodpack")

    @discord.ui.button(label="Set Safe for Trade Ping", style=discord.ButtonStyle.primary)
    async def safe_trade_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        await interaction.response.defer(ephemeral=True)
        await self.set_ping_role(interaction, "safe_trade")

    @discord.ui.button(label="Skip Pings", style=discord.ButtonStyle.secondary)
    async def skip_pings(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        await self.proceed_to_next_step(interaction)

    async def set_ping_role(self, interaction: discord.Interaction, ping_type: str):
        roles = sorted(self.guild.roles, key=lambda r: r.position, reverse=True)[:25]
        if self.guild.default_role in roles:
            roles.remove(self.guild.default_role)
        
        class PingSelectView(discord.ui.View):
            def __init__(self, parent):
                super().__init__(timeout=300)
                self.parent = parent
            
            @discord.ui.select(placeholder="Select Ping Role...")
            async def role_select(self, interaction: discord.Interaction, select: discord.ui.Select):
                if interaction.user != self.parent.original_user:
                    await interaction.response.defer()
                    return
                await self.parent.ping_callback(interaction, ping_type, int(select.values[0]))
        
        view = PingSelectView(self)
        options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in roles]
        view.role_select.options = options
        await interaction.followup.send(
            f"Select the role for {self.ping_labels[ping_type]}:",
            view=view,
            ephemeral=True
        )

    async def ping_callback(self, interaction: discord.Interaction, ping_type: str, role_id: int):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        
        guild_config = load_guild_config(self.guild_id)
        guild_config[f"{ping_type}_ping"] = role_id
        save_guild_config(self.guild_id, guild_config)
        
        await interaction.response.defer()
        await interaction.followup.send(f"✅ {self.ping_labels[ping_type]} set to <@&{role_id}>", ephemeral=True)

    async def proceed_to_next_step(self, interaction: discord.Interaction):
        # FIXED: Create modal and set BOTH guild_id AND original_user
        modal = SourceModal()
        modal.guild_id = self.guild_id
        modal.original_user = self.original_user  # NEW: Set original_user
        await interaction.response.send_modal(modal)

# Modal for Source Channels
class SourceModal(discord.ui.Modal, title="Set Source Channels (Optional)"):
    source_input = discord.ui.TextInput(
        label="Source Channels",
        style=discord.TextStyle.short,
        placeholder="Mention multiple channels, e.g., #general #tcg-chat (leave empty for all channels)",
        required=False,
        max_length=500
    )

    def __init__(self):
        super().__init__()
        self.guild_id = None  # Set dynamically
        self.original_user = None  # NEW: Set dynamically (though not used directly here)

    async def on_submit(self, interaction: discord.Interaction):
        # Defer response first
        await interaction.response.defer(ephemeral=True)
        
        # FIXED: Ensure original_user is set before proceeding
        if not self.original_user:
            await interaction.followup.send("❌ Setup error: Original user not set. Please restart /setup.", ephemeral=True)
            return
        
        # Parse channel mentions and names
        source_ids = []
        input_value = self.source_input.value.strip()
        
        if input_value:
            # First, try to parse full mentions <#ID>
            matches = re.findall(r'<#(\d+)>', input_value)
            for match in matches:
                try:
                    ch_id = int(match)
                    if interaction.guild.get_channel(ch_id):
                        source_ids.append(ch_id)
                except ValueError:
                    pass
            
            # If no IDs found, or additionally, parse channel names like #allgemein
            if not source_ids or len(matches) != len(input_value.split(',')):
                channel_names = [name.strip().strip('#').strip().lower() for name in input_value.split(',') if name.strip()]
                for name in channel_names:
                    # Case-insensitive search for channels
                    channel = None
                    for ch in interaction.guild.text_channels:
                        if ch.name.lower() == name:
                            channel = ch
                            break
                    
                    if channel:
                        source_ids.append(channel.id)
                        print(f"✅ Found channel: {channel.name} (ID: {channel.id})")
                    else:
                        print(f"❌ Channel name '{name}' not found in guild.")

        guild_config = load_guild_config(self.guild_id)
        # Set global default sources (can be overridden per filter)
        guild_config["default_source_channel_ids"] = source_ids
        print(f"📌 Saved source_ids: {source_ids}")

        # Apply to all existing maps
        if "keyword_channel_map" in guild_config:
            for kw, cfg in guild_config["keyword_channel_map"].items():
                cfg["source_channel_ids"] = source_ids[:]
        if "pack_channel_map" in guild_config:
            for pack, cfg in guild_config["pack_channel_map"].items():
                cfg["source_channel_ids"] = source_ids[:]

        save_guild_config(self.guild_id, guild_config)

        # Proceed to Validation Buttons Setup
        val_embed = discord.Embed(
            title="Step 4: Validation Buttons",
            description="Do you want to enable traded buttons for Safe 4 Trade embeds?",
            color=discord.Color.green()
        )
        val_view = ValidationSetupView(self.original_user, self.guild_id, interaction.guild)  # Now safe
        await interaction.followup.send(embed=val_embed, view=val_view, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(f"Source modal error: {error}")
        await interaction.followup.send("An error occurred during source setup.", ephemeral=True)

# Validation Setup View
class ValidationSetupView(discord.ui.View):
    def __init__(self, original_user, guild_id, guild):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id
        self.guild = guild

    @discord.ui.button(label="Enable Traded Buttons", style=discord.ButtonStyle.success)
    async def enable_validation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        
        await interaction.response.defer(ephemeral=True)
        guild_config = load_guild_config(self.guild_id)
        guild_config["validation_buttons_enabled"] = True
        save_guild_config(self.guild_id, guild_config)
        await interaction.followup.send("✅ Traded buttons enabled for Safe 4 Trade embeds.", ephemeral=True)
        await self.proceed_to_heartbeat(interaction)

    @discord.ui.button(label="Disable Traded Buttons", style=discord.ButtonStyle.danger)
    async def disable_validation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        
        await interaction.response.defer(ephemeral=True)
        guild_config = load_guild_config(self.guild_id)
        guild_config["validation_buttons_enabled"] = False
        save_guild_config(self.guild_id, guild_config)
        await interaction.followup.send("✅ Traded buttons disabled.", ephemeral=True)
        await self.proceed_to_heartbeat(interaction)

    async def proceed_to_heartbeat(self, interaction: discord.Interaction):
        # Proceed to Heartbeat Setup
        heartbeat_embed = discord.Embed(
            title="Step 5: Heartbeat Monitor",
            description="Do you want to enable the heartbeat monitor?",
            color=discord.Color.green()
        )
        heartbeat_view = HeartbeatSetupView(self.original_user, self.guild_id, interaction.guild)
        await interaction.followup.send(embed=heartbeat_embed, view=heartbeat_view, ephemeral=True)

# Heartbeat Setup View (UPDATED WITH FIX)
class HeartbeatSetupView(discord.ui.View):
    def __init__(self, original_user, guild_id, guild):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id
        self.guild = guild
        self.source_id = None  # To store source channel ID

    @discord.ui.button(label="Enable Heartbeat", style=discord.ButtonStyle.success)
    async def enable_heartbeat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Create a proper view for channel selection
        class ChannelSelectView(discord.ui.View):
            def __init__(self, parent):
                super().__init__(timeout=300)
                self.parent = parent
                self.source_id = None
            
            @discord.ui.select(placeholder="Select Source Channel...", min_values=1, max_values=1)
            async def source_select(self, interaction: discord.Interaction, select: discord.ui.Select):
                if interaction.user != self.parent.original_user:
                    await interaction.response.defer()
                    return
                
                self.source_id = int(select.values[0])
                await interaction.response.defer()
                await interaction.followup.send(f"✅ Source set to <#{self.source_id}>", ephemeral=True)
                
                # Now ask for target channel
                class TargetSelectView(discord.ui.View):
                    def __init__(self, source_id, parent):
                        super().__init__(timeout=300)
                        self.source_id = source_id
                        self.parent = parent
                    
                    @discord.ui.select(placeholder="Select Target Channel...", min_values=1, max_values=1)
                    async def target_select(self, interaction: discord.Interaction, select: discord.ui.Select):
                        if interaction.user != self.parent.original_user:
                            await interaction.response.defer()
                            return
                        
                        target_id = int(select.values[0])
                        guild_config = load_guild_config(self.parent.guild_id)
                        guild_config["heartbeat_source_channel_id"] = self.source_id
                        guild_config["heartbeat_target_channel_id"] = target_id
                        
                        embed = create_heartbeat_embed(guild_config)
                        target_channel = self.parent.guild.get_channel(target_id)
                        sent_message = await target_channel.send(embed=embed)
                        guild_config["heartbeat_message_id"] = sent_message.id
                        save_guild_config(self.parent.guild_id, guild_config)
                        
                        await interaction.response.defer()
                        await interaction.followup.send(f"✅ Heartbeat configured. Target: <#{target_id}>", ephemeral=True)
                        
                        # Final setup embed
                        final_embed = self.parent.build_final_embed(self.parent.guild)
                        await interaction.followup.send(embed=final_embed, ephemeral=True)
                        self.parent.stop()
                
                target_view = TargetSelectView(self.source_id, self.parent)
                # Set target channel options dynamically
                target_channels = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in self.parent.guild.text_channels[:25]]
                target_view.target_select.options = target_channels
                await interaction.followup.send("Select target channel for heartbeat:", view=target_view, ephemeral=True)
        
        view = ChannelSelectView(self)
        # Set channel options dynamically
        channels = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in interaction.guild.text_channels[:25]]
        view.source_select.options = channels
        
        await interaction.followup.send("Select source channel for heartbeat:", view=view, ephemeral=True)

    @discord.ui.button(label="Disable Heartbeat", style=discord.ButtonStyle.danger)
    async def disable_heartbeat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        # For disable, use response directly
        await interaction.response.defer()
        final_embed = self.build_final_embed(interaction.guild)
        await interaction.followup.send(embed=final_embed, ephemeral=True)
        self.stop()

    def build_final_embed(self, guild):
        # Extract the embed building logic from final_setup to this helper method
        guild_config = load_guild_config(self.guild_id)
        source_ids = guild_config.get("default_source_channel_ids", [])
        sources_mention = ', '.join([f'<#{sid}>' for sid in source_ids]) if source_ids else 'All channels'
        pack_mode = guild_config.get('pack_channel_mode', 'series')
        pack_mode_desc = 'One channel per series' if pack_mode == 'series' else 'One channel per pack'
        validator_role = guild.get_role(guild_config.get('validator_role_id'))
        godpack_ping = guild.get_role(guild_config.get('godpack_ping'))
        invgodpack_ping = guild.get_role(guild_config.get('invgodpack_ping'))
        safe_trade_ping = guild.get_role(guild_config.get('safe_trade_ping'))
        validation_enabled = guild_config.get('validation_buttons_enabled', False)
        heartbeat_enabled = 'heartbeat_source_channel_id' in guild_config

        final_embed = discord.Embed(
            title="🎉 Full Setup Complete!",
            description=(
                f"✅ Validator Role: {validator_role.mention if validator_role else 'Not set'}\n"
                f"🌟 God Pack Ping: {godpack_ping.mention if godpack_ping else 'Not set'}\n"
                f"🚫 Invalid God Pack Ping: {invgodpack_ping.mention if invgodpack_ping else 'Not set'}\n"
                f"✅ Safe for Trade Ping: {safe_trade_ping.mention if safe_trade_ping else 'Not set'}\n"
                f"📡 Sources: {sources_mention}\n"
                f"📦 Pack Mode: {pack_mode_desc}\n"
                f"🔍 Traded Buttons: {'Enabled' if validation_enabled else 'Disabled'}\n"
                f"💓 Heartbeat: {'Enabled' if heartbeat_enabled else 'Disabled'}\n\n"
                "Use /showfilters to verify. Set pings later with /setpingroles. Enjoy your TCGP bot!"
            ),
            color=discord.Color.green()
        )
        return final_embed

# Slash-Command: /setpingroles (new command)
@tree.command(name="setpingroles", description="Set ping roles for god pack, invalid god pack, or safe for trade")
async def setpingroles(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(title="Error", description="Administrator required.", color=discord.Color.red())
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    select = discord.ui.Select(
        placeholder="Select Ping Type...",
        options=[
            discord.SelectOption(label="God Pack Ping", value="godpack"),
            discord.SelectOption(label="Invalid God Pack Ping", value="invgodpack"),
            discord.SelectOption(label="Safe for Trade Ping", value="safe_trade")
        ]
    )
    select.callback = lambda inter: ping_type_callback(inter)
    view = discord.ui.View()
    view.add_item(select)
    embed = discord.Embed(title="Set Ping Role", description="First, select the ping type.", color=discord.Color.blue())
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

async def ping_type_callback(interaction: discord.Interaction):
    ping_type = interaction.data['values'][0]
    guild_id = str(interaction.guild.id)
    roles = sorted(interaction.guild.roles, key=lambda r: r.position, reverse=True)[:25]
    if interaction.guild.default_role in roles:
        roles.remove(interaction.guild.default_role)
    role_select = discord.ui.Select(
        placeholder=f"Select Role for {ping_type.replace('_', ' ').title()}...",
        options=[discord.SelectOption(label=role.name, value=str(role.id)) for role in roles]
    )
    role_select.callback = lambda i: set_ping(i, ping_type, guild_id)
    view = discord.ui.View()
    view.add_item(role_select)
    await interaction.response.edit_message(content=f"Select role for {ping_type.replace('_', ' ').title()}:", view=view, embed=None)

async def set_ping(interaction: discord.Interaction, ping_type: str, guild_id: str):
    role_id = int(interaction.data['values'][0])
    guild_config = load_guild_config(guild_id)
    guild_config[f"{ping_type}_ping"] = role_id
    save_guild_config(guild_id, guild_config)
    role = interaction.guild.get_role(role_id)
    await interaction.response.edit_message(content=f"✅ {ping_type.replace('_', ' ').title()} set to {role.mention}", view=None)

# Slash-Command: /setpackmode (new command for changing mode post-setup)
@tree.command(name="setpackmode", description="Change the pack channel mode after setup")
@app_commands.describe(mode="Pack channel organization mode")
@app_commands.choices(mode=[
    app_commands.Choice(name="One channel per series", value="series"),
    app_commands.Choice(name="One channel per pack", value="pack")
])
async def setpackmode(interaction: discord.Interaction, mode: str):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(title="Error", description="Administrator required.", color=discord.Color.red())
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    guild_config = load_guild_config(guild_id)
    guild_config["pack_channel_mode"] = mode
    save_guild_config(guild_id, guild_config)

    mode_desc = "one channel per series" if mode == "series" else "one channel per pack"
    embed = discord.Embed(
        title="Pack Mode Updated",
        description=f"Pack channels are now set to {mode_desc}. Use /clearfilters pack to reset and reconfigure channels if needed.",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

# Slash-Command: /clearfilters
@tree.command(name="clearfilters", description="Clear all filters of a selected type")
@app_commands.describe(filter_type="Type of filters to clear")
@app_commands.choices(filter_type=CLEAR_FILTER_CHOICES)
async def clearfilters(interaction: discord.Interaction, filter_type: str):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error",
            description="You need administrator permissions to use this command.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)
    guild_config = load_guild_config(guild_id)
    
    if not guild_config or (not guild_config.get("keyword_channel_map") and not guild_config.get("pack_channel_map")):
        embed = discord.Embed(
            title="Error",
            description="No filters configured for this server.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    cleared = False
    cleared_count = 0
    
    if filter_type == "normal" or filter_type == "all":
        if "keyword_channel_map" in guild_config:
            cleared_count += len(guild_config["keyword_channel_map"])
            del guild_config["keyword_channel_map"]
            cleared = True
    
    if filter_type == "pack" or filter_type == "all":
        if "pack_channel_map" in guild_config:
            cleared_count += len(guild_config["pack_channel_map"])
            del guild_config["pack_channel_map"]
            cleared = True
    
    if not cleared:
        embed = discord.Embed(
            title="Error",
            description=f"No {filter_type} filters found.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    save_guild_config(guild_id, guild_config)
    
    type_name = {"normal": "Normal", "pack": "Pack", "all": "All"}[filter_type]
    embed = discord.Embed(
        title="Filters Cleared",
        description=f"{cleared_count} {type_name} filter(s) cleared successfully.",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed)

# Updated /setfilter to auto-create channel if needed
@tree.command(name="setfilter", description="Configuration of Filter for TCGP Rerolling")
@app_commands.describe(
    filter_keyword="The Filter",
    channel="The target channel for the forwarding (optional; auto-creates if omitted)",
    source_channels="Space-separated source channel mentions (optional, e.g., #channel1 #channel2)",
    godpack_ping="Role Ping for GOD Pack (optional)",
    invgodpack_ping="Role Ping for Invalid God Pack (optional)",
    safe_trade_ping="Role Ping for Safe for Trade (optional)"
)
@app_commands.choices(filter_keyword=FILTER_CHOICES)
async def setfilter(
    interaction: discord.Interaction,
    filter_keyword: str,
    channel: discord.TextChannel = None,  # Now optional
    source_channels: str = None,
    godpack_ping: discord.Role = None,
    invgodpack_ping: discord.Role = None,
    safe_trade_ping: discord.Role = None
):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error",
            description="You need administrator permissions to use this command.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)
    guild_config = load_guild_config(guild_id)
    
    if filter_keyword.lower() not in CUSTOM_EMBED_TEXT:
        embed = discord.Embed(
            title="Error",
            description=f"Invalid Filter: '{filter_keyword}'.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    # Determine target channel: if provided, use it; else auto-create under category
    target_channel = channel
    if not target_channel:
        # Map keyword to category and create individual channel
        keyword_to_cat = {
            "one star": "Save 4 Trade", "three diamond": "Save 4 Trade", "four diamond ex": "Save 4 Trade",
            "gimmighoul": "Save 4 Trade", "shiny": "Save 4 Trade", "rainbow": "Save 4 Trade",
            "full art": "Save 4 Trade", "trainer": "Save 4 Trade",
            "god pack": "God Packs", "invalid god pack": "God Packs",
            "crown": "Detection", "immersive": "Detection"
        }
        cat_name = keyword_to_cat.get(filter_keyword.lower())
        if cat_name:
            category = discord.utils.get(interaction.guild.categories, name=cat_name)
            if category:
                clean_name = filter_keyword.lower().replace(" ", "-").replace("invalid god pack", "invalid-god-pack")
                channel_name = OLD_TO_NEW_CHANNEL_NAMES.get(f"prefix-{clean_name}", clean_name)  # Adjust if needed
                target_channel = discord.utils.get(category.text_channels, name=channel_name)
                if not target_channel:
                    # Auto-create
                    try:
                        overwrites = {
                            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                        }
                        target_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                    except discord.Forbidden:
                        embed = discord.Embed(title="Error", description="Bot lacks permission to create channels.", color=discord.Color.red())
                        await interaction.followup.send(embed=embed, ephemeral=True)
                        return
        if not target_channel:
            # Fallback error
            embed = discord.Embed(title="Error", description="Could not auto-create channel. Provide one manually.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

    source_channel_ids = []
    if source_channels:
        matches = re.findall(r'<#(\d+)>', source_channels)
        for match in matches:
            try:
                channel_id = int(match)
                if bot.get_channel(channel_id):
                    source_channel_ids.append(channel_id)
                else:
                    print(f"Invalid channel ID: {channel_id}")
            except ValueError:
                print(f"Invalid channel format: {match}")

    guild_config = load_guild_config(guild_id)
    
    if "keyword_channel_map" not in guild_config:
        guild_config["keyword_channel_map"] = {}
    
    guild_config["keyword_channel_map"][filter_keyword.lower()] = {
        "channel_id": target_channel.id,
        "source_channel_ids": source_channel_ids if source_channel_ids else None
    }

    if godpack_ping:
        guild_config["godpack_ping"] = godpack_ping.id
    if invgodpack_ping:
        guild_config["invgodpack_ping"] = invgodpack_ping.id
    if safe_trade_ping:
        guild_config["safe_trade_ping"] = safe_trade_ping.id

    save_guild_config(guild_id, guild_config)

    sources_mention = ", ".join([f"<#{sid}>" for sid in source_channel_ids]) if source_channel_ids else "All channels"
    embed = discord.Embed(
        title="New Filter Set",
        description=f"Filter '{filter_keyword}' is now being used for {target_channel.mention}.\n"
                    f"Source Channels: {sources_mention}\n"
                    f"God Pack Ping: {godpack_ping.mention if godpack_ping else 'Not set'}\n"
                    f"Invalid God Pack Ping: {invgodpack_ping.mention if invgodpack_ping else 'Not set'}\n"
                    f"Safe for Trade Ping: {safe_trade_ping.mention if safe_trade_ping else 'Not set'}",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed)

# Updated /setpackfilter with auto-create and mode awareness
@tree.command(name="setpackfilter", description="Configuration of Filter for Packs")
@app_commands.describe(
    pack="The Pack (ignored in series mode; sets all in series)",
    channel="The target channel for the pack forwarding (optional; auto-creates if omitted)",
    source_channels="Space-separated source channel mentions (optional, e.g., #channel1 #channel2)"
)
@app_commands.autocomplete(pack=autocomplete_packs)
async def setpackfilter(
    interaction: discord.Interaction,
    pack: str,
    channel: discord.TextChannel = None,  # Optional for auto-create
    source_channels: str = None
):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error",
            description="You need administrator permissions to use this command.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)
    guild_config = load_guild_config(guild_id)
    pack_mode = guild_config.get("pack_channel_mode", "series")
    
    if pack_mode == "series":
        # Find series for pack and set all packs in series
        series_name = None
        for s, packs_in_s in config.get("series", {}).items():
            if pack.lower() in [p.lower() for p in packs_in_s]:
                series_name = s
                break
        if not series_name:
            embed = discord.Embed(title="Error", description=f"Pack '{pack}' not in any series.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        packs_to_set = [p.lower() for p in config["series"][series_name]]
        embed_desc = f"Series '{series_name}' ({len(packs_to_set)} packs)"
    else:
        # Per pack
        if pack.lower() not in [p.lower() for p in PACKS]:
            embed = discord.Embed(
                title="Error",
                description=f"Invalid Pack: '{pack}'.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        packs_to_set = [pack.lower()]
        embed_desc = f"Pack '{pack}'"

    # Determine target channel
    target_channel = channel
    if not target_channel:
        series_name = next((s for s, packs_in_s in config.get("series", {}).items() if any(p.lower() == packs_to_set[0] for p in packs_in_s)), None)
        if series_name:
            category = discord.utils.get(interaction.guild.categories, name=series_name)
            if category:
                if pack_mode == "series":
                    channel_name = f"{series_name.lower().replace(' ', '-')}-packs"
                else:
                    channel_name = f"{packs_to_set[0]}-pack"
                target_channel = discord.utils.get(category.text_channels, name=channel_name)
                if not target_channel:
                    overwrites = {
                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                        interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                    }
                    try:
                        target_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                    except discord.Forbidden:
                        embed = discord.Embed(title="Error", description="Bot lacks permission to create channels.", color=discord.Color.red())
                        await interaction.followup.send(embed=embed, ephemeral=True)
                        return
        if not target_channel:
            embed = discord.Embed(title="Error", description="Could not auto-create channel. Provide one manually.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

    source_channel_ids = []
    if source_channels:
        matches = re.findall(r'<#(\d+)>', source_channels)
        for match in matches:
            try:
                channel_id = int(match)
                if bot.get_channel(channel_id):
                    source_channel_ids.append(channel_id)
                else:
                    print(f"Invalid channel ID: {channel_id}")
            except ValueError:
                print(f"Invalid channel format: {match}")

    guild_config = load_guild_config(guild_id)
    
    if "pack_channel_map" not in guild_config:
        guild_config["pack_channel_map"] = {}
    
    for p in packs_to_set:
        guild_config["pack_channel_map"][p] = {
            "channel_id": target_channel.id,
            "source_channel_ids": source_channel_ids if source_channel_ids else None
        }

    save_guild_config(guild_id, guild_config)

    sources_mention = ", ".join([f"<#{sid}>" for sid in source_channel_ids]) if source_channel_ids else "All channels"
    embed = discord.Embed(
        title="New Pack Filter Set",
        description=f"{embed_desc} is now being forwarded to {target_channel.mention}.\n"
                    f"Source Channels: {sources_mention}",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed)

# Angepasste /removefilter
@tree.command(name="removefilter", description="Remove a certain filter from the configuration")
@app_commands.describe(
    filter_keyword="Filter to remove"
)
@app_commands.choices(filter_keyword=FILTER_CHOICES)
async def removefilter(interaction: discord.Interaction, filter_keyword: str):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error",
            description="You need administrator permissions to use this command.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)
    guild_config = load_guild_config(guild_id)
    
    if "keyword_channel_map" not in guild_config or filter_keyword.lower() not in guild_config["keyword_channel_map"]:
        embed = discord.Embed(
            title="Error",
            description=f"Filter '{filter_keyword}' not found in configuration.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    del guild_config["keyword_channel_map"][filter_keyword.lower()]
    
    if not guild_config["keyword_channel_map"]:
        del guild_config["keyword_channel_map"]

    save_guild_config(guild_id, guild_config)

    embed = discord.Embed(
        title="Filter Removed",
        description=f"Filter '{filter_keyword}' was successfully removed.",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed)

# Angepasste /removepackfilter mit Autocomplete (dynamisch!)
@tree.command(name="removepackfilter", description="Remove a certain pack filter from the configuration")
@app_commands.describe(
    pack="Pack to remove"
)
@app_commands.autocomplete(pack=autocomplete_packs)
async def removepackfilter(interaction: discord.Interaction, pack: str):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error",
            description="You need administrator permissions to use this command.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)
    guild_config = load_guild_config(guild_id)
    
    if "pack_channel_map" not in guild_config or pack.lower() not in guild_config["pack_channel_map"]:
        embed = discord.Embed(
            title="Error",
            description=f"Pack filter '{pack}' not found in configuration.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    del guild_config["pack_channel_map"][pack.lower()]
    
    if not guild_config["pack_channel_map"]:
        del guild_config["pack_channel_map"]

    save_guild_config(guild_id, guild_config)

    embed = discord.Embed(
        title="Pack Filter Removed",
        description=f"Pack filter '{pack}' was successfully removed.",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed)

# Updated /addseries (now auto-creates in ALL guilds with setup configs)
@tree.command(name="addseries", description="Fügt eine neue Series zur Konfiguration hinzu (DEV only) - Auto-creates in all setup guilds")
@app_commands.describe(series_name="Der Name der neuen Series (z.B. 'B-Series')")
async def addseries(interaction: discord.Interaction, series_name: str):
    await interaction.response.defer(ephemeral=True)
    if not await owner_only(interaction):
        return
    
    series_lower = series_name.lower().strip()
    if not series_lower or len(series_lower) < 2:
        embed = discord.Embed(
            title="Fehler",
            description="Series-Name muss mindestens 2 Zeichen lang sein.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    if series_lower in [s.lower() for s in config["series"]]:
        embed = discord.Embed(
            title="Fehler",
            description=f"Series '{series_name}' existiert bereits.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    # Hinzufügen zur globalen Config
    config["series"][series_name] = []
    update_packs(config)
    config["packs"] = PACKS
    save_config(config)
    
    # Auto-Sync
    await tree.sync()
    
    # Auto-create in ALL guilds that have run setup (iterate through guild_configs/ directory)
    created_count = 0
    error_count = 0
    
    ensure_guild_config_dir()
    if os.path.exists(GUILD_CONFIG_DIR):
        for config_file in os.listdir(GUILD_CONFIG_DIR):
            if config_file.startswith("guild_") and config_file.endswith(".json"):
                guild_id_str = config_file.replace("guild_", "").replace(".json", "")
                try:
                    guild_config = load_guild_config(guild_id_str)
                    guild = bot.get_guild(int(guild_id_str))
                    if not guild:
                        continue
                    # Check if setup was run (e.g., has pack_channel_mode or keyword_channel_map)
                    if "pack_channel_mode" not in guild_config:
                        continue
                    
                    # Create category if not exists
                    category = discord.utils.get(guild.categories, name=series_name)
                    if not category:
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                        }
                        category = await guild.create_category(series_name, overwrites=overwrites)
                        print(f"Created category '{series_name}' in guild {guild.name} ({guild_id_str})")
                    
                    # Create default channel
                    channel_name = f"{series_name.lower().replace(' ', '-')}-packs"
                    existing_channel = discord.utils.get(category.text_channels, name=channel_name)
                    if not existing_channel:
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                        }
                        await category.create_text_channel(channel_name, overwrites=overwrites)
                        print(f"Created channel '{channel_name}' in category '{series_name}' for guild {guild.name}")
                    
                    # Update pack_channel_map for this series (empty for now)
                    if "pack_channel_map" not in guild_config:
                        guild_config["pack_channel_map"] = {}
                    # No packs yet, but set mode if not set
                    if "pack_channel_mode" not in guild_config:
                        guild_config["pack_channel_mode"] = "series"  # Default
                    created_count += 1
                    
                    save_guild_config(guild_id_str, guild_config)
                    
                except discord.Forbidden:
                    print(f"Permission error: Bot lacks perms to create category/channel in guild {guild_id_str}")
                    error_count += 1
                except Exception as e:
                    print(f"Error creating series '{series_name}' in guild {guild_id_str}: {e}")
                    error_count += 1
    
    embed = discord.Embed(
        title="Series hinzugefügt & Auto-Created",
        description=f"'{series_name}' wurde global hinzugefügt und in **{created_count}** guilds auto-erstellt.\n"
                    f"Errors in **{error_count}** guilds (check perms).\n"
                    f"**Aktuelle Series:** {', '.join(config['series'].keys())}",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

# Updated /addpack (now auto-creates channels in ALL guilds with setup configs, based on pack mode)
@tree.command(name="addpack", description="Fügt ein neues Pack zur Liste hinzu (Owner only) - Auto-creates channels in all setup guilds")
@app_commands.describe(pack_name="Der Name des neuen Packs (z.B. 'neuespack')", series="Die Series, in die das Pack hinzugefügt werden soll")
@app_commands.autocomplete(pack_name=autocomplete_packs, series=autocomplete_series)  # pack autocomplete um Duplikate zu vermeiden
async def addpack(interaction: discord.Interaction, pack_name: str, series: str = "A-Series"):
    await interaction.response.defer(ephemeral=True)
    if not await owner_only(interaction):
        return
    
    pack_lower = pack_name.lower().strip()
    if not pack_lower or len(pack_lower) < 2:
        embed = discord.Embed(
            title="Fehler",
            description="Pack-Name muss mindestens 2 Zeichen lang sein.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    if pack_lower in [p.lower() for p in PACKS]:
        embed = discord.Embed(
            title="Fehler",
            description=f"Pack '{pack_name}' existiert bereits.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    if series not in config["series"]:
        embed = discord.Embed(
            title="Fehler",
            description=f"Series '{series}' existiert nicht. Füge sie zuerst mit /addseries hinzu.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    # Hinzufügen zur globalen Series
    config["series"][series].append(pack_name)
    update_packs(config)
    config["packs"] = PACKS  # Backward compat
    save_config(config)
    
    # Auto-Sync
    await tree.sync()
    
    # Auto-create/update channels in ALL guilds that have run setup
    created_count = 0
    updated_count = 0
    error_count = 0
    
    # Iterate through guild_configs/ directory instead of bot_config.json
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
                # Check if setup was run
                if "pack_channel_mode" not in guild_config:
                    continue
                
                pack_mode = guild_config.get("pack_channel_mode", "series")
                category = discord.utils.get(guild.categories, name=series)
                if not category:
                    # If series category missing, skip or create? For safety, skip—user should re-run /setup
                    print(f"Skipping pack '{pack_name}' in guild {guild_id_str}: No '{series}' category found.")
                    continue
                
                if pack_mode == "series":
                    # Find or create series channel and update map for ALL packs in series
                    channel_name = f"{series.lower().replace(' ', '-')}-packs"
                    target_channel = discord.utils.get(category.text_channels, name=channel_name)
                    if not target_channel:
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                        }
                        target_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                        print(f"Created series channel '{channel_name}' in '{series}' for guild {guild.name}")
                    
                    # Update map for ALL packs in this series
                    for p in config["series"][series]:
                        if "pack_channel_map" not in guild_config:
                            guild_config["pack_channel_map"] = {}
                        guild_config["pack_channel_map"][p.lower()] = {
                            "channel_id": target_channel.id,
                            "source_channel_ids": guild_config.get("default_source_channel_ids", [])
                        }
                    updated_count += 1
                else:  # pack_mode == "pack"
                    # Create individual pack channel
                    channel_name = f"{pack_lower}-pack"
                    target_channel = discord.utils.get(category.text_channels, name=channel_name)
                    if not target_channel:
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                        }
                        target_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                        print(f"Created pack channel '{channel_name}' in '{series}' for guild {guild.name}")
                        created_count += 1
                    else:
                        updated_count += 1
                    
                    # Update map for this pack
                    if "pack_channel_map" not in guild_config:
                        guild_config["pack_channel_map"] = {}
                    guild_config["pack_channel_map"][pack_lower] = {
                        "channel_id": target_channel.id,
                        "source_channel_ids": guild_config.get("default_source_channel_ids", [])
                    }
                
                save_guild_config(guild_id_str, guild_config)
                
            except discord.Forbidden:
                error_msg = f"Permission error: Bot lacks perms to create/update channels in guild {guild_id_str}"
                print(error_msg)
                await log_permission_warning_to_webhook(error_msg, guild_id=guild_id_str, command_name="addpack")
                error_count += 1
            except Exception as e:
                error_msg = f"Error adding pack '{pack_name}' to guild {guild_id_str}: {e}"
                print(error_msg)
                await log_error_to_webhook(error_msg, guild_id=guild_id_str, command_name="addpack")
                error_count += 1
    
    embed = discord.Embed(
        title="Pack hinzugefügt & Auto-Created/Updated",
        description=f"'{pack_name}' wurde zur Series '{series}' hinzugefügt.\n"
                    f"Auto-created/updated in **{created_count + updated_count}** guilds (series mode: updated maps; pack mode: new channels).\n"
                    f"Errors in **{error_count}** guilds (check perms).\n"
                    f"**Aktuelle Packs:** {', '.join(PACKS)}",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

# /removepack mit Autocomplete (auch dynamisch!) - jetzt sucht es die Series und löscht Channels in pack mode
@tree.command(name="removepack", description="Entfernt ein Pack aus der Liste (Owner only) - Deletes channels if in pack mode")
@app_commands.describe(pack_name="Der Name des zu entfernenden Packs")
@app_commands.autocomplete(pack_name=autocomplete_packs)
async def removepack(interaction: discord.Interaction, pack_name: str):
    await interaction.response.defer(ephemeral=True)
    if not await owner_only(interaction):
        return
    
    pack_lower = pack_name.lower()
    if pack_lower not in [p.lower() for p in PACKS]:
        embed = discord.Embed(
            title="Fehler",
            description=f"Pack '{pack_name}' nicht gefunden.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    # Finde die Series, in der das Pack ist
    series_found = None
    for series_name, packs_in_series in config["series"].items():
        if pack_lower in [p.lower() for p in packs_in_series]:
            series_found = series_name
            break
    
    if series_found:
        config["series"][series_found] = [p for p in config["series"][series_found] if p.lower() != pack_lower]
        if not config["series"][series_found]:  # Entferne leere Series
            del config["series"][series_found]
    
    update_packs(config)
    config["packs"] = PACKS  # Backward compat
    save_config(config)
    
    # Auto-Sync (für Sicherheit, obwohl Autocomplete live ist)
    await tree.sync()
    
    # Delete channels in pack mode guilds
    deleted_count = 0
    updated_count = 0
    error_count = 0
    
    # Iterate through guild_configs/ directory instead of bot_config.json
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
                # Check if setup was run
                if "pack_channel_mode" not in guild_config:
                    continue
                
                pack_mode = guild_config.get("pack_channel_mode", "series")
                category = discord.utils.get(guild.categories, name=series_found)
                if not category:
                    # Just remove from map if category missing
                    if "pack_channel_map" in guild_config and pack_lower in guild_config["pack_channel_map"]:
                        del guild_config["pack_channel_map"][pack_lower]
                        updated_count += 1
                    continue
                
                if pack_mode == "pack":
                    # Delete individual pack channel
                    channel_name = f"{pack_lower}-pack"
                    target_channel = discord.utils.get(category.text_channels, name=channel_name)
                    if target_channel:
                        await target_channel.delete()
                        print(f"Deleted pack channel '{channel_name}' in '{series_found}' for guild {guild.name}")
                        deleted_count += 1
                    else:
                        updated_count += 1  # Just removed from map
                else:  # series mode: no channel deletion, just remove from map
                    updated_count += 1
                
                # Always remove from pack_channel_map
                if "pack_channel_map" in guild_config and pack_lower in guild_config["pack_channel_map"]:
                    del guild_config["pack_channel_map"][pack_lower]
                
                save_guild_config(guild_id_str, guild_config)
                
            except discord.Forbidden:
                error_msg = f"Permission error: Bot lacks perms to delete channels in guild {guild_id_str}"
                print(error_msg)
                await log_permission_warning_to_webhook(error_msg, guild_id=guild_id_str, command_name="removepack")
                error_count += 1
            except Exception as e:
                print(f"Error removing pack '{pack_name}' from guild {guild_id_str}: {e}")
                error_count += 1
    
    embed = discord.Embed(
        title="Pack entfernt & Channels Deleted/Updated",
        description=f"'{pack_name}' wurde aus {series_found} entfernt.\n"
                    f"Deleted channels in **{deleted_count}** guilds (pack mode).\n"
                    f"Updated maps in **{updated_count}** guilds (series mode).\n"
                    f"Errors in **{error_count}** guilds (check perms).\n"
                    f"**Aktuelle Packs:** {', '.join(PACKS)}",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

# New /removeseries command - deletes all channels in category and category itself in all guilds
@tree.command(name="removeseries", description="Removes a series globally and deletes all channels/category in all setup guilds (Owner only)")
@app_commands.describe(series_name="The name of the series to remove (e.g., 'B-Series')")
@app_commands.autocomplete(series_name=autocomplete_series)
async def removeseries(interaction: discord.Interaction, series_name: str):
    await interaction.response.defer(ephemeral=True)
    if not await owner_only(interaction):
        return
    
    if series_name not in config["series"]:
        embed = discord.Embed(
            title="Fehler",
            description=f"Series '{series_name}' nicht gefunden.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    # Remove from global config
    packs_to_remove = [p.lower() for p in config["series"][series_name]]
    del config["series"][series_name]
    update_packs(config)
    config["packs"] = PACKS  # Backward compat
    save_config(config)
    
    # Auto-Sync
    await tree.sync()
    
    # Delete channels and category in ALL guilds that have run setup
    deleted_channels_count = 0
    deleted_categories_count = 0
    updated_count = 0
    error_count = 0
    
    # Iterate through guild_configs/ directory instead of bot_config.json
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
                # Check if setup was run
                if "pack_channel_mode" not in guild_config:
                    continue
                
                category = discord.utils.get(guild.categories, name=series_name)
                if not category:
                    # Just remove packs from map if category missing
                    if "pack_channel_map" in guild_config:
                        removed_packs = [p for p in packs_to_remove if p in guild_config["pack_channel_map"]]
                        for p in removed_packs:
                            del guild_config["pack_channel_map"][p]
                        if removed_packs:
                            updated_count += 1
                    continue
                
                # Delete all text channels in the category
                text_channels = [ch for ch in category.text_channels if isinstance(ch, discord.TextChannel)]
                for channel in text_channels:
                    await channel.delete()
                    deleted_channels_count += 1
                    print(f"Deleted channel '{channel.name}' in '{series_name}' for guild {guild.name}")
                
                # Delete the category
                await category.delete()
                deleted_categories_count += 1
                print(f"Deleted category '{series_name}' for guild {guild.name}")
                
                # Remove packs from pack_channel_map
                if "pack_channel_map" in guild_config:
                    removed_packs = [p for p in packs_to_remove if p in guild_config["pack_channel_map"]]
                    for p in removed_packs:
                        del guild_config["pack_channel_map"][p]
                    if removed_packs:
                        updated_count += 1
                
                save_guild_config(guild_id_str, guild_config)
                
            except discord.Forbidden:
                error_msg = f"Permission error: Bot lacks perms to delete channels/category in guild {guild_id_str}"
                print(error_msg)
                await log_permission_warning_to_webhook(error_msg, guild_id=guild_id_str, command_name="removeseries")
                error_count += 1
            except Exception as e:
                print(f"Error removing series '{series_name}' from guild {guild_id_str}: {e}")
                error_count += 1
    
    embed = discord.Embed(
        title="Series entfernt & Channels/Categories Deleted",
        description=f"'{series_name}' wurde global entfernt.\n"
                    f"Deleted **{deleted_channels_count}** channels and **{deleted_categories_count}** categories.\n"
                    f"Updated maps in **{updated_count}** guilds.\n"
                    f"Errors in **{error_count}** guilds (check perms).\n"
                    f"**Aktuelle Series:** {', '.join(config['series'].keys())}",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

# Slash-Command: /setvalidatorrole
@tree.command(name="setvalidatorrole", description="Set the validator role for validation buttons")
@app_commands.describe(
    role="The role allowed to use validation buttons"
)
async def setvalidatorrole(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error",
            description="You need administrator permissions to use this command.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)
    
    guild_config = load_guild_config(guild_id)
    guild_config["validator_role_id"] = role.id
    save_guild_config(guild_id, guild_config)

    embed = discord.Embed(
        title="Validator Role Set",
        description=f"The validator role has been set to {role.mention}.",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

# Slash-Command: /setstatus
@tree.command(name="setstatus", description="Enable or disable traded buttons for Safe 4 Trade embeds")
@app_commands.describe(status="Set to True to enable traded buttons for Safe 4 Trade embeds; False to disable them")
async def setstatus(interaction: discord.Interaction, status: bool):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error",
            description="You need administrator permissions to use this command.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)

    guild_config = load_guild_config(guild_id)
    guild_config["validation_buttons_enabled"] = status
    save_guild_config(guild_id, guild_config)

    embed = discord.Embed(
        title="Traded Buttons Status Updated",
        description=f"Traded buttons for Safe 4 Trade embeds are now {'**enabled**' if status else '**disabled**'}. God pack embeds will always have validation buttons.",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

# Slash-Command: /setheartbeat
@tree.command(name="setheartbeat", description="Set the source and target channels for heartbeat stats")
@app_commands.describe(
    source_channel="The channel where heartbeat messages are posted",
    target_channel="The channel to post the updating heartbeat embed"
)
async def setheartbeat(interaction: discord.Interaction, source_channel: discord.TextChannel, target_channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error",
            description="You need administrator permissions to use this command.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)
    guild_config = load_guild_config(guild_id)
    guild_config["heartbeat_source_channel_id"] = source_channel.id
    guild_config["heartbeat_target_channel_id"] = target_channel.id
    
    embed = create_heartbeat_embed(guild_config)
    sent_message = await target_channel.send(embed=embed)
    guild_config["heartbeat_message_id"] = sent_message.id
    save_guild_config(guild_id, guild_config)
    
    response_embed = discord.Embed(
        title="Heartbeat Embed Configured",
        description=f"Source channel set to {source_channel.mention}. The heartbeat stats embed will update in {target_channel.mention}.",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=response_embed, ephemeral=True)

# Slash-Command: /stats
@tree.command(name="stats", description="Shows server validation and trade stats, optionally posts auto-updating embed")
@app_commands.describe(channel="Optional: Channel to post the auto-updating stats embed")
async def stats(interaction: discord.Interaction, channel: discord.TextChannel = None):
    await interaction.response.defer(ephemeral=False)
    guild_id = str(interaction.guild.id)
    guild_config = load_guild_config(guild_id)

    embed = create_stats_embed(guild_config)

    if channel:
        sent_message = await channel.send(embed=embed)
        guild_config["stats_channel_id"] = channel.id
        guild_config["stats_message_id"] = sent_message.id
        save_guild_config(guild_id, guild_config)
        response_embed = discord.Embed(
            title="Stats Embed Posted",
            description=f"The stats embed has been posted in {channel.mention} and will be automatically updated.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=response_embed, ephemeral=True)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)

# Slash-Command: /detailedstats
@tree.command(name="detailedstats", description="Shows detailed statistics for each filter, optionally posts an auto-updating embed in a channel")
@app_commands.describe(channel="Optional: The channel to post the auto-updating detailed stats embed")
async def detailedstats(interaction: discord.Interaction, channel: discord.TextChannel = None):
    await interaction.response.defer(ephemeral=False)
    guild_id = str(interaction.guild.id)
    guild_config = load_guild_config(guild_id)

    embed = create_detailed_stats_embed(guild_config)

    if channel:
        sent_message = await channel.send(embed=embed)
        guild_config["detailed_stats_channel_id"] = channel.id
        guild_config["detailed_stats_message_id"] = sent_message.id
        save_guild_config(guild_id, guild_config)
        response_embed = discord.Embed(
            title="Detailed Stats Embed Posted",
            description=f"The detailed stats embed has been posted in {channel.mention} and will be automatically updated.",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=response_embed, ephemeral=True)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)

# Slash-Command: /packstats
@tree.command(name="packstats", description="Shows pack statistics for this server, optionally posts an auto-updating embed")
@app_commands.describe(channel="Optional: The channel to post the auto-updating pack stats embed")
async def packstats(interaction: discord.Interaction, channel: discord.TextChannel = None):
    await interaction.response.defer(ephemeral=False)
    guild_id = str(interaction.guild.id)
    guild_config = load_guild_config(guild_id)

    embed = create_pack_stats_embed(guild_config)

    if channel:
        sent_message = await channel.send(embed=embed)
        guild_config["pack_stats_channel_id"] = channel.id
        guild_config["pack_stats_message_id"] = sent_message.id
        save_guild_config(guild_id, guild_config)
        response_embed = discord.Embed(
            title="Pack Stats Embed Posted",
            description=f"The pack stats embed has been posted in {channel.mention} and will be automatically updated.",
            color=discord.Color.teal()
        )
        await interaction.followup.send(embed=response_embed, ephemeral=True)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)

# Slash-Command: /pick4me
@tree.command(name="pick4me", description="Let fate decide which card you get!")
async def pick4me(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    options = [
        ("> Top Left", "wp/top-left.png"),
        ("> Top Middle", "wp/middle.png"),
        ("> Top Right", "wp/top-right.png"),
        ("> Bottom Left", "wp/bottom-left.png"),
        ("> Bottom Right", "wp/bottom-right.png")
    ]

    choice_text, image_path = random.choice(options)

    embed = discord.Embed(
        description=choice_text,
        color=discord.Color.green()
    )

    file = discord.File(image_path, filename="card.png")
    embed.set_image(url="attachment://card.png")

    await interaction.followup.send(embed=embed, file=file)        
        
        
# Angepasste /showfilters (mit Packs-Übersicht und Series-Gruppierung, fixed length issue)
@tree.command(name="showfilters", description="Shows all active filters for this server")
async def showfilters(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    guild_id = str(interaction.guild.id)
    guild_config = load_guild_config(guild_id)
    
    if not guild_config or (not guild_config.get("keyword_channel_map") and not guild_config.get("pack_channel_map")):
        embed = discord.Embed(
            title="No Filters Configured",
            description="There are no filters configured for this server.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=False)
        return

    keyword_channel_map = guild_config.get("keyword_channel_map", {})
    pack_channel_map = guild_config.get("pack_channel_map", {})
    pack_mode = guild_config.get("pack_channel_mode", "series")
    
    embed = discord.Embed(
        title="Active Filters",
        description=f"Here are the currently configured filters for this server (Pack Mode: {pack_mode.title()}).",
        color=discord.Color.blue()
    )

    # Filters field (updated to show channel lists)
    filter_list = []
    all_custom_sources = set()
    for keyword, filter_config in keyword_channel_map.items():
        channel = interaction.guild.get_channel(filter_config["channel_id"])
        channel_mention = channel.mention if channel else f"ID: {filter_config['channel_id']} (not found)"
        source_channel_ids = filter_config.get("source_channel_ids", [])
        if source_channel_ids:
            all_custom_sources.update(source_channel_ids)
            source_str = "Custom sources"
        else:
            source_str = "All channels"
        filter_list.append(f"**{keyword.title()}**: {channel_mention} (Sources: {source_str})")
    
    filter_value = "\n".join(filter_list) if filter_list else "No filters configured."
    filter_chunks = split_field_value(filter_value, field_name="Filters")
    for field_name, chunk in filter_chunks:
        embed.add_field(name=field_name, value=chunk, inline=False)

    # Pack Filters grouped by series (updated similarly)
    pack_list_by_series = {}
    for pack, pack_config in pack_channel_map.items():
        # Find series for this pack
        series_for_pack = next((s for s, packs_in_s in config["series"].items() if pack in [p.lower() for p in packs_in_s]), "Unassigned")
        
        if series_for_pack not in pack_list_by_series:
            pack_list_by_series[series_for_pack] = []
        
        channel = interaction.guild.get_channel(pack_config["channel_id"])
        channel_mention = channel.mention if channel else f"ID: {pack_config['channel_id']} (not found)"
        source_channel_ids = pack_config.get("source_channel_ids", [])
        if source_channel_ids:
            all_custom_sources.update(source_channel_ids)  # Collect for summary
            source_str = "Custom sources"
        else:
            source_str = "All channels"
        pack_list_by_series[series_for_pack].append(f"**{pack.title()}**: {channel_mention} (Sources: {source_str})")
    
    # Add fields for each series (unchanged)
    for series_name, packs_list in pack_list_by_series.items():
        value = "\n".join(packs_list) if packs_list else "No pack filters configured."
        pack_chunks = split_field_value(value, field_name=f"Pack Filters - {series_name}")
        for field_name, chunk in pack_chunks:
            embed.add_field(name=field_name, value=chunk, inline=False)

    godpack_ping = guild_config.get("godpack_ping")
    invgodpack_ping = guild_config.get("invgodpack_ping")
    safe_trade_ping = guild_config.get("safe_trade_ping")
    validator_role_id = guild_config.get("validator_role_id")
    validator_role = interaction.guild.get_role(validator_role_id) if validator_role_id else None
    
    embed.add_field(
        name="Pings",
        value=f"God Pack Ping: {f'<@&{godpack_ping}>' if godpack_ping else 'Not set'}\n"
              f"Invalid God Pack Ping: {f'<@&{invgodpack_ping}>' if invgodpack_ping else 'Not set'}\n"
              f"Safe for Trade Ping: {f'<@&{safe_trade_ping}>' if safe_trade_ping else 'Not set'}",
        inline=False
    )

    embed.add_field(
        name="Validator Role",
        value=f"{validator_role.mention if validator_role else 'Not set'}",
        inline=False
    )

    embed.add_field(
        name="Traded Buttons",
        value=f"{'**Enabled**' if guild_config.get('validation_buttons_enabled', False) else '**Disabled**'}",
        inline=False
    )

    heartbeat_source_id = guild_config.get("heartbeat_source_channel_id")
    heartbeat_target_id = guild_config.get("heartbeat_target_channel_id")
    heartbeat_source = interaction.guild.get_channel(heartbeat_source_id) if heartbeat_source_id else None
    heartbeat_target = interaction.guild.get_channel(heartbeat_target_id) if heartbeat_target_id else None
    embed.add_field(
        name="Heartbeat Source",
        value=f"{heartbeat_source.mention if heartbeat_source else 'Not set'}",
        inline=True
    )
    embed.add_field(
        name="Heartbeat Target",
        value=f"{heartbeat_target.mention if heartbeat_target else 'Not set'}",
        inline=True
    )

    # Neue Packs-Übersicht mit Series
    series_overview = "\n".join(f"**{s}**: {', '.join(packs)}" for s, packs in config["series"].items())
    series_chunks = split_field_value(series_overview, field_name="Globale Series & Packs")
    for field_name, chunk in series_chunks:
        embed.add_field(name=field_name, value=chunk, inline=False)

    # NEW: Add a summary field at the bottom for all unique custom sources
    if all_custom_sources:
        all_sources_list = sorted(list(all_custom_sources))  # Sort by ID for consistency
        source_summary = ", ".join([f"<#{sid}>" for sid in all_sources_list])
        source_chunks = split_field_value(source_summary, field_name="All Custom Source Channels")
        for field_name, chunk in source_chunks:
            embed.add_field(
                name=field_name,
                value=chunk,
                inline=False
            )
    else:
        embed.add_field(
            name="All Custom Source Channels",
            value="None (using all channels)",
            inline=False
        )

    # Optional: Update footer for even more visibility
    embed.set_footer(
        text=f"Total Custom Sources: {len(all_custom_sources) if all_custom_sources else 0} channels | Use /setfilter to update",
        icon_url="https://imgur.com/T0KX069.png"
    )

    await interaction.followup.send(embed=embed)

# Slash-Command: /meta
@tree.command(name="meta", description="Shows you current TCGP meta!")
async def meta(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    embed = discord.Embed(
        title="TCG POCKET - META DECKS",
        description="Websites which list with the current META Decks for TCGP",
        color=discord.Color.yellow()
    )
    embed.set_thumbnail(url="https://i.imgur.com/nBWsWgp.png")
    embed.add_field(name="**Websites:**", value="[Pokemon Zone](https://www.pokemon-zone.com/decks)\n[PTCGPOCKET](https://ptcgpocket.gg/)", inline=False)
    await interaction.followup.send(embed=embed)

# NEW: Create lifetime stats embed (aggregate from all guilds)
def create_lifetime_stats_embed():
    """Create embed with lifetime stats aggregated from ALL guild config files."""
    if DEBUG_LIFETIME_STATS:
        print(f"🔄 Creating lifetime stats embed...")
    
    total_godpacks = 0
    total_godpacks_valid = 0
    total_godpacks_invalid = 0
    total_trades = 0
    total_traded = 0
    # Use a dict that maps normalized lowercase names to (count, display_name)
    total_filter_stats = {}
    
    guild_count = 0
    active_guild_count = 0
    
    # Build a map of all known pack names (lowercase -> display_name from config)
    known_packs = {}
    for series_name, packs_in_series in config.get("series", {}).items():
        for pack in packs_in_series:
            known_packs[pack.lower()] = pack  # Map lowercase to original name
    
    # Aggregate stats from ALL guild config files in guild_configs/
    ensure_guild_config_dir()
    if os.path.exists(GUILD_CONFIG_DIR):
        for filename in os.listdir(GUILD_CONFIG_DIR):
            if filename.startswith("guild_") and filename.endswith(".json") and not filename.endswith(".bak"):
                try:
                    guild_id_str = filename.replace("guild_", "").replace(".json", "")
                    guild_id = int(guild_id_str)
                    
                    # Load the guild config
                    guild_config = load_guild_config(guild_id)
                    guild_count += 1
                    
                    # Check if guild has any stats
                    stats = guild_config.get("stats", {})
                    filter_stats_guild = guild_config.get("filter_stats", {})
                    
                    # Only count as "active" if has stats
                    if stats or filter_stats_guild:
                        active_guild_count += 1
                    
                    # God Packs stats
                    godpacks = stats.get("godpacks", {})
                    total_godpacks += godpacks.get("total", 0)
                    total_godpacks_valid += godpacks.get("valid", 0)
                    total_godpacks_invalid += godpacks.get("invalid", 0)
                    
                    # Trades stats
                    general = stats.get("general", {})
                    total_trades += general.get("total", 0)
                    total_traded += general.get("valid", 0)
                    
                    # Filter stats - normalize keys to lowercase to prevent duplicates
                    for keyword, count in filter_stats_guild.items():
                        # Normalize keyword to lowercase
                        keyword_normalized = keyword.lower().strip()
                        
                        # Aggregate by normalized key
                        if keyword_normalized in total_filter_stats:
                            total_filter_stats[keyword_normalized] += count
                        else:
                            total_filter_stats[keyword_normalized] = count
                            
                except (ValueError, json.JSONDecodeError):
                    continue
    
    if DEBUG_LIFETIME_STATS:
        print(f"  ✓ Loaded {guild_count} guilds, {active_guild_count} active")
        print(f"  ✓ Total found: {sum(total_filter_stats.values())}")
    
    # Create embed
    now_berlin = datetime.now(BERLIN_TZ)
    embed = discord.Embed(
        title="🌍 Lifetime Statistics (All Servers)",
        description=f"Global stats aggregated from **{guild_count}** total servers (with data on **{active_guild_count}**)",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url="https://i.imgur.com/pxqjVbO.png")
    
    # Overview
    embed.add_field(
        name="📊 Overall",
        value=f"Total Servers Configured: **{guild_count}**\n"
              f"Servers with Activity: **{active_guild_count}**\n"
              f"Total Found: **{sum(total_filter_stats.values())}**",
        inline=False
    )
    
    # God Packs section
    embed.add_field(
        name="🌟 God Packs (Global)",
        value=f"Total: **{total_godpacks}**\n"
              f"Valid: **{total_godpacks_valid}** ✅\n"
              f"Invalid: **{total_godpacks_invalid}** ❌",
        inline=False
    )
    
    # Safe 4 Trade section
    embed.add_field(
        name="✅ Safe 4 Trade (Global)",
        value=f"Total: **{total_trades}**\n"
              f"Traded: **{total_traded}**",
        inline=False
    )
    
    # Filter breakdown
    filter_list = []
    for keyword in ["one star", "three diamond", "four diamond ex", "gimmighoul", "shiny", "rainbow", "full art", "trainer"]:
        count = total_filter_stats.get(keyword, 0)
        filter_list.append(f"{keyword.title()}: **{count}**")
    
    if filter_list:
        embed.add_field(
            name="🎴 Safe 4 Trade Breakdown",
            value="\n".join(filter_list),
            inline=False
        )
    
    # Detection breakdown
    detection_list = []
    for keyword in ["crown", "immersive"]:
        count = total_filter_stats.get(keyword, 0)
        detection_list.append(f"{keyword.title()}: **{count}**")
    
    if detection_list:
        embed.add_field(
            name="🔍 Detection",
            value="\n".join(detection_list),
            inline=False
        )
    
    # Pack breakdown grouped by series - ALLE Series anzeigen (auch wenn 0 Count)
    pack_stats_by_series = {}
    
    # Zuerst alle Series initialisieren (mit leeren Listen)
    for series_name in config.get("series", {}).keys():
        pack_stats_by_series[series_name] = []
    
    # Dann nur die Packs anzeigen die in config.series definiert sind
    # Jeder Pack wird NUR EINMAL pro Serie angezeigt (verhindert Duplikate)
    for series_name, packs_in_series in config.get("series", {}).items():
        for pack in packs_in_series:
            pack_lower = pack.lower()
            # Get the count from total_filter_stats using the normalized key
            count = total_filter_stats.get(pack_lower, 0)
            pack_entry = f"{pack.title()}: **{count}**"
            pack_stats_by_series[series_name].append(pack_entry)
    
    # Zeige alle Series mit ihren Packs an
    for series_name, packs_list in sorted(pack_stats_by_series.items()):
        if packs_list:  # Nur wenn es Packs gibt
            value = "\n".join(packs_list)
            chunks = split_field_value(value, field_name=f"📦 {series_name} Packs")
            for field_name, chunk in chunks:
                embed.add_field(name=field_name, value=chunk, inline=False)
    
    embed.set_footer(
        text=f"Last updated: {now_berlin.strftime('%d.%m.%Y %H:%M:%S')} Berlin Time",
        icon_url="https://imgur.com/T0KX069.png"
    )
    
    if DEBUG_LIFETIME_STATS:
        print(f"  ✓ Embed created with timestamp: {now_berlin.strftime('%d.%m.%Y %H:%M:%S')}")
    
    return embed

# AUTO-UPDATE Background Task for Lifetime Stats
# NEW: /lifetimestats command (owner-only)
@tree.command(name="lifetimestats", description="Shows lifetime statistics across all servers (Owner only)")
@app_commands.describe(channel="Optional: The channel to post the auto-updating lifetime stats embed")
async def lifetimestats(interaction: discord.Interaction, channel: discord.TextChannel = None):
    await interaction.response.defer(ephemeral=False)
    if not await owner_only(interaction):
        return
    
    # Run embed creation in thread to avoid blocking event loop
    embed = await asyncio.to_thread(create_lifetime_stats_embed)
    
    if channel:
        # Send to specified channel
        sent_message = await channel.send(embed=embed)
        
        # Store message info for auto-update - Use INT IDs in dict
        message_key = f"{channel.guild.id}_{channel.id}_{sent_message.id}"
        LIFETIME_STATS_MESSAGES[message_key] = {
            "channel_id": int(channel.id),
            "message_id": int(sent_message.id),
            "guild_id": int(channel.guild.id),
            "posted_at": datetime.now(BERLIN_TZ)
        }
        
        # Save to file for persistence
        save_lifetime_stats_messages()
        
        if DEBUG_LIFETIME_STATS:
            print(f"📌 Lifetime Stats Command: Message registered for auto-update")
            print(f"   Guild: {channel.guild.id} | Channel: {channel.id} | Message: {sent_message.id}")
            print(f"   Stored in memory - Total tracked messages: {len(LIFETIME_STATS_MESSAGES)}")
        
        response_embed = discord.Embed(
            title="Lifetime Stats Embed Posted",
            description=f"The lifetime stats embed has been posted in {channel.mention} and will be automatically updated every minute.",
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=response_embed, ephemeral=True)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)

# /sync (bleibt gleich)
@tree.command(name="sync", description="Synchronisiert alle Slash-Commands neu (Owner only)")
async def sync(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not await owner_only(interaction):
        return
    
    try:
        synced = await tree.sync()
        embed = discord.Embed(
            title="Sync erfolgreich",
            description=f"{len(synced)} Commands synchronisiert. Packs-Änderungen sind jetzt live.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        print("Commands synced by owner.")
    except Exception as e:
        embed = discord.Embed(
            title="Sync-Fehler",
            description=f"Fehler beim Sync: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        print(f"Sync error: {e}")

# /createpackcategory - Create a new category for a specific pack with Save 4 Trade channels
@tree.command(name="createpackcategory", description="Create a category for a pack with Save 4 Trade channels (Admin only)")
@app_commands.autocomplete(pack=autocomplete_packs)
async def createpackcategory(interaction: discord.Interaction, pack: str):
    await interaction.response.defer(ephemeral=True)
    # Check admin permissions
    member = interaction.guild.get_member(interaction.user.id)
    if not member.guild_permissions.administrator:
        embed = discord.Embed(
            title="Error",
            description="You need administrator permissions to use this command.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    # Validate pack exists in config (most up-to-date source)
    pack_lower = pack.lower()
    all_packs = [p.lower() for series_packs in config.get("series", {}).values() for p in series_packs]
    if pack_lower not in all_packs:
        embed = discord.Embed(
            title="Error",
            description=f"Pack `{pack}` not found in the global pack list. Use `/addpack` to add it first.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    guild = interaction.guild
    guild_id = str(guild.id)
    guild_config = load_guild_config(guild_id)

    # Create category with pack name
    category_name = f"{pack.title()} - Save 4 Trade"
    category = discord.utils.get(guild.categories, name=category_name)
    
    if not category:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        try:
            category = await guild.create_category(category_name, overwrites=overwrites)
        except discord.Forbidden:
            embed = discord.Embed(
                title="Error",
                description="Bot lacks permissions to create categories. Please grant **Manage Channels** permission.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        except Exception as e:
            embed = discord.Embed(
                title="Error",
                description=f"Failed to create category: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

    # Create channels for each Save 4 Trade keyword
    save4trade_keywords = SAVE4TRADE_KEYWORDS
    created_channels = []
    
    for keyword in save4trade_keywords:
        channel_name = keyword.lower().replace(" ", "-")
        channel = discord.utils.get(category.text_channels, name=channel_name)
        
        if not channel:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            }
            try:
                channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
                created_channels.append(channel.mention)
            except Exception as e:
                print(f"Error creating channel {channel_name}: {e}")
                continue
        else:
            created_channels.append(f"{channel.mention} (existed)")

    # Update config to route pack messages to pack-specific channels
    if "pack_specific_categories" not in guild_config:
        guild_config["pack_specific_categories"] = {}
    
    # Store category and channel mapping for this pack
    guild_config["pack_specific_categories"][pack_lower] = {
        "category_id": category.id,
        "channels": {}
    }
    
    # Map each keyword to its channel in this category
    for keyword in save4trade_keywords:
        channel_name = keyword.lower().replace(" ", "-")
        channel = discord.utils.get(category.text_channels, name=channel_name)
        if channel:
            guild_config["pack_specific_categories"][pack_lower]["channels"][keyword.lower()] = channel.id

    save_guild_config(guild_id, guild_config)

    # Fetch and repost existing messages from source channels that mention this pack
    source_channel_ids = guild_config.get("default_source_channel_ids", [])
    reposted_count = 0
    
    if source_channel_ids:
        content_lower = pack.lower()
        keyword_channel_map = guild_config.get("keyword_channel_map", {})
        
        for source_channel_id in source_channel_ids:
            source_channel = bot.get_channel(source_channel_id)
            if not source_channel:
                continue
            
            try:
                # Fetch last 100 messages from source channel
                async for msg in source_channel.history(limit=100):
                    if msg.author.bot:  # Skip bot messages
                        continue
                    
                    message_content = msg.content.lower()
                    
                    # Check if pack is mentioned in message
                    if not re.search(r'\b' + re.escape(content_lower) + r'\b', message_content):
                        continue
                    
                    # Find matching Save 4 Trade keywords in this message
                    for keyword in SAVE4TRADE_KEYWORDS:
                        if keyword.lower() not in message_content:
                            continue
                        
                        # Get the pack-specific target channel
                        pack_channel_id = guild_config["pack_specific_categories"][pack_lower]["channels"].get(keyword.lower())
                        if not pack_channel_id:
                            continue
                        
                        target_channel = bot.get_channel(pack_channel_id)
                        if not target_channel:
                            continue
                        
                        # Create and send embed
                        custom_text = CUSTOM_EMBED_TEXT.get(keyword, msg.content)
                        message_link = f"https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}"
                        embed_color = EMBED_COLORS.get(keyword, discord.Color.blue())
                        
                        embed = discord.Embed(
                            title=LOCALE_TEXT["embed_title"].format(keyword=keyword.title()),
                            description=f"{custom_text}\n\n" +
                                        LOCALE_TEXT["embed_link_text"].format(link=message_link),
                            color=embed_color
                        )
                        
                        embed.set_author(
                            name=CUSTOM_AUTHOR_TEXT.get(keyword, LOCALE_TEXT["embed_author_name"]),
                            icon_url="https://imgur.com/T0KX069.png"
                        )
                        
                        embed.set_footer(
                            text="Forwarded by HELPER ¦ TCGP",
                            icon_url="https://imgur.com/T0KX069.png"
                        )
                        
                        thumbnail_url = EMBED_THUMBNAILS.get(keyword)
                        if thumbnail_url:
                            embed.set_thumbnail(url=thumbnail_url)
                        
                        # Attach images if available
                        image_attached = False
                        for attachment in msg.attachments:
                            if attachment.content_type and "image" in attachment.content_type and not image_attached:
                                embed.set_image(url=attachment.url)
                                image_attached = True
                        
                        try:
                            await target_channel.send(embed=embed)
                            reposted_count += 1
                        except Exception as e:
                            print(f"Error reposting message to {target_channel.name}: {e}")
                        
                        # Only post once per message (break on first keyword match)
                        break
            
            except Exception as e:
                print(f"Error fetching messages from source channel {source_channel_id}: {e}")

    # Success message
    embed = discord.Embed(
        title="✅ Pack Category Created",
        description=f"Successfully created category **{category_name}** with Save 4 Trade channels!",
        color=discord.Color.green()
    )
    embed.add_field(
        name="Pack",
        value=pack.title(),
        inline=True
    )
    embed.add_field(
        name="Channels Created",
        value="\n".join(created_channels[:10]) + (f"\n... and {len(created_channels)-10} more" if len(created_channels) > 10 else ""),
        inline=False
    )
    embed.add_field(
        name="Existing Messages Reposted",
        value=f"{reposted_count} message(s) from this pack were found and forwarded to the new channels.",
        inline=False
    )
    embed.set_footer(text="All Save 4 Trade messages from this pack will now be forwarded to these channels.")
    
    await interaction.followup.send(embed=embed, ephemeral=True)
    print(f"Created pack category '{category_name}' for {pack} in guild {guild.name} - Reposted {reposted_count} existing messages")

# NEW: Function to clean stale guild configs (bot removed from server)
def clean_stale_guilds():
    """Removes guild configs from bot_config.json if the bot is no longer in that guild."""
    stale_guilds = []
    for guild_id_str in list(config.keys()):
        if guild_id_str in ["series", "packs"]:  # Skip global keys
            continue
        try:
            guild = bot.get_guild(int(guild_id_str))
            if not guild:
                stale_guilds.append(guild_id_str)
        except ValueError:
            # Skip invalid guild IDs
            continue
    
    for guild_id_str in stale_guilds:
        del config[guild_id_str]
        print(f"Removed stale guild config for {guild_id_str} (bot removed from server)")
    
    if stale_guilds:
        save_config(config)
        print(f"Cleaned {len(stale_guilds)} stale guild configs from bot_config.json")

# NEW: Function to remove guild config duplicates from bot_config.json
def clean_config_duplicates():
    """Removes guild configs from bot_config.json if they already exist in guild_configs/"""
    duplicates = []
    for guild_id_str in list(config.keys()):
        if guild_id_str in ["series", "packs"]:  # Skip global keys
            continue
        try:
            # Check if this guild config exists in guild_configs/
            guild_config_file = os.path.join(GUILD_CONFIG_DIR, f"guild_{guild_id_str}.json")
            if os.path.exists(guild_config_file):
                duplicates.append(guild_id_str)
        except Exception:
            continue
    
    for guild_id_str in duplicates:
        del config[guild_id_str]
        print(f"✓ Removed duplicate guild config {guild_id_str} from bot_config.json (already in guild_configs/)")
    
    if duplicates:
        save_config(config)
        print(f"✅ Cleaned {len(duplicates)} duplicate guild configs from bot_config.json")

# Updated on_ready event with setup restoration on bot restart/update
# NEW: Dictionary to track missing configs per guild
missing_configs = {}  # Format: {guild_id: {"packs": set(), "filters": set(), "first_reported": time, "last_notified": time}}

async def notify_admin_of_missing_configs(guild_id, missing_packs, missing_filters):
    """Send admin a DM about missing pack/filter configs."""
    try:
        guild = bot.get_guild(int(guild_id))
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

@bot.event
async def on_ready():
    global LIFETIME_STATS_TASK_STARTED, LIFETIME_STATS_TASK
    
    bot.start_time = datetime.now(BERLIN_TZ)  # Track bot start time for uptime
    print(LOCALE_TEXT["bot_started"].format(bot_name=bot.user))
    await bot.change_presence(status=discord.Status.online, activity=discord.Game("Pokémon TCG Pocket"))
    await tree.sync()
    print("Slash commands synchronized.")
    
    # Load lifetime stats messages from file
    load_lifetime_stats_messages()
    
    # Start lifetime stats update task directly (simple approach)
    if not LIFETIME_STATS_TASK_STARTED:
        print("🚀 Creating Lifetime Stats Update Task...")
        LIFETIME_STATS_TASK_STARTED = True
        try:
            LIFETIME_STATS_TASK = asyncio.create_task(lifetime_stats_update_task(), name="lifetime_stats_update_task")
            print(f"✅ Lifetime Stats Task created successfully\n")
        except Exception as e:
            print(f"❌ FAILED to create Lifetime Stats Task: {e}")
            import traceback
            traceback.print_exc()
            LIFETIME_STATS_TASK_STARTED = False
    
    # Clean up bot_config.json
    print("🧹 Bereinige bot_config.json...")
    clean_stale_guilds()  # Remove guilds bot is no longer in
    clean_config_duplicates()  # Remove duplicate entries (already in guild_configs/)
    
    # Stelle sicher, dass alle Guilds eine Config-Datei haben (SYNCHRON - blockierend!)
    print("🔄 Initialisiere Guild-Configs...")
    ensure_guild_config_dir()
    guilds_initialized = 0
    for guild in bot.guilds:
        guild_config = load_guild_config(guild.id)
        # Wenn Config leer ist, erstelle Standard-Struktur
        if not guild_config or guild_config == {"packs": {}, "filters": {}, "channels": {}}:
            default_config = {
                "packs": {},
                "filters": {},
                "channels": {},
                "stats": {"godpacks": {"total": 0, "valid": 0, "invalid": 0}, "general": {"total": 0, "valid": 0}},
                "filter_stats": {},
                "keyword_channel_map": {},
                "pack_channel_map": {},
                "pack_channel_mode": "series"
            }
            save_guild_config_sync(guild.id, default_config)  # Synchron speichern!
            guilds_initialized += 1
    
    if guilds_initialized > 0:
        print(f"✓ {guilds_initialized} neue Server-Configs initialisiert (synchron)")
    print(f"✓ Alle {len(bot.guilds)} Guild-Configs geladen und bereit")
    
    # Start missing config notification task
    async def check_and_notify_missing_configs():
        while True:
            await asyncio.sleep(60)  # Check every 1 minute
            current_time = time.time()
            
            for guild_id, config_data in list(missing_configs.items()):
                if config_data["packs"] or config_data["filters"]:
                    # First notification after 30 minutes
                    if config_data["last_notified"] == 0 and (current_time - config_data.get("first_reported", current_time)) > 1800:
                        await notify_admin_of_missing_configs(guild_id, config_data["packs"], config_data["filters"])
                        config_data["last_notified"] = current_time
                    # Subsequent reminders every 12 hours
                    elif config_data["last_notified"] > 0 and (current_time - config_data["last_notified"]) > 43200:
                        await notify_admin_of_missing_configs(guild_id, config_data["packs"], config_data["filters"])
                        config_data["last_notified"] = current_time
    
    asyncio.create_task(check_and_notify_missing_configs())

    # Register persistent views - they'll auto-reconnect to messages on restart
    # (no need to update all messages anymore!)
    bot.add_view(GodPackValidationView(None, guild_id=None))
    bot.add_view(TradedView(None, guild_id=None))

    # DISABLED: Only restore setup for guilds that have explicitly configured it via /setup
    # await restore_setup_for_all_guilds()
    
    # Queue für Nachrichten-Wiederherstellung (now only for heartbeat messages)
    edit_queue = deque()
    
    # Heartbeat-Nachrichten sammeln (only heartbeat needs updating)
    # Iterate through guild_configs/ directory instead of bot_config.json
    ensure_guild_config_dir()
    if os.path.exists(GUILD_CONFIG_DIR):
        for config_file in os.listdir(GUILD_CONFIG_DIR):
            if not config_file.startswith("guild_") or not config_file.endswith(".json"):
                continue
            
            guild_id = config_file.replace("guild_", "").replace(".json", "")
            guild_config = load_guild_config(guild_id)
            
            if "heartbeat_message_id" in guild_config:
                edit_queue.append(("heartbeat", guild_id, guild_config["heartbeat_message_id"], {"channel_id": guild_config["heartbeat_target_channel_id"]}))
    
    # Queue mit Rate-Limit-Handling verarbeiten (simplified - only heartbeat messages)
    async def process_edit_queue():
        while edit_queue:
            edit_type, guild_id, message_id, data = edit_queue.popleft()
            channel_id = data["channel_id"]
            channel = bot.get_channel(int(channel_id))
            
            if not channel:
                print(f"Channel {channel_id} not found for heartbeat message {message_id}")
                guild_config = load_guild_config(guild_id)
                if "heartbeat_target_channel_id" in guild_config:
                    del guild_config["heartbeat_target_channel_id"]
                if "heartbeat_message_id" in guild_config:
                    del guild_config["heartbeat_message_id"]
                save_guild_config(guild_id, guild_config)
                continue
                
            try:
                if bot.is_closed():
                    print(f"Bot connection closed, stopping queue processing")
                    edit_queue.appendleft((edit_type, guild_id, message_id, data))
                    break
                
                message = await channel.fetch_message(int(message_id))
                guild_config = load_guild_config(guild_id)
                embed = create_heartbeat_embed(guild_config)
                await message.edit(embed=embed)
                if DEBUG_PACK_LOGS:
                    print(f"Restored heartbeat message {message_id} in channel {channel_id}")
                await asyncio.sleep(0.5)
                
            except discord.NotFound:
                if DEBUG_PACK_LOGS:
                    print(f"Heartbeat message {message_id} not found, removing reference")
                guild_config = load_guild_config(guild_id)
                if "heartbeat_target_channel_id" in guild_config:
                    del guild_config["heartbeat_target_channel_id"]
                if "heartbeat_message_id" in guild_config:
                    del guild_config["heartbeat_message_id"]
                save_guild_config(guild_id, guild_config)
            except RuntimeError as e:
                if "Session is closed" in str(e):
                    print(f"Session closed while processing heartbeat message {message_id}, stopping queue")
                    edit_queue.appendleft((edit_type, guild_id, message_id, data))
                    break
                else:
                    print(f"RuntimeError processing heartbeat message {message_id}: {e}")
            except discord.HTTPException as e:
                print(f"Error restoring heartbeat message {message_id}: {e}")
                if e.status == 429:
                    await asyncio.sleep(e.retry_after)
                    edit_queue.appendleft((edit_type, guild_id, message_id, data))
    
    # Queue-Verarbeitung ausführen
    await process_edit_queue()

    # Heartbeat-Monitor-Task starten (existing)
    async def heartbeat_monitor():
        while True:
            # Iterate through guild_configs/ directory
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
                            error_msg = f"Error in heartbeat monitor for guild {guild_id}: {e}"
                            print(error_msg)
                            await log_error_to_webhook(error_msg, guild_id=guild_id, command_name="heartbeat_monitor")
            await asyncio.sleep(300)  # Überprüfe alle 5 Minuten
            
    asyncio.create_task(heartbeat_monitor())
    
    # Lifetime Stats Monitor-Task starten (NEW)
    # REMOVED: lifetime_stats_monitor()
    # Reason: lifetime_stats is now stored per-guild in guild_configs/, not in global config
    # Each guild manages its own lifetime stats settings and updates

# NEW: Function to restore/recreate setup for all guilds on bot restart
async def restore_setup_for_all_guilds():
    """Restores categories, channels, and configs for all guilds on bot restart."""
    restored_guilds = 0
    error_count = 0
    config_error_guilds = []  # Track guilds with missing pack configs for batch summary if needed
    
    # Iterate through guild_configs/ directory instead of bot_config.json
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
                print(f"Restoring setup for guild {guild.name} ({guild_id_str})")
                missing_packs = await restore_guild_setup(guild, guild_config)  # Now returns list of missing packs
                if missing_packs:
                    config_error_guilds.append((guild, missing_packs))
                else:
                    restored_guilds += 1
            except discord.Forbidden as perm_error:
                # Permission error handling - send to separate webhook
                error_msg = f"Permission error restoring guild {guild_id_str}: {perm_error}"
                print(error_msg)
                await log_permission_warning_to_webhook(error_msg, guild_id=guild_id_str, command_name="restore_setup")
                error_count += 1
                try:
                    owner = guild.owner
                    if owner:
                        embed = discord.Embed(
                            title="⚠️ Bot Permission Error During Setup Restoration",
                            description=f"Hello {owner.mention},\n\n"
                                       f"The bot tried to restore your server setup (categories, channels, filters) on startup but encountered a permission error in **{guild.name}**:\n"
                                       f"**{str(perm_error)}**\n\n"
                                       f"Please ensure the bot has **Manage Channels** and **Manage Roles** permissions.\n"
                                       f"**Support:** [Discord Server](https://discord.gg/2zSUgWJyYJ)\n"
                                       f"You can re-run `/setup` in {guild.name} to fix this manually.\n\n"
                                       f"Thanks! – TCGP Helper Bot",
                            color=discord.Color.orange()
                        )
                        embed.set_footer(text="If you need help, contact the bot developer.")
                        await owner.send(embed=embed)
                        print(f"DM sent to owner of {guild_id_str}")
                        await asyncio.sleep(1)  # Rate-limit safety for multiple DMs
                except discord.Forbidden:
                    print(f"Owner of {guild_id_str} has DMs disabled; couldn't notify.")
                except Exception as dm_error:
                    print(f"Failed to DM owner of {guild_id_str}: {dm_error}")
            except Exception as e:
                error_msg = f"Error restoring guild {guild_id_str}: {e}"
                print(error_msg)
                await log_error_to_webhook(error_msg, guild_id=guild_id_str, command_name="restore_setup")
                error_count += 1
    
    # Handle config error DMs after the loop (to batch if many)
    for guild, missing_packs in config_error_guilds:
        try:
            owner = guild.owner
            if owner:
                missing_list = ", ".join(missing_packs)
                embed = discord.Embed(
                    title="⚠️ Missing Pack Configs Detected During Restoration",
                    description=f"Hello {owner.mention},\n\n"
                               f"In **{guild.name}**, the following packs have no channel mappings configured:\n"
                               f"**{missing_list}**\n\n"
                               f"This can cause 'No pack config found' errors when messages are processed.\n"
                               f"**Quick Fix:** Run `/setpackfilter [pack_name] [channel] [source_channels]` for each, or re-run `/setup` to auto-configure all.\n"
                               f"Example: `/setpackfilter deluxe deluxe-pack #s4t,#success` (creates channel and mapping automatically).\n"
                               f"**Support:** [Discord Server](https://discord.gg/2zSUgWJyYJ)\n\n"
                               f"Thanks! – TCGP Helper Bot",
                    color=discord.Color.orange()
                )
                embed.set_footer(text="Check /showfilters to verify configs afterward.")
                await owner.send(embed=embed)
                print(f"Config error DM sent to owner of {guild.id} for packs: {missing_list}")
                await asyncio.sleep(1)  # Rate-limit
        except discord.Forbidden:
            print(f"Owner of {guild.id} has DMs disabled; couldn't notify about config errors.")
        except Exception as dm_error:
            print(f"Failed to DM owner of {guild.id} about config errors: {dm_error}")
    
    print(f"Setup restoration complete: {restored_guilds} guilds restored, {error_count} errors, {len(config_error_guilds)} config warnings.")

# === UPDATED: restore_guild_setup with auto-rename ===
async def restore_guild_setup(guild, guild_config):
    """Restores categories, channels, and sources. Also renames old channels to new format."""
    missing_packs = []
    renamed_count = 0

    category_configs = {
        "Save 4 Trade": {
            "keywords": ["one star", "three diamond", "four diamond ex", "gimmighoul", "shiny", "rainbow", "full art", "trainer"],
            "channel_prefix": "save-4-trade-"
        },
        "God Packs": {
            "keywords": ["god pack", "invalid god pack"],
            "channel_prefix": "god-packs-"
        },
        "Detection": {
            "keywords": ["crown", "immersive"],
            "channel_prefix": "detection-"
        },
        "A-Series": {
            "series": "A-Series",
            "channel_name": "a-series-packs"
        },
        "B-Series": {
            "series": "B-Series",
            "channel_name": "b-series-packs"
        }
    }

    created_channels = {}
    for cat_name, cfg in category_configs.items():
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        category = discord.utils.get(guild.categories, name=cat_name)
        if not category:
            category = await guild.create_category(cat_name, overwrites=overwrites)
        created_channels[cat_name] = category

        if "keywords" in cfg:
            for keyword in cfg["keywords"]:
                clean_name = keyword.lower().replace(" ", "-").replace("invalid god pack", "invalid-god-pack")
                old_channel_name = f"{cfg['channel_prefix']}{clean_name}"
                channel_name = OLD_TO_NEW_CHANNEL_NAMES.get(old_channel_name, clean_name)

                channel = discord.utils.get(category.text_channels, name=channel_name)
                if not channel:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                    }
                    channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                    print(f"Created keyword channel '{channel.name}' in '{cat_name}'")
                else:
                    # Rename if old name
                    if channel.name == old_channel_name and channel.name != channel_name:
                        try:
                            await channel.edit(name=channel_name)
                            print(f"Renamed '{old_channel_name}' → '{channel_name}' in '{cat_name}'")
                            renamed_count += 1
                        except discord.Forbidden:
                            print(f"Missing perms to rename {old_channel_name}")
                        except discord.HTTPException as e:
                            print(f"Failed to rename {old_channel_name}: {e}")

                # Update map
                if "keyword_channel_map" not in guild_config:
                    guild_config["keyword_channel_map"] = {}
                guild_config["keyword_channel_map"][keyword.lower()] = {
                    "channel_id": channel.id,
                    "source_channel_ids": guild_config.get("default_source_channel_ids", [])
                }

        # Pack channels
        if "series" in cfg:
            series_name = cfg["series"]
            global_series_packs = config.get("series", {}).get(series_name, [])
            pack_mode = guild_config.get("pack_channel_mode", "series")
            category = created_channels[cat_name]

            if pack_mode == "series" and global_series_packs:
                channel_name = f"{series_name.lower().replace(' ', '-')}-packs"
                channel = discord.utils.get(category.text_channels, name=channel_name)
                if not channel:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                    }
                    channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                for pack in global_series_packs:
                    if "pack_channel_map" not in guild_config:
                        guild_config["pack_channel_map"] = {}
                    guild_config["pack_channel_map"][pack.lower()] = {
                        "channel_id": channel.id,
                        "source_channel_ids": guild_config.get("default_source_channel_ids", [])
                    }
            else:
                for pack in global_series_packs:
                    channel_name = f"{pack.lower()}-pack"
                    channel = discord.utils.get(category.text_channels, name=channel_name)
                    if not channel:
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                        }
                        channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                    if "pack_channel_map" not in guild_config:
                        guild_config["pack_channel_map"] = {}
                    guild_config["pack_channel_map"][pack.lower()] = {
                        "channel_id": channel.id,
                        "source_channel_ids": guild_config.get("default_source_channel_ids", [])
                    }

    # Check missing packs
    if "pack_channel_map" not in guild_config:
        guild_config["pack_channel_map"] = {}
    for pack in PACKS:
        if pack.lower() not in guild_config["pack_channel_map"]:
            missing_packs.append(pack.title())

    if "default_source_channel_ids" not in guild_config:
        guild_config["default_source_channel_ids"] = []

    save_guild_config(str(guild.id), guild_config)
    print(f"Restored setup for {guild.name}. Renamed {renamed_count} channels. Missing packs: {missing_packs}")
    return missing_packs

# === DEVELOPER COMMANDS - PREFIX BASED ===

class DevCommandView(discord.ui.View):
    """View mit Buttons für Dev Commands"""
    def __init__(self, owner_id):
        super().__init__(timeout=300)
        self.owner_id = owner_id
    
    @discord.ui.button(label="🔄 Bot Restart", style=discord.ButtonStyle.danger, emoji="🔄")
    async def restart_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Du darfst das nicht!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🔄 Bot wird neu gestartet...",
            description="Der Bot startet in 3 Sekunden neu.",
            color=discord.Color.orange()
        )
        await interaction.response.defer()
        await interaction.followup.send(embed=embed)
        
        # Restart after 3 seconds
        await asyncio.sleep(3)
        import os
        os.execv(sys.executable, ['python'] + sys.argv)
    
    @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.primary, emoji="📊")
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Du darfst das nicht!", ephemeral=True)
            return
        
        # Sammle Bot-Stats
        guild_count = len(bot.guilds)
        user_count = sum(len(g.members) for g in bot.guilds)
        uptime = datetime.now(BERLIN_TZ) - bot.start_time if hasattr(bot, 'start_time') else "Unknown"
        
        config_file_size = os.path.getsize(CONFIG_FILE) if os.path.exists(CONFIG_FILE) else 0
        guild_configs_count = len([f for f in os.listdir(GUILD_CONFIG_DIR) if f.endswith('.json')]) if os.path.exists(GUILD_CONFIG_DIR) else 0
        
        embed = discord.Embed(
            title="📊 Bot Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.now(BERLIN_TZ)
        )
        embed.add_field(name="🏢 Guilds", value=f"`{guild_count}`", inline=True)
        embed.add_field(name="👥 Users", value=f"`{user_count}`", inline=True)
        embed.add_field(name="⏱️ Uptime", value=f"`{uptime}`", inline=True)
        embed.add_field(name="💾 Config File Size", value=f"`{config_file_size:,} bytes`", inline=True)
        embed.add_field(name="📁 Guild Config Files", value=f"`{guild_configs_count}`", inline=True)
        embed.add_field(name="📦 Packs", value=f"`{len(PACKS)}`", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🐛 Errors", style=discord.ButtonStyle.secondary, emoji="🐛")
    async def errors_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Du darfst das nicht!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🐛 Recent Errors",
            description="Fehler werden an den Error-Webhook gepostet.\nSchau im Error-Channel nach!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🔍 Config Check", style=discord.ButtonStyle.success, emoji="🔍")
    async def config_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Du darfst das nicht!", ephemeral=True)
            return
        
        # Überprüfe Config-Integrität
        errors = []
        
        # Prüfe bot_config.json
        if not os.path.exists(CONFIG_FILE):
            errors.append("❌ bot_config.json nicht gefunden")
        else:
            try:
                with open(CONFIG_FILE, "r") as f:
                    test_config = json.load(f)
                    if "series" not in test_config:
                        errors.append("⚠️ 'series' Key fehlt in bot_config.json")
                    if "packs" not in test_config:
                        errors.append("⚠️ 'packs' Key fehlt in bot_config.json")
            except json.JSONDecodeError as e:
                errors.append(f"❌ bot_config.json ist korrupt: {e}")
        
        # Prüfe guild_configs/
        if os.path.exists(GUILD_CONFIG_DIR):
            guild_files = [f for f in os.listdir(GUILD_CONFIG_DIR) if f.endswith('.json')]
            for gf in guild_files[:5]:  # Nur erste 5 prüfen
                try:
                    with open(os.path.join(GUILD_CONFIG_DIR, gf), "r") as f:
                        json.load(f)
                except json.JSONDecodeError:
                    errors.append(f"❌ {gf} ist korrupt")
        
        if errors:
            error_text = "\n".join(errors)
            embed = discord.Embed(
                title="❌ Config Errors gefunden",
                description=error_text,
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="✅ Config ist sauber",
                description="Keine Fehler gefunden!",
                color=discord.Color.green()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Handler für Prefix Commands
@bot.event
async def on_message(message):
    # === DEVELOPER COMMANDS (Prefix-based) ===
    if message.content.startswith("-help"):
        if message.author.id != OWNER_ID:
            await message.reply("❌ Nur der Bot-Owner kann das nutzen!", mention_author=False)
            return
        
        embed = discord.Embed(
            title="🔧 Developer Commands",
            description="Verwende die Buttons unten um Dev-Funktionen zu steuern.",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="🔄 Bot Restart",
            value="Startet den Bot neu",
            inline=False
        )
        embed.add_field(
            name="📊 Stats",
            value="Zeigt Bot-Statistiken (Guilds, Users, Uptime, etc.)",
            inline=False
        )
        embed.add_field(
            name="🐛 Errors",
            value="Zeigt wo Fehler gepostet werden",
            inline=False
        )
        embed.add_field(
            name="🔍 Config Check",
            value="Überprüft Integrität der Config-Dateien",
            inline=False
        )
        embed.set_footer(text=f"Nur {message.author.name} kann diese Buttons nutzen")
        
        view = DevCommandView(OWNER_ID)
        await message.reply(embed=embed, view=view, mention_author=False)
        return
    
    # Normale Message-Verarbeitung (Pack-Filter-System)
    if message.author == bot.user:
        return


    guild_id = str(message.guild.id)
    guild_config = load_guild_config(guild_id)
    keyword_channel_map = guild_config.get("keyword_channel_map", {})
    pack_channel_map = guild_config.get("pack_channel_map", {})
    validation_buttons_enabled = guild_config.get("validation_buttons_enabled", False)

    content_lower = message.content.lower()
    KEYWORDS_PRIORITY = list(CUSTOM_EMBED_TEXT.keys())

    # Track whether any keyword was processed to avoid duplicate processing
    processed_keywords = set()

    for keyword in KEYWORDS_PRIORITY:
        # Skip if keyword was already processed
        if keyword in processed_keywords:
            continue

        # Special handling for "shiny" to match "Shiny found" exactly
        
        # Special case: skip "god pack" if "invalid god pack" is present
        if keyword == "god pack" and "invalid god pack" in content_lower:
            continue
        # Check for exact keyword match (case-insensitive) for other keywords
        if keyword.lower() not in content_lower:
            continue

        # Mark keyword as processed
        processed_keywords.add(keyword)

        filter_config = keyword_channel_map.get(keyword.lower())
        if not filter_config:
            # Track missing filter config
            if guild_id not in missing_configs:
                missing_configs[guild_id] = {"packs": set(), "filters": set(), "first_reported": time.time(), "last_notified": 0}
            missing_configs[guild_id]["filters"].add(keyword)
            print(f"No filter config found for keyword: {keyword}")
            continue

        target_channel_id = filter_config.get("channel_id")
        source_channel_ids = filter_config.get("source_channel_ids") or guild_config.get("default_source_channel_ids", [])
        
        # Skip if the message is not from the configured source channels (if set)
        if source_channel_ids and message.channel.id not in source_channel_ids:
            print(f"Message channel {message.channel.id} does not match source channels {source_channel_ids} for keyword {keyword}")
            continue

        # Check if this is a Save 4 Trade keyword AND if there's a pack-specific category
        pack_specific_target = None
        if keyword.lower() in SAVE4TRADE_KEYWORDS:
            pack_specific_categories = guild_config.get("pack_specific_categories", {})
            # Check which pack is mentioned in the message (use config series for most up-to-date list)
            all_config_packs = [p for series_packs in config.get("series", {}).values() for p in series_packs]
            for pack in all_config_packs:
                if re.search(r'\b' + re.escape(pack.lower()) + r'\b', content_lower):
                    # Check if there's a pack-specific category for this pack
                    if pack.lower() in pack_specific_categories:
                        pack_category_config = pack_specific_categories[pack.lower()]
                        pack_channel_id = pack_category_config.get("channels", {}).get(keyword.lower())
                        if pack_channel_id:
                            pack_specific_channel = bot.get_channel(pack_channel_id)
                            if pack_specific_channel:
                                pack_specific_target = pack_specific_channel
                                if DEBUG_PACK_LOGS:
                                    print(f"Routing '{keyword}' from pack '{pack}' to pack-specific channel {pack_specific_channel.name}")
                                break

        # Use pack-specific target if found, otherwise use default
        target_channel = pack_specific_target if pack_specific_target else bot.get_channel(target_channel_id)
        
        if not target_channel:
            if DEBUG_PACK_LOGS:
                print(f"Target channel {target_channel_id} not found for keyword {keyword}")
            continue

        custom_text = CUSTOM_EMBED_TEXT.get(keyword, message.content)
        message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
        embed_color = EMBED_COLORS.get(keyword, discord.Color.blue())

        embed = discord.Embed(
            title=LOCALE_TEXT["embed_title"].format(keyword=keyword.title()),
            description=f"{custom_text}\n\n" +
                        LOCALE_TEXT["embed_link_text"].format(link=message_link),
            color=embed_color
        )

        embed.set_author(
            name=CUSTOM_AUTHOR_TEXT.get(keyword, LOCALE_TEXT["embed_author_name"]),
            icon_url="https://imgur.com/T0KX069.png"
        )

        embed.set_footer(
            text="Forwarded by HELPER ¦ TCGP",
            icon_url="https://imgur.com/T0KX069.png"
        )

        thumbnail_url = EMBED_THUMBNAILS.get(keyword)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        image_attached = False
        for attachment in message.attachments:
            if attachment.content_type and "image" in attachment.content_type and not image_attached:
                embed.set_image(url=attachment.url)
                image_attached = True

        godpack_ping = guild_config.get("godpack_ping")
        invgodpack_ping = guild_config.get("invgodpack_ping")
        safe_trade_ping = guild_config.get("safe_trade_ping")

        view = None
        if 'stats' not in guild_config:
            guild_config['stats'] = {
                'godpacks': {'total': 0, 'valid': 0, 'invalid': 0},
                'general': {'total': 0, 'valid': 0, 'invalid': 0}
            }
        if keyword == "god pack":
            view = GodPackValidationView(embed, guild_id=guild_id)
            guild_config['stats']['godpacks']['total'] += 1
            if 'filter_stats' not in guild_config:
                guild_config['filter_stats'] = {key: 0 for key in CUSTOM_EMBED_TEXT.keys()}
            guild_config['filter_stats']['god pack'] = guild_config['filter_stats'].get('god pack', 0) + 1
        elif validation_buttons_enabled and keyword in SAVE4TRADE_KEYWORDS:
            view = TradedView(embed, guild_id=guild_id)
            guild_config['stats']['general']['total'] += 1
            if 'filter_stats' not in guild_config:
                guild_config['filter_stats'] = {key: 0 for key in CUSTOM_EMBED_TEXT.keys()}
            guild_config['filter_stats'][keyword] = guild_config['filter_stats'].get(keyword, 0) + 1
        else:
            if 'filter_stats' not in guild_config:
                guild_config['filter_stats'] = {key: 0 for key in CUSTOM_EMBED_TEXT.keys()}
            guild_config['filter_stats'][keyword] = guild_config['filter_stats'].get(keyword, 0) + 1

        save_guild_config(guild_id, guild_config)
        await update_stats_message(guild_id)
        await update_detailed_stats_message(guild_id)

        try:
            sent_message = await target_channel.send(embed=embed, view=view)
            if DEBUG_PACK_LOGS:
                print(f"Sent embed for keyword '{keyword}' to channel {target_channel_id}")
        except Exception as e:
            if DEBUG_PACK_LOGS:
                print(f"Error sending embed for keyword '{keyword}' to channel {target_channel_id}: {e}")
            continue

        if isinstance(view, (GodPackValidationView, TradedView)):
            view.original_message = sent_message
            if "validation_messages" not in guild_config:
                guild_config["validation_messages"] = {}
            view_type = "godpack" if keyword == "god pack" else "traded"
            guild_config["validation_messages"][str(sent_message.id)] = {
                "channel_id": str(target_channel.id),
                "view_type": view_type
            }
            save_guild_config(guild_id, guild_config)
            save_config(config)

        if keyword == "god pack" and godpack_ping:
            await target_channel.send(f"<@&{godpack_ping}>")
        if keyword == "invalid god pack" and invgodpack_ping:
            await target_channel.send(f"<@&{invgodpack_ping}>")
        if keyword in ["one star", "three diamond", "four diamond ex", "crown"] and safe_trade_ping:
            await target_channel.send(f"<@&{safe_trade_ping}>")

    # Pack-Filter verarbeiten
    processed_packs = set()
    for pack in PACKS:
        if pack in processed_packs:
            continue

        # Use whole-word matching to avoid substring issues like "mew" in "mewtwo"
        if re.search(r'\b' + re.escape(pack.lower()) + r'\b', content_lower):
            processed_packs.add(pack)

            pack_config = pack_channel_map.get(pack.lower())
            if not pack_config:
                # Track missing pack config
                if guild_id not in missing_configs:
                    missing_configs[guild_id] = {"packs": set(), "filters": set(), "first_reported": time.time(), "last_notified": 0}
                missing_configs[guild_id]["packs"].add(pack)
                print(f"No pack config found for pack: {pack}")
                continue

            target_channel_id = pack_config.get("channel_id")
            source_channel_ids = pack_config.get("source_channel_ids") or guild_config.get("default_source_channel_ids", [])

            if source_channel_ids and message.channel.id not in source_channel_ids:
                print(f"Message channel {message.channel.id} not in source channels {source_channel_ids} for pack {pack}")
                continue

            target_channel = bot.get_channel(target_channel_id)
            if not target_channel:
                print(f"Target channel {target_channel_id} not found for pack {pack}")
                continue

            custom_text = f"A {pack.title()} pack was opened!"
            message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
            embed_color = discord.Color.blue()

            embed = discord.Embed(
                title=f"🔍 Opened: {pack.title()} Pack",
                description=f"{custom_text}\n\n" +
                            LOCALE_TEXT["embed_link_text"].format(link=message_link),
                color=embed_color
            )

            embed.set_author(
                name=LOCALE_TEXT["embed_author_name"],
                icon_url="https://imgur.com/T0KX069.png"
            )

            embed.set_footer(
                text="Forwarded by HELPER ¦ TCGP",
                icon_url="https://imgur.com/T0KX069.png"
            )

            image_attached = False
            for attachment in message.attachments:
                if attachment.content_type and "image" in attachment.content_type and not image_attached:
                    embed.set_image(url=attachment.url)
                    image_attached = True

            if 'filter_stats' not in guild_config:
                guild_config['filter_stats'] = {}
            guild_config['filter_stats'][pack] = guild_config['filter_stats'].get(pack, 0) + 1

            save_guild_config(guild_id, guild_config)
            await update_pack_stats_message(guild_id)

            try:
                await target_channel.send(embed=embed)
                if DEBUG_PACK_LOGS:
                    print(f"Sent embed for pack '{pack}' to channel {target_channel_id}")
            except Exception as e:
                if DEBUG_PACK_LOGS:
                    print(f"Error sending embed for pack '{pack}' to channel {target_channel_id}: {e}")

    # Heartbeat processing
    if "heartbeat_source_channel_id" in guild_config and guild_config["heartbeat_source_channel_id"] == message.channel.id:
        if message.content.startswith("Heartbeat"):
            content = message.content
            online_match = re.search(r"Online: (.*)", content)
            offline_match = re.search(r"Offline: (.*)", content)
            time_match = re.search(r"Time: (\d+m)", content)
            packs_match = re.search(r"Packs: (\d+)", content)
            avg_match = re.search(r"Avg: ([\d.]+) packs/min", content)
            version_match = re.search(r"Version: (.*)", content)
            type_match = re.search(r"Type: (.*)", content)
            opening_match = re.search(r"Opening: (.*)", content)

            heartbeat_data = {}
            if online_match:
                online_str = online_match.group(1).strip()
                if online_str.lower() != "none":
                    heartbeat_data["online"] = [x.strip() for x in online_str.split(",") if x.strip()]
                else:
                    heartbeat_data["online"] = []
            if offline_match:
                offline_str = offline_match.group(1).strip()
                if offline_str.lower() != "none":
                    heartbeat_data["offline"] = [x.strip() for x in offline_str.split(",") if x.strip()]
                else:
                    heartbeat_data["offline"] = []
            if time_match:
                heartbeat_data["time"] = time_match.group(1)
            if packs_match:
                heartbeat_data["packs"] = packs_match.group(1)
            if avg_match:
                heartbeat_data["avg"] = avg_match.group(1)
            if version_match:
                heartbeat_data["version"] = version_match.group(1).strip()
            if type_match:
                heartbeat_data["type"] = type_match.group(1).strip()
            if opening_match:
                opening_str = opening_match.group(1).strip()
                heartbeat_data["opening"] = [x.strip() for x in opening_str.split(",") if x.strip()]

            if heartbeat_data:
                heartbeat_data["last_update"] = datetime.now(BERLIN_TZ).isoformat()  # TZ-aware Timestamp
                guild_config["heartbeat_data"] = heartbeat_data
                save_guild_config(guild_id, guild_config)
                await update_heartbeat_message(guild_id)

# Improved /help command (with categories and better formatting)
@tree.command(name="help", description="Shows an overview of all bot commands")
async def help(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    embed = discord.Embed(
        title="🤖 Bot Commands Overview",
        description="Here's a list of all available commands, grouped by category. **Pro Tip:** Try /meta for some fun!",
        color=discord.Color.orange()
    )
    embed.set_thumbnail(url="https://i.imgur.com/T0KX069.png")
    
    # Category 1: Fun & Meta
    fun_commands = (
        "**/meta** – Current TCGP meta decks (links to guides)\n"
        "**/pick4me** – Decides for you on a wonder pick\n"

    )
    embed.add_field(
        name="🎮 Fun & Meta",
        value=fun_commands,
        inline=False
    )
    
    # Category 2: Filter Setup (Admin)
    filter_commands = (
		"**/setup** – Setup the whole Discord Bot with one command\n"
        "**/setfilter** – Configure filter for cards\n"
        "**/setpackfilter** – Set up pack filters\n"
        "**/setpackmode** – Choose pack channel mode (series or per pack)\n"
        "**/createpackcategory** – Create a pack-specific category with Save 4 Trade channels\n"
        "**/clearfilters** – Clear all filters (by type)\n"
        "**/removefilter** – Remove a single filter\n"
        "**/removepackfilter** – Remove a pack filter\n"
        "**/showfilters** – Show all active filters"
    )
    embed.add_field(
        name="⚙️ Filter Setup (Admin)",
        value=filter_commands,
        inline=False
    )
    
    # Category 3: Validation (Admin)
    admin_commands = (
        "**/setstatus** – Enable/disable traded buttons (for Safe 4 Trade)\n"
        "**/setvalidatorrole** – Set role for validators\n"
        "**/setpingroles** – Set ping roles for god pack, invalid, or safe trade"
    )
    embed.add_field(
        name="🔒 Validation (Admin)",
        value=admin_commands,
        inline=False
    )
    
    # Category 4: Statistics
    stats_commands = (
        "**/stats** – Server stats (validation/trade)\n"
        "**/detailedstats** – Detailed filter stats\n"
        "**/packstats** – Pack-specific stats\n"
        "**/setheartbeat** – Set up heartbeat monitor"
    )
    embed.add_field(
        name="📊 Statistics",
        value=stats_commands,
        inline=False
    )
    
    # Category 5: Dev-Only (short, since owner-only)
    dev_commands = (
        "**/lifetimestats** – Global stats from all servers\n"
        "**/addseries** – Add a new series for packs\n"
        "**/addpack** – Add pack to a series\n"
        "**/removepack** – Remove a pack\n"
        "**/removeseries** – Remove a series and delete channels/category\n"
        "**/sync** – Resync commands"
    )
    embed.add_field(
        name="🔧 Dev Commands (Owner only)",
        value=dev_commands,
        inline=False
    )
    
    # Support & Info
    support_info = (
        f"**Support:** [Discord Server](https://discord.gg/X5YKZBh9xV)\n"
        f"**GitHub:** [Repository](https://github.com/SimpliAj/HELPER-TCGP)\n"
        f"**Status:** Active in {len(bot.guilds)} servers\n"
        f"**Developer:** <@{OWNER_ID}>"
    )
    embed.add_field(
        name="ℹ️ Support & Info",
        value=support_info,
        inline=False
    )
    
    embed.set_footer(
        text="Need more help? Ping in the support channel!",
        icon_url="https://cdn.discordapp.com/avatars/{OWNER_ID}/a2fdd22758af30821f503ea329a31fe8.webp?size=1024"
    )
    
    await interaction.followup.send(embed=embed, ephemeral=False)  # Public visibility for easy sharing

# DUPLICATE (Removed): clean_stale_guilds was already defined earlier
# This duplicate at the end of file is removed to avoid redefinition

# Starte den Bot
load_dotenv()
bot.run(os.getenv("TOKEN"))