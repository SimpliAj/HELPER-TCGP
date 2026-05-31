import discord
from discord.ext import commands
from discord import app_commands
import re
import utils


# ── Modals ────────────────────────────────────────────────────────────────────

class HeartbeatConfigView(discord.ui.View):
    def __init__(self, guild_id: str):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.source_ids = []
        self.target_id = None

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="1. Source channel(s) — bot reads heartbeat here",
        min_values=1, max_values=10,
        channel_types=[discord.ChannelType.text],
        row=0,
    )
    async def source_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
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
        self.target_id = select.values[0].id
        await interaction.response.defer()

    @discord.ui.button(label="✅ Save Heartbeat", style=discord.ButtonStyle.success, row=2)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.source_ids or not self.target_id:
            await interaction.response.send_message("❌ Select source and target channels first.", ephemeral=True)
            return
        gc = utils.load_guild_config(self.guild_id)
        gc["heartbeat_source_channel_ids"] = self.source_ids
        gc["heartbeat_source_channel_id"] = self.source_ids[0]
        gc["heartbeat_target_channel_id"] = self.target_id
        embed = utils.create_heartbeat_embed(gc)
        target_ch = interaction.guild.get_channel(self.target_id)
        sent = await target_ch.send(embed=embed)
        gc["heartbeat_message_id"] = sent.id
        utils.save_guild_config(self.guild_id, gc)
        sources = ", ".join(f"<#{sid}>" for sid in self.source_ids)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ Heartbeat Configured",
                description=f"**Sources:** {sources}\n**Target:** <#{self.target_id}>",
                color=discord.Color.green(),
            ),
            view=None,
        )


class ValidatorRoleView(discord.ui.View):
    def __init__(self, guild_id: str):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select the validator role...",
        min_values=1, max_values=1,
        row=0,
    )
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        role = select.values[0]
        gc = utils.load_guild_config(self.guild_id)
        gc["validator_role_id"] = role.id
        utils.save_guild_config(self.guild_id, gc)
        await interaction.response.edit_message(
            embed=discord.Embed(title="✅ Validator Role Set", description=f"Set to {role.mention}.", color=discord.Color.green()),
            view=None,
        )


class SourceChannelView(discord.ui.View):
    def __init__(self, guild_id: str):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.source_ids = []

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Select source channel(s)...",
        min_values=1, max_values=25,
        channel_types=[discord.ChannelType.text],
        row=0,
    )
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        self.source_ids = [ch.id for ch in select.values]
        await interaction.response.defer()

    @discord.ui.button(label="✅ Save Sources", style=discord.ButtonStyle.success, row=1)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        gc = utils.load_guild_config(self.guild_id)
        gc["default_source_channel_ids"] = self.source_ids
        for cfg in gc.get("keyword_channel_map", {}).values():
            cfg["source_channel_ids"] = self.source_ids[:]
        for cfg in gc.get("pack_channel_map", {}).values():
            cfg["source_channel_ids"] = self.source_ids[:]
        utils.save_guild_config(self.guild_id, gc)
        mentions = ", ".join(f"<#{sid}>" for sid in self.source_ids) if self.source_ids else "All channels"
        await interaction.response.edit_message(
            embed=discord.Embed(title="✅ Sources Updated", description=f"Source channels: {mentions}", color=discord.Color.green()),
            view=None,
        )

    @discord.ui.button(label="Reset (All Channels)", style=discord.ButtonStyle.danger, row=1)
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        gc = utils.load_guild_config(self.guild_id)
        gc["default_source_channel_ids"] = []
        for cfg in gc.get("keyword_channel_map", {}).values():
            cfg["source_channel_ids"] = []
        for cfg in gc.get("pack_channel_map", {}).values():
            cfg["source_channel_ids"] = []
        utils.save_guild_config(self.guild_id, gc)
        await interaction.response.edit_message(
            embed=discord.Embed(title="✅ Sources Reset", description="Listening to all channels.", color=discord.Color.green()),
            view=None,
        )


# ── Pack Role View ────────────────────────────────────────────────────────────

def _bot_category_names() -> set:
    """All category names the bot manages (setup categories + series names)."""
    fixed = {"Save 4 Trade", "God Packs", "Detection"}
    series = set(utils.config.get("series", {}).keys())
    return fixed | series


def _is_bot_category(cat: discord.CategoryChannel) -> bool:
    return cat.name.endswith(" - Save 4 Trade") or cat.name in _bot_category_names()


class PackRoleView(discord.ui.View):
    def __init__(self, guild_id: str):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.role_ids = []

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select roles that can access bot channels...",
        min_values=0, max_values=10,
        row=0,
    )
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        self.role_ids = [r.id for r in select.values]
        await interaction.response.defer()

    @discord.ui.button(label="✅ Save Roles", style=discord.ButtonStyle.success, row=1)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        gc = utils.load_guild_config(self.guild_id)
        gc["pack_category_view_roles"] = self.role_ids
        utils.save_guild_config(self.guild_id, gc)

        guild = interaction.guild
        pack_roles = [r for rid in self.role_ids if (r := guild.get_role(rid))]

        def _ow():
            ow = {guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)}
            if pack_roles:
                ow[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
                for role in pack_roles:
                    ow[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
            else:
                ow[guild.default_role] = discord.PermissionOverwrite(view_channel=True)
            return ow

        updated = 0
        for cat in guild.categories:
            if not _is_bot_category(cat):
                continue
            try:
                await cat.edit(overwrites=_ow())
            except Exception:
                pass
            for ch in cat.text_channels:
                try:
                    await ch.edit(sync_permissions=True)
                    updated += 1
                except Exception:
                    pass

        if self.role_ids:
            desc = "Bot channels **hidden** from @everyone, **visible** to: " + ", ".join(f"<@&{r}>" for r in self.role_ids)
        else:
            desc = "No role restriction — bot channels visible to everyone."
        if updated:
            desc += f"\n✅ Updated {updated} channel(s) across all bot categories."
        await interaction.followup.send(
            embed=discord.Embed(title="✅ Channel Access Roles Saved", description=desc, color=discord.Color.green()),
            ephemeral=True,
        )

    @discord.ui.button(label="🗑 Clear (Allow Everyone)", style=discord.ButtonStyle.danger, row=1)
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        gc = utils.load_guild_config(self.guild_id)
        gc["pack_category_view_roles"] = []
        utils.save_guild_config(self.guild_id, gc)
        guild = interaction.guild
        open_ow = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        updated = 0
        for cat in guild.categories:
            if not _is_bot_category(cat):
                continue
            try:
                await cat.edit(overwrites=open_ow)
            except Exception:
                pass
            for ch in cat.text_channels:
                try:
                    await ch.edit(sync_permissions=True)
                    updated += 1
                except Exception:
                    pass
        desc = "All bot channels visible to everyone."
        if updated:
            desc += f"\n✅ Updated {updated} channel(s)."
        await interaction.followup.send(
            embed=discord.Embed(title="✅ Roles Cleared", description=desc, color=discord.Color.green()),
            ephemeral=True,
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
                discord.SelectOption(label="Channel Access Roles", value="packroles", description="Roles that can see all bot-managed categories", emoji="🔒"),
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
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="💓 Configure Heartbeat",
                    description="**Step 1:** Select source channel(s) where the heartbeat bot posts.\n**Step 2:** Select the target channel where the embed should appear.\n**Step 3:** Click Save.",
                    color=discord.Color.blue(),
                ),
                view=HeartbeatConfigView(self.guild_id),
            )

        elif choice == "packroles":
            gc = utils.load_guild_config(self.guild_id)
            current_ids = gc.get("pack_category_view_roles", [])
            current_str = ", ".join(f"<@&{r}>" for r in current_ids) if current_ids else "Everyone (no restriction)"
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="🔒 Pack Category Roles",
                    description=f"**Current:** {current_str}\n\nSelect the roles that can see all bot-managed categories (Save 4 Trade, God Packs, Detection, Series, Pack-specific). @everyone gets hidden.",
                    color=discord.Color.blue(),
                ),
                view=PackRoleView(self.guild_id),
            )

        elif choice == "validatorrole":
            gc = utils.load_guild_config(self.guild_id)
            current = gc.get("validator_role_id")
            current_str = f"<@&{current}>" if current else "*not set*"
            await interaction.response.edit_message(
                embed=discord.Embed(title="🛡️ Validator Role", description=f"**Current:** {current_str}\n\nSelect the role allowed to use validation buttons.", color=discord.Color.blue()),
                view=ValidatorRoleView(self.guild_id),
            )

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
            gc = utils.load_guild_config(self.guild_id)
            current_sources = gc.get("default_source_channel_ids", [])
            sources_mention = ', '.join([f'<#{sid}>' for sid in current_sources]) if current_sources else "All channels"
            await interaction.response.edit_message(
                embed=discord.Embed(title="📡 Source Channels", description=f"**Current:** {sources_mention}\n\nSelect up to 25 channels to listen to. Click Reset to listen to all.", color=discord.Color.blue()),
                view=SourceChannelView(self.guild_id)
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


# ── /filters helpers ──────────────────────────────────────────────────────────

def build_filters_embed(guild: discord.Guild, gc: dict) -> discord.Embed:
    keyword_map = gc.get("keyword_channel_map", {})
    pack_map = gc.get("pack_channel_map", {})
    pack_mode = gc.get("pack_channel_mode", "series")

    embed = discord.Embed(
        title="🔍 Active Filters",
        description=f"Pack Mode: **{pack_mode.title()}** — select an action below.",
        color=discord.Color.blurple()
    )

    if keyword_map:
        lines = []
        for kw, cfg in keyword_map.items():
            ch = guild.get_channel(cfg["channel_id"])
            ch_str = ch.mention if ch else f"<#{cfg['channel_id']}>"
            src = "Custom" if cfg.get("source_channel_ids") else "All channels"
            lines.append(f"**{kw.title()}** → {ch_str} ({src})")
        embed.add_field(name="Keyword Filters", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Keyword Filters", value="*none*", inline=False)

    if pack_map:
        by_series: dict = {}
        for pack, cfg in pack_map.items():
            series = next((s for s, packs in utils.config["series"].items() if pack in [p.lower() for p in packs]), "Unassigned")
            by_series.setdefault(series, [])
            ch = guild.get_channel(cfg["channel_id"])
            ch_str = ch.mention if ch else f"<#{cfg['channel_id']}>"
            src = "Custom" if cfg.get("source_channel_ids") else "All channels"
            by_series[series].append(f"**{pack.title()}** → {ch_str} ({src})")
        for series_name, lines in by_series.items():
            embed.add_field(name=f"Pack Filters — {series_name}", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Pack Filters", value="*none*", inline=False)

    return embed


class FiltersView(discord.ui.View):
    def __init__(self, guild_id: str):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        select = discord.ui.Select(
            placeholder="Manage filters...",
            options=[
                discord.SelectOption(label="Remove Keyword Filter", value="remove_kw", emoji="🗑️", description="Remove a specific keyword filter"),
                discord.SelectOption(label="Remove Pack Filter", value="remove_pack", emoji="🗑️", description="Remove a specific pack filter"),
                discord.SelectOption(label="Clear Keyword Filters", value="clear_kw", emoji="❌", description="Delete all keyword filters"),
                discord.SelectOption(label="Clear Pack Filters", value="clear_pack", emoji="❌", description="Delete all pack filters"),
                discord.SelectOption(label="Clear All Filters", value="clear_all", emoji="🧹", description="Delete every filter"),
            ]
        )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        gc = utils.load_guild_config(self.guild_id)
        choice = interaction.data["values"][0]

        if choice == "remove_kw":
            kw_map = gc.get("keyword_channel_map", {})
            if not kw_map:
                await interaction.response.send_message("No keyword filters configured.", ephemeral=True)
                return
            opts = [discord.SelectOption(label=k.title(), value=k) for k in list(kw_map.keys())[:25]]
            sel = discord.ui.Select(placeholder="Select keyword filter to remove...", options=opts)
            guild_id = self.guild_id
            async def remove_kw_cb(inter: discord.Interaction):
                kw = inter.data["values"][0]
                gc2 = utils.load_guild_config(guild_id)
                gc2.get("keyword_channel_map", {}).pop(kw, None)
                if not gc2.get("keyword_channel_map"):
                    gc2.pop("keyword_channel_map", None)
                utils.save_guild_config(guild_id, gc2)
                await inter.response.edit_message(
                    embed=discord.Embed(title="✅ Filter Removed", description=f"Keyword filter **{kw.title()}** removed.", color=discord.Color.green()),
                    view=None
                )
            sel.callback = remove_kw_cb
            v = discord.ui.View(); v.add_item(sel)
            await interaction.response.edit_message(
                embed=discord.Embed(title="🗑️ Remove Keyword Filter", description="Select the filter to remove:", color=discord.Color.blue()),
                view=v
            )

        elif choice == "remove_pack":
            pack_map = gc.get("pack_channel_map", {})
            if not pack_map:
                await interaction.response.send_message("No pack filters configured.", ephemeral=True)
                return
            opts = [discord.SelectOption(label=p.title(), value=p) for p in list(pack_map.keys())[:25]]
            sel = discord.ui.Select(placeholder="Select pack filter to remove...", options=opts)
            guild_id = self.guild_id
            async def remove_pack_cb(inter: discord.Interaction):
                pack = inter.data["values"][0]
                gc2 = utils.load_guild_config(guild_id)
                gc2.get("pack_channel_map", {}).pop(pack, None)
                if not gc2.get("pack_channel_map"):
                    gc2.pop("pack_channel_map", None)
                utils.save_guild_config(guild_id, gc2)
                await inter.response.edit_message(
                    embed=discord.Embed(title="✅ Pack Filter Removed", description=f"Pack filter **{pack.title()}** removed.", color=discord.Color.green()),
                    view=None
                )
            sel.callback = remove_pack_cb
            v = discord.ui.View(); v.add_item(sel)
            await interaction.response.edit_message(
                embed=discord.Embed(title="🗑️ Remove Pack Filter", description="Select the pack filter to remove:", color=discord.Color.blue()),
                view=v
            )

        elif choice in ("clear_kw", "clear_pack", "clear_all"):
            label_map = {"clear_kw": "keyword", "clear_pack": "pack", "clear_all": "all"}
            ftype = label_map[choice]
            guild_id = self.guild_id

            class ConfirmView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=30)
                @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
                async def confirm(self_inner, inter: discord.Interaction, btn: discord.ui.Button):
                    gc2 = utils.load_guild_config(guild_id)
                    count = 0
                    if ftype in ("keyword", "all") and "keyword_channel_map" in gc2:
                        count += len(gc2["keyword_channel_map"])
                        del gc2["keyword_channel_map"]
                    if ftype in ("pack", "all") and "pack_channel_map" in gc2:
                        count += len(gc2["pack_channel_map"])
                        del gc2["pack_channel_map"]
                    utils.save_guild_config(guild_id, gc2)
                    await inter.response.edit_message(
                        embed=discord.Embed(title="✅ Filters Cleared", description=f"{count} filter(s) removed.", color=discord.Color.green()),
                        view=None
                    )
                @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
                async def cancel(self_inner, inter: discord.Interaction, btn: discord.ui.Button):
                    await inter.response.edit_message(
                        embed=discord.Embed(title="Cancelled", description="No filters were removed.", color=discord.Color.greyple()),
                        view=None
                    )

            await interaction.response.edit_message(
                embed=discord.Embed(
                    title=f"⚠️ Clear {ftype.title()} Filters",
                    description=f"This will delete **all {ftype} filters**. Are you sure?",
                    color=discord.Color.orange()
                ),
                view=ConfirmView()
            )


# ── Cog ───────────────────────────────────────────────────────────────────────

class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _build_config_embed(self, guild: discord.Guild, gc: dict) -> discord.Embed:
        embed = discord.Embed(title="⚙️ Server Configuration", description="Select what you want to configure:", color=discord.Color.blurple())

        pack_mode = gc.get("pack_channel_mode")
        embed.add_field(name="📦 Pack Mode", value=("One per series" if pack_mode == "series" else "One per pack") if pack_mode else "*not set*", inline=True)

        status = gc.get("validation_buttons_enabled")
        embed.add_field(name="🔘 Traded Buttons", value=("Enabled" if status else "Disabled") if status is not None else "*not set*", inline=True)

        src_id = gc.get("heartbeat_source_channel_id")
        tgt_id = gc.get("heartbeat_target_channel_id")
        if src_id and tgt_id:
            embed.add_field(name="💓 Heartbeat", value=f"<#{src_id}> → <#{tgt_id}>", inline=False)
        else:
            embed.add_field(name="💓 Heartbeat", value="*not set*", inline=False)

        val_role_id = gc.get("validator_role_id")
        embed.add_field(name="🛡️ Validator Role", value=f"<@&{val_role_id}>" if val_role_id else "*not set*", inline=True)

        ping_parts = []
        if gc.get("godpack_ping"):
            ping_parts.append(f"God Pack: <@&{gc['godpack_ping']}>")
        if gc.get("invgodpack_ping"):
            ping_parts.append(f"Invalid GP: <@&{gc['invgodpack_ping']}>")
        if gc.get("safe_trade_ping"):
            ping_parts.append(f"Safe Trade: <@&{gc['safe_trade_ping']}>")
        embed.add_field(name="🔔 Ping Roles", value="\n".join(ping_parts) if ping_parts else "*not set*", inline=True)

        sources = gc.get("default_source_channel_ids", [])
        embed.add_field(name="📡 Sources", value=", ".join([f"<#{sid}>" for sid in sources]) if sources else "All channels", inline=False)

        pack_role_ids = gc.get("pack_category_view_roles", [])
        embed.add_field(name="🔒 Channel Access Roles", value=", ".join(f"<@&{r}>" for r in pack_role_ids) if pack_role_ids else "Everyone (no restriction)", inline=False)

        return embed

    @app_commands.command(name="configure", description="Server configuration (Admin only)")
    async def set_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                embed=discord.Embed(title="Error", description="Administrator required.", color=discord.Color.red()),
                ephemeral=True
            )
            return
        guild_id = str(interaction.guild.id)
        gc = utils.load_guild_config(guild_id)
        embed = self._build_config_embed(interaction.guild, gc)
        await interaction.followup.send(embed=embed, view=SetSelectView(guild_id), ephemeral=True)

    @app_commands.command(name="filters", description="View and manage active filters (Admin only)")
    async def filters_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(embed=discord.Embed(title="Error", description="Administrator required.", color=discord.Color.red()), ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        gc = utils.load_guild_config(guild_id)
        embed = build_filters_embed(interaction.guild, gc)
        await interaction.followup.send(embed=embed, view=FiltersView(guild_id), ephemeral=True)

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



async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
