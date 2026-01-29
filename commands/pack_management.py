"""
Pack Management Commands: addseries, addpack, removepack, removeseries (Owner only)
Auto-creates/deletes channels in all setup guilds
"""
import discord
from discord import app_commands
from discord.ext import commands
import os
from config import load_guild_config, save_guild_config, load_config, save_config, ensure_guild_config_dir, GUILD_CONFIG_DIR
from webhooks import log_error_to_webhook, log_permission_warning_to_webhook


# Autocomplete Functions
async def autocomplete_packs(interaction: discord.Interaction, current: str):
    """Autocomplete für Packs."""
    packs = interaction.client.config.get("packs", [])
    choices = [app_commands.Choice(name=p.title(), value=p) for p in packs[:25]]
    if not current:
        return choices
    return [c for c in choices if current.lower() in c.value.lower()][:25]


async def autocomplete_series(interaction: discord.Interaction, current: str):
    """Autocomplete für Series."""
    series_names = list(interaction.client.config.get("series", {}).keys())
    choices = [app_commands.Choice(name=s, value=s) for s in series_names]
    if not current:
        return choices[:25]
    return [app_commands.Choice(name=s, value=s) for s in series_names if current.lower() in s.lower()][:25]


async def owner_only(interaction: discord.Interaction) -> bool:
    """Check if user is owner."""
    if interaction.user.id != interaction.client.OWNER_ID:
        embed = discord.Embed(
            title="Error",
            description="This command is only available to the bot owner.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return False
    return True


class PackManagementCommands(commands.Cog):
    def __init__(self, bot, config, OWNER_ID):
        self.bot = bot
        self.config = config
        self.OWNER_ID = OWNER_ID
    
    @app_commands.command(name="addseries", description="Add a new series globally (Owner only) - Auto-creates in all setup guilds")
    @app_commands.describe(series_name="The name of the new series (e.g., 'B-Series')")
    async def addseries(self, interaction: discord.Interaction, series_name: str):
        await interaction.response.defer(ephemeral=True)
        if not await owner_only(interaction):
            return
        
        series_lower = series_name.lower().strip()
        if not series_lower or len(series_lower) < 2:
            embed = discord.Embed(
                title="Error",
                description="Series name must be at least 2 characters long.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        if series_lower in [s.lower() for s in self.config["series"]]:
            embed = discord.Embed(
                title="Error",
                description=f"Series '{series_name}' already exists.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Add to global config
        self.config["series"][series_name] = []
        save_config(self.config)
        
        # Auto-Sync
        await self.bot.tree.sync()
        
        # Auto-create in ALL guilds that have run setup
        created_count = 0
        error_count = 0
        
        ensure_guild_config_dir()
        if os.path.exists(GUILD_CONFIG_DIR):
            for config_file in os.listdir(GUILD_CONFIG_DIR):
                if config_file.startswith("guild_") and config_file.endswith(".json"):
                    guild_id_str = config_file.replace("guild_", "").replace(".json", "")
                    try:
                        guild_config = load_guild_config(guild_id_str)
                        guild = self.bot.get_guild(int(guild_id_str))
                        if not guild:
                            continue
                        # Check if setup was run
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
                            print(f"✅ Created category '{series_name}' in guild {guild.name} ({guild_id_str})")
                        
                        # Create default channel
                        channel_name = f"{series_name.lower().replace(' ', '-')}-packs"
                        existing_channel = discord.utils.get(category.text_channels, name=channel_name)
                        if not existing_channel:
                            overwrites = {
                                guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                            }
                            await category.create_text_channel(channel_name, overwrites=overwrites)
                            print(f"✅ Created channel '{channel_name}' in category '{series_name}' for guild {guild.name}")
                        
                        # Update pack_channel_map if needed
                        if "pack_channel_map" not in guild_config:
                            guild_config["pack_channel_map"] = {}
                        if "pack_channel_mode" not in guild_config:
                            guild_config["pack_channel_mode"] = "series"
                        
                        created_count += 1
                        save_guild_config(guild_id_str, guild_config)
                        
                    except discord.Forbidden:
                        print(f"❌ Permission error in guild {guild_id_str}")
                        error_count += 1
                    except Exception as e:
                        print(f"❌ Error creating series '{series_name}' in guild {guild_id_str}: {e}")
                        error_count += 1
        
        embed = discord.Embed(
            title="Series Added & Auto-Created",
            description=f"'{series_name}' was added globally and auto-created in **{created_count}** guilds.\n"
                        f"Errors in **{error_count}** guilds (check permissions).\n"
                        f"**Current Series:** {', '.join(self.config['series'].keys())}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="addpack", description="Add a new pack globally (Owner only) - Auto-creates channels in all setup guilds")
    @app_commands.describe(pack_name="The name of the new pack (e.g., 'newpack')", series="The series to add the pack to")
    @app_commands.autocomplete(pack_name=autocomplete_packs, series=autocomplete_series)
    async def addpack(self, interaction: discord.Interaction, pack_name: str, series: str = "A-Series"):
        await interaction.response.defer(ephemeral=True)
        if not await owner_only(interaction):
            return
        
        pack_lower = pack_name.lower().strip()
        if not pack_lower or len(pack_lower) < 2:
            embed = discord.Embed(
                title="Error",
                description="Pack name must be at least 2 characters long.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        if pack_lower in [p.lower() for p in self.config.get("packs", [])]:
            embed = discord.Embed(
                title="Error",
                description=f"Pack '{pack_name}' already exists.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        if series not in self.config["series"]:
            embed = discord.Embed(
                title="Error",
                description=f"Series '{series}' does not exist. Add it first with /addseries.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Add to global config
        self.config["series"][series].append(pack_name)
        save_config(self.config)
        
        # Auto-Sync
        await self.bot.tree.sync()
        
        # Auto-create/update channels in ALL guilds
        created_count = 0
        updated_count = 0
        error_count = 0
        
        ensure_guild_config_dir()
        if os.path.exists(GUILD_CONFIG_DIR):
            for config_file in os.listdir(GUILD_CONFIG_DIR):
                if not config_file.startswith("guild_") or not config_file.endswith(".json"):
                    continue
                
                guild_id_str = config_file.replace("guild_", "").replace(".json", "")
                guild_config = load_guild_config(guild_id_str)
                
                try:
                    guild = self.bot.get_guild(int(guild_id_str))
                    if not guild:
                        continue
                    if "pack_channel_mode" not in guild_config:
                        continue
                    
                    pack_mode = guild_config.get("pack_channel_mode", "series")
                    category = discord.utils.get(guild.categories, name=series)
                    if not category:
                        print(f"⚠️ Skipping pack '{pack_name}' in guild {guild_id_str}: No '{series}' category")
                        continue
                    
                    if pack_mode == "series":
                        # Update map for this pack in series channel
                        channel_name = f"{series.lower().replace(' ', '-')}-packs"
                        target_channel = discord.utils.get(category.text_channels, name=channel_name)
                        if not target_channel:
                            overwrites = {
                                guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                            }
                            target_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                            print(f"✅ Created series channel '{channel_name}' in '{series}'")
                        
                        # Update map for this pack
                        if "pack_channel_map" not in guild_config:
                            guild_config["pack_channel_map"] = {}
                        guild_config["pack_channel_map"][pack_lower] = {
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
                            print(f"✅ Created pack channel '{channel_name}' in '{series}'")
                            created_count += 1
                        else:
                            updated_count += 1
                        
                        if "pack_channel_map" not in guild_config:
                            guild_config["pack_channel_map"] = {}
                        guild_config["pack_channel_map"][pack_lower] = {
                            "channel_id": target_channel.id,
                            "source_channel_ids": guild_config.get("default_source_channel_ids", [])
                        }
                    
                    save_guild_config(guild_id_str, guild_config)
                    
                except discord.Forbidden:
                    error_msg = f"Permission error in guild {guild_id_str}"
                    print(f"❌ {error_msg}")
                    await log_permission_warning_to_webhook(error_msg, guild_id=guild_id_str, command_name="addpack")
                    error_count += 1
                except Exception as e:
                    error_msg = f"Error adding pack '{pack_name}' to guild {guild_id_str}: {e}"
                    print(f"❌ {error_msg}")
                    await log_error_to_webhook(error_msg, guild_id=guild_id_str, command_name="addpack")
                    error_count += 1
        
        embed = discord.Embed(
            title="Pack Added & Auto-Created",
            description=f"'{pack_name}' was added to series '{series}'.\n"
                        f"Auto-created/updated in **{created_count + updated_count}** guilds.\n"
                        f"Errors in **{error_count}** guilds (check permissions).\n"
                        f"**Current Packs:** {', '.join(self.config.get('packs', []))}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="removepack", description="Remove a pack globally (Owner only) - Deletes channels if in pack mode")
    @app_commands.describe(pack_name="The name of the pack to remove")
    @app_commands.autocomplete(pack_name=autocomplete_packs)
    async def removepack(self, interaction: discord.Interaction, pack_name: str):
        await interaction.response.defer(ephemeral=True)
        if not await owner_only(interaction):
            return
        
        pack_lower = pack_name.lower()
        if pack_lower not in [p.lower() for p in self.config.get("packs", [])]:
            embed = discord.Embed(
                title="Error",
                description=f"Pack '{pack_name}' not found.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Find the series containing this pack
        series_found = None
        for series_name, packs_in_series in self.config["series"].items():
            if pack_lower in [p.lower() for p in packs_in_series]:
                series_found = series_name
                break
        
        if series_found:
            self.config["series"][series_found] = [p for p in self.config["series"][series_found] if p.lower() != pack_lower]
            if not self.config["series"][series_found]:
                del self.config["series"][series_found]
        
        save_config(self.config)
        
        # Auto-Sync
        await self.bot.tree.sync()
        
        # Delete channels in pack mode guilds
        deleted_count = 0
        updated_count = 0
        error_count = 0
        
        ensure_guild_config_dir()
        if os.path.exists(GUILD_CONFIG_DIR):
            for config_file in os.listdir(GUILD_CONFIG_DIR):
                if not config_file.startswith("guild_") or not config_file.endswith(".json"):
                    continue
                
                guild_id_str = config_file.replace("guild_", "").replace(".json", "")
                guild_config = load_guild_config(guild_id_str)
                
                try:
                    guild = self.bot.get_guild(int(guild_id_str))
                    if not guild:
                        continue
                    if "pack_channel_mode" not in guild_config:
                        continue
                    
                    pack_mode = guild_config.get("pack_channel_mode", "series")
                    category = discord.utils.get(guild.categories, name=series_found) if series_found else None
                    if not category:
                        # Just remove from map
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
                            print(f"✅ Deleted pack channel '{channel_name}' in '{series_found}'")
                            deleted_count += 1
                        else:
                            updated_count += 1
                    else:
                        updated_count += 1
                    
                    # Always remove from map
                    if "pack_channel_map" in guild_config and pack_lower in guild_config["pack_channel_map"]:
                        del guild_config["pack_channel_map"][pack_lower]
                    
                    save_guild_config(guild_id_str, guild_config)
                    
                except discord.Forbidden:
                    error_msg = f"Permission error in guild {guild_id_str}"
                    print(f"❌ {error_msg}")
                    await log_permission_warning_to_webhook(error_msg, guild_id=guild_id_str, command_name="removepack")
                    error_count += 1
                except Exception as e:
                    print(f"❌ Error removing pack '{pack_name}' from guild {guild_id_str}: {e}")
                    error_count += 1
        
        embed = discord.Embed(
            title="Pack Removed & Channels Deleted",
            description=f"'{pack_name}' was removed from {series_found or 'unknown series'}.\n"
                        f"Deleted channels in **{deleted_count}** guilds (pack mode).\n"
                        f"Updated maps in **{updated_count}** guilds (series mode).\n"
                        f"Errors in **{error_count}** guilds (check permissions).\n"
                        f"**Current Packs:** {', '.join(self.config.get('packs', []))}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="removeseries", description="Remove a series globally (Owner only) - Deletes all channels/categories")
    @app_commands.describe(series_name="The name of the series to remove (e.g., 'B-Series')")
    @app_commands.autocomplete(series_name=autocomplete_series)
    async def removeseries(self, interaction: discord.Interaction, series_name: str):
        await interaction.response.defer(ephemeral=True)
        if not await owner_only(interaction):
            return
        
        if series_name not in self.config["series"]:
            embed = discord.Embed(
                title="Error",
                description=f"Series '{series_name}' not found.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Remove from global config
        packs_to_remove = [p.lower() for p in self.config["series"][series_name]]
        del self.config["series"][series_name]
        save_config(self.config)
        
        # Auto-Sync
        await self.bot.tree.sync()
        
        # Delete channels and categories in ALL guilds
        deleted_channels_count = 0
        deleted_categories_count = 0
        updated_count = 0
        error_count = 0
        
        ensure_guild_config_dir()
        if os.path.exists(GUILD_CONFIG_DIR):
            for config_file in os.listdir(GUILD_CONFIG_DIR):
                if not config_file.startswith("guild_") or not config_file.endswith(".json"):
                    continue
                
                guild_id_str = config_file.replace("guild_", "").replace(".json", "")
                guild_config = load_guild_config(guild_id_str)
                
                try:
                    guild = self.bot.get_guild(int(guild_id_str))
                    if not guild:
                        continue
                    if "pack_channel_mode" not in guild_config:
                        continue
                    
                    category = discord.utils.get(guild.categories, name=series_name)
                    if not category:
                        # Just remove from map
                        if "pack_channel_map" in guild_config:
                            removed_packs = [p for p in packs_to_remove if p in guild_config["pack_channel_map"]]
                            for p in removed_packs:
                                del guild_config["pack_channel_map"][p]
                            if removed_packs:
                                updated_count += 1
                        continue
                    
                    # Delete all text channels in category
                    text_channels = [ch for ch in category.text_channels if isinstance(ch, discord.TextChannel)]
                    for channel in text_channels:
                        await channel.delete()
                        deleted_channels_count += 1
                    
                    # Delete category
                    await category.delete()
                    deleted_categories_count += 1
                    print(f"✅ Deleted category '{series_name}' in guild {guild.name}")
                    
                    # Remove packs from map
                    if "pack_channel_map" in guild_config:
                        removed_packs = [p for p in packs_to_remove if p in guild_config["pack_channel_map"]]
                        for p in removed_packs:
                            del guild_config["pack_channel_map"][p]
                        if removed_packs:
                            updated_count += 1
                    
                    save_guild_config(guild_id_str, guild_config)
                    
                except discord.Forbidden:
                    error_msg = f"Permission error in guild {guild_id_str}"
                    print(f"❌ {error_msg}")
                    await log_permission_warning_to_webhook(error_msg, guild_id=guild_id_str, command_name="removeseries")
                    error_count += 1
                except Exception as e:
                    print(f"❌ Error removing series '{series_name}' from guild {guild_id_str}: {e}")
                    error_count += 1
        
        embed = discord.Embed(
            title="Series Removed & Channels Deleted",
            description=f"'{series_name}' was removed globally.\n"
                        f"Deleted **{deleted_channels_count}** channels and **{deleted_categories_count}** categories.\n"
                        f"Updated maps in **{updated_count}** guilds.\n"
                        f"Errors in **{error_count}** guilds (check permissions).\n"
                        f"**Current Series:** {', '.join(self.config['series'].keys())}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(PackManagementCommands(bot, bot.config, bot.OWNER_ID))
