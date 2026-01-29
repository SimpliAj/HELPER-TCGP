"""
Setup Views für Bot-Konfiguration.
Enthält: ModeView, ValidatorView, PingSetupView, SourceModal, ValidationSetupView, HeartbeatSetupView
"""
import discord
import re
from config import load_guild_config, save_guild_config
from zoneinfo import ZoneInfo
from datetime import datetime


class ModeView(discord.ui.View):
    """View für Pack-Channel-Modus Auswahl (Series oder Pack)."""
    def __init__(self, original_user, guild_id, created_categories, config):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id
        self.created_categories = created_categories
        self.guild_config = load_guild_config(guild_id)
        self.config = config

    @discord.ui.button(label="One Channel per Series", style=discord.ButtonStyle.primary, custom_id="series_mode")
    async def series_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_user:
            await interaction.response.defer()
            return

        await interaction.response.defer(ephemeral=True)
        self.guild_config["pack_channel_mode"] = "series"

        # Override/create channels for series mode
        global_series = self.config.get("series", {})
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

        save_guild_config(self.guild_id, self.guild_config)

        # Proceed to Validator
        from views.setup_views import ValidatorView
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
            await interaction.response.defer()
            return

        await interaction.response.defer(ephemeral=True)
        self.guild_config["pack_channel_mode"] = "pack"

        # Create individual channels
        global_series = self.config.get("series", {})
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
                if "pack_channel_map" not in self.guild_config:
                    self.guild_config["pack_channel_map"] = {}
                self.guild_config["pack_channel_map"][pack.lower()] = {
                    "channel_id": channel.id,
                    "source_channel_ids": self.guild_config.get("default_source_channel_ids", [])
                }

        save_guild_config(self.guild_id, self.guild_config)

        # Proceed to Validator
        from views.setup_views import ValidatorView
        val_embed = discord.Embed(
            title="✅ Pack Mode Set! – Step 2: Validator Role",
            description="Pack channels finalized. Select validator role next.",
            color=discord.Color.green()
        )
        val_view = ValidatorView(self.original_user, self.guild_id, interaction.guild)
        await interaction.followup.send(embed=val_embed, view=val_view)
        self.stop()


class ValidatorView(discord.ui.View):
    """View für Validator-Rolle Auswahl."""
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
        guild_config = load_guild_config(self.guild_id)
        guild_config["validator_role_id"] = role_id
        save_guild_config(self.guild_id, guild_config)

        # Step 3: Ping Setup
        from views.setup_views import PingSetupView
        ping_embed = discord.Embed(
            title="Step 3: Optional Ping Roles",
            description="Select which ping roles to configure (optional).",
            color=discord.Color.green()
        )
        ping_view = PingSetupView(self.original_user, self.guild_id, inter.guild)
        await inter.response.send_message(embed=ping_embed, view=ping_view, ephemeral=True)
        self.stop()


class PingSetupView(discord.ui.View):
    """View für Ping-Rollen Setup."""
    def __init__(self, original_user, guild_id, guild):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id
        self.guild = guild
        self.ping_types = ["godpack", "invgodpack", "safe_trade"]
        self.ping_labels = {
            "godpack": "God Pack Ping",
            "invgodpack": "Invalid God Pack Ping",
            "safe_trade": "Safe for Trade Ping"
        }

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
            async def role_select(self, inter: discord.Interaction, select: discord.ui.Select):
                if inter.user != self.parent.original_user:
                    await inter.response.defer()
                    return
                await self.parent.ping_callback(inter, ping_type, int(select.values[0]))
        
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
        modal = SourceModal()
        modal.guild_id = self.guild_id
        modal.original_user = self.original_user
        await interaction.response.send_modal(modal)


class SourceModal(discord.ui.Modal, title="Set Source Channels (Optional)"):
    """Modal für Source Channel Eingabe."""
    source_input = discord.ui.TextInput(
        label="Source Channels",
        style=discord.TextStyle.short,
        placeholder="Mention channels: #general #tcg-chat (leave empty for all)",
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
            await interaction.followup.send("❌ Setup error: User not set.", ephemeral=True)
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
            
            if not source_ids or len(matches) != len(input_value.split(',')):
                channel_names = [name.strip().strip('#').strip().lower() for name in input_value.split(',') if name.strip()]
                for name in channel_names:
                    channel = None
                    for ch in interaction.guild.text_channels:
                        if ch.name.lower() == name:
                            channel = ch
                            break
                    if channel:
                        source_ids.append(channel.id)

        guild_config = load_guild_config(self.guild_id)
        guild_config["default_source_channel_ids"] = source_ids

        if "keyword_channel_map" in guild_config:
            for kw, cfg in guild_config["keyword_channel_map"].items():
                cfg["source_channel_ids"] = source_ids[:]
        if "pack_channel_map" in guild_config:
            for pack, cfg in guild_config["pack_channel_map"].items():
                cfg["source_channel_ids"] = source_ids[:]

        save_guild_config(self.guild_id, guild_config)

        # Proceed to Validation Setup
        from views.setup_views import ValidationSetupView
        val_embed = discord.Embed(
            title="Step 4: Validation Buttons",
            description="Enable traded buttons for Safe 4 Trade embeds?",
            color=discord.Color.green()
        )
        val_view = ValidationSetupView(self.original_user, self.guild_id, interaction.guild)
        await interaction.followup.send(embed=val_embed, view=val_view, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(f"Source modal error: {error}")
        await interaction.followup.send("An error occurred during source setup.", ephemeral=True)


class ValidationSetupView(discord.ui.View):
    """View für Validation Buttons Setup."""
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
        await interaction.followup.send("✅ Traded buttons enabled.", ephemeral=True)
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
        from views.setup_views import HeartbeatSetupView
        heartbeat_embed = discord.Embed(
            title="Step 5: Heartbeat Monitor",
            description="Enable heartbeat monitoring?",
            color=discord.Color.green()
        )
        heartbeat_view = HeartbeatSetupView(self.original_user, self.guild_id, self.guild)
        await interaction.followup.send(embed=heartbeat_embed, view=heartbeat_view, ephemeral=True)


class HeartbeatSetupView(discord.ui.View):
    """View für Heartbeat Monitor Setup."""
    def __init__(self, original_user, guild_id, guild):
        super().__init__(timeout=300)
        self.original_user = original_user
        self.guild_id = guild_id
        self.guild = guild

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
            
            @discord.ui.select(placeholder="Select Source Channel...", min_values=1, max_values=1)
            async def source_select(self, inter: discord.Interaction, select: discord.ui.Select):
                if inter.user != self.parent.original_user:
                    await inter.response.defer()
                    return
                
                source_id = int(select.values[0])
                await inter.response.defer()
                await inter.followup.send(f"✅ Source set to <#{source_id}>", ephemeral=True)
                
                class TargetSelectView(discord.ui.View):
                    def __init__(self, source_id, parent):
                        super().__init__(timeout=300)
                        self.source_id = source_id
                        self.parent = parent
                    
                    @discord.ui.select(placeholder="Select Target Channel...", min_values=1, max_values=1)
                    async def target_select(self, inter: discord.Interaction, select: discord.ui.Select):
                        if inter.user != self.parent.original_user:
                            await inter.response.defer()
                            return
                        
                        target_id = int(select.values[0])
                        guild_config = load_guild_config(self.parent.guild_id)
                        guild_config["heartbeat_source_channel_id"] = self.source_id
                        guild_config["heartbeat_target_channel_id"] = target_id
                        
                        from utils import create_heartbeat_embed
                        embed = create_heartbeat_embed(guild_config)
                        target_channel = self.parent.guild.get_channel(target_id)
                        sent_message = await target_channel.send(embed=embed)
                        guild_config["heartbeat_message_id"] = sent_message.id
                        save_guild_config(self.parent.guild_id, guild_config)
                        
                        await inter.response.defer()
                        await inter.followup.send(f"✅ Heartbeat configured. Target: <#{target_id}>", ephemeral=True)
                        
                        # Final embed
                        final_embed = self.parent.build_final_embed(self.parent.guild)
                        await inter.followup.send(embed=final_embed, ephemeral=True)
                        self.parent.stop()
                
                target_view = TargetSelectView(self.source_id, self.parent)
                target_channels = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in self.parent.guild.text_channels[:25]]
                target_view.target_select.options = target_channels
                await inter.followup.send("Select target channel for heartbeat:", view=target_view, ephemeral=True)
        
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
        from zoneinfo import ZoneInfo
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
                "Use /showfilters to verify. Enjoy your TCGP bot!"
            ),
            color=discord.Color.green()
        )
        return final_embed
