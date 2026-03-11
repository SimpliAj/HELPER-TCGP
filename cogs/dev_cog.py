import discord
from discord.ext import commands
from discord import app_commands
import utils


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


async def setup(bot: commands.Bot):
    await bot.add_cog(DevCog(bot))
