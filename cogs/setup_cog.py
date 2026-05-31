import discord
from discord.ext import commands
from discord import app_commands
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
        val_view = ValidatorView(self.original_user, self.guild_id)
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
        val_view = ValidatorView(self.original_user, self.guild_id)
        await interaction.followup.send(embed=val_embed, view=val_view)
        self.stop()


class ValidatorView(discord.ui.View):
    def __init__(self, original_user, guild_id):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select Validator Role...",
        min_values=1, max_values=1,
        row=0,
    )
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        role = select.values[0]
        gc = utils.load_guild_config(self.guild_id)
        gc["validator_role_id"] = role.id
        utils.save_guild_config(self.guild_id, gc)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Step 3: Optional Ping Roles",
                description=f"✅ Validator role set to {role.mention}\n\nNow configure ping roles (optional). Skip to set later with /configure.",
                color=discord.Color.green(),
            ),
            view=PingSetupView(self.original_user, self.guild_id),
        )


_PING_LABELS = {"godpack": "God Pack", "invgodpack": "Invalid God Pack", "safe_trade": "Safe for Trade"}


class PingSetupView(discord.ui.View):
    def __init__(self, original_user, guild_id):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id

    def _ping_embed(self) -> discord.Embed:
        gc = utils.load_guild_config(self.guild_id)
        lines = []
        for key, label in _PING_LABELS.items():
            rid = gc.get(f"{key}_ping")
            lines.append(f"**{label}:** {'<@&' + str(rid) + '>' if rid else '*not set*'}")
        return discord.Embed(
            title="Step 3: Ping Roles (Optional)",
            description="\n".join(lines) + "\n\nSet each ping role or click **Continue** when done.",
            color=discord.Color.green(),
        )

    @discord.ui.button(label="God Pack Ping", style=discord.ButtonStyle.primary, row=0)
    async def godpack_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        await self._show_role_picker(interaction, "godpack")

    @discord.ui.button(label="Invalid God Pack Ping", style=discord.ButtonStyle.primary, row=0)
    async def invgodpack_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        await self._show_role_picker(interaction, "invgodpack")

    @discord.ui.button(label="Safe for Trade Ping", style=discord.ButtonStyle.primary, row=1)
    async def safe_trade_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        await self._show_role_picker(interaction, "safe_trade")

    @discord.ui.button(label="Continue →", style=discord.ButtonStyle.secondary, row=1)
    async def skip_pings(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        await self.proceed_to_next_step(interaction)

    async def _show_role_picker(self, interaction: discord.Interaction, ping_type: str):
        guild_id = self.guild_id
        original_user = self.original_user
        parent = self

        class PingRoleView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)

            @discord.ui.select(
                cls=discord.ui.RoleSelect,
                placeholder=f"Select role for {_PING_LABELS[ping_type]} ping...",
                min_values=1, max_values=1,
                row=0,
            )
            async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
                if interaction.user != original_user:
                    await interaction.response.defer()
                    return
                gc = utils.load_guild_config(guild_id)
                gc[f"{ping_type}_ping"] = select.values[0].id
                utils.save_guild_config(guild_id, gc)
                await interaction.response.edit_message(embed=parent._ping_embed(), view=parent)

        await interaction.response.edit_message(
            embed=discord.Embed(
                title=f"🔔 {_PING_LABELS[ping_type]} Ping",
                description="Select a role to ping when this event occurs.",
                color=discord.Color.blue(),
            ),
            view=PingRoleView(),
        )

    async def proceed_to_next_step(self, interaction: discord.Interaction):
        view = SetupSourceView(self.guild_id, self.original_user)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Step 3: Source Channels (Optional)",
                description="Select which channels the bot should listen to for card detection.\nLeave empty and click **Skip** to listen to all channels.",
                color=discord.Color.blue(),
            ),
            view=view,
        )


class SetupSourceView(discord.ui.View):
    def __init__(self, guild_id: str, original_user):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.original_user = original_user
        self.source_ids = []

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Select source channel(s)...",
        min_values=1, max_values=25,
        channel_types=[discord.ChannelType.text],
        row=0,
    )
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        self.source_ids = [ch.id for ch in select.values]
        await interaction.response.defer()

    @discord.ui.button(label="✅ Save & Continue", style=discord.ButtonStyle.success, row=1)
    async def save(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        await self._apply(interaction, self.source_ids)

    @discord.ui.button(label="Skip (All Channels)", style=discord.ButtonStyle.secondary, row=1)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return
        await self._apply(interaction, [])

    async def _apply(self, interaction: discord.Interaction, source_ids: list):
        gc = utils.load_guild_config(self.guild_id)
        gc["default_source_channel_ids"] = source_ids
        for cfg in gc.get("keyword_channel_map", {}).values():
            cfg["source_channel_ids"] = source_ids[:]
        for cfg in gc.get("pack_channel_map", {}).values():
            cfg["source_channel_ids"] = source_ids[:]
        utils.save_guild_config(self.guild_id, gc)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Step 4: Validation Buttons",
                description="Do you want to enable traded buttons for Safe 4 Trade embeds?",
                color=discord.Color.green(),
            ),
            view=ValidationSetupView(self.original_user, self.guild_id, interaction.guild),
        )


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
        original_user = self.original_user
        guild_id = self.guild_id
        parent = self

        class HeartbeatSetupView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)
                self.source_ids = []
                self.target_id = None

            @discord.ui.select(
                cls=discord.ui.ChannelSelect,
                placeholder="1. Source channel(s) — where heartbeat bot posts",
                min_values=1, max_values=10,
                channel_types=[discord.ChannelType.text],
                row=0,
            )
            async def source_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
                if interaction.user != original_user:
                    await interaction.response.defer()
                    return
                self.source_ids = [ch.id for ch in select.values]
                await interaction.response.defer()

            @discord.ui.select(
                cls=discord.ui.ChannelSelect,
                placeholder="2. Target channel — heartbeat embed posted here",
                min_values=1, max_values=1,
                channel_types=[discord.ChannelType.text],
                row=1,
            )
            async def target_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
                if interaction.user != original_user:
                    await interaction.response.defer()
                    return
                self.target_id = select.values[0].id
                await interaction.response.defer()

            @discord.ui.button(label="✅ Save Heartbeat", style=discord.ButtonStyle.success, row=2)
            async def confirm(self, interaction: discord.Interaction, btn: discord.ui.Button):
                if interaction.user != original_user:
                    await interaction.response.defer()
                    return
                if not self.source_ids or not self.target_id:
                    await interaction.response.send_message("❌ Select source and target channels first.", ephemeral=True)
                    return
                gc = utils.load_guild_config(guild_id)
                gc["heartbeat_source_channel_ids"] = self.source_ids
                gc["heartbeat_source_channel_id"] = self.source_ids[0]
                gc["heartbeat_target_channel_id"] = self.target_id
                embed = utils.create_heartbeat_embed(gc)
                target_ch = interaction.guild.get_channel(self.target_id)
                sent = await target_ch.send(embed=embed)
                gc["heartbeat_message_id"] = sent.id
                utils.save_guild_config(guild_id, gc)
                final_embed = parent.build_final_embed(interaction.guild)
                await interaction.response.edit_message(embed=final_embed, view=None)
                parent.stop()

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Step 5: Heartbeat",
                description="Select the source channel(s) where the heartbeat bot posts, then the target channel for the embed.",
                color=discord.Color.blue(),
            ),
            view=HeartbeatSetupView(),
        )

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

                    _role_ids = guild_config.get("pack_category_view_roles", [])
                    _roles = [r for rid in _role_ids if (r := guild.get_role(rid))]

                    def _setup_ow():
                        ow = {guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)}
                        if _roles:
                            ow[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
                            for role in _roles:
                                ow[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
                        else:
                            ow[guild.default_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
                        return ow

                    created_channels = {}
                    for cat_name, cfg in category_configs.items():
                        category = discord.utils.get(guild.categories, name=cat_name)
                        if not category:
                            category = await guild.create_category(cat_name, overwrites=_setup_ow())
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
                                    existing_channel = await category.create_text_channel(channel_name, overwrites=_setup_ow())
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



async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
