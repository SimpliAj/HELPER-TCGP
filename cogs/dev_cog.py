import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import utils
from datetime import datetime


class AddSeriesModal(discord.ui.Modal, title="Add Series"):
    series_name = discord.ui.TextInput(label="Series Name", placeholder="e.g. B-Series", min_length=2, max_length=50)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        packs_cog = self.bot.cogs.get("PacksCog")
        if not packs_cog:
            await interaction.followup.send("PacksCog not loaded.", ephemeral=True)
            return
        await packs_cog._do_addseries(interaction, self.series_name.value)


class AddPackModal(discord.ui.Modal, title="Add Pack"):
    pack_name = discord.ui.TextInput(label="Pack Name", placeholder="e.g. Mythical Island", min_length=2, max_length=50)
    series = discord.ui.TextInput(label="Series", placeholder="e.g. A-Series", default="A-Series", min_length=2, max_length=50)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        packs_cog = self.bot.cogs.get("PacksCog")
        if not packs_cog:
            await interaction.followup.send("PacksCog not loaded.", ephemeral=True)
            return
        await packs_cog._do_addpack(interaction, self.pack_name.value, self.series.value)


class RemovePackModal(discord.ui.Modal, title="Remove Pack"):
    pack_name = discord.ui.TextInput(label="Pack Name", placeholder="Exact pack name to remove", min_length=2, max_length=50)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        packs_cog = self.bot.cogs.get("PacksCog")
        if not packs_cog:
            await interaction.followup.send("PacksCog not loaded.", ephemeral=True)
            return
        await packs_cog._do_removepack(interaction, self.pack_name.value)


class RemoveSeriesModal(discord.ui.Modal, title="Remove Series"):
    series_name = discord.ui.TextInput(label="Series Name", placeholder="Exact series name to remove", min_length=2, max_length=50)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        packs_cog = self.bot.cogs.get("PacksCog")
        if not packs_cog:
            await interaction.followup.send("PacksCog not loaded.", ephemeral=True)
            return
        await packs_cog._do_removeseries(interaction, self.series_name.value)


class LifetimeStatsPostView(discord.ui.View):
    def __init__(self, embed: discord.Embed, guild_id: int):
        super().__init__(timeout=60)
        self.embed = embed
        self.guild_id = guild_id
        select = discord.ui.ChannelSelect(
            placeholder="Select channel to post auto-updating embed...",
            channel_types=[discord.ChannelType.text]
        )
        select.callback = self.on_channel_select
        self.add_item(select)

    async def on_channel_select(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.guild.get_channel(int(interaction.data["values"][0]))
        if not channel:
            await interaction.followup.send("❌ Channel not found.", ephemeral=True)
            return
        sent_message = await channel.send(embed=self.embed)
        now = datetime.now(utils.BERLIN_TZ)
        message_key = f"{self.guild_id}_{channel.id}"
        utils.LIFETIME_STATS_MESSAGES[message_key] = {
            "channel_id": str(channel.id),
            "message_id": str(sent_message.id),
            "guild_id": str(self.guild_id),
            "posted_at": now
        }
        utils.save_lifetime_stats_messages()
        await interaction.followup.send(
            embed=discord.Embed(title="✅ Lifetime Stats Posted", description=f"Posted in {channel.mention}, auto-updates every 15 minutes.", color=discord.Color.gold()),
            ephemeral=True
        )


class DevPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=120)
        self.bot = bot

    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != utils.OWNER_ID:
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Run Pack Scan", style=discord.ButtonStyle.primary, emoji="🔍", row=0)
    async def run_scan(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        packs_cog = self.bot.cogs.get("PacksCog")
        if not packs_cog:
            await interaction.followup.send("PacksCog not loaded.", ephemeral=True)
            return
        try:
            await packs_cog.auto_pack_sync()
            await interaction.followup.send("✅ Pack scan completed.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Scan error: {e}", ephemeral=True)

    @discord.ui.button(label="Sync Commands", style=discord.ButtonStyle.secondary, emoji="🔄", row=0)
    async def sync_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            synced = await self.bot.tree.sync()
            await interaction.followup.send(f"✅ {len(synced)} commands synced.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Sync error: {e}", ephemeral=True)

    @discord.ui.button(label="Add Series", style=discord.ButtonStyle.success, emoji="📂", row=1)
    async def add_series(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        await interaction.response.send_modal(AddSeriesModal(self.bot))

    @discord.ui.button(label="Add Pack", style=discord.ButtonStyle.success, emoji="📦", row=1)
    async def add_pack(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        await interaction.response.send_modal(AddPackModal(self.bot))

    @discord.ui.button(label="Remove Pack", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
    async def remove_pack(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        await interaction.response.send_modal(RemovePackModal(self.bot))

    @discord.ui.button(label="Remove Series", style=discord.ButtonStyle.danger, emoji="❌", row=2)
    async def remove_series(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        await interaction.response.send_modal(RemoveSeriesModal(self.bot))

    @discord.ui.button(label="Lifetime Stats", style=discord.ButtonStyle.secondary, emoji="🌍", row=3)
    async def lifetime_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        embed = await asyncio.to_thread(utils.create_lifetime_stats_embed)
        await interaction.followup.send(
            embed=embed,
            view=LifetimeStatsPostView(embed, interaction.guild.id),
            ephemeral=True
        )


class DevCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="devpanel", description="Developer control panel (Owner only)")
    async def devpanel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await utils.owner_only(interaction):
            return
        embed = discord.Embed(
            title="🛠️ Dev Panel",
            description="Bot control panel — owner only.",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Row 1", value="🔍 Run Pack Scan  •  🔄 Sync Commands", inline=False)
        embed.add_field(name="Row 2", value="📂 Add Series  •  📦 Add Pack", inline=False)
        embed.add_field(name="Row 3", value="🗑️ Remove Pack  •  ❌ Remove Series", inline=False)
        embed.add_field(name="Row 4", value="🌍 Lifetime Stats (view + post to channel)", inline=False)
        await interaction.followup.send(embed=embed, view=DevPanelView(self.bot), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DevCog(bot))
