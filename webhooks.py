"""
Error logging to Discord webhooks.
"""
import aiohttp
import discord
import time
from datetime import datetime

async def log_error_to_webhook(config, berlin_tz, error_message: str, guild_id: str = None, command_name: str = None):
    """Sende Fehler an Discord Webhook als Embed."""
    try:
        webhook_url = config.get("error_webhook_url")
        if not webhook_url:
            print(f"⚠️ Error Webhook URL not configured in bot_config.json")
            return
        
        # Kürze lange Nachrichten
        if len(error_message) > 1500:
            error_message = error_message[:1500] + "\n... (gekürzt)"
        
        embed = discord.Embed(
            title="🚨 Bot Error",
            description=error_message,
            color=discord.Color.red(),
            timestamp=datetime.now(berlin_tz)
        )
        
        if command_name:
            embed.add_field(name="Befehl", value=f"`{command_name}`", inline=True)
        
        if guild_id:
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
        
        embed.add_field(name="Zeitstempel", value=f"<t:{int(time.time())}:F>", inline=False)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json={"embeds": [embed.to_dict()]}) as resp:
                if resp.status not in [200, 204]:
                    print(f"⚠️ Failed to send error to webhook: {resp.status}")
    except Exception as e:
        print(f"❌ Error logging to webhook: {e}")

async def log_permission_warning_to_webhook(config, berlin_tz, error_message: str, guild_id: str = None, command_name: str = None):
    """Sende Permission-Warnungen an separaten Discord Webhook als Embed."""
    try:
        webhook_url = config.get("permission_warning_webhook_url")
        if not webhook_url:
            # Fallback to regular error webhook if permission webhook not configured
            await log_error_to_webhook(config, berlin_tz, error_message, guild_id, command_name)
            return
        
        # Kürze lange Nachrichten
        if len(error_message) > 1500:
            error_message = error_message[:1500] + "\n... (gekürzt)"
        
        embed = discord.Embed(
            title="⚠️ Permission Warning",
            description=error_message,
            color=discord.Color.orange(),
            timestamp=datetime.now(berlin_tz)
        )
        
        if command_name:
            embed.add_field(name="Befehl", value=f"`{command_name}`", inline=True)
        
        if guild_id:
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
        
        embed.add_field(name="Zeitstempel", value=f"<t:{int(time.time())}:F>", inline=False)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json={"embeds": [embed.to_dict()]}) as resp:
                if resp.status not in [200, 204]:
                    print(f"⚠️ Failed to send permission warning to webhook: {resp.status}")
    except Exception as e:
        print(f"❌ Error logging permission warning to webhook: {e}")
