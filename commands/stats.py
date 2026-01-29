"""
Stats Commands: /stats, /meta, /setpingroles und Autocomplete-Funktionen
"""
import discord
from discord import app_commands
from discord.ext import commands
from config import load_guild_config, save_guild_config
from utils import create_stats_embed
import os


async def autocomplete_packs(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Autocomplete für Packs aus Config."""
    packs = interaction.client.config.get("packs", [])
    choices = [app_commands.Choice(name=pack.title(), value=pack) for pack in packs[:25]]
    if not current:
        return choices
    filtered = [choice for choice in choices if current.lower() in choice.value.lower()]
    return filtered[:25]


async def autocomplete_series(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Autocomplete für Series aus Config."""
    series_names = list(interaction.client.config.get("series", {}).keys())
    if not current:
        return [app_commands.Choice(name=s, value=s) for s in series_names[:25]]
    filtered = [app_commands.Choice(name=s, value=s) for s in series_names if current.lower() in s.lower()]
    return filtered[:25]


def split_field_value(value, max_len=1024, field_name="Field"):
    """Split long field values into multiple fields."""
    lines = value.split('\n')
    chunks = []
    current_chunk = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > max_len and current_chunk:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_len = line_len
        else:
            current_chunk.append(line)
            current_len += line_len
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    return [(field_name, chunk) for chunk in chunks]


class StatsCommands(commands.Cog):
    def __init__(self, bot, config, OWNER_ID, BERLIN_TZ):
        self.bot = bot
        self.config = config
        self.OWNER_ID = OWNER_ID
        self.BERLIN_TZ = BERLIN_TZ
    
    @app_commands.command(name="stats", description="Shows server validation and trade stats")
    @app_commands.describe(channel="Optional: Channel to post the auto-updating stats embed")
    async def stats(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=False)
        guild_id = str(interaction.guild.id)
        guild_config = load_guild_config(guild_id)

        embed = create_stats_embed(guild_config)

        if channel:
            sent_message = await channel.send(embed=embed)
            guild_config["stats_channel_id"] = channel.id
            guild_config["stats_message_id"] = sent_message.id
            save_guild_config(guild_id, guild_config)
            response_embed = discord.Embed(
                title="Stats Embed Posted",
                description=f"Stats embed posted in {channel.mention} and will auto-update.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=response_embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="meta", description="Shows current TCGP meta decks!")
    async def meta(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        embed = discord.Embed(
            title="TCG POCKET - META DECKS",
            description="Websites with current META Decks for TCGP",
            color=discord.Color.yellow()
        )
        embed.set_thumbnail(url="https://i.imgur.com/nBWsWgp.png")
        embed.add_field(
            name="**Websites:**",
            value="[Pokemon Zone](https://www.pokemon-zone.com/decks)\n[PTCGPOCKET](https://ptcgpocket.gg/)",
            inline=False
        )
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="setpingroles", description="Set ping roles for god pack, invalid god pack, or safe for trade")
    async def setpingroles(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(
                title="Error",
                description="Administrator required.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        select = discord.ui.Select(
            placeholder="Select Ping Type...",
            options=[
                discord.SelectOption(label="God Pack Ping", value="godpack"),
                discord.SelectOption(label="Invalid God Pack Ping", value="invgodpack"),
                discord.SelectOption(label="Safe for Trade Ping", value="safe_trade")
            ]
        )
        
        async def ping_type_callback(inter: discord.Interaction):
            ping_type = inter.data['values'][0]
            guild_id = str(inter.guild.id)
            roles = sorted(inter.guild.roles, key=lambda r: r.position, reverse=True)[:25]
            if inter.guild.default_role in roles:
                roles.remove(inter.guild.default_role)
            
            role_select = discord.ui.Select(
                placeholder=f"Select Role for {ping_type.replace('_', ' ').title()}...",
                options=[discord.SelectOption(label=role.name, value=str(role.id)) for role in roles]
            )
            
            async def set_ping(i: discord.Interaction):
                role_id = int(i.data['values'][0])
                guild_config = load_guild_config(guild_id)
                guild_config[f"{ping_type}_ping"] = role_id
                save_guild_config(guild_id, guild_config)
                role = inter.guild.get_role(role_id)
                await i.response.edit_message(content=f"✅ {ping_type.replace('_', ' ').title()} set to {role.mention}", view=None)
            
            role_select.callback = set_ping
            view = discord.ui.View()
            view.add_item(role_select)
            await inter.response.edit_message(content=f"Select role for {ping_type.replace('_', ' ').title()}:", view=view, embed=None)
        
        select.callback = ping_type_callback
        view = discord.ui.View()
        view.add_item(select)
        embed = discord.Embed(title="Set Ping Role", description="First, select the ping type.", color=discord.Color.blue())
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(StatsCommands(bot, bot.config, bot.OWNER_ID, bot.BERLIN_TZ))
