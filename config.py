import os
import json
import copy
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

# Thread-safe lock for config saves
config_save_lock = threading.Lock()

# Pfad zur Konfigurationsdatei
CONFIG_FILE = "bot_config.json"

# Guild-Config System
GUILD_CONFIG_DIR = "guild_configs"

# Globale Variablen (werden später geladen)
OWNER_ID = None
BERLIN_TZ = None
PACKS = []

def load_config():
    """Load config from bot_config.json. Automatically extracts any guild data to separate files."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                
                # AUTO-CLEANUP: Extract any guild IDs that shouldn't be here
                guild_ids_found = []
                for key in list(config.keys()):
                    if key not in ["series", "packs", "error_webhook_url", "permission_warning_webhook_url", "owner_id", "timezone"]:
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
    """Update global PACKS list from config."""
    global PACKS
    PACKS = [p for sublist in config["series"].values() for p in sublist]

def save_config(config):
    """Save config to bot_config.json (runs in background thread). Auto-filters out any guild data."""
    def _save():
        # Use lock to prevent multiple threads from saving simultaneously
        with config_save_lock:
            try:
                # DEEP COPY to prevent race conditions from concurrent modifications
                config_copy = copy.deepcopy(config)
                
                # AUTO-FILTER: Remove any guild IDs before saving (SAFETY NET)
                keys_to_remove = []
                for key in list(config_copy.keys()):
                    if key not in ["series", "packs", "error_webhook_url", "permission_warning_webhook_url", "owner_id", "timezone"]:
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

def ensure_guild_config_dir():
    """Stelle sicher, dass der guild_configs Ordner existiert."""
    if not os.path.exists(GUILD_CONFIG_DIR):
        os.makedirs(GUILD_CONFIG_DIR)

def get_guild_config_path(guild_id):
    """Gib den Pfad zur Config-Datei eines Servers zurück."""
    return os.path.join(GUILD_CONFIG_DIR, f"guild_{guild_id}.json")

def load_guild_config(guild_id):
    """Lade die Config für einen spezifischen Server."""
    ensure_guild_config_dir()
    config_path = get_guild_config_path(guild_id)
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"Guild config corrupted for {guild_id}, returning empty config")
            return {"packs": {}, "filters": {}, "channels": {}}
    
    # Neue Server bekommen leere Config
    return {"packs": {}, "filters": {}, "channels": {}}

def save_guild_config(guild_id, guild_config):
    """Speichere die Config für einen spezifischen Server (thread-safe, asynchron)."""
    def _save():
        with config_save_lock:
            ensure_guild_config_dir()
            config_path = get_guild_config_path(guild_id)
            
            try:
                config_copy = copy.deepcopy(guild_config)
                with open(config_path, "w") as f:
                    json.dump(config_copy, f, indent=4)
            except Exception as e:
                print(f"Error saving guild config for {guild_id}: {e}")
    
    threading.Thread(target=_save, daemon=True).start()

def save_guild_config_sync(guild_id, guild_config):
    """Speichere die Config für einen spezifischen Server SYNCHRON (blocking)."""
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
        if guild_id_str in ["series", "packs", "error_webhook_url", "permission_warning_webhook_url", "owner_id", "timezone"]:
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

def final_cleanup_config(config):
    """Final synchrone Cleanup um sicherzustellen dass nur globale Daten bleiben."""
    # Globale Config-Keys die behalten werden sollen
    ALLOWED_GLOBAL_KEYS = ["series", "packs", "error_webhook_url", "permission_warning_webhook_url", "owner_id", "timezone"]
    
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
