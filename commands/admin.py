"""
Admin Commands: clearfilters, setpackmode, resetsources, setfilter, setpackfilter, setvalidatorrole
"""
import discord
from discord import app_commands
from discord.ext import commands
from config import load_guild_config, save_guild_config
from utils import FILTER_CHOICES, CLEAR_FILTER_CHOICES, OLD_TO_NEW_CHANNEL_NAMES, CUSTOM_EMBED_TEXT, SAVE4TRADE_KEYWORDS
import re


# Autocomplete für Packs
async def autocomplete_packs(interaction: discord.Interaction, current: str):
    """Autocomplete für Packs."""
    packs = interaction.client.config.get("packs", [])
    choices = [app_commands.Choice(name=p.title(), value=p) for p in packs[:25]]
    if not current:
        return choices
    return [c for c in choices if current.lower() in c.value.lower()][:25]


class AdminCommands(commands.Cog):
    def __init__(self, bot, config, OWNER_ID):
        self.bot = bot
        self.config = config
        self.OWNER_ID = OWNER_ID
    
    @app_commands.command(name="clearfilters", description="Clear all filters of a selected type")
    @app_commands.describe(filter_type="Type of filters to clear")
    @app_commands.choices(filter_type=CLEAR_FILTER_CHOICES)
    async def clearfilters(self, interaction: discord.Interaction, filter_type: str):
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
    
    @app_commands.command(name="setpackmode", description="Change the pack channel mode after setup")
    @app_commands.describe(mode="Pack channel organization mode")
    @app_commands.choices(mode=[
        app_commands.Choice(name="One channel per series", value="series"),
        app_commands.Choice(name="One channel per pack", value="pack")
    ])
    async def setpackmode(self, interaction: discord.Interaction, mode: str):
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
            description=f"Pack channels are now set to {mode_desc}.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="resetsources", description="Set or reset source channels (Admin only)")
    async def resetsources(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
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
        
        has_sources = "default_source_channel_ids" in guild_config and guild_config["default_source_channel_ids"]
        
        class SourceOptionsView(discord.ui.View):
            def __init__(self, parent):
                super().__init__(timeout=300)
                self.parent = parent
            
            @discord.ui.button(label="Set New Sources", style=discord.ButtonStyle.primary)
            async def set_sources(self, inter: discord.Interaction, button: discord.ui.Button):
                from views.setup_views import SourceModal
                modal = SourceModal()
                modal.guild_id = guild_id
                modal.original_user = interaction.user
                await inter.response.send_modal(modal)
            
            @discord.ui.button(label="Reset to All Channels", style=discord.ButtonStyle.danger)
            async def reset_sources(self, inter: discord.Interaction, button: discord.ui.Button):
                await inter.response.defer(ephemeral=True)
                
                guild_config = load_guild_config(guild_id)
                old_sources = guild_config.get("default_source_channel_ids", [])
                guild_config["default_source_channel_ids"] = []
                
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
                await inter.followup.send(embed=embed, ephemeral=True)
        
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
                description="No source channels currently set.\n\nWhat do you want to do?",
                color=discord.Color.blue()
            )
        
        view = SourceOptionsView(self)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="setfilter", description="Configure a Filter for TCGP")
    @app_commands.describe(
        filter_keyword="The Filter",
        channel="Target channel (optional; auto-creates if omitted)",
        source_channels="Space-separated source channel mentions (optional)",
        godpack_ping="Role Ping for GOD Pack (optional)",
        invgodpack_ping="Role Ping for Invalid God Pack (optional)",
        safe_trade_ping="Role Ping for Safe for Trade (optional)"
    )
    @app_commands.choices(filter_keyword=FILTER_CHOICES)
    async def setfilter(
        self,
        interaction: discord.Interaction,
        filter_keyword: str,
        channel: discord.TextChannel = None,
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

        # Determine target channel
        target_channel = channel
        if not target_channel:
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
                    channel_name = OLD_TO_NEW_CHANNEL_NAMES.get(f"prefix-{clean_name}", clean_name)
                    target_channel = discord.utils.get(category.text_channels, name=channel_name)
                    if not target_channel:
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
            embed = discord.Embed(title="Error", description="Could not auto-create channel. Provide one manually.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        source_channel_ids = []
        if source_channels:
            matches = re.findall(r'<#(\d+)>', source_channels)
            for match in matches:
                try:
                    channel_id = int(match)
                    if self.bot.get_channel(channel_id):
                        source_channel_ids.append(channel_id)
                except ValueError:
                    pass

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
            description=f"Filter '{filter_keyword}' set to {target_channel.mention}.\n"
                        f"Source Channels: {sources_mention}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="setpackfilter", description="Configuration of Filter for Packs")
    @app_commands.describe(
        pack="The Pack (ignored in series mode; sets all in series)",
        channel="The target channel for the pack forwarding (optional; auto-creates if omitted)",
        source_channels="Space-separated source channel mentions (optional, e.g., #channel1 #channel2)"
    )
    @app_commands.autocomplete(pack=autocomplete_packs)
    async def setpackfilter(
        self,
        interaction: discord.Interaction,
        pack: str,
        channel: discord.TextChannel = None,
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
            for s, packs_in_s in self.config.get("series", {}).items():
                if pack.lower() in [p.lower() for p in packs_in_s]:
                    series_name = s
                    break
            if not series_name:
                embed = discord.Embed(title="Error", description=f"Pack '{pack}' not in any series.", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            packs_to_set = [p.lower() for p in self.config["series"][series_name]]
            embed_desc = f"Series '{series_name}' ({len(packs_to_set)} packs)"
        else:
            # Per pack
            if pack.lower() not in [p.lower() for series_packs in self.config.get("series", {}).values() for p in series_packs]:
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
            series_name = next((s for s, packs_in_s in self.config.get("series", {}).items() if any(p.lower() == packs_to_set[0] for p in packs_in_s)), None)
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
                    if self.bot.get_channel(channel_id):
                        source_channel_ids.append(channel_id)
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
    
    @app_commands.command(name="setvalidatorrole", description="Set the validator role for validation buttons")
    @app_commands.describe(role="The role allowed to use validation buttons")
    async def setvalidatorrole(self, interaction: discord.Interaction, role: discord.Role):
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


async def setup(bot):
    await bot.add_cog(AdminCommands(bot, bot.config, bot.OWNER_ID))
