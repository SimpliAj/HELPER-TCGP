"""
Zusätzliche Commands: removefilter, removepackfilter, showfilters, detailedstats, packstats, 
setheartbeat, setstatus, pick4me, help, lifetimestats, createpackcategory
Note: Pack management commands (addseries, addpack, removepack, removeseries) are in pack_management.py
"""
import discord
from discord import app_commands
from discord.ext import commands
import os
import re
import asyncio
import json
from datetime import datetime
from config import load_guild_config, save_guild_config, load_config, save_config, ensure_guild_config_dir, GUILD_CONFIG_DIR
from utils import (
    FILTER_CHOICES, OLD_TO_NEW_CHANNEL_NAMES, CUSTOM_EMBED_TEXT,
    create_stats_embed, create_detailed_stats_embed, create_heartbeat_embed, create_pack_stats_embed,
    SAVE4TRADE_KEYWORDS
)


# Autocomplete Funktionen
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


def create_lifetime_stats_embed(config, berlin_tz):
    """Create embed with lifetime stats aggregated from ALL guild config files."""
    total_godpacks = 0
    total_godpacks_valid = 0
    total_godpacks_invalid = 0
    total_trades = 0
    total_traded = 0
    total_filter_stats = {}
    
    guild_count = 0
    active_guild_count = 0
    
    # Build a map of all known pack names (lowercase -> display_name from config)
    known_packs = {}
    for series_name, packs_in_series in config.get("series", {}).items():
        for pack in packs_in_series:
            known_packs[pack.lower()] = pack
    
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
                        keyword_normalized = keyword.lower().strip()
                        
                        if keyword_normalized in total_filter_stats:
                            total_filter_stats[keyword_normalized] += count
                        else:
                            total_filter_stats[keyword_normalized] = count
                            
                except (ValueError, json.JSONDecodeError):
                    continue
    
    # Create embed
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
    
    # Pack breakdown grouped by series
    pack_stats_by_series = {}
    
    for series_name in config.get("series", {}).keys():
        pack_stats_by_series[series_name] = []
    
    for series_name, packs_in_series in config.get("series", {}).items():
        for pack in packs_in_series:
            pack_lower = pack.lower()
            count = total_filter_stats.get(pack_lower, 0)
            pack_entry = f"{pack.title()}: **{count}**"
            pack_stats_by_series[series_name].append(pack_entry)
    
    for series_name, packs_list in sorted(pack_stats_by_series.items()):
        if packs_list:
            value = "\n".join(packs_list)
            if len(value) > 1024:
                chunks = [value[i:i+1024] for i in range(0, len(value), 1024)]
                for idx, chunk in enumerate(chunks):
                    field_name = f"📦 {series_name} Packs" if idx == 0 else f"📦 {series_name} Packs (cont.)"
                    embed.add_field(name=field_name, value=chunk, inline=False)
            else:
                embed.add_field(name=f"📦 {series_name} Packs", value=value, inline=False)
    
    embed.set_footer(
        text=f"Last updated: {datetime.now(berlin_tz).strftime('%d.%m.%Y %H:%M:%S')} Berlin Time",
        icon_url="https://imgur.com/T0KX069.png"
    )
    
    return embed


class UtilityCommands(commands.Cog):
    def __init__(self, bot, config, OWNER_ID, BERLIN_TZ):
        self.bot = bot
        self.config = config
        self.OWNER_ID = OWNER_ID
        self.BERLIN_TZ = BERLIN_TZ
    
    @app_commands.command(name="removefilter", description="Remove a filter from configuration")
    @app_commands.describe(filter_keyword="Filter to remove")
    @app_commands.choices(filter_keyword=FILTER_CHOICES)
    async def removefilter(self, interaction: discord.Interaction, filter_keyword: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(
                title="Error",
                description="Administrator required.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
        guild_config = load_guild_config(guild_id)
        
        if "keyword_channel_map" not in guild_config or filter_keyword.lower() not in guild_config["keyword_channel_map"]:
            embed = discord.Embed(
                title="Error",
                description=f"Filter '{filter_keyword}' not found.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        del guild_config["keyword_channel_map"][filter_keyword.lower()]
        save_guild_config(guild_id, guild_config)

        embed = discord.Embed(
            title="Filter Removed",
            description=f"Filter '{filter_keyword}' was removed.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="removepackfilter", description="Remove a pack filter")
    @app_commands.describe(pack="Pack to remove")
    @app_commands.autocomplete(pack=autocomplete_packs)
    async def removepackfilter(self, interaction: discord.Interaction, pack: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(
                title="Error",
                description="Administrator required.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
        guild_config = load_guild_config(guild_id)
        
        if "pack_channel_map" not in guild_config or pack.lower() not in guild_config["pack_channel_map"]:
            embed = discord.Embed(
                title="Error",
                description=f"Pack filter '{pack}' not found.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        del guild_config["pack_channel_map"][pack.lower()]
        save_guild_config(guild_id, guild_config)

        embed = discord.Embed(
            title="Pack Filter Removed",
            description=f"Pack filter '{pack}' was removed.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="showfilters", description="Show all active filters")
    async def showfilters(self, interaction: discord.Interaction):
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
        
        embed = discord.Embed(
            title="Active Filters",
            description="Currently configured filters for this server",
            color=discord.Color.blue()
        )

        # Keyword filters
        filter_list = []
        for keyword, filter_config in keyword_channel_map.items():
            channel = interaction.guild.get_channel(filter_config["channel_id"])
            channel_mention = channel.mention if channel else f"ID: {filter_config['channel_id']}"
            filter_list.append(f"**{keyword.title()}**: {channel_mention}")
        
        if filter_list:
            embed.add_field(name="Filters", value="\n".join(filter_list), inline=False)

        # Pack filters
        pack_list = []
        for pack, pack_config in pack_channel_map.items():
            channel = interaction.guild.get_channel(pack_config["channel_id"])
            channel_mention = channel.mention if channel else f"ID: {pack_config['channel_id']}"
            pack_list.append(f"**{pack.title()}**: {channel_mention}")
        
        if pack_list:
            embed.add_field(name="Pack Filters", value="\n".join(pack_list[:10]), inline=False)

        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="detailedstats", description="Show detailed filter statistics")
    @app_commands.describe(channel="Optional: Channel to post auto-updating embed")
    async def detailedstats(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
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
                description=f"Posted in {channel.mention}",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="packstats", description="Show pack statistics")
    @app_commands.describe(channel="Optional: Channel to post auto-updating embed")
    async def packstats(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=False)
        guild_id = str(interaction.guild.id)
        guild_config = load_guild_config(guild_id)

        embed = create_pack_stats_embed(guild_config, self.config.get("series", {}))

        if channel:
            sent_message = await channel.send(embed=embed)
            guild_config["pack_stats_channel_id"] = channel.id
            guild_config["pack_stats_message_id"] = sent_message.id
            save_guild_config(guild_id, guild_config)
            response_embed = discord.Embed(
                title="Pack Stats Embed Posted",
                description=f"Posted in {channel.mention}",
                color=discord.Color.teal()
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=False)
    
    @app_commands.command(name="setheartbeat", description="Set heartbeat source and target channels")
    @app_commands.describe(
        source_channel="Source channel",
        target_channel="Target channel for heartbeat embed"
    )
    async def setheartbeat(self, interaction: discord.Interaction, source_channel: discord.TextChannel, target_channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(title="Error", description="Administrator required.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
        guild_config = load_guild_config(guild_id)
        guild_config["heartbeat_source_channel_id"] = source_channel.id
        guild_config["heartbeat_target_channel_id"] = target_channel.id
        
        embed = create_heartbeat_embed(guild_config, self.BERLIN_TZ)
        sent_message = await target_channel.send(embed=embed)
        guild_config["heartbeat_message_id"] = sent_message.id
        save_guild_config(guild_id, guild_config)
        
        response_embed = discord.Embed(
            title="Heartbeat Configured",
            description=f"Source: {source_channel.mention}\nTarget: {target_channel.mention}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=response_embed, ephemeral=True)
    
    @app_commands.command(name="setstatus", description="Enable or disable traded buttons")
    @app_commands.describe(status="Enable (True) or disable (False)")
    async def setstatus(self, interaction: discord.Interaction, status: bool):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(title="Error", description="Administrator required.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
        guild_config = load_guild_config(guild_id)
        guild_config["validation_buttons_enabled"] = status
        save_guild_config(guild_id, guild_config)

        embed = discord.Embed(
            title="Status Updated",
            description=f"Traded buttons: {'**enabled**' if status else '**disabled**'}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="pick4me", description="Let fate decide!")
    async def pick4me(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        import random
        options = ["Top Left", "Top Middle", "Top Right", "Bottom Left", "Bottom Right"]
        choice = random.choice(options)
        
        embed = discord.Embed(
            description=f"> {choice}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="lifetimestats", description="Shows lifetime statistics across all servers (Owner only)")
    @app_commands.describe(channel="Optional: The channel to post the auto-updating lifetime stats embed")
    async def lifetimestats(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=False)
        if interaction.user.id != self.OWNER_ID:
            embed = discord.Embed(
                title="Access Denied",
                description="This command can only be used by the bot owner.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Run embed creation in thread to avoid blocking event loop
        embed = await asyncio.to_thread(create_lifetime_stats_embed, self.config, self.BERLIN_TZ)
        
        if channel:
            # Send to specified channel
            sent_message = await channel.send(embed=embed)
            
            # Store message info for auto-update (simplified - can be extended for auto-update tasks)
            response_embed = discord.Embed(
                title="Lifetime Stats Embed Posted",
                description=f"The lifetime stats embed has been posted in {channel.mention}.",
                color=discord.Color.gold()
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="createpackcategory", description="Create a category for a pack with Save 4 Trade channels (Admin only)")
    @app_commands.describe(pack="The Pack to create category for")
    @app_commands.autocomplete(pack=autocomplete_packs)
    async def createpackcategory(self, interaction: discord.Interaction, pack: str):
        await interaction.response.defer(ephemeral=True)
        # Check admin permissions
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not member.guild_permissions.administrator:
            embed = discord.Embed(
                title="Error",
                description="You need administrator permissions to use this command.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Validate pack exists in config (most up-to-date source)
        pack_lower = pack.lower()
        all_packs = [p.lower() for series_packs in self.config.get("series", {}).values() for p in series_packs]
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

        # Build success embed
        embed = discord.Embed(
            title="✅ Pack Category Created",
            description=f"Category **{category_name}** has been created successfully.",
            color=discord.Color.green()
        )
        
        if created_channels:
            embed.add_field(
                name="Channels Created",
                value="\n".join(created_channels[:10]),
                inline=False
            )
        
        embed.add_field(
            name="Info",
            value=f"All messages mentioning **{pack.title()}** will be forwarded to the appropriate channels in this category.",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        
        embed = discord.Embed(
            title="🤖 Bot Commands",
            description="All available commands",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url="https://i.imgur.com/T0KX069.png")
        
        embed.add_field(
            name="Setup",
            value="/setup, /showfilters, /setpingroles",
            inline=False
        )
        embed.add_field(
            name="Filters",
            value="/setfilter, /removefilter, /setpackmode, /clearfilters",
            inline=False
        )
        embed.add_field(
            name="Stats",
            value="/stats, /detailedstats, /packstats, /meta",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=False)
    
    @app_commands.command(name="sync", description="Sync commands (Owner only)")
    async def sync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != self.OWNER_ID:
            await interaction.followup.send("❌ Owner only", ephemeral=True)
            return
        
        try:
            synced = await self.bot.tree.sync()
            embed = discord.Embed(
                title="✅ Synced",
                description=f"{len(synced)} commands synced",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=str(e),
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(UtilityCommands(bot, bot.config, bot.OWNER_ID, bot.BERLIN_TZ))
