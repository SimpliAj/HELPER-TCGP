import discord
from discord.ext import commands
from discord import app_commands
import re
import utils


class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setpingroles", description="Set ping roles for god pack, invalid god pack, or safe for trade")
    async def setpingroles(self, interaction: discord.Interaction):
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
        select.callback = lambda inter: self._ping_type_callback(inter)
        view = discord.ui.View()
        view.add_item(select)
        embed = discord.Embed(title="Set Ping Role", description="First, select the ping type.", color=discord.Color.blue())
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def _ping_type_callback(self, interaction: discord.Interaction):
        ping_type = interaction.data['values'][0]
        guild_id = str(interaction.guild.id)
        roles = sorted(interaction.guild.roles, key=lambda r: r.position, reverse=True)[:25]
        if interaction.guild.default_role in roles:
            roles.remove(interaction.guild.default_role)
        role_select = discord.ui.Select(
            placeholder=f"Select Role for {ping_type.replace('_', ' ').title()}...",
            options=[discord.SelectOption(label=role.name, value=str(role.id)) for role in roles]
        )
        role_select.callback = lambda i: self._set_ping(i, ping_type, guild_id)
        view = discord.ui.View()
        view.add_item(role_select)
        await interaction.response.edit_message(content=f"Select role for {ping_type.replace('_', ' ').title()}:", view=view, embed=None)

    async def _set_ping(self, interaction: discord.Interaction, ping_type: str, guild_id: str):
        role_id = int(interaction.data['values'][0])
        guild_config = utils.load_guild_config(guild_id)
        guild_config[f"{ping_type}_ping"] = role_id
        utils.save_guild_config(guild_id, guild_config)
        role = interaction.guild.get_role(role_id)
        await interaction.response.edit_message(content=f"✅ {ping_type.replace('_', ' ').title()} set to {role.mention}", view=None)

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
        guild_config = utils.load_guild_config(guild_id)
        guild_config["pack_channel_mode"] = mode
        utils.save_guild_config(guild_id, guild_config)
        mode_desc = "one channel per series" if mode == "series" else "one channel per pack"
        embed = discord.Embed(
            title="Pack Mode Updated",
            description=f"Pack channels are now set to {mode_desc}. Use /clearfilters pack to reset and reconfigure channels if needed.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="clearfilters", description="Clear all filters of a selected type")
    @app_commands.describe(filter_type="Type of filters to clear")
    @app_commands.choices(filter_type=utils.CLEAR_FILTER_CHOICES)
    async def clearfilters(self, interaction: discord.Interaction, filter_type: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(title="Error", description="You need administrator permissions to use this command.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        if not guild_config or (not guild_config.get("keyword_channel_map") and not guild_config.get("pack_channel_map")):
            embed = discord.Embed(title="Error", description="No filters configured for this server.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        cleared = False
        cleared_count = 0
        if filter_type in ("normal", "all"):
            if "keyword_channel_map" in guild_config:
                cleared_count += len(guild_config["keyword_channel_map"])
                del guild_config["keyword_channel_map"]
                cleared = True
        if filter_type in ("pack", "all"):
            if "pack_channel_map" in guild_config:
                cleared_count += len(guild_config["pack_channel_map"])
                del guild_config["pack_channel_map"]
                cleared = True
        if not cleared:
            embed = discord.Embed(title="Error", description=f"No {filter_type} filters found.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        utils.save_guild_config(guild_id, guild_config)
        type_name = {"normal": "Normal", "pack": "Pack", "all": "All"}[filter_type]
        embed = discord.Embed(title="Filters Cleared", description=f"{cleared_count} {type_name} filter(s) cleared successfully.", color=discord.Color.green())
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="setfilter", description="Configuration of Filter for TCGP Rerolling")
    @app_commands.describe(
        filter_keyword="The Filter",
        channel="The target channel for the forwarding (optional; auto-creates if omitted)",
        source_channels="Space-separated source channel mentions (optional, e.g., #channel1 #channel2)",
        godpack_ping="Role Ping for GOD Pack (optional)",
        invgodpack_ping="Role Ping for Invalid God Pack (optional)",
        safe_trade_ping="Role Ping for Safe for Trade (optional)"
    )
    @app_commands.choices(filter_keyword=utils.FILTER_CHOICES)
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
            embed = discord.Embed(title="Error", description="You need administrator permissions to use this command.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)

        if filter_keyword.lower() not in utils.CUSTOM_EMBED_TEXT:
            embed = discord.Embed(title="Error", description=f"Invalid Filter: '{filter_keyword}'.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

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
                    clean_name = filter_keyword.lower().replace(" ", "-")
                    channel_name = utils.OLD_TO_NEW_CHANNEL_NAMES.get(f"prefix-{clean_name}", clean_name)
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
                    if interaction.client.get_channel(channel_id):
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
        utils.save_guild_config(guild_id, guild_config)

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

    @app_commands.command(name="setpackfilter", description="Configuration of Filter for Packs")
    @app_commands.describe(
        pack="The Pack (ignored in series mode; sets all in series)",
        channel="The target channel for the pack forwarding (optional; auto-creates if omitted)",
        source_channels="Space-separated source channel mentions (optional, e.g., #channel1 #channel2)"
    )
    @app_commands.autocomplete(pack=utils.autocomplete_packs)
    async def setpackfilter(
        self,
        interaction: discord.Interaction,
        pack: str,
        channel: discord.TextChannel = None,
        source_channels: str = None
    ):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(title="Error", description="You need administrator permissions to use this command.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        pack_mode = guild_config.get("pack_channel_mode", "series")

        if pack_mode == "series":
            series_name = None
            for s, packs_in_s in utils.config.get("series", {}).items():
                if pack.lower() in [p.lower() for p in packs_in_s]:
                    series_name = s
                    break
            if not series_name:
                embed = discord.Embed(title="Error", description=f"Pack '{pack}' not in any series.", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            packs_to_set = [p.lower() for p in utils.config["series"][series_name]]
            embed_desc = f"Series '{series_name}' ({len(packs_to_set)} packs)"
        else:
            if pack.lower() not in [p.lower() for p in utils.PACKS]:
                embed = discord.Embed(title="Error", description=f"Invalid Pack: '{pack}'.", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            packs_to_set = [pack.lower()]
            embed_desc = f"Pack '{pack}'"

        target_channel = channel
        if not target_channel:
            s_name = next((s for s, packs_in_s in utils.config.get("series", {}).items() if any(p.lower() == packs_to_set[0] for p in packs_in_s)), None)
            if s_name:
                category = discord.utils.get(interaction.guild.categories, name=s_name)
                if category:
                    channel_name = f"{s_name.lower().replace(' ', '-')}-packs" if pack_mode == "series" else f"{packs_to_set[0]}-pack"
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
                    if interaction.client.get_channel(channel_id):
                        source_channel_ids.append(channel_id)
                except ValueError:
                    pass

        if "pack_channel_map" not in guild_config:
            guild_config["pack_channel_map"] = {}
        for p in packs_to_set:
            guild_config["pack_channel_map"][p] = {
                "channel_id": target_channel.id,
                "source_channel_ids": source_channel_ids if source_channel_ids else None
            }
        utils.save_guild_config(guild_id, guild_config)

        sources_mention = ", ".join([f"<#{sid}>" for sid in source_channel_ids]) if source_channel_ids else "All channels"
        embed = discord.Embed(
            title="New Pack Filter Set",
            description=f"{embed_desc} is now being forwarded to {target_channel.mention}.\nSource Channels: {sources_mention}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="removefilter", description="Remove a certain filter from the configuration")
    @app_commands.describe(filter_keyword="Filter to remove")
    @app_commands.choices(filter_keyword=utils.FILTER_CHOICES)
    async def removefilter(self, interaction: discord.Interaction, filter_keyword: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(title="Error", description="You need administrator permissions to use this command.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        if "keyword_channel_map" not in guild_config or filter_keyword.lower() not in guild_config["keyword_channel_map"]:
            embed = discord.Embed(title="Error", description=f"Filter '{filter_keyword}' not found in configuration.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        del guild_config["keyword_channel_map"][filter_keyword.lower()]
        if not guild_config["keyword_channel_map"]:
            del guild_config["keyword_channel_map"]
        utils.save_guild_config(guild_id, guild_config)
        embed = discord.Embed(title="Filter Removed", description=f"Filter '{filter_keyword}' was successfully removed.", color=discord.Color.green())
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="removepackfilter", description="Remove a certain pack filter from the configuration")
    @app_commands.describe(pack="Pack to remove")
    @app_commands.autocomplete(pack=utils.autocomplete_packs)
    async def removepackfilter(self, interaction: discord.Interaction, pack: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(title="Error", description="You need administrator permissions to use this command.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        if "pack_channel_map" not in guild_config or pack.lower() not in guild_config["pack_channel_map"]:
            embed = discord.Embed(title="Error", description=f"Pack filter '{pack}' not found in configuration.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        del guild_config["pack_channel_map"][pack.lower()]
        if not guild_config["pack_channel_map"]:
            del guild_config["pack_channel_map"]
        utils.save_guild_config(guild_id, guild_config)
        embed = discord.Embed(title="Pack Filter Removed", description=f"Pack filter '{pack}' was successfully removed.", color=discord.Color.green())
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="setvalidatorrole", description="Set the validator role for validation buttons")
    @app_commands.describe(role="The role allowed to use validation buttons")
    async def setvalidatorrole(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(title="Error", description="You need administrator permissions to use this command.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        guild_config["validator_role_id"] = role.id
        utils.save_guild_config(guild_id, guild_config)
        embed = discord.Embed(title="Validator Role Set", description=f"The validator role has been set to {role.mention}.", color=discord.Color.green())
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="setstatus", description="Enable or disable traded buttons for Safe 4 Trade embeds")
    @app_commands.describe(status="Set to True to enable traded buttons; False to disable them")
    async def setstatus(self, interaction: discord.Interaction, status: bool):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(title="Error", description="You need administrator permissions to use this command.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        guild_config["validation_buttons_enabled"] = status
        utils.save_guild_config(guild_id, guild_config)
        embed = discord.Embed(
            title="Traded Buttons Status Updated",
            description=f"Traded buttons for Safe 4 Trade embeds are now {'**enabled**' if status else '**disabled**'}. God pack embeds will always have validation buttons.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="setheartbeat", description="Set the source and target channels for heartbeat stats")
    @app_commands.describe(
        source_channel="The channel where heartbeat messages are posted",
        target_channel="The channel to post the updating heartbeat embed"
    )
    async def setheartbeat(self, interaction: discord.Interaction, source_channel: discord.TextChannel, target_channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(title="Error", description="You need administrator permissions to use this command.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        guild_config["heartbeat_source_channel_id"] = source_channel.id
        guild_config["heartbeat_target_channel_id"] = target_channel.id
        embed = utils.create_heartbeat_embed(guild_config)
        sent_message = await target_channel.send(embed=embed)
        guild_config["heartbeat_message_id"] = sent_message.id
        utils.save_guild_config(guild_id, guild_config)
        response_embed = discord.Embed(
            title="Heartbeat Embed Configured",
            description=f"Source channel set to {source_channel.mention}. The heartbeat stats embed will update in {target_channel.mention}.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=response_embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
