"""
Message Handler - on_message Event mit kompletter Pack-Filter Verarbeitung
"""
import discord
import re
import time
from config import load_guild_config, save_guild_config
from utils import CUSTOM_EMBED_TEXT, CUSTOM_AUTHOR_TEXT, EMBED_THUMBNAILS, EMBED_COLORS, SAVE4TRADE_KEYWORDS
from views.validation import GodPackValidationView, TradedView


async def process_message(message, bot, config, BERLIN_TZ):
    """Verarbeite Message auf Pack/Filter Keywords."""
    if message.author == bot.user:
        return

    guild_id = str(message.guild.id)
    guild_config = load_guild_config(guild_id)
    keyword_channel_map = guild_config.get("keyword_channel_map", {})
    pack_channel_map = guild_config.get("pack_channel_map", {})
    validation_buttons_enabled = guild_config.get("validation_buttons_enabled", False)

    content_lower = message.content.lower()
    KEYWORDS_PRIORITY = list(CUSTOM_EMBED_TEXT.keys())

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
            if guild_id not in bot.missing_configs:
                bot.missing_configs[guild_id] = {"packs": set(), "filters": set(), "first_reported": time.time(), "last_notified": 0}
            bot.missing_configs[guild_id]["filters"].add(keyword)
            print(f"No filter config for keyword: {keyword}")
            continue

        target_channel_id = filter_config.get("channel_id")
        source_channel_ids = filter_config.get("source_channel_ids") or guild_config.get("default_source_channel_ids", [])
        
        if source_channel_ids and message.channel.id not in source_channel_ids:
            continue

        # Pack-specific target
        pack_specific_target = None
        if keyword.lower() in SAVE4TRADE_KEYWORDS:
            pack_specific_categories = guild_config.get("pack_specific_categories", {})
            all_config_packs = [p for series_packs in config.get("series", {}).values() for p in series_packs]
            for pack in all_config_packs:
                if re.search(r'\b' + re.escape(pack.lower()) + r'\b', content_lower):
                    if pack.lower() in pack_specific_categories:
                        pack_category_config = pack_specific_categories[pack.lower()]
                        pack_channel_id = pack_category_config.get("channels", {}).get(keyword.lower())
                        if pack_channel_id:
                            pack_specific_channel = bot.get_channel(pack_channel_id)
                            if pack_specific_channel:
                                pack_specific_target = pack_specific_channel
                                break

        target_channel = pack_specific_target if pack_specific_target else bot.get_channel(target_channel_id)
        
        if not target_channel:
            continue

        custom_text = CUSTOM_EMBED_TEXT.get(keyword, message.content)
        message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
        embed_color = EMBED_COLORS.get(keyword, discord.Color.blue())

        embed = discord.Embed(
            title=f"Found: {keyword.title()}",
            description=f"{custom_text}\n\n[Go to original message]({message_link})",
            color=embed_color
        )

        embed.set_author(
            name=CUSTOM_AUTHOR_TEXT.get(keyword, "Save 4 Trade"),
            icon_url="https://imgur.com/T0KX069.png"
        )

        embed.set_footer(
            text="Forwarded by HELPER ¦ TCGP",
            icon_url="https://imgur.com/T0KX069.png"
        )

        thumbnail_url = EMBED_THUMBNAILS.get(keyword)
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
            guild_config['stats'] = {
                'godpacks': {'total': 0, 'valid': 0, 'invalid': 0},
                'general': {'total': 0, 'valid': 0, 'invalid': 0}
            }
        
        if keyword == "god pack":
            view = GodPackValidationView(embed, guild_id=guild_id)
            guild_config['stats']['godpacks']['total'] += 1
            if 'filter_stats' not in guild_config:
                guild_config['filter_stats'] = {key: 0 for key in CUSTOM_EMBED_TEXT.keys()}
            guild_config['filter_stats']['god pack'] = guild_config['filter_stats'].get('god pack', 0) + 1
        elif validation_buttons_enabled and keyword in SAVE4TRADE_KEYWORDS:
            view = TradedView(embed, guild_id=guild_id)
            guild_config['stats']['general']['total'] += 1
            if 'filter_stats' not in guild_config:
                guild_config['filter_stats'] = {key: 0 for key in CUSTOM_EMBED_TEXT.keys()}
            guild_config['filter_stats'][keyword] = guild_config['filter_stats'].get(keyword, 0) + 1
        else:
            if 'filter_stats' not in guild_config:
                guild_config['filter_stats'] = {key: 0 for key in CUSTOM_EMBED_TEXT.keys()}
            guild_config['filter_stats'][keyword] = guild_config['filter_stats'].get(keyword, 0) + 1

        save_guild_config(guild_id, guild_config)
        
        # Import hier um zirkuläre Imports zu vermeiden
        from main import update_stats_message, update_detailed_stats_message
        await update_stats_message(guild_id)
        await update_detailed_stats_message(guild_id)

        try:
            sent_message = await target_channel.send(embed=embed, view=view)
            print(f"Sent embed for keyword '{keyword}' to channel {target_channel_id}")
        except Exception as e:
            print(f"Error sending embed for keyword '{keyword}': {e}")
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
            save_guild_config(guild_id, guild_config)

        if keyword == "god pack" and godpack_ping:
            await target_channel.send(f"<@&{godpack_ping}>")
        if keyword == "invalid god pack" and invgodpack_ping:
            await target_channel.send(f"<@&{invgodpack_ping}>")
        if keyword in ["one star", "three diamond", "four diamond ex", "crown"] and safe_trade_ping:
            await target_channel.send(f"<@&{safe_trade_ping}>")

    # Pack-Filter Processing
    processed_packs = set()
    for pack in config.get("packs", []):
        if pack in processed_packs:
            continue

        if re.search(r'\b' + re.escape(pack.lower()) + r'\b', content_lower):
            processed_packs.add(pack)

            pack_config = pack_channel_map.get(pack.lower())
            if not pack_config:
                if guild_id not in bot.missing_configs:
                    bot.missing_configs[guild_id] = {"packs": set(), "filters": set(), "first_reported": time.time(), "last_notified": 0}
                bot.missing_configs[guild_id]["packs"].add(pack)
                print(f"No pack config for pack: {pack}")
                continue

            target_channel_id = pack_config.get("channel_id")
            source_channel_ids = pack_config.get("source_channel_ids") or guild_config.get("default_source_channel_ids", [])

            if source_channel_ids and message.channel.id not in source_channel_ids:
                continue

            target_channel = bot.get_channel(target_channel_id)
            if not target_channel:
                continue

            custom_text = f"A {pack.title()} pack was opened!"
            message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"

            embed = discord.Embed(
                title=f"🔍 Opened: {pack.title()} Pack",
                description=f"{custom_text}\n\n[Go to original message]({message_link})",
                color=discord.Color.blue()
            )

            embed.set_author(
                name="Save 4 Trade",
                icon_url="https://imgur.com/T0KX069.png"
            )

            embed.set_footer(
                text="Forwarded by HELPER ¦ TCGP",
                icon_url="https://imgur.com/T0KX069.png"
            )

            image_attached = False
            for attachment in message.attachments:
                if attachment.content_type and "image" in attachment.content_type and not image_attached:
                    embed.set_image(url=attachment.url)
                    image_attached = True

            if 'filter_stats' not in guild_config:
                guild_config['filter_stats'] = {}
            guild_config['filter_stats'][pack] = guild_config['filter_stats'].get(pack, 0) + 1

            save_guild_config(guild_id, guild_config)
            
            from main import update_pack_stats_message
            await update_pack_stats_message(guild_id)

            try:
                await target_channel.send(embed=embed)
                print(f"Sent pack embed for '{pack}'")
            except Exception as e:
                print(f"Error sending pack embed for '{pack}': {e}")

    # Heartbeat Processing
    if "heartbeat_source_channel_id" in guild_config and guild_config["heartbeat_source_channel_id"] == message.channel.id:
        if message.content.startswith("Heartbeat"):
            content = message.content
            heartbeat_data = {}
            
            online_match = re.search(r"Online: (.*)", content)
            if online_match:
                online_str = online_match.group(1).strip()
                heartbeat_data["online"] = [x.strip() for x in online_str.split(",") if x.strip() and x.strip().lower() != "none"]
            
            time_match = re.search(r"Time: (\d+m)", content)
            if time_match:
                heartbeat_data["time"] = time_match.group(1)
            
            packs_match = re.search(r"Packs: (\d+)", content)
            if packs_match:
                heartbeat_data["packs"] = packs_match.group(1)
            
            avg_match = re.search(r"Avg: ([\d.]+) packs/min", content)
            if avg_match:
                heartbeat_data["avg"] = avg_match.group(1)
            
            type_match = re.search(r"Type: (.*)", content)
            if type_match:
                heartbeat_data["type"] = type_match.group(1).strip()
            
            opening_match = re.search(r"Opening: (.*)", content)
            if opening_match:
                opening_str = opening_match.group(1).strip()
                heartbeat_data["opening"] = [x.strip() for x in opening_str.split(",") if x.strip()]

            if heartbeat_data:
                from datetime import datetime
                heartbeat_data["last_update"] = datetime.now(BERLIN_TZ).isoformat()
                guild_config["heartbeat_data"] = heartbeat_data
                save_guild_config(guild_id, guild_config)
                
                from main import update_heartbeat_message
                await update_heartbeat_message(guild_id)
