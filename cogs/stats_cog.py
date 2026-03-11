import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import utils
from datetime import datetime


class StatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Shows server validation and trade stats, optionally posts auto-updating embed")
    @app_commands.describe(channel="Optional: Channel to post the auto-updating stats embed")
    async def stats(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=False)
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        embed = utils.create_stats_embed(guild_config)

        if channel:
            sent_message = await channel.send(embed=embed)
            guild_config["stats_channel_id"] = channel.id
            guild_config["stats_message_id"] = sent_message.id
            utils.save_guild_config(guild_id, guild_config)
            response_embed = discord.Embed(
                title="Stats Embed Posted",
                description=f"The stats embed has been posted in {channel.mention} and will be automatically updated.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="detailedstats", description="Shows detailed statistics for each filter, optionally posts an auto-updating embed")
    @app_commands.describe(channel="Optional: The channel to post the auto-updating detailed stats embed")
    async def detailedstats(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=False)
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        embed = utils.create_detailed_stats_embed(guild_config)

        if channel:
            sent_message = await channel.send(embed=embed)
            guild_config["detailed_stats_channel_id"] = channel.id
            guild_config["detailed_stats_message_id"] = sent_message.id
            utils.save_guild_config(guild_id, guild_config)
            response_embed = discord.Embed(
                title="Detailed Stats Embed Posted",
                description=f"The detailed stats embed has been posted in {channel.mention} and will be automatically updated.",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="packstats", description="Shows pack statistics for this server, optionally posts an auto-updating embed")
    @app_commands.describe(channel="Optional: The channel to post the auto-updating pack stats embed")
    async def packstats(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=False)
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        embed = utils.create_pack_stats_embed(guild_config)

        if channel:
            sent_message = await channel.send(embed=embed)
            guild_config["pack_stats_channel_id"] = channel.id
            guild_config["pack_stats_message_id"] = sent_message.id
            utils.save_guild_config(guild_id, guild_config)
            response_embed = discord.Embed(
                title="Pack Stats Embed Posted",
                description=f"The pack stats embed has been posted in {channel.mention} and will be automatically updated.",
                color=discord.Color.teal()
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="lifetimestats", description="Shows lifetime statistics across all servers (Owner only)")
    @app_commands.describe(channel="Optional: The channel to post the auto-updating lifetime stats embed")
    async def lifetimestats(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=False)
        if not await utils.owner_only(interaction):
            return

        embed = await asyncio.to_thread(utils.create_lifetime_stats_embed)

        if channel:
            sent_message = await channel.send(embed=embed)
            now = datetime.now(utils.BERLIN_TZ)
            message_key = f"{interaction.guild.id}_{channel.id}"
            utils.LIFETIME_STATS_MESSAGES[message_key] = {
                "channel_id": str(channel.id),
                "message_id": str(sent_message.id),
                "guild_id": str(interaction.guild.id),
                "posted_at": now
            }
            utils.save_lifetime_stats_messages()

            response_embed = discord.Embed(
                title="Lifetime Stats Embed Posted",
                description=f"The lifetime stats embed has been posted in {channel.mention} and will be automatically updated every minute.",
                color=discord.Color.gold()
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(StatsCog(bot))
