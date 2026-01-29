"""
Dev Commands - Prefix-based developer commands
"""
import discord
from datetime import datetime
import os
import json


async def show_dev_help(message: discord.Message, bot):
    """Show dev help menu with buttons."""
    embed = discord.Embed(
        title="🔧 Developer Commands",
        description="Use the buttons below for dev functions.",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Only {message.author.name} can use these buttons")
    
    class DevView(discord.ui.View):
        def __init__(self, owner_id):
            super().__init__(timeout=300)
            self.owner_id = owner_id
        
        @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.primary, emoji="📊")
        async def stats_btn(self, inter: discord.Interaction, button: discord.ui.Button):
            if inter.user.id != self.owner_id:
                await inter.response.send_message("❌ Access denied!", ephemeral=True)
                return
            
            guild_count = len(bot.guilds)
            user_count = sum(len(g.members) for g in bot.guilds)
            uptime = datetime.now(bot.BERLIN_TZ) - bot.start_time if hasattr(bot, 'start_time') else "Unknown"
            
            stats_embed = discord.Embed(
                title="📊 Bot Statistics",
                color=discord.Color.blue()
            )
            stats_embed.add_field(name="🏢 Guilds", value=f"`{guild_count}`", inline=True)
            stats_embed.add_field(name="👥 Users", value=f"`{user_count}`", inline=True)
            stats_embed.add_field(name="⏱️ Uptime", value=f"`{uptime}`", inline=True)
            
            await inter.response.send_message(embed=stats_embed, ephemeral=True)
        
        @discord.ui.button(label="🔍 Config Check", style=discord.ButtonStyle.success, emoji="🔍")
        async def config_btn(self, inter: discord.Interaction, button: discord.ui.Button):
            if inter.user.id != self.owner_id:
                await inter.response.send_message("❌ Access denied!", ephemeral=True)
                return
            
            errors = []
            CONFIG_FILE = "bot_config.json"
            GUILD_CONFIG_DIR = "guild_configs"
            
            if not os.path.exists(CONFIG_FILE):
                errors.append("❌ bot_config.json not found")
            else:
                try:
                    with open(CONFIG_FILE, "r") as f:
                        test_config = json.load(f)
                        if "series" not in test_config:
                            errors.append("⚠️ 'series' key missing")
                except json.JSONDecodeError as e:
                    errors.append(f"❌ bot_config.json corrupted: {e}")
            
            if errors:
                config_embed = discord.Embed(
                    title="❌ Config Errors",
                    description="\n".join(errors),
                    color=discord.Color.red()
                )
            else:
                config_embed = discord.Embed(
                    title="✅ Config OK",
                    description="No errors found!",
                    color=discord.Color.green()
                )
            
            await inter.response.send_message(embed=config_embed, ephemeral=True)
    
    view = DevView(message.author.id)
    await message.reply(embed=embed, view=view, mention_author=False)
