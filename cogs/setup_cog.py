import discord
from discord.ext import commands
from discord import app_commands
import re
import utils


# ============================================================
# SETUP VIEWS (used only during /setup flow)
# ============================================================

class ModeView(discord.ui.View):
    def __init__(self, original_user, guild_id, created_categories):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id
        self.created_categories = created_categories
        self.guild_config = utils.load_guild_config(guild_id)

    @discord.ui.button(label="One Channel per Series", style=discord.ButtonStyle.primary, custom_id="series_mode")
    async def series_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.followup.send("Only the command issuer can proceed.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        self.guild_config["pack_channel_mode"] = "series"
        global_series = utils.config.get("series", {})
        for series_name, packs_in_series in global_series.items():
            if not packs_in_series:
                continue
            cat = self.created_categories.get(series_name)
            if not cat:
                continue
            channel_name = f"{series_name.lower().replace(' ', '-')}-packs"
            channel = discord.utils.get(cat.text_channels, name=channel_name)
            if not channel:
                overwrites = {
                    interaction.guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                }
                channel = await cat.create_text_channel(channel_name, overwrites=overwrites)
            for pack in packs_in_series:
                if "pack_channel_map" not in self.guild_config:
                    self.guild_config["pack_channel_map"] = {}
                self.guild_config["pack_channel_map"][pack.lower()] = {
                    "channel_id": channel.id,
                    "source_channel_ids": self.guild_config.get("default_source_channel_ids", [])
                }
        utils.save_guild_config(self.guild_id, self.guild_config)
        val_embed = discord.Embed(
            title="✅ Series Mode Set! – Step 2: Validator Role",
            description="Pack channels finalized. Select validator role next.",
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
        global_series = utils.config.get("series", {})
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
                if "pack_channel_map" not in self.guild_config:
                    self.guild_config["pack_channel_map"] = {}
                self.guild_config["pack_channel_map"][pack.lower()] = {
                    "channel_id": channel.id,
                    "source_channel_ids": self.guild_config.get("default_source_channel_ids", [])
                }
        utils.save_guild_config(self.guild_id, self.guild_config)
        val_embed = discord.Embed(
            title="✅ Pack Mode Set! – Step 2: Validator Role",
            description=f"Created {created_in_mode} individual pack channels. Select validator role next.",
            color=discord.Color.green()
        )
        val_view = ValidatorView(self.original_user, self.guild_id, interaction.guild)
        await interaction.followup.send(embed=val_embed, view=val_view)
        self.stop()


class ValidatorView(discord.ui.View):
    def __init__(self, original_user, guild_id, guild):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id
        self.guild = guild
        roles = sorted(guild.roles, key=lambda r: r.position, reverse=True)[:25]
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
        guild_config = utils.load_guild_config(self.guild_id)
        guild_config["validator_role_id"] = role_id
        utils.save_guild_config(self.guild_id, guild_config)
        ping_embed = discord.Embed(
            title="Step 3: Optional Ping Roles",
            description="Select which ping roles to configure (optional). You can skip and set them later with /setpingroles.",
            color=discord.Color.green()
        )
        ping_view = PingSetupView(self.original_user, self.guild_id, inter.guild)
        await inter.response.send_message(embed=ping_embed, view=ping_view, ephemeral=True)
        self.stop()


class PingSetupView(discord.ui.View):
    def __init__(self, original_user, guild_id, guild):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id
        self.guild = guild
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
        await interaction.followup.send(f"Select the role for {self.ping_labels[ping_type]}:", view=view, ephemeral=True)

    async def ping_callback(self, interaction: discord.Interaction, ping_type: str, role_id: int):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        guild_config = utils.load_guild_config(self.guild_id)
        guild_config[f"{ping_type}_ping"] = role_id
        utils.save_guild_config(self.guild_id, guild_config)
        await interaction.response.defer()
        await interaction.followup.send(f"✅ {self.ping_labels[ping_type]} set to <@&{role_id}>", ephemeral=True)

    async def proceed_to_next_step(self, interaction: discord.Interaction):
        modal = SourceModal()
        modal.guild_id = self.guild_id
        modal.original_user = self.original_user
        await interaction.response.send_modal(modal)


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
        self.guild_id = None
        self.original_user = None

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.original_user:
            await interaction.followup.send("❌ Setup error: Original user not set. Please restart /setup.", ephemeral=True)
            return

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
                channel_names = [name.strip().strip('#').strip().lower() for name in input_value.split(',') if name.strip()]
                for name in channel_names:
                    for ch in interaction.guild.text_channels:
                        if ch.name.lower() == name:
                            source_ids.append(ch.id)
                            break

        guild_config = utils.load_guild_config(self.guild_id)
        guild_config["default_source_channel_ids"] = source_ids
        if "keyword_channel_map" in guild_config:
            for kw, cfg in guild_config["keyword_channel_map"].items():
                cfg["source_channel_ids"] = source_ids[:]
        if "pack_channel_map" in guild_config:
            for pack, cfg in guild_config["pack_channel_map"].items():
                cfg["source_channel_ids"] = source_ids[:]
        utils.save_guild_config(self.guild_id, guild_config)

        val_embed = discord.Embed(
            title="Step 4: Validation Buttons",
            description="Do you want to enable traded buttons for Safe 4 Trade embeds?",
            color=discord.Color.green()
        )
        val_view = ValidationSetupView(self.original_user, self.guild_id, interaction.guild)
        await interaction.followup.send(embed=val_embed, view=val_view, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(f"Source modal error: {error}")
        await interaction.followup.send("An error occurred during source setup.", ephemeral=True)


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
        guild_config = utils.load_guild_config(self.guild_id)
        guild_config["validation_buttons_enabled"] = True
        utils.save_guild_config(self.guild_id, guild_config)
        await interaction.followup.send("✅ Traded buttons enabled for Safe 4 Trade embeds.", ephemeral=True)
        await self.proceed_to_heartbeat(interaction)

    @discord.ui.button(label="Disable Traded Buttons", style=discord.ButtonStyle.danger)
    async def disable_validation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        await interaction.response.defer(ephemeral=True)
        guild_config = utils.load_guild_config(self.guild_id)
        guild_config["validation_buttons_enabled"] = False
        utils.save_guild_config(self.guild_id, guild_config)
        await interaction.followup.send("✅ Traded buttons disabled.", ephemeral=True)
        await self.proceed_to_heartbeat(interaction)

    async def proceed_to_heartbeat(self, interaction: discord.Interaction):
        heartbeat_embed = discord.Embed(
            title="Step 5: Heartbeat Monitor",
            description="Do you want to enable the heartbeat monitor?",
            color=discord.Color.green()
        )
        heartbeat_view = HeartbeatSetupView(self.original_user, self.guild_id, interaction.guild)
        await interaction.followup.send(embed=heartbeat_embed, view=heartbeat_view, ephemeral=True)


class HeartbeatSetupView(discord.ui.View):
    def __init__(self, original_user, guild_id, guild):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id
        self.guild = guild
        self.source_id = None

    @discord.ui.button(label="Enable Heartbeat", style=discord.ButtonStyle.success)
    async def enable_heartbeat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        await interaction.response.defer(ephemeral=True)

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
                        guild_config = utils.load_guild_config(self.parent.guild_id)
                        guild_config["heartbeat_source_channel_id"] = self.source_id
                        guild_config["heartbeat_target_channel_id"] = target_id
                        embed = utils.create_heartbeat_embed(guild_config)
                        target_channel = self.parent.guild.get_channel(target_id)
                        sent_message = await target_channel.send(embed=embed)
                        guild_config["heartbeat_message_id"] = sent_message.id
                        utils.save_guild_config(self.parent.guild_id, guild_config)
                        await interaction.response.defer()
                        await interaction.followup.send(f"✅ Heartbeat configured. Target: <#{target_id}>", ephemeral=True)
                        final_embed = self.parent.build_final_embed(self.parent.guild)
                        await interaction.followup.send(embed=final_embed, ephemeral=True)
                        self.parent.stop()

                target_view = TargetSelectView(self.source_id, self.parent)
                target_channels = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in self.parent.guild.text_channels[:25]]
                target_view.target_select.options = target_channels
                await interaction.followup.send("Select target channel for heartbeat:", view=target_view, ephemeral=True)

        view = ChannelSelectView(self)
        channels = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in interaction.guild.text_channels[:25]]
        view.source_select.options = channels
        await interaction.followup.send("Select source channel for heartbeat:", view=view, ephemeral=True)

    @discord.ui.button(label="Disable Heartbeat", style=discord.ButtonStyle.danger)
    async def disable_heartbeat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        await interaction.response.defer()
        final_embed = self.build_final_embed(interaction.guild)
        await interaction.followup.send(embed=final_embed, ephemeral=True)
        self.stop()

    def build_final_embed(self, guild):
        guild_config = utils.load_guild_config(self.guild_id)
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


# ============================================================
# SETUP COG
# ============================================================

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Automated setup for bot channels, categories, and configurations (Admin only)")
    async def setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            embed = discord.Embed(title="Error", description="Unable to fetch your member information. Please try again.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        if not member.guild_permissions.administrator:
            embed = discord.Embed(title="Error", description="You need administrator permissions to use this command.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        guild = interaction.guild
        guild_id = str(guild.id)

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
        embed.set_thumbnail(url="https://i.imgur.com/iNJRSxh.png")

        class SetupView(discord.ui.View):
            def __init__(self_inner, original_user):
                super().__init__(timeout=300)
                self_inner.original_user = original_user

            @discord.ui.button(label="✅ Agree & Setup", style=discord.ButtonStyle.success, emoji="✅")
            async def agree(self_inner, inter: discord.Interaction, button: discord.ui.Button):
                if inter.user != self_inner.original_user:
                    await inter.followup.send("Only the command issuer can proceed.", ephemeral=True)
                    return
                await inter.response.defer(ephemeral=True)
                try:
                    guild_config = utils.load_guild_config(guild_id)

                    if "B-Series" not in utils.config["series"]:
                        utils.config["series"]["B-Series"] = []
                        utils.update_packs(utils.config)
                        utils.config["packs"] = utils.PACKS
                        utils.save_config(utils.config)

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
                        "A-Series": {"series": "A-Series", "channel_name": "a-series"},
                        "B-Series": {"series": "B-Series", "channel_name": "b-series"}
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

                    keyword_channel_map = {}
                    created_keyword_channels = 0
                    for cat_name, cfg in category_configs.items():
                        if "keywords" in cfg:
                            category = created_channels[cat_name]
                            for keyword in cfg["keywords"]:
                                clean_name = keyword.lower().replace(" ", "-").replace("invalid god pack", "invalid-god-pack")
                                old_channel_name = f"{cfg['channel_prefix']}{clean_name}"
                                channel_name = utils.OLD_TO_NEW_CHANNEL_NAMES.get(old_channel_name, clean_name)
                                existing_channel = discord.utils.get(category.text_channels, name=channel_name)
                                if not existing_channel:
                                    overwrites = {
                                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                                    }
                                    existing_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                                    created_keyword_channels += 1
                                old_channel = discord.utils.get(category.text_channels, name=old_channel_name)
                                if old_channel:
                                    await old_channel.edit(name=channel_name)
                                keyword_channel_map[keyword.lower()] = {
                                    "channel_id": existing_channel.id,
                                    "source_channel_ids": []
                                }

                    if keyword_channel_map:
                        guild_config["keyword_channel_map"] = keyword_channel_map
                        utils.save_guild_config(guild_id, guild_config)

                    created_pack_channels = 0
                    for cat_name, cfg in category_configs.items():
                        if "series" in cfg:
                            category = created_channels[cat_name]
                            series_name = cfg["series"]
                            global_series_packs = utils.config.get("series", {}).get(series_name, [])
                            if global_series_packs:
                                channel_name = f"{series_name.lower().replace(' ', '-')}-packs"
                                existing_channel = discord.utils.get(category.text_channels, name=channel_name)
                                if not existing_channel:
                                    overwrites = {
                                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                                    }
                                    existing_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                                    created_pack_channels += 1
                                if "pack_channel_map" not in guild_config:
                                    guild_config["pack_channel_map"] = {}
                                for pack in global_series_packs:
                                    guild_config["pack_channel_map"][pack.lower()] = {
                                        "channel_id": existing_channel.id,
                                        "source_channel_ids": []
                                    }
                    utils.save_guild_config(guild_id, guild_config)

                    mode_embed = discord.Embed(
                        title="✅ Keyword Channels Created! – Step 1: Choose Pack Channel Mode",
                        description=f"Created {created_keyword_channels} filter channels + {created_pack_channels} default pack channels.\n\n"
                                    "Select mode to finalize/override pack channels (no empties left):\n\n"
                                    "**One Channel per Series:** Uses the pre-created #a-series-packs, etc.\n"
                                    "**One Channel per Pack:** Creates individual #palkia-pack, etc. (overrides defaults).",
                        color=discord.Color.orange()
                    )
                    mode_view = ModeView(self_inner.original_user, guild_id, created_channels)
                    await inter.followup.send(embed=mode_embed, view=mode_view)

                    setup_embed = discord.Embed(
                        title="✅ Setup In Progress!",
                        description=f"Categories & {created_keyword_channels} filter channels created. {created_pack_channels} default pack channels ready. Finalizing packs next.",
                        color=discord.Color.green()
                    )
                    await inter.edit_original_response(embed=setup_embed, view=None)

                except discord.Forbidden:
                    error_msg = "Bot lacks 'Manage Channels' permission. Grant it and try again."
                    error_embed = discord.Embed(title="❌ Permission Error", description=error_msg, color=discord.Color.red())
                    await inter.followup.send(embed=error_embed, ephemeral=True)
                    await utils.log_permission_warning_to_webhook(error_msg, guild_id=str(guild.id), command_name="setup")
                except Exception as e:
                    print(f"Setup error: {e}")
                    error_msg = f"An error occurred: {str(e)}"
                    error_embed = discord.Embed(title="❌ Setup Failed", description=error_msg, color=discord.Color.red())
                    await inter.followup.send(embed=error_embed, ephemeral=True)
                    await utils.log_error_to_webhook(error_msg, guild_id=str(guild.id), command_name="setup")

        view = SetupView(interaction.user)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="resetsources", description="Set or reset source channels (Admin only)")
    async def resetsources(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        member = interaction.guild.get_member(interaction.user.id)
        if member is None or not member.guild_permissions.administrator:
            embed = discord.Embed(title="Error", description="You need administrator permissions to use this command.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        has_sources = "default_source_channel_ids" in guild_config and guild_config["default_source_channel_ids"]

        class SourceOptionsView(discord.ui.View):
            def __init__(self_inner):
                super().__init__(timeout=300)

            @discord.ui.button(label="Set New Sources", style=discord.ButtonStyle.primary)
            async def set_sources(self_inner, inter: discord.Interaction, button: discord.ui.Button):
                modal = SourceModal()
                modal.guild_id = guild_id
                modal.original_user = inter.user
                await inter.response.send_modal(modal)

            @discord.ui.button(label="Reset to All Channels", style=discord.ButtonStyle.danger)
            async def reset_sources(self_inner, inter: discord.Interaction, button: discord.ui.Button):
                await inter.response.defer(ephemeral=True)
                gc = utils.load_guild_config(guild_id)
                old_sources = gc.get("default_source_channel_ids", [])
                gc["default_source_channel_ids"] = []
                if "keyword_channel_map" in gc:
                    for kw, cfg in gc["keyword_channel_map"].items():
                        cfg["source_channel_ids"] = []
                if "pack_channel_map" in gc:
                    for pack, cfg in gc["pack_channel_map"].items():
                        cfg["source_channel_ids"] = []
                utils.save_guild_config(guild_id, gc)
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
                description="No source channels currently set (monitoring all channels).\n\nWhat do you want to do?",
                color=discord.Color.blue()
            )

        view = SourceOptionsView()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
