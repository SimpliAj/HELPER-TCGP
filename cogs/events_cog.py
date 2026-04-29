import discord
from discord.ext import commands
import asyncio
import os
import re
import sys
import json
import time
from datetime import datetime, timedelta
import utils
from views import GodPackValidationView, TradedView


class DevCommandView(discord.ui.View):
    """View with buttons for dev commands (triggered via -help prefix)."""
    def __init__(self, owner_id):
        super().__init__(timeout=300)
        self.owner_id = owner_id

    @discord.ui.button(label="🔄 Bot Restart", style=discord.ButtonStyle.danger, emoji="🔄")
    async def restart_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Du darfst das nicht!", ephemeral=True)
            return
        embed = discord.Embed(title="🔄 Bot wird neu gestartet...", description="Der Bot startet in 3 Sekunden neu.", color=discord.Color.orange())
        await interaction.response.defer()
        await interaction.followup.send(embed=embed)
        await asyncio.sleep(3)
        os.execv(sys.executable, ['python'] + sys.argv)

    @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.primary, emoji="📊")
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Du darfst das nicht!", ephemeral=True)
            return
        guild_count = len(utils._bot.guilds)
        user_count = sum(len(g.members) for g in utils._bot.guilds)
        uptime = datetime.now(utils.BERLIN_TZ) - utils._bot.start_time if hasattr(utils._bot, 'start_time') else "Unknown"
        config_file_size = os.path.getsize(utils.CONFIG_FILE) if os.path.exists(utils.CONFIG_FILE) else 0
        guild_configs_count = len([f for f in os.listdir(utils.GUILD_CONFIG_DIR) if f.endswith('.json')]) if os.path.exists(utils.GUILD_CONFIG_DIR) else 0
        embed = discord.Embed(title="📊 Bot Statistics", color=discord.Color.blue(), timestamp=datetime.now(utils.BERLIN_TZ))
        embed.add_field(name="🏢 Guilds", value=f"`{guild_count}`", inline=True)
        embed.add_field(name="👥 Users", value=f"`{user_count}`", inline=True)
        embed.add_field(name="⏱️ Uptime", value=f"`{uptime}`", inline=True)
        embed.add_field(name="💾 Config File Size", value=f"`{config_file_size:,} bytes`", inline=True)
        embed.add_field(name="📁 Guild Config Files", value=f"`{guild_configs_count}`", inline=True)
        embed.add_field(name="📦 Packs", value=f"`{len(utils.PACKS)}`", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🐛 Errors", style=discord.ButtonStyle.secondary, emoji="🐛")
    async def errors_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Du darfst das nicht!", ephemeral=True)
            return
        embed = discord.Embed(title="🐛 Recent Errors", description="Fehler werden an den Error-Webhook gepostet.\nSchau im Error-Channel nach!", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔍 Config Check", style=discord.ButtonStyle.success, emoji="🔍")
    async def config_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Du darfst das nicht!", ephemeral=True)
            return
        errors = []
        if not os.path.exists(utils.CONFIG_FILE):
            errors.append("❌ bot_config.json nicht gefunden")
        else:
            try:
                with open(utils.CONFIG_FILE, "r") as f:
                    test_config = json.load(f)
                    if "series" not in test_config:
                        errors.append("⚠️ 'series' Key fehlt in bot_config.json")
                    if "packs" not in test_config:
                        errors.append("⚠️ 'packs' Key fehlt in bot_config.json")
            except json.JSONDecodeError as e:
                errors.append(f"❌ bot_config.json ist korrupt: {e}")
        if os.path.exists(utils.GUILD_CONFIG_DIR):
            guild_files = [f for f in os.listdir(utils.GUILD_CONFIG_DIR) if f.endswith('.json')]
            for gf in guild_files[:5]:
                try:
                    with open(os.path.join(utils.GUILD_CONFIG_DIR, gf), "r") as f:
                        json.load(f)
                except json.JSONDecodeError:
                    errors.append(f"❌ {gf} ist korrupt")
        if errors:
            embed = discord.Embed(title="❌ Config Errors gefunden", description="\n".join(errors), color=discord.Color.red())
        else:
            embed = discord.Embed(title="✅ Config ist sauber", description="Keine Fehler gefunden!", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        global lifetime_stats_task_started, lifetime_stats_task
        utils.set_bot(self.bot)
        self.bot.start_time = datetime.now(utils.BERLIN_TZ)
        print(utils.LOCALE_TEXT["bot_started"].format(bot_name=self.bot.user))
        await self.bot.change_presence(status=discord.Status.online, activity=discord.Game("Pokémon TCG Pocket"))
        await self.bot.tree.sync()
        print("Slash commands synchronized.")

        utils.load_lifetime_stats_messages()

        if not utils.LIFETIME_STATS_TASK_STARTED:
            print("🚀 Creating Lifetime Stats Update Task...")
            utils.LIFETIME_STATS_TASK_STARTED = True
            try:
                utils.LIFETIME_STATS_TASK = asyncio.create_task(self._lifetime_stats_update_task(), name="lifetime_stats_update_task")
                print(f"✅ Lifetime Stats Task created successfully\n")
            except Exception as e:
                print(f"❌ FAILED to create Lifetime Stats Task: {e}")
                utils.LIFETIME_STATS_TASK_STARTED = False

        asyncio.create_task(self._auto_cleanup_task())

        print("🧹 Bereinige bot_config.json...")
        utils.clean_stale_guilds()
        utils.clean_config_duplicates()

        print("🔄 Initialisiere Guild-Configs...")
        utils.ensure_guild_config_dir()
        guilds_initialized = 0
        for guild in self.bot.guilds:
            guild_config = utils.load_guild_config(guild.id)
            if not guild_config or guild_config == {"packs": {}, "filters": {}, "channels": {}}:
                default_config = {
                    "packs": {},
                    "filters": {},
                    "channels": {},
                    "stats": {"godpacks": {"total": 0, "valid": 0, "invalid": 0}, "general": {"total": 0, "valid": 0}},
                    "filter_stats": {},
                    "keyword_channel_map": {},
                    "pack_channel_map": {},
                    "pack_channel_mode": "series"
                }
                utils.save_guild_config_sync(guild.id, default_config)
                guilds_initialized += 1
        if guilds_initialized > 0:
            print(f"✓ {guilds_initialized} neue Server-Configs initialisiert (synchron)")
        print(f"✓ Alle {len(self.bot.guilds)} Guild-Configs geladen und bereit")

        async def check_and_notify_missing_configs():
            while True:
                await asyncio.sleep(60)
                current_time = time.time()
                for guild_id, config_data in list(utils.missing_configs.items()):
                    if config_data["packs"] or config_data["filters"]:
                        if config_data["last_notified"] == 0 and (current_time - config_data.get("first_reported", current_time)) > 1800:
                            await utils.notify_admin_of_missing_configs(guild_id, config_data["packs"], config_data["filters"])
                            config_data["last_notified"] = current_time
                        elif config_data["last_notified"] > 0 and (current_time - config_data["last_notified"]) > 43200:
                            await utils.notify_admin_of_missing_configs(guild_id, config_data["packs"], config_data["filters"])
                            config_data["last_notified"] = current_time

        asyncio.create_task(check_and_notify_missing_configs())

        self.bot.add_view(GodPackValidationView(None, guild_id=None))
        self.bot.add_view(TradedView(None, guild_id=None))

        edit_queue = []
        utils.ensure_guild_config_dir()
        if os.path.exists(utils.GUILD_CONFIG_DIR):
            for config_file in os.listdir(utils.GUILD_CONFIG_DIR):
                if not config_file.startswith("guild_") or not config_file.endswith(".json"):
                    continue
                guild_id = config_file.replace("guild_", "").replace(".json", "")
                guild_config = utils.load_guild_config(guild_id)
                if "heartbeat_message_id" in guild_config:
                    edit_queue.append(("heartbeat", guild_id, guild_config["heartbeat_message_id"], {"channel_id": guild_config["heartbeat_target_channel_id"]}))

        for edit_type, guild_id, message_id, data in edit_queue:
            channel_id = data["channel_id"]
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                guild_config = utils.load_guild_config(guild_id)
                guild_config.pop("heartbeat_target_channel_id", None)
                guild_config.pop("heartbeat_message_id", None)
                utils.save_guild_config(guild_id, guild_config)
                continue
            try:
                message = await channel.fetch_message(int(message_id))
                guild_config = utils.load_guild_config(guild_id)
                embed = utils.create_heartbeat_embed(guild_config)
                await message.edit(embed=embed)
                await asyncio.sleep(0.5)
            except discord.NotFound:
                guild_config = utils.load_guild_config(guild_id)
                guild_config.pop("heartbeat_target_channel_id", None)
                guild_config.pop("heartbeat_message_id", None)
                utils.save_guild_config(guild_id, guild_config)
            except Exception as e:
                print(f"Error restoring heartbeat message {message_id}: {e}")

        asyncio.create_task(self._heartbeat_monitor())

    async def _auto_cleanup_task(self):
        await self.bot.wait_until_ready()
        print("✅ Auto-Cleanup Task started - monitoring bot_config.json for stray guild IDs...\n")
        while not self.bot.is_closed():
            try:
                await asyncio.sleep(60)
                if not os.path.exists(utils.CONFIG_FILE):
                    continue
                try:
                    with open(utils.CONFIG_FILE, "r") as f:
                        current_config = json.load(f)
                except (json.JSONDecodeError, Exception):
                    continue
                guild_ids_found = []
                for key in list(current_config.keys()):
                    if key not in ["series", "packs"]:
                        try:
                            guild_id_int = int(key)
                            if 10**17 <= guild_id_int <= 10**19:
                                guild_ids_found.append(key)
                        except ValueError:
                            pass
                if guild_ids_found:
                    print(f"\n⚠️ [AUTO-CLEANUP] Found {len(guild_ids_found)} server IDs in bot_config.json!")
                    for guild_id_str in guild_ids_found:
                        try:
                            gc = current_config[guild_id_str]
                            if isinstance(gc, dict):
                                utils.save_guild_config_sync(guild_id_str, gc)
                            del current_config[guild_id_str]
                        except Exception as e:
                            print(f"  ❌ [AUTO-CLEANUP] Error extracting guild {guild_id_str}: {e}")
                    utils.save_config(current_config)
                    print(f"\n✅ [AUTO-CLEANUP] bot_config.json cleaned\n")
            except Exception as e:
                print(f"Error in auto_cleanup_task: {e}")

    async def _lifetime_stats_update_task(self):
        try:
            await asyncio.sleep(2)
            print("✅ Lifetime Stats Update Task started - updating every 60 seconds\n")
            utils.load_lifetime_stats_messages()
            cycle_count = 0
            while not self.bot.is_closed():
                try:
                    cycle_count += 1
                    if utils.DEBUG_LIFETIME_STATS:
                        print(f"[Lifetime Stats #{cycle_count}] Update at {datetime.now(utils.BERLIN_TZ).strftime('%H:%M:%S')} - Tracked: {len(utils.LIFETIME_STATS_MESSAGES)} message(s)")
                    await utils.update_lifetime_stats_message()
                    await asyncio.sleep(60)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"❌ Error in lifetime_stats_update_task cycle: {e}")
                    await asyncio.sleep(10)
        except Exception as e:
            print(f"❌ Critical error in lifetime_stats_update_task: {e}")

    async def _heartbeat_monitor(self):
        while True:
            utils.ensure_guild_config_dir()
            if os.path.exists(utils.GUILD_CONFIG_DIR):
                for config_file in os.listdir(utils.GUILD_CONFIG_DIR):
                    if not config_file.startswith("guild_") or not config_file.endswith(".json"):
                        continue
                    guild_id = config_file.replace("guild_", "").replace(".json", "")
                    guild_config = utils.load_guild_config(guild_id)
                    if "heartbeat_data" in guild_config and "last_update" in guild_config["heartbeat_data"]:
                        try:
                            last_update = datetime.fromisoformat(guild_config["heartbeat_data"]["last_update"])
                            now = datetime.now(utils.BERLIN_TZ)
                            if now - last_update > timedelta(minutes=60):
                                await utils.update_heartbeat_message(guild_id)
                        except Exception as e:
                            error_msg = f"Error in heartbeat monitor for guild {guild_id}: {e}"
                            print(error_msg)
                            await utils.log_error_to_webhook(error_msg, guild_id=guild_id, command_name="heartbeat_monitor")
            await asyncio.sleep(300)

    @commands.Cog.listener()
    async def on_message(self, message):
        # === DEVELOPER COMMANDS (Prefix-based) ===
        if message.content.startswith("-help"):
            if message.author.id != utils.OWNER_ID:
                await message.reply("❌ Nur der Bot-Owner kann das nutzen!", mention_author=False)
                return
            embed = discord.Embed(
                title="🔧 Developer Commands",
                description="Verwende die Buttons unten um Dev-Funktionen zu steuern.",
                color=discord.Color.gold()
            )
            embed.add_field(name="🔄 Bot Restart", value="Startet den Bot neu", inline=False)
            embed.add_field(name="📊 Stats", value="Zeigt Bot-Statistiken (Guilds, Users, Uptime, etc.)", inline=False)
            embed.add_field(name="🐛 Errors", value="Zeigt wo Fehler gepostet werden", inline=False)
            embed.add_field(name="🔍 Config Check", value="Überprüft Integrität der Config-Dateien", inline=False)
            embed.set_footer(text=f"Nur {message.author.name} kann diese Buttons nutzen")
            view = DevCommandView(utils.OWNER_ID)
            await message.reply(embed=embed, view=view, mention_author=False)
            return

        if message.author == self.bot.user:
            return
        if not message.guild:
            return

        guild_id = str(message.guild.id)
        guild_config = utils.load_guild_config(guild_id)
        keyword_channel_map = guild_config.get("keyword_channel_map", {})
        pack_channel_map = guild_config.get("pack_channel_map", {})
        validation_buttons_enabled = guild_config.get("validation_buttons_enabled", False)

        content_lower = message.content.lower()
        KEYWORDS_PRIORITY = list(utils.CUSTOM_EMBED_TEXT.keys())
        processed_keywords = set()

        for keyword in KEYWORDS_PRIORITY:
            if keyword in processed_keywords:
                continue
            if keyword == "god pack" and "invalid god pack" in content_lower:
                continue
            if keyword.lower() not in content_lower:
                continue
            processed_keywords.add(keyword)

            filter_config = keyword_channel_map.get(keyword.lower())
            if not filter_config:
                if guild_id not in utils.missing_configs:
                    utils.missing_configs[guild_id] = {"packs": set(), "filters": set(), "first_reported": time.time(), "last_notified": 0}
                utils.missing_configs[guild_id]["filters"].add(keyword)
                print(f"No filter config found for keyword: {keyword}")
                continue

            target_channel_id = filter_config.get("channel_id")
            source_channel_ids = filter_config.get("source_channel_ids") or guild_config.get("default_source_channel_ids", [])

            if source_channel_ids and message.channel.id not in source_channel_ids:
                continue

            # Check for pack-specific category
            pack_specific_target = None
            if keyword.lower() in utils.SAVE4TRADE_KEYWORDS:
                pack_specific_categories = guild_config.get("pack_specific_categories", {})
                all_config_packs = [p for series_packs in utils.config.get("series", {}).values() for p in series_packs]
                for pack in all_config_packs:
                    if re.search(r'\b' + re.escape(pack.lower()) + r'\b', content_lower):
                        if pack.lower() in pack_specific_categories:
                            pack_category_config = pack_specific_categories[pack.lower()]
                            pack_channel_id = pack_category_config.get("channels", {}).get(keyword.lower())
                            if pack_channel_id:
                                pack_specific_channel = self.bot.get_channel(pack_channel_id)
                                if pack_specific_channel:
                                    pack_specific_target = pack_specific_channel
                                    break

            target_channel = pack_specific_target if pack_specific_target else self.bot.get_channel(target_channel_id)
            if not target_channel:
                continue

            custom_text = utils.CUSTOM_EMBED_TEXT.get(keyword, message.content)
            message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
            embed_color = utils.EMBED_COLORS.get(keyword, discord.Color.blue())

            embed = discord.Embed(
                title=utils.LOCALE_TEXT["embed_title"].format(keyword=keyword.title()),
                description=f"{custom_text}\n\n" + utils.LOCALE_TEXT["embed_link_text"].format(link=message_link),
                color=embed_color
            )
            embed.set_author(
                name=utils.CUSTOM_AUTHOR_TEXT.get(keyword, utils.LOCALE_TEXT["embed_author_name"]),
                icon_url="https://imgur.com/T0KX069.png"
            )
            embed.set_footer(text="Forwarded by HELPER ¦ TCGP", icon_url="https://imgur.com/T0KX069.png")
            thumbnail_url = utils.EMBED_THUMBNAILS.get(keyword)
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
            image_attached = False
            for attachment in message.attachments:
                if attachment.content_type and "image" in attachment.content_type and not image_attached:
                    embed.set_image(url=attachment.url)
                    image_attached = True

            godpack_ping = guild_config.get("godpack_ping")
            invgodpack_ping = guild_config.get("invgodpack_ping")
            safe_trade_ping = guild_config.get("safe_trade_ping")

            view = None
            if 'stats' not in guild_config:
                guild_config['stats'] = {'godpacks': {'total': 0, 'valid': 0, 'invalid': 0}, 'general': {'total': 0, 'valid': 0, 'invalid': 0}}
            if keyword == "god pack":
                view = GodPackValidationView(embed, guild_id=guild_id)
                guild_config['stats']['godpacks']['total'] += 1
                if 'filter_stats' not in guild_config:
                    guild_config['filter_stats'] = {key: 0 for key in utils.CUSTOM_EMBED_TEXT.keys()}
                guild_config['filter_stats']['god pack'] = guild_config['filter_stats'].get('god pack', 0) + 1
            elif validation_buttons_enabled and keyword in utils.SAVE4TRADE_KEYWORDS:
                view = TradedView(embed, guild_id=guild_id)
                guild_config['stats']['general']['total'] += 1
                if 'filter_stats' not in guild_config:
                    guild_config['filter_stats'] = {key: 0 for key in utils.CUSTOM_EMBED_TEXT.keys()}
                guild_config['filter_stats'][keyword] = guild_config['filter_stats'].get(keyword, 0) + 1
            else:
                if 'filter_stats' not in guild_config:
                    guild_config['filter_stats'] = {key: 0 for key in utils.CUSTOM_EMBED_TEXT.keys()}
                guild_config['filter_stats'][keyword] = guild_config['filter_stats'].get(keyword, 0) + 1

            utils.save_guild_config(guild_id, guild_config)
            await utils.update_stats_message(guild_id)
            await utils.update_detailed_stats_message(guild_id)

            try:
                sent_message = await target_channel.send(embed=embed, view=view)
            except Exception as e:
                if utils.DEBUG_PACK_LOGS:
                    print(f"Error sending embed for keyword '{keyword}' to channel {target_channel_id}: {e}")
                continue

            if isinstance(view, (GodPackValidationView, TradedView)):
                view.original_message = sent_message
                if "validation_messages" not in guild_config:
                    guild_config["validation_messages"] = {}
                view_type = "godpack" if keyword == "god pack" else "traded"
                guild_config["validation_messages"][str(sent_message.id)] = {
                    "channel_id": str(target_channel.id),
                    "view_type": view_type
                }
                utils.save_guild_config(guild_id, guild_config)

            if keyword == "god pack" and godpack_ping:
                await target_channel.send(f"<@&{godpack_ping}>")
            if keyword == "invalid god pack" and invgodpack_ping:
                await target_channel.send(f"<@&{invgodpack_ping}>")
            if keyword in ["one star", "three diamond", "four diamond ex", "crown"] and safe_trade_ping:
                await target_channel.send(f"<@&{safe_trade_ping}>")

        # Pack filter processing
        processed_packs = set()
        for pack in utils.PACKS:
            if pack in processed_packs:
                continue
            if re.search(r'\b' + re.escape(pack.lower()) + r'\b', content_lower):
                processed_packs.add(pack)
                pack_config = pack_channel_map.get(pack.lower())
                if not pack_config:
                    if guild_id not in utils.missing_configs:
                        utils.missing_configs[guild_id] = {"packs": set(), "filters": set(), "first_reported": time.time(), "last_notified": 0}
                    utils.missing_configs[guild_id]["packs"].add(pack)
                    print(f"No pack config found for pack: {pack}")
                    continue

                target_channel_id = pack_config.get("channel_id")
                source_channel_ids = pack_config.get("source_channel_ids") or guild_config.get("default_source_channel_ids", [])
                if source_channel_ids and message.channel.id not in source_channel_ids:
                    continue

                target_channel = self.bot.get_channel(target_channel_id)
                if not target_channel:
                    continue

                custom_text = f"A {pack.title()} pack was opened!"
                message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                embed = discord.Embed(
                    title=f"🔍 Opened: {pack.title()} Pack",
                    description=f"{custom_text}\n\n" + utils.LOCALE_TEXT["embed_link_text"].format(link=message_link),
                    color=discord.Color.blue()
                )
                embed.set_author(name=utils.LOCALE_TEXT["embed_author_name"], icon_url="https://imgur.com/T0KX069.png")
                embed.set_footer(text="Forwarded by HELPER ¦ TCGP", icon_url="https://imgur.com/T0KX069.png")
                for attachment in message.attachments:
                    if attachment.content_type and "image" in attachment.content_type:
                        embed.set_image(url=attachment.url)
                        break

                if 'filter_stats' not in guild_config:
                    guild_config['filter_stats'] = {}
                guild_config['filter_stats'][pack] = guild_config['filter_stats'].get(pack, 0) + 1
                utils.save_guild_config(guild_id, guild_config)
                await utils.update_pack_stats_message(guild_id)

                try:
                    await target_channel.send(embed=embed)
                except Exception as e:
                    if utils.DEBUG_PACK_LOGS:
                        print(f"Error sending embed for pack '{pack}' to channel {target_channel_id}: {e}")

        # Heartbeat processing
        if "heartbeat_source_channel_id" in guild_config and guild_config["heartbeat_source_channel_id"] == message.channel.id:
            if message.content.startswith("Bot"):
                content = message.content
                online_match = re.search(r"Online: (.*)", content)
                offline_match = re.search(r"Offline: (.*)", content)
                time_match = re.search(r"Time: (\d+m)", content)
                packs_match = re.search(r"Packs: (\d+)", content)
                avg_match = re.search(r"Avg: ([\d.]+) packs/min", content)
                version_match = re.search(r"Version: (.*)", content)
                type_match = re.search(r"Type: (.*)", content)
                opening_match = re.search(r"Opening: (.*)", content)

                heartbeat_data = {}
                if online_match:
                    online_str = online_match.group(1).strip()
                    heartbeat_data["online"] = [] if online_str.lower() == "none" else [x.strip() for x in online_str.split(",") if x.strip()]
                if offline_match:
                    offline_str = offline_match.group(1).strip()
                    heartbeat_data["offline"] = [] if offline_str.lower() == "none" else [x.strip() for x in offline_str.split(",") if x.strip()]
                if time_match:
                    heartbeat_data["time"] = time_match.group(1)
                if packs_match:
                    heartbeat_data["packs"] = packs_match.group(1)
                if avg_match:
                    heartbeat_data["avg"] = avg_match.group(1)
                if version_match:
                    heartbeat_data["version"] = version_match.group(1).strip()
                if type_match:
                    heartbeat_data["type"] = type_match.group(1).strip()
                if opening_match:
                    opening_str = opening_match.group(1).strip()
                    heartbeat_data["opening"] = [x.strip() for x in opening_str.split(",") if x.strip()]

                if heartbeat_data:
                    heartbeat_data["last_update"] = datetime.now(utils.BERLIN_TZ).isoformat()
                    guild_config["heartbeat_data"] = heartbeat_data
                    utils.save_guild_config(guild_id, guild_config)
                    await utils.update_heartbeat_message(guild_id)


async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))
