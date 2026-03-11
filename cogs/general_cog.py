import discord
from discord.ext import commands
from discord import app_commands
import random
import utils


class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="pick4me", description="Let fate decide which card you get!")
    async def pick4me(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        options = [
            ("> Top Left", "wp/top-left.png"),
            ("> Top Middle", "wp/middle.png"),
            ("> Top Right", "wp/top-right.png"),
            ("> Bottom Left", "wp/bottom-left.png"),
            ("> Bottom Right", "wp/bottom-right.png")
        ]
        choice_text, image_path = random.choice(options)
        embed = discord.Embed(description=choice_text, color=discord.Color.green())
        file = discord.File(image_path, filename="card.png")
        embed.set_image(url="attachment://card.png")
        await interaction.followup.send(embed=embed, file=file)

    @app_commands.command(name="showfilters", description="Shows all active filters for this server")
    async def showfilters(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        guild_id = str(interaction.guild.id)
        guild_config = utils.load_guild_config(guild_id)

        if not guild_config or (not guild_config.get("keyword_channel_map") and not guild_config.get("pack_channel_map")):
            embed = discord.Embed(title="No Filters Configured", description="There are no filters configured for this server.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=False)
            return

        keyword_channel_map = guild_config.get("keyword_channel_map", {})
        pack_channel_map = guild_config.get("pack_channel_map", {})
        pack_mode = guild_config.get("pack_channel_mode", "series")

        embed = discord.Embed(
            title="Active Filters",
            description=f"Here are the currently configured filters for this server (Pack Mode: {pack_mode.title()}).",
            color=discord.Color.blue()
        )

        filter_list = []
        all_custom_sources = set()
        for keyword, filter_config in keyword_channel_map.items():
            channel = interaction.guild.get_channel(filter_config["channel_id"])
            channel_mention = channel.mention if channel else f"ID: {filter_config['channel_id']} (not found)"
            source_channel_ids = filter_config.get("source_channel_ids", [])
            if source_channel_ids:
                all_custom_sources.update(source_channel_ids)
                source_str = "Custom sources"
            else:
                source_str = "All channels"
            filter_list.append(f"**{keyword.title()}**: {channel_mention} (Sources: {source_str})")

        filter_value = "\n".join(filter_list) if filter_list else "No filters configured."
        for field_name, chunk in utils.split_field_value(filter_value, field_name="Filters"):
            embed.add_field(name=field_name, value=chunk, inline=False)

        pack_list_by_series = {}
        for pack, pack_config in pack_channel_map.items():
            series_for_pack = next(
                (s for s, packs_in_s in utils.config["series"].items() if pack in [p.lower() for p in packs_in_s]),
                "Unassigned"
            )
            if series_for_pack not in pack_list_by_series:
                pack_list_by_series[series_for_pack] = []
            channel = interaction.guild.get_channel(pack_config["channel_id"])
            channel_mention = channel.mention if channel else f"ID: {pack_config['channel_id']} (not found)"
            source_channel_ids = pack_config.get("source_channel_ids", [])
            if source_channel_ids:
                all_custom_sources.update(source_channel_ids)
                source_str = "Custom sources"
            else:
                source_str = "All channels"
            pack_list_by_series[series_for_pack].append(f"**{pack.title()}**: {channel_mention} (Sources: {source_str})")

        for series_name, packs_list in pack_list_by_series.items():
            value = "\n".join(packs_list) if packs_list else "No pack filters configured."
            for field_name, chunk in utils.split_field_value(value, field_name=f"Pack Filters - {series_name}"):
                embed.add_field(name=field_name, value=chunk, inline=False)

        godpack_ping = guild_config.get("godpack_ping")
        invgodpack_ping = guild_config.get("invgodpack_ping")
        safe_trade_ping = guild_config.get("safe_trade_ping")
        validator_role_id = guild_config.get("validator_role_id")
        validator_role = interaction.guild.get_role(validator_role_id) if validator_role_id else None

        embed.add_field(
            name="Pings",
            value=f"God Pack Ping: {f'<@&{godpack_ping}>' if godpack_ping else 'Not set'}\n"
                  f"Invalid God Pack Ping: {f'<@&{invgodpack_ping}>' if invgodpack_ping else 'Not set'}\n"
                  f"Safe for Trade Ping: {f'<@&{safe_trade_ping}>' if safe_trade_ping else 'Not set'}",
            inline=False
        )
        embed.add_field(name="Validator Role", value=f"{validator_role.mention if validator_role else 'Not set'}", inline=False)
        embed.add_field(name="Traded Buttons", value=f"{'**Enabled**' if guild_config.get('validation_buttons_enabled', False) else '**Disabled**'}", inline=False)

        heartbeat_source_id = guild_config.get("heartbeat_source_channel_id")
        heartbeat_target_id = guild_config.get("heartbeat_target_channel_id")
        heartbeat_source = interaction.guild.get_channel(heartbeat_source_id) if heartbeat_source_id else None
        heartbeat_target = interaction.guild.get_channel(heartbeat_target_id) if heartbeat_target_id else None
        embed.add_field(name="Heartbeat Source", value=f"{heartbeat_source.mention if heartbeat_source else 'Not set'}", inline=True)
        embed.add_field(name="Heartbeat Target", value=f"{heartbeat_target.mention if heartbeat_target else 'Not set'}", inline=True)

        series_overview = "\n".join(f"**{s}**: {', '.join(packs)}" for s, packs in utils.config["series"].items())
        for field_name, chunk in utils.split_field_value(series_overview, field_name="Globale Series & Packs"):
            embed.add_field(name=field_name, value=chunk, inline=False)

        if all_custom_sources:
            all_sources_list = sorted(list(all_custom_sources))
            source_summary = ", ".join([f"<#{sid}>" for sid in all_sources_list])
            for field_name, chunk in utils.split_field_value(source_summary, field_name="All Custom Source Channels"):
                embed.add_field(name=field_name, value=chunk, inline=False)
        else:
            embed.add_field(name="All Custom Source Channels", value="None (using all channels)", inline=False)

        embed.set_footer(
            text=f"Total Custom Sources: {len(all_custom_sources) if all_custom_sources else 0} channels | Use /setfilter to update",
            icon_url="https://imgur.com/T0KX069.png"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="meta", description="Shows you current TCGP meta!")
    async def meta(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        embed = discord.Embed(
            title="TCG POCKET - META DECKS",
            description="Websites which list with the current META Decks for TCGP",
            color=discord.Color.yellow()
        )
        embed.set_thumbnail(url="https://i.imgur.com/NskEnQG.png")
        embed.add_field(name="**Websites:**", value="[Pokemon Zone](https://www.pokemon-zone.com/decks)\n[PTCGPOCKET](https://ptcgpocket.gg/)", inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="help", description="Shows an overview of all bot commands")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        embed = discord.Embed(
            title="🤖 Bot Commands Overview",
            description="Here's a list of all available commands, grouped by category. **Pro Tip:** Try /meta for some fun!",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url="https://i.imgur.com/iNJRSxh.png")

        embed.add_field(
            name="🎮 Fun & Meta",
            value="**/meta** – Current TCGP meta decks (links to guides)\n**/pick4me** – Decides for you on a wonder pick",
            inline=False
        )
        embed.add_field(
            name="⚙️ Filter Setup (Admin)",
            value="**/setup** – Setup the whole Discord Bot with one command\n"
                  "**/setfilter** – Configure filter for cards\n"
                  "**/setpackfilter** – Set up pack filters\n"
                  "**/setpackmode** – Choose pack channel mode (series or per pack)\n"
                  "**/createpackcategory** – Create a pack-specific category with Save 4 Trade channels\n"
                  "**/clearfilters** – Clear all filters (by type)\n"
                  "**/removefilter** – Remove a single filter\n"
                  "**/removepackfilter** – Remove a pack filter\n"
                  "**/showfilters** – Show all active filters",
            inline=False
        )
        embed.add_field(
            name="🔒 Validation (Admin)",
            value="**/setstatus** – Enable/disable traded buttons (for Safe 4 Trade)\n"
                  "**/setvalidatorrole** – Set role for validators\n"
                  "**/setpingroles** – Set ping roles for god pack, invalid, or safe trade",
            inline=False
        )
        embed.add_field(
            name="📊 Statistics",
            value="**/stats** – Server stats (validation/trade)\n"
                  "**/detailedstats** – Detailed filter stats\n"
                  "**/packstats** – Pack-specific stats\n"
                  "**/setheartbeat** – Set up heartbeat monitor",
            inline=False
        )
        embed.add_field(
            name="🔧 Dev Commands (Owner only)",
            value="**/lifetimestats** – Global stats from all servers\n"
                  "**/addseries** – Add a new series for packs\n"
                  "**/addpack** – Add pack to a series\n"
                  "**/removepack** – Remove a pack\n"
                  "**/removeseries** – Remove a series and delete channels/category\n"
                  "**/sync** – Resync commands",
            inline=False
        )
        embed.add_field(
            name="ℹ️ Support & Info",
            value=f"**Support:** [Discord Server](https://discord.gg/X5YKZBh9xV)\n"
                  f"**GitHub:** [Repository](https://github.com/SimpliAj/HELPER-TCGP)\n"
                  f"**Status:** Active in {len(self.bot.guilds)} servers\n"
                  f"**Developer:** <@{utils.OWNER_ID}>",
            inline=False
        )
        embed.set_footer(text="Need more help? Ping in the support channel!")
        await interaction.followup.send(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCog(bot))
