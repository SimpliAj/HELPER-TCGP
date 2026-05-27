import discord
from discord.ext import commands
from discord import app_commands
import re
import utils


# ── Modals ────────────────────────────────────────────────────────────────────

class HeartbeatModal(discord.ui.Modal, title="Set Heartbeat Channels"):
    source = discord.ui.TextInput(label="Source Channel", placeholder="#channel or channel ID", min_length=2, max_length=100)
    target = discord.ui.TextInput(label="Target Channel", placeholder="#channel or channel ID", min_length=2, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        def resolve_channel(value: str):
            value = value.strip()
            match = re.search(r'(\d{17,20})', value)
            if match:
                return interaction.guild.get_channel(int(match.group(1)))
            name = value.lstrip('#').lower()
            return discord.utils.get(interaction.guild.text_channels, name=name)

        source_ch = resolve_channel(self.source.value)
        target_ch = resolve_channel(self.target.value)

        if not source_ch or not target_ch:
            await interaction.followup.send("❌ Could not find one or both channels. Use #mention or channel ID.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        guild_config["heartbeat_source_channel_id"] = source_ch.id
        guild_config["heartbeat_target_channel_id"] = target_ch.id
        embed = utils.create_heartbeat_embed(guild_config)
        sent_message = await target_ch.send(embed=embed)
        guild_config["heartbeat_message_id"] = sent_message.id
        utils.save_guild_config(guild_id, guild_config)

        await interaction.followup.send(
            embed=discord.Embed(title="✅ Heartbeat Configured",
                                description=f"Source: {source_ch.mention} → Stats in {target_ch.mention}.",
                                color=discord.Color.green()),
            ephemeral=True
        )


class ValidatorRoleModal(discord.ui.Modal, title="Set Validator Role"):
    role_input = discord.ui.TextInput(label="Role", placeholder="@RoleName or role ID", min_length=1, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        value = self.role_input.value.strip()
        match = re.search(r'(\d{17,20})', value)
        role = None
        if match:
            role = interaction.guild.get_role(int(match.group(1)))
        if not role:
            name = value.lstrip('@').lower()
            role = discord.utils.get(interaction.guild.roles, name=name)
        if not role:
            await interaction.followup.send("❌ Role not found. Use @mention or role ID.", ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        guild_config["validator_role_id"] = role.id
        utils.save_guild_config(guild_id, guild_config)
        await interaction.followup.send(
            embed=discord.Embed(title="✅ Validator Role Set", description=f"Set to {role.mention}.", color=discord.Color.green()),
            ephemeral=True
        )


class SourceModal(discord.ui.Modal, title="Set Source Channels"):
    source_input = discord.ui.TextInput(
        label="Source Channels",
        style=discord.TextStyle.short,
        placeholder="Mention channels e.g. #general #tcg-chat (leave empty for all)",
        required=False,
        max_length=500
    )

    def __init__(self):
        super().__init__()
        self.guild_id = None
        self.original_user = None

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        source_ids = []
        input_value = self.source_input.value.strip()
        if input_value:
            matches = re.findall(r'<#(\d+)>', input_value)
            for match in matches:
                try:
                    ch_id = int(match)
                    if interaction.guild.get_channel(ch_id):
                        source_ids.append(ch_id)
                except ValueError:
                    pass
            if not source_ids:
                for name in [n.strip().strip('#').lower() for n in input_value.split(',') if n.strip()]:
                    for ch in interaction.guild.text_channels:
                        if ch.name.lower() == name:
                            source_ids.append(ch.id)
                            break
        guild_config = utils.load_guild_config(self.guild_id)
        guild_config["default_source_channel_ids"] = source_ids
        if "keyword_channel_map" in guild_config:
            for cfg in guild_config["keyword_channel_map"].values():
                cfg["source_channel_ids"] = source_ids[:]
        if "pack_channel_map" in guild_config:
            for cfg in guild_config["pack_channel_map"].values():
                cfg["source_channel_ids"] = source_ids[:]
        utils.save_guild_config(self.guild_id, guild_config)
        sources_mention = ', '.join([f'<#{sid}>' for sid in source_ids]) if source_ids else "All channels"
        await interaction.followup.send(
            embed=discord.Embed(title="✅ Sources Updated", description=f"Source channels: {sources_mention}", color=discord.Color.green()),
            ephemeral=True
        )


# ── /set flow ─────────────────────────────────────────────────────────────────

class SetSelectView(discord.ui.View):
    def __init__(self, guild_id: str):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        select = discord.ui.Select(
            placeholder="What do you want to configure?",
            options=[
                discord.SelectOption(label="Pack Mode", value="packmode", description="One channel per series or per pack", emoji="📦"),
                discord.SelectOption(label="Status", value="status", description="Enable/disable traded buttons", emoji="🔘"),
                discord.SelectOption(label="Heartbeat", value="heartbeat", description="Set heartbeat source & target channels", emoji="💓"),
                discord.SelectOption(label="Validator Role", value="validatorrole", description="Role allowed to use validation buttons", emoji="🛡️"),
                discord.SelectOption(label="Ping Roles", value="pingroles", description="Set ping roles for god pack / safe trade", emoji="🔔"),
                discord.SelectOption(label="Sources", value="sources", description="Set or reset source channels", emoji="📡"),
            ]
        )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        choice = interaction.data["values"][0]

        if choice == "packmode":
            view = PackModeView(self.guild_id)
            await interaction.response.edit_message(
                embed=discord.Embed(title="📦 Pack Mode", description="Choose how pack channels are organized:", color=discord.Color.blue()),
                view=view
            )

        elif choice == "status":
            view = StatusView(self.guild_id)
            await interaction.response.edit_message(
                embed=discord.Embed(title="🔘 Traded Buttons Status", description="Enable or disable traded buttons for Safe 4 Trade embeds:", color=discord.Color.blue()),
                view=view
            )

        elif choice == "heartbeat":
            await interaction.response.send_modal(HeartbeatModal())

        elif choice == "validatorrole":
            await interaction.response.send_modal(ValidatorRoleModal())

        elif choice == "pingroles":
            roles = sorted(interaction.guild.roles, key=lambda r: r.position, reverse=True)[:25]
            if interaction.guild.default_role in roles:
                roles.remove(interaction.guild.default_role)
            ping_type_select = discord.ui.Select(
                placeholder="Select Ping Type...",
                options=[
                    discord.SelectOption(label="God Pack Ping", value="godpack"),
                    discord.SelectOption(label="Invalid God Pack Ping", value="invgodpack"),
                    discord.SelectOption(label="Safe for Trade Ping", value="safe_trade")
                ]
            )
            guild_id = self.guild_id

            async def ping_type_cb(inter: discord.Interaction):
                ping_type = inter.data["values"][0]
                role_select = discord.ui.Select(
                    placeholder=f"Select role for {ping_type.replace('_', ' ').title()}...",
                    options=[discord.SelectOption(label=r.name, value=str(r.id)) for r in roles]
                )
                async def role_cb(i: discord.Interaction):
                    role_id = int(i.data["values"][0])
                    gc = utils.load_guild_config(guild_id)
                    gc[f"{ping_type}_ping"] = role_id
                    utils.save_guild_config(guild_id, gc)
                    role = i.guild.get_role(role_id)
                    await i.response.edit_message(
                        content=f"✅ {ping_type.replace('_', ' ').title()} set to {role.mention}",
                        embed=None, view=None
                    )
                role_select.callback = role_cb
                v = discord.ui.View()
                v.add_item(role_select)
                await inter.response.edit_message(
                    embed=discord.Embed(title="🔔 Select Role", description=f"Pick a role for **{ping_type.replace('_', ' ').title()}**:", color=discord.Color.blue()),
                    view=v
                )

            ping_type_select.callback = ping_type_cb
            v = discord.ui.View()
            v.add_item(ping_type_select)
            await interaction.response.edit_message(
                embed=discord.Embed(title="🔔 Ping Roles", description="Select the ping type to configure:", color=discord.Color.blue()),
                view=v
            )

        elif choice == "sources":
            guild_id = self.guild_id
            gc = utils.load_guild_config(guild_id)
            current_sources = gc.get("default_source_channel_ids", [])
            sources_mention = ', '.join([f'<#{sid}>' for sid in current_sources]) if current_sources else "All channels"

            class SourceOptionsView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=300)

                @discord.ui.button(label="Set New Sources", style=discord.ButtonStyle.primary)
                async def btn_set(self_inner, inter: discord.Interaction, button: discord.ui.Button):
                    modal = SourceModal()
                    modal.guild_id = guild_id
                    modal.original_user = inter.user
                    await inter.response.send_modal(modal)

                @discord.ui.button(label="Reset to All Channels", style=discord.ButtonStyle.danger)
                async def btn_reset(self_inner, inter: discord.Interaction, button: discord.ui.Button):
                    await inter.response.defer(ephemeral=True)
                    gc2 = utils.load_guild_config(guild_id)
                    old = gc2.get("default_source_channel_ids", [])
                    gc2["default_source_channel_ids"] = []
                    for cfg in gc2.get("keyword_channel_map", {}).values():
                        cfg["source_channel_ids"] = []
                    for cfg in gc2.get("pack_channel_map", {}).values():
                        cfg["source_channel_ids"] = []
                    utils.save_guild_config(guild_id, gc2)
                    old_mention = ', '.join([f'<#{sid}>' for sid in old]) if old else "None"
                    await inter.followup.send(
                        embed=discord.Embed(title="✅ Sources Reset", description=f"**Previous:** {old_mention}\n**New:** All channels", color=discord.Color.green()),
                        ephemeral=True
                    )

            await interaction.response.edit_message(
                embed=discord.Embed(title="📡 Manage Source Channels", description=f"**Current:** {sources_mention}", color=discord.Color.blue()),
                view=SourceOptionsView()
            )


class PackModeView(discord.ui.View):
    def __init__(self, guild_id: str):
        super().__init__(timeout=60)
        self.guild_id = guild_id

    @discord.ui.button(label="One channel per Series", style=discord.ButtonStyle.primary)
    async def btn_series(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set(interaction, "series", "one channel per series")

    @discord.ui.button(label="One channel per Pack", style=discord.ButtonStyle.secondary)
    async def btn_pack(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set(interaction, "pack", "one channel per pack")

    async def _set(self, interaction: discord.Interaction, mode: str, desc: str):
        gc = utils.load_guild_config(self.guild_id)
        gc["pack_channel_mode"] = mode
        utils.save_guild_config(self.guild_id, gc)
        await interaction.response.edit_message(
            embed=discord.Embed(title="✅ Pack Mode Updated", description=f"Pack channels set to {desc}.", color=discord.Color.green()),
            view=None
        )


class StatusView(discord.ui.View):
    def __init__(self, guild_id: str):
        super().__init__(timeout=60)
        self.guild_id = guild_id

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success)
    async def btn_enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set(interaction, True)

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.danger)
    async def btn_disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set(interaction, False)

    async def _set(self, interaction: discord.Interaction, status: bool):
        gc = utils.load_guild_config(self.guild_id)
        gc["validation_buttons_enabled"] = status
        utils.save_guild_config(self.guild_id, gc)
        await interaction.response.edit_message(
            embed=discord.Embed(title="✅ Status Updated", description=f"Traded buttons are now {'**enabled**' if status else '**disabled**'}.", color=discord.Color.green()),
            view=None
        )


# ── Cog ───────────────────────────────────────────────────────────────────────

class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="set", description="Server configuration (Admin only)")
    async def set_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=discord.Embed(title="Error", description="Administrator required.", color=discord.Color.red()),
                ephemeral=True
            )
            return
        guild_id = str(interaction.guild.id)
        embed = discord.Embed(title="⚙️ Server Configuration", description="Select what you want to configure:", color=discord.Color.blurple())
        await interaction.followup.send(embed=embed, view=SetSelectView(guild_id), ephemeral=True)

    @app_commands.command(name="clearfilters", description="Clear all filters of a selected type")
    @app_commands.describe(filter_type="Type of filters to clear")
    @app_commands.choices(filter_type=utils.CLEAR_FILTER_CHOICES)
    async def clearfilters(self, interaction: discord.Interaction, filter_type: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(embed=discord.Embed(title="Error", description="Administrator required.", color=discord.Color.red()), ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        if not guild_config or (not guild_config.get("keyword_channel_map") and not guild_config.get("pack_channel_map")):
            await interaction.followup.send(embed=discord.Embed(title="Error", description="No filters configured for this server.", color=discord.Color.red()), ephemeral=True)
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
            await interaction.followup.send(embed=discord.Embed(title="Error", description=f"No {filter_type} filters found.", color=discord.Color.red()), ephemeral=True)
            return
        utils.save_guild_config(guild_id, guild_config)
        type_name = {"normal": "Normal", "pack": "Pack", "all": "All"}[filter_type]
        await interaction.followup.send(embed=discord.Embed(title="Filters Cleared", description=f"{cleared_count} {type_name} filter(s) cleared.", color=discord.Color.green()))

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
        self, interaction: discord.Interaction, filter_keyword: str,
        channel: discord.TextChannel = None, source_channels: str = None,
        godpack_ping: discord.Role = None, invgodpack_ping: discord.Role = None,
        safe_trade_ping: discord.Role = None
    ):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(embed=discord.Embed(title="Error", description="Administrator required.", color=discord.Color.red()), ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        if filter_keyword.lower() not in utils.CUSTOM_EMBED_TEXT:
            await interaction.followup.send(embed=discord.Embed(title="Error", description=f"Invalid Filter: '{filter_keyword}'.", color=discord.Color.red()), ephemeral=True)
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
                            await interaction.followup.send(embed=discord.Embed(title="Error", description="Bot lacks permission to create channels.", color=discord.Color.red()), ephemeral=True)
                            return
            if not target_channel:
                await interaction.followup.send(embed=discord.Embed(title="Error", description="Could not auto-create channel. Provide one manually.", color=discord.Color.red()), ephemeral=True)
                return
        source_channel_ids = []
        if source_channels:
            for match in re.findall(r'<#(\d+)>', source_channels):
                try:
                    ch_id = int(match)
                    if interaction.client.get_channel(ch_id):
                        source_channel_ids.append(ch_id)
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
        await interaction.followup.send(embed=discord.Embed(
            title="New Filter Set",
            description=f"Filter '{filter_keyword}' → {target_channel.mention}\nSources: {sources_mention}\n"
                        f"God Pack Ping: {godpack_ping.mention if godpack_ping else 'Not set'}\n"
                        f"Invalid God Pack Ping: {invgodpack_ping.mention if invgodpack_ping else 'Not set'}\n"
                        f"Safe for Trade Ping: {safe_trade_ping.mention if safe_trade_ping else 'Not set'}",
            color=discord.Color.green()
        ))

    @app_commands.command(name="setpackfilter", description="Configuration of Filter for Packs")
    @app_commands.describe(
        pack="The Pack (ignored in series mode; sets all in series)",
        channel="The target channel (optional; auto-creates if omitted)",
        source_channels="Space-separated source channel mentions (optional)"
    )
    @app_commands.autocomplete(pack=utils.autocomplete_packs)
    async def setpackfilter(self, interaction: discord.Interaction, pack: str, channel: discord.TextChannel = None, source_channels: str = None):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(embed=discord.Embed(title="Error", description="Administrator required.", color=discord.Color.red()), ephemeral=True)
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
                await interaction.followup.send(embed=discord.Embed(title="Error", description=f"Pack '{pack}' not in any series.", color=discord.Color.red()), ephemeral=True)
                return
            packs_to_set = [p.lower() for p in utils.config["series"][series_name]]
            embed_desc = f"Series '{series_name}' ({len(packs_to_set)} packs)"
        else:
            if pack.lower() not in [p.lower() for p in utils.PACKS]:
                await interaction.followup.send(embed=discord.Embed(title="Error", description=f"Invalid Pack: '{pack}'.", color=discord.Color.red()), ephemeral=True)
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
                        try:
                            overwrites = {
                                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                            }
                            target_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                        except discord.Forbidden:
                            await interaction.followup.send(embed=discord.Embed(title="Error", description="Bot lacks permission to create channels.", color=discord.Color.red()), ephemeral=True)
                            return
            if not target_channel:
                await interaction.followup.send(embed=discord.Embed(title="Error", description="Could not auto-create channel. Provide one manually.", color=discord.Color.red()), ephemeral=True)
                return
        source_channel_ids = []
        if source_channels:
            for match in re.findall(r'<#(\d+)>', source_channels):
                try:
                    ch_id = int(match)
                    if interaction.client.get_channel(ch_id):
                        source_channel_ids.append(ch_id)
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
        await interaction.followup.send(embed=discord.Embed(
            title="New Pack Filter Set",
            description=f"{embed_desc} → {target_channel.mention}\nSources: {sources_mention}",
            color=discord.Color.green()
        ))

    @app_commands.command(name="removefilter", description="Remove a certain filter from the configuration")
    @app_commands.describe(filter_keyword="Filter to remove")
    @app_commands.choices(filter_keyword=utils.FILTER_CHOICES)
    async def removefilter(self, interaction: discord.Interaction, filter_keyword: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(embed=discord.Embed(title="Error", description="Administrator required.", color=discord.Color.red()), ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        if "keyword_channel_map" not in guild_config or filter_keyword.lower() not in guild_config["keyword_channel_map"]:
            await interaction.followup.send(embed=discord.Embed(title="Error", description=f"Filter '{filter_keyword}' not found.", color=discord.Color.red()), ephemeral=True)
            return
        del guild_config["keyword_channel_map"][filter_keyword.lower()]
        if not guild_config["keyword_channel_map"]:
            del guild_config["keyword_channel_map"]
        utils.save_guild_config(guild_id, guild_config)
        await interaction.followup.send(embed=discord.Embed(title="Filter Removed", description=f"Filter '{filter_keyword}' removed.", color=discord.Color.green()))

    @app_commands.command(name="removepackfilter", description="Remove a certain pack filter from the configuration")
    @app_commands.describe(pack="Pack to remove")
    @app_commands.autocomplete(pack=utils.autocomplete_packs)
    async def removepackfilter(self, interaction: discord.Interaction, pack: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(embed=discord.Embed(title="Error", description="Administrator required.", color=discord.Color.red()), ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        if "pack_channel_map" not in guild_config or pack.lower() not in guild_config["pack_channel_map"]:
            await interaction.followup.send(embed=discord.Embed(title="Error", description=f"Pack filter '{pack}' not found.", color=discord.Color.red()), ephemeral=True)
            return
        del guild_config["pack_channel_map"][pack.lower()]
        if not guild_config["pack_channel_map"]:
            del guild_config["pack_channel_map"]
        utils.save_guild_config(guild_id, guild_config)
        await interaction.followup.send(embed=discord.Embed(title="Pack Filter Removed", description=f"Pack filter '{pack}' removed.", color=discord.Color.green()))


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
