import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import re
import utils
from datetime import datetime


class PostToChannelModal(discord.ui.Modal, title="Post Stats to Channel"):
    channel_input = discord.ui.TextInput(label="Channel", placeholder="#channel or channel ID", min_length=1, max_length=100)

    def __init__(self, stat_type: str, guild_id: str):
        super().__init__()
        self.stat_type = stat_type
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        value = self.channel_input.value.strip()
        match = re.search(r'(\d{17,20})', value)
        channel = None
        if match:
            channel = interaction.guild.get_channel(int(match.group(1)))
        if not channel:
            name = value.lstrip('#').lower()
            channel = discord.utils.get(interaction.guild.text_channels, name=name)
        if not channel:
            await interaction.followup.send("❌ Channel not found. Use #mention or channel ID.", ephemeral=True)
            return

        guild_config = utils.load_guild_config(self.guild_id)

        if self.stat_type == "overview":
            embed = utils.create_stats_embed(guild_config)
            sent = await channel.send(embed=embed)
            guild_config["stats_channel_id"] = channel.id
            guild_config["stats_message_id"] = sent.id
            utils.save_guild_config(self.guild_id, guild_config)
            title = "Stats Embed Posted"

        elif self.stat_type == "detailed":
            embed = utils.create_detailed_stats_embed(guild_config)
            sent = await channel.send(embed=embed)
            guild_config["detailed_stats_channel_id"] = channel.id
            guild_config["detailed_stats_message_id"] = sent.id
            utils.save_guild_config(self.guild_id, guild_config)
            title = "Detailed Stats Embed Posted"

        elif self.stat_type == "pack":
            embed = utils.create_pack_stats_embed(guild_config)
            sent = await channel.send(embed=embed)
            guild_config["pack_stats_channel_id"] = channel.id
            guild_config["pack_stats_message_id"] = sent.id
            utils.save_guild_config(self.guild_id, guild_config)
            title = "Pack Stats Embed Posted"

        await interaction.followup.send(
            embed=discord.Embed(title=f"✅ {title}", description=f"Posted in {channel.mention} — will auto-update.", color=discord.Color.green()),
            ephemeral=True
        )


class StatsResultView(discord.ui.View):
    def __init__(self, stat_type: str, guild_id: str):
        super().__init__(timeout=120)
        self.stat_type = stat_type
        self.guild_id = guild_id

    @discord.ui.button(label="📌 Post to Channel", style=discord.ButtonStyle.secondary)
    async def post_to_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PostToChannelModal(self.stat_type, self.guild_id))


class StatsSelectView(discord.ui.View):
    def __init__(self, guild_id: str):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        select = discord.ui.Select(
            placeholder="Which stats do you want to see?",
            options=[
                discord.SelectOption(label="Overview Stats", value="overview", emoji="📊", description="Server validation and trade stats"),
                discord.SelectOption(label="Detailed Stats", value="detailed", emoji="🔎", description="Breakdown per filter"),
                discord.SelectOption(label="Pack Stats", value="pack", emoji="📦", description="Pack-specific statistics"),
            ]
        )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        gc = utils.load_guild_config(self.guild_id)
        choice = interaction.data["values"][0]

        if choice == "overview":
            embed = utils.create_stats_embed(gc)
        elif choice == "detailed":
            embed = utils.create_detailed_stats_embed(gc)
        elif choice == "pack":
            embed = utils.create_pack_stats_embed(gc)

        await interaction.followup.send(embed=embed, view=StatsResultView(choice, self.guild_id), ephemeral=True)


class StatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="View server statistics")
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild.id)
        embed = discord.Embed(title="📊 Statistics", description="Select which stats to view:", color=discord.Color.blurple())
        await interaction.followup.send(embed=embed, view=StatsSelectView(guild_id), ephemeral=True)

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
            await interaction.followup.send(
                embed=discord.Embed(title="✅ Lifetime Stats Posted", description=f"Posted in {channel.mention}, auto-updates every minute.", color=discord.Color.gold()),
                ephemeral=True
            )
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(StatsCog(bot))
