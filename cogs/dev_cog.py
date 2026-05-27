import discord
from discord.ext import commands
from discord import app_commands
import utils


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


class DevCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="sync", description="Synchronisiert alle Slash-Commands neu (Owner only)")
    async def sync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await utils.owner_only(interaction):
            return
        try:
            synced = await self.bot.tree.sync()
            embed = discord.Embed(
                title="Sync erfolgreich",
                description=f"{len(synced)} Commands synchronisiert. Packs-Änderungen sind jetzt live.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            print("Commands synced by owner.")
        except Exception as e:
            embed = discord.Embed(
                title="Sync-Fehler",
                description=f"Fehler beim Sync: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"Sync error: {e}")

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
        await interaction.followup.send(embed=embed, view=DevPanelView(self.bot), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DevCog(bot))
