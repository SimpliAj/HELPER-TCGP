"""Developer commands - Prefix-based -help command with button view."""
import discord
import asyncio
import os
import sys
import json
from datetime import datetime


class DevCommandView(discord.ui.View):
    """View mit Buttons für Dev Commands"""
    def __init__(self, bot, owner_id, config, berlin_tz, guild_config_dir):
        super().__init__(timeout=300)
        self.bot = bot
        self.owner_id = owner_id
        self.config = config
        self.berlin_tz = berlin_tz
        self.guild_config_dir = guild_config_dir
    
    @discord.ui.button(label="🔄 Bot Restart", style=discord.ButtonStyle.danger, emoji="🔄")
    async def restart_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Du darfst das nicht!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🔄 Bot wird neu gestartet...",
            description="Der Bot startet in 3 Sekunden neu.",
            color=discord.Color.orange()
        )
        await interaction.response.defer()
        await interaction.followup.send(embed=embed)
        
        # Restart after 3 seconds
        await asyncio.sleep(3)
        os.execv(sys.executable, ['python'] + sys.argv)
    
    @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.primary, emoji="📊")
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Du darfst das nicht!", ephemeral=True)
            return
        
        # Sammle Bot-Stats
        guild_count = len(self.bot.guilds)
        user_count = sum(len(g.members) for g in self.bot.guilds)
        uptime = datetime.now(self.berlin_tz) - self.bot.start_time if hasattr(self.bot, 'start_time') else "Unknown"
        
        config_file_size = os.path.getsize("bot_config.json") if os.path.exists("bot_config.json") else 0
        guild_configs_count = len([f for f in os.listdir(self.guild_config_dir) if f.endswith('.json')]) if os.path.exists(self.guild_config_dir) else 0
        
        packs = self.config.get("packs", [])
        
        embed = discord.Embed(
            title="📊 Bot Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.now(self.berlin_tz)
        )
        embed.add_field(name="🏢 Guilds", value=f"`{guild_count}`", inline=True)
        embed.add_field(name="👥 Users", value=f"`{user_count}`", inline=True)
        embed.add_field(name="⏱️ Uptime", value=f"`{uptime}`", inline=True)
        embed.add_field(name="💾 Config File Size", value=f"`{config_file_size:,} bytes`", inline=True)
        embed.add_field(name="📁 Guild Config Files", value=f"`{guild_configs_count}`", inline=True)
        embed.add_field(name="📦 Packs", value=f"`{len(packs)}`", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🐛 Errors", style=discord.ButtonStyle.secondary, emoji="🐛")
    async def errors_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Du darfst das nicht!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🐛 Recent Errors",
            description="Fehler werden an den Error-Webhook gepostet.\nSchau im Error-Channel nach!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🔍 Config Check", style=discord.ButtonStyle.success, emoji="🔍")
    async def config_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Du darfst das nicht!", ephemeral=True)
            return
        
        # Überprüfe Config-Integrität
        errors = []
        
        # Prüfe bot_config.json
        if not os.path.exists("bot_config.json"):
            errors.append("❌ bot_config.json nicht gefunden")
        else:
            try:
                with open("bot_config.json", "r") as f:
                    test_config = json.load(f)
                    if "series" not in test_config:
                        errors.append("⚠️ 'series' Key fehlt in bot_config.json")
                    if "packs" not in test_config:
                        errors.append("⚠️ 'packs' Key fehlt in bot_config.json")
            except json.JSONDecodeError as e:
                errors.append(f"❌ bot_config.json ist korrupt: {e}")
        
        # Prüfe guild_configs/
        if os.path.exists(self.guild_config_dir):
            guild_files = [f for f in os.listdir(self.guild_config_dir) if f.endswith('.json')]
            for gf in guild_files[:5]:  # Nur erste 5 prüfen
                try:
                    with open(os.path.join(self.guild_config_dir, gf), "r") as f:
                        json.load(f)
                except json.JSONDecodeError:
                    errors.append(f"❌ {gf} ist korrupt")
        
        if errors:
            error_text = "\n".join(errors)
            embed = discord.Embed(
                title="❌ Config Errors gefunden",
                description=error_text,
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="✅ Config ist sauber",
                description="Keine Fehler gefunden!",
                color=discord.Color.green()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup_dev_commands(bot, tree, owner_id, config, berlin_tz, guild_config_dir):
    """Registriere Dev-Commands mit dem Bot."""
    
    @bot.event
    async def on_message_dev(message):
        """Handle für Dev-Commands via Message Events."""
        if message.content.startswith("-help"):
            if message.author.id != owner_id:
                await message.reply("❌ Nur der Bot-Owner kann das nutzen!", mention_author=False)
                return
            
            embed = discord.Embed(
                title="🔧 Developer Commands",
                description="Verwende die Buttons unten um Dev-Funktionen zu steuern.",
                color=discord.Color.gold()
            )
            embed.add_field(
                name="🔄 Bot Restart",
                value="Startet den Bot neu",
                inline=False
            )
            embed.add_field(
                name="📊 Stats",
                value="Zeigt Bot-Statistiken (Guilds, Users, Uptime, etc.)",
                inline=False
            )
            embed.add_field(
                name="🐛 Errors",
                value="Zeigt wo Fehler gepostet werden",
                inline=False
            )
            embed.add_field(
                name="🔍 Config Check",
                value="Überprüft Integrität der Config-Dateien",
                inline=False
            )
            embed.set_footer(text=f"Nur {message.author.name} kann diese Buttons nutzen")
            
            view = DevCommandView(bot, owner_id, config, berlin_tz, guild_config_dir)
            await message.reply(embed=embed, view=view, mention_author=False)
