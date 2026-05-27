import discord
from discord.ext import commands
from discord import app_commands
import utils


class DevPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=120)
        self.bot = bot

    @discord.ui.button(label="Run Pack Scan", style=discord.ButtonStyle.primary, emoji="🔍")
    async def run_scan(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != utils.OWNER_ID:
            await interaction.response.send_message("Access denied.", ephemeral=True)
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

    @discord.ui.button(label="Sync Commands", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def sync_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != utils.OWNER_ID:
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            synced = await self.bot.tree.sync()
            await interaction.followup.send(f"✅ {len(synced)} commands synced.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Sync error: {e}", ephemeral=True)


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
        embed.add_field(name="🔍 Run Pack Scan", value="Manually trigger the hourly auto-sync to detect new packs/series.", inline=False)
        embed.add_field(name="🔄 Sync Commands", value="Re-sync all slash commands with Discord.", inline=False)
        await interaction.followup.send(embed=embed, view=DevPanelView(self.bot), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DevCog(bot))
