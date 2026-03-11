import os
import asyncio
from dotenv import load_dotenv
import discord
from discord.ext import commands

load_dotenv()

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

EXTENSIONS = [
    "cogs.events_cog",
    "cogs.setup_cog",
    "cogs.config_cog",
    "cogs.packs_cog",
    "cogs.stats_cog",
    "cogs.general_cog",
    "cogs.dev_cog",
]

async def main():
    async with bot:
        for ext in EXTENSIONS:
            await bot.load_extension(ext)
        await bot.start(os.getenv("TOKEN"))

asyncio.run(main())
