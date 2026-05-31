import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
import utils
import aiohttp

PACKDATA_URL = "https://raw.githubusercontent.com/kevnITG/PTCGPB/refs/heads/main/Data/packdata.dat"
PACKDATA_URL_2 = "https://raw.githubusercontent.com/Leanny/PTCGPB/refs/heads/main/Data/packdata.dat"


def _build_scan_result_embed(new_series: list[str], new_packs: list[str], triggered_by: str = "manual") -> discord.Embed:
    if not new_series and not new_packs:
        embed = discord.Embed(
            title="🔍 Pack Scan Complete",
            description="No new packs or series found.",
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="🆕 New Content Detected",
            description=f"Found during {'manual scan' if triggered_by == 'manual' else 'auto-sync'}.",
            color=discord.Color.gold()
        )
        if new_series:
            embed.add_field(name="📂 New Series", value=", ".join(new_series), inline=False)
        if new_packs:
            embed.add_field(name="📦 New Packs", value=", ".join(new_packs), inline=False)
        embed.set_footer(text=f"{len(new_series)} series · {len(new_packs)} packs added")
    return embed


class PacksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_pack_sync.start()

    async def _do_addseries(self, interaction: discord.Interaction, series_name: str):
        try:
            series_lower = series_name.lower().strip()
            if not series_lower or len(series_lower) < 2:
                embed = discord.Embed(title="Fehler", description="Series-Name muss mindestens 2 Zeichen lang sein.", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if series_lower in [s.lower() for s in utils.config["series"]]:
                embed = discord.Embed(title="Fehler", description=f"Series '{series_name}' existiert bereits.", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            utils.config["series"][series_name] = []
            utils.update_packs(utils.config)
            utils.config["packs"] = utils.PACKS
            utils.save_config(utils.config)
            await self.bot.tree.sync()

            created_count = 0
            error_count = 0

            utils.ensure_guild_config_dir()
            if os.path.exists(utils.GUILD_CONFIG_DIR):
                for config_file in os.listdir(utils.GUILD_CONFIG_DIR):
                    if config_file.startswith("guild_") and config_file.endswith(".json"):
                        guild_id_str = config_file.replace("guild_", "").replace(".json", "")
                        try:
                            guild_config = await asyncio.to_thread(utils.load_guild_config, guild_id_str)
                            guild = self.bot.get_guild(int(guild_id_str))
                            if not guild or "pack_channel_mode" not in guild_config:
                                continue
                            category = discord.utils.get(guild.categories, name=series_name)
                            if not category:
                                overwrites = {
                                    guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                                }
                                category = await guild.create_category(series_name, overwrites=overwrites)
                            channel_name = f"{series_name.lower().replace(' ', '-')}-packs"
                            existing_channel = discord.utils.get(category.text_channels, name=channel_name)
                            if not existing_channel:
                                overwrites = {
                                    guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                                }
                                await category.create_text_channel(channel_name, overwrites=overwrites)
                            if "pack_channel_map" not in guild_config:
                                guild_config["pack_channel_map"] = {}
                            if "pack_channel_mode" not in guild_config:
                                guild_config["pack_channel_mode"] = "series"
                            created_count += 1
                            utils.save_guild_config(guild_id_str, guild_config)
                        except discord.Forbidden:
                            error_count += 1
                        except Exception as e:
                            print(f"Error creating series '{series_name}' in guild {guild_id_str}: {e}")
                            error_count += 1

            embed = discord.Embed(
                title="Series hinzugefügt & Auto-Created",
                description=f"'{series_name}' wurde global hinzugefügt und in **{created_count}** guilds auto-erstellt.\n"
                            f"Errors in **{error_count}** guilds (check perms).\n"
                            f"**Aktuelle Series:** {', '.join(utils.config['series'].keys())}",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"Error in _do_addseries: {e}")
            try:
                await interaction.followup.send("❌ An error occurred. Please try again.", ephemeral=True)
            except Exception:
                pass



    async def _do_addpack(self, interaction: discord.Interaction, pack_name: str, series: str):
        try:
            pack_lower = pack_name.lower().strip()
            if not pack_lower or len(pack_lower) < 2:
                embed = discord.Embed(title="Fehler", description="Pack-Name muss mindestens 2 Zeichen lang sein.", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if pack_lower in [p.lower() for p in utils.PACKS]:
                embed = discord.Embed(title="Fehler", description=f"Pack '{pack_name}' existiert bereits.", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if series not in utils.config["series"]:
                embed = discord.Embed(title="Fehler", description=f"Series '{series}' existiert nicht. Füge sie zuerst mit /addseries hinzu.", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            utils.config["series"][series].append(pack_name)
            utils.update_packs(utils.config)
            utils.config["packs"] = utils.PACKS
            utils.save_config(utils.config)
            await self.bot.tree.sync()

            created_count = 0
            updated_count = 0
            error_count = 0

            utils.ensure_guild_config_dir()
            if os.path.exists(utils.GUILD_CONFIG_DIR):
                for config_file in os.listdir(utils.GUILD_CONFIG_DIR):
                    if not config_file.startswith("guild_") or not config_file.endswith(".json"):
                        continue
                    guild_id_str = config_file.replace("guild_", "").replace(".json", "")
                    guild_config = await asyncio.to_thread(utils.load_guild_config, guild_id_str)
                    try:
                        guild = self.bot.get_guild(int(guild_id_str))
                        if not guild or "pack_channel_mode" not in guild_config:
                            continue
                        pack_mode = guild_config.get("pack_channel_mode", "series")
                        category = discord.utils.get(guild.categories, name=series)
                        if not category:
                            continue
                        if pack_mode == "series":
                            channel_name = f"{series.lower().replace(' ', '-')}-packs"
                            target_channel = discord.utils.get(category.text_channels, name=channel_name)
                            if not target_channel:
                                overwrites = {
                                    guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                                }
                                target_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                            for p in utils.config["series"][series]:
                                if "pack_channel_map" not in guild_config:
                                    guild_config["pack_channel_map"] = {}
                                guild_config["pack_channel_map"][p.lower()] = {
                                    "channel_id": target_channel.id,
                                    "source_channel_ids": guild_config.get("default_source_channel_ids", [])
                                }
                            updated_count += 1
                        else:
                            channel_name = f"{pack_lower}-pack"
                            target_channel = discord.utils.get(category.text_channels, name=channel_name)
                            if not target_channel:
                                overwrites = {
                                    guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                                }
                                target_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                                created_count += 1
                            else:
                                updated_count += 1
                            if "pack_channel_map" not in guild_config:
                                guild_config["pack_channel_map"] = {}
                            guild_config["pack_channel_map"][pack_lower] = {
                                "channel_id": target_channel.id,
                                "source_channel_ids": guild_config.get("default_source_channel_ids", [])
                            }
                        utils.save_guild_config(guild_id_str, guild_config)
                    except discord.Forbidden:
                        await utils.log_permission_warning_to_webhook(
                            f"Permission error: Bot lacks perms to create/update channels in guild {guild_id_str}",
                            guild_id=guild_id_str, command_name="addpack"
                        )
                        error_count += 1
                    except Exception as e:
                        await utils.log_error_to_webhook(
                            f"Error adding pack '{pack_name}' to guild {guild_id_str}: {e}",
                            guild_id=guild_id_str, command_name="addpack"
                        )
                        error_count += 1

            embed = discord.Embed(
                title="Pack hinzugefügt & Auto-Created/Updated",
                description=f"'{pack_name}' wurde zur Series '{series}' hinzugefügt.\n"
                            f"Auto-created/updated in **{created_count + updated_count}** guilds.\n"
                            f"Errors in **{error_count}** guilds (check perms).\n"
                            f"**Aktuelle Packs:** {', '.join(utils.PACKS)}",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"Error in _do_addpack: {e}")
            try:
                await interaction.followup.send("❌ An error occurred. Please try again.", ephemeral=True)
            except Exception:
                pass


    async def _do_removepack(self, interaction: discord.Interaction, pack_name: str):
        try:
            pack_lower = pack_name.lower()
            if pack_lower not in [p.lower() for p in utils.PACKS]:
                embed = discord.Embed(title="Fehler", description=f"Pack '{pack_name}' nicht gefunden.", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            series_found = None
            for series_name, packs_in_series in utils.config["series"].items():
                if pack_lower in [p.lower() for p in packs_in_series]:
                    series_found = series_name
                    break

            if series_found:
                utils.config["series"][series_found] = [p for p in utils.config["series"][series_found] if p.lower() != pack_lower]
                if not utils.config["series"][series_found]:
                    del utils.config["series"][series_found]

            utils.update_packs(utils.config)
            utils.config["packs"] = utils.PACKS
            utils.save_config(utils.config)
            await self.bot.tree.sync()

            deleted_count = 0
            updated_count = 0
            error_count = 0

            utils.ensure_guild_config_dir()
            if os.path.exists(utils.GUILD_CONFIG_DIR):
                for config_file in os.listdir(utils.GUILD_CONFIG_DIR):
                    if not config_file.startswith("guild_") or not config_file.endswith(".json"):
                        continue
                    guild_id_str = config_file.replace("guild_", "").replace(".json", "")
                    guild_config = await asyncio.to_thread(utils.load_guild_config, guild_id_str)
                    try:
                        guild = self.bot.get_guild(int(guild_id_str))
                        if not guild or "pack_channel_mode" not in guild_config:
                            continue
                        pack_mode = guild_config.get("pack_channel_mode", "series")
                        category = discord.utils.get(guild.categories, name=series_found) if series_found else None
                        if not category:
                            if "pack_channel_map" in guild_config and pack_lower in guild_config["pack_channel_map"]:
                                del guild_config["pack_channel_map"][pack_lower]
                                updated_count += 1
                            continue
                        if pack_mode == "pack":
                            channel_name = f"{pack_lower}-pack"
                            target_channel = discord.utils.get(category.text_channels, name=channel_name)
                            if target_channel:
                                await target_channel.delete()
                                deleted_count += 1
                            else:
                                updated_count += 1
                        else:
                            updated_count += 1
                        if "pack_channel_map" in guild_config and pack_lower in guild_config["pack_channel_map"]:
                            del guild_config["pack_channel_map"][pack_lower]
                        utils.save_guild_config(guild_id_str, guild_config)
                    except discord.Forbidden:
                        await utils.log_permission_warning_to_webhook(
                            f"Permission error: Bot lacks perms to delete channels in guild {guild_id_str}",
                            guild_id=guild_id_str, command_name="removepack"
                        )
                        error_count += 1
                    except Exception as e:
                        print(f"Error removing pack '{pack_name}' from guild {guild_id_str}: {e}")
                        error_count += 1

            embed = discord.Embed(
                title="Pack entfernt & Channels Deleted/Updated",
                description=f"'{pack_name}' wurde aus {series_found} entfernt.\n"
                            f"Deleted channels in **{deleted_count}** guilds (pack mode).\n"
                            f"Updated maps in **{updated_count}** guilds (series mode).\n"
                            f"Errors in **{error_count}** guilds (check perms).\n"
                            f"**Aktuelle Packs:** {', '.join(utils.PACKS)}",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"Error in _do_removepack: {e}")
            try:
                await interaction.followup.send("❌ An error occurred. Please try again.", ephemeral=True)
            except Exception:
                pass


    async def _do_removeseries(self, interaction: discord.Interaction, series_name: str):
        try:
            if series_name not in utils.config["series"]:
                embed = discord.Embed(title="Fehler", description=f"Series '{series_name}' nicht gefunden.", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            packs_to_remove = [p.lower() for p in utils.config["series"][series_name]]
            del utils.config["series"][series_name]
            utils.update_packs(utils.config)
            utils.config["packs"] = utils.PACKS
            utils.save_config(utils.config)
            await self.bot.tree.sync()

            deleted_channels_count = 0
            deleted_categories_count = 0
            updated_count = 0
            error_count = 0

            utils.ensure_guild_config_dir()
            if os.path.exists(utils.GUILD_CONFIG_DIR):
                for config_file in os.listdir(utils.GUILD_CONFIG_DIR):
                    if not config_file.startswith("guild_") or not config_file.endswith(".json"):
                        continue
                    guild_id_str = config_file.replace("guild_", "").replace(".json", "")
                    guild_config = await asyncio.to_thread(utils.load_guild_config, guild_id_str)
                    try:
                        guild = self.bot.get_guild(int(guild_id_str))
                        if not guild or "pack_channel_mode" not in guild_config:
                            continue
                        category = discord.utils.get(guild.categories, name=series_name)
                        if not category:
                            if "pack_channel_map" in guild_config:
                                removed_packs = [p for p in packs_to_remove if p in guild_config["pack_channel_map"]]
                                for p in removed_packs:
                                    del guild_config["pack_channel_map"][p]
                                if removed_packs:
                                    updated_count += 1
                            continue
                        for channel in category.text_channels:
                            await channel.delete()
                            deleted_channels_count += 1
                        await category.delete()
                        deleted_categories_count += 1
                        if "pack_channel_map" in guild_config:
                            for p in packs_to_remove:
                                guild_config["pack_channel_map"].pop(p, None)
                            updated_count += 1
                        utils.save_guild_config(guild_id_str, guild_config)
                    except discord.Forbidden:
                        await utils.log_permission_warning_to_webhook(
                            f"Permission error: Bot lacks perms to delete channels/category in guild {guild_id_str}",
                            guild_id=guild_id_str, command_name="removeseries"
                        )
                        error_count += 1
                    except Exception as e:
                        print(f"Error removing series '{series_name}' from guild {guild_id_str}: {e}")
                        error_count += 1

            embed = discord.Embed(
                title="Series entfernt & Channels/Categories Deleted",
                description=f"'{series_name}' wurde global entfernt.\n"
                            f"Deleted **{deleted_channels_count}** channels and **{deleted_categories_count}** categories.\n"
                            f"Updated maps in **{updated_count}** guilds.\n"
                            f"Errors in **{error_count}** guilds (check perms).\n"
                            f"**Aktuelle Series:** {', '.join(utils.config['series'].keys())}",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"Error in _do_removeseries: {e}")
            try:
                await interaction.followup.send("❌ An error occurred. Please try again.", ephemeral=True)
            except Exception:
                pass



    @app_commands.command(name="createpackcategory", description="Create a category for a pack with Save 4 Trade channels (Admin only)")
    @app_commands.autocomplete(pack=utils.autocomplete_packs)
    async def createpackcategory(self, interaction: discord.Interaction, pack: str):
        await interaction.response.defer(ephemeral=True)
        try:
            if not interaction.guild:
                await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
                return
            member = interaction.guild.get_member(interaction.user.id)
            if not member or not member.guild_permissions.administrator:
                embed = discord.Embed(title="Error", description="You need administrator permissions to use this command.", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            pack_lower = pack.lower()
            all_packs = [p.lower() for series_packs in utils.config.get("series", {}).values() for p in series_packs]
            if pack_lower not in all_packs:
                embed = discord.Embed(title="Error", description=f"Pack `{pack}` not found in the global pack list. Use `/addpack` to add it first.", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            guild = interaction.guild
            guild_id = str(guild.id)
            guild_config = await asyncio.to_thread(utils.load_guild_config, guild_id)

            category_name = f"{pack.title()} - Save 4 Trade"
            category = discord.utils.get(guild.categories, name=category_name)

            pack_role_ids = guild_config.get("pack_category_view_roles", [])
            pack_roles = [r for rid in pack_role_ids if (r := guild.get_role(rid))]

            def _build_overwrites(send_ok=True):
                ow = {guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)}
                if pack_roles:
                    ow[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
                    for role in pack_roles:
                        ow[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
                else:
                    ow[guild.default_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True if send_ok else False)
                return ow

            if not category:
                try:
                    category = await guild.create_category(category_name, overwrites=_build_overwrites())
                except discord.Forbidden:
                    embed = discord.Embed(title="Error", description="Bot lacks permissions to create categories. Please grant **Manage Channels** permission.", color=discord.Color.red())
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                except Exception as e:
                    embed = discord.Embed(title="Error", description=f"Failed to create category: {str(e)}", color=discord.Color.red())
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

            GIMMIGHOUL_PACKS = {"shining", "megashine"}
            keywords_for_pack = [kw for kw in utils.SAVE4TRADE_KEYWORDS if kw != "gimmighoul" or pack_lower in GIMMIGHOUL_PACKS]

            created_channels = []
            for keyword in keywords_for_pack:
                channel_name = keyword.lower().replace(" ", "-")
                channel = discord.utils.get(category.text_channels, name=channel_name)
                if not channel:
                    try:
                        channel = await guild.create_text_channel(channel_name, category=category, overwrites=_build_overwrites())
                        created_channels.append(channel.mention)
                    except Exception as e:
                        print(f"Error creating channel {channel_name}: {e}")
                        continue
                else:
                    created_channels.append(f"{channel.mention} (existed)")

            if "pack_specific_categories" not in guild_config:
                guild_config["pack_specific_categories"] = {}
            guild_config["pack_specific_categories"][pack_lower] = {"category_id": category.id, "channels": {}}

            for keyword in keywords_for_pack:
                channel_name = keyword.lower().replace(" ", "-")
                channel = discord.utils.get(category.text_channels, name=channel_name)
                if channel:
                    guild_config["pack_specific_categories"][pack_lower]["channels"][keyword.lower()] = channel.id

            await asyncio.to_thread(utils.save_guild_config_sync, guild_id, guild_config)

            # Repost existing messages from source channels
            source_channel_ids = guild_config.get("default_source_channel_ids", [])
            reposted_count = 0
            import re
            if source_channel_ids:
                content_lower = pack.lower()
                for source_channel_id in source_channel_ids:
                    source_channel = interaction.client.get_channel(source_channel_id)
                    if not source_channel:
                        continue
                    try:
                        async for msg in source_channel.history(limit=100):
                            if msg.author == interaction.client.user:
                                continue
                            message_content = msg.content.lower()
                            if not re.search(utils.pack_search_pattern(pack), message_content):
                                continue
                            for keyword in keywords_for_pack:
                                if keyword.lower() not in message_content:
                                    continue
                                pack_channel_id = guild_config["pack_specific_categories"][pack_lower]["channels"].get(keyword.lower())
                                if not pack_channel_id:
                                    continue
                                target_channel = interaction.client.get_channel(pack_channel_id)
                                if not target_channel:
                                    continue
                                custom_text = utils.CUSTOM_EMBED_TEXT.get(keyword, msg.content)
                                message_link = f"https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}"
                                embed = discord.Embed(
                                    title=utils.LOCALE_TEXT["embed_title"].format(keyword=keyword.title()),
                                    description=f"{custom_text}\n\n" + utils.LOCALE_TEXT["embed_link_text"].format(link=message_link),
                                    color=utils.EMBED_COLORS.get(keyword, discord.Color.blue())
                                )
                                embed.set_author(name=utils.CUSTOM_AUTHOR_TEXT.get(keyword, utils.LOCALE_TEXT["embed_author_name"]), icon_url="https://imgur.com/T0KX069.png")
                                embed.set_footer(text="Forwarded by HELPER ¦ TCGP", icon_url="https://imgur.com/T0KX069.png")
                                thumbnail_url = utils.EMBED_THUMBNAILS.get(keyword)
                                if thumbnail_url:
                                    embed.set_thumbnail(url=thumbnail_url)
                                for attachment in msg.attachments:
                                    if attachment.content_type and "image" in attachment.content_type:
                                        embed.set_image(url=attachment.url)
                                        break
                                try:
                                    await target_channel.send(embed=embed)
                                    reposted_count += 1
                                except Exception as e:
                                    print(f"Error reposting message to {target_channel.name}: {e}")
                                break
                    except Exception as e:
                        print(f"Error fetching messages from source channel {source_channel_id}: {e}")

            embed = discord.Embed(
                title="✅ Pack Category Created",
                description=f"Successfully created category **{category_name}** with Save 4 Trade channels!",
                color=discord.Color.green()
            )
            embed.add_field(name="Pack", value=pack.title(), inline=True)
            embed.add_field(
                name="Channels Created",
                value="\n".join(created_channels[:10]) + (f"\n... and {len(created_channels)-10} more" if len(created_channels) > 10 else ""),
                inline=False
            )
            embed.add_field(name="Existing Messages Reposted", value=f"{reposted_count} message(s) from this pack were found and forwarded to the new channels.", inline=False)
            embed.set_footer(text="All Save 4 Trade messages from this pack will now be forwarded to these channels.")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"Error in /createpackcategory: {e}")
            try:
                await interaction.followup.send("❌ An error occurred. Please try again.", ephemeral=True)
            except Exception:
                pass


    async def _auto_add_series(self, series_name: str) -> int:
        if series_name.lower() in [s.lower() for s in utils.config["series"]]:
            return 0
        utils.config["series"][series_name] = []
        utils.update_packs(utils.config)
        utils.config["packs"] = utils.PACKS
        utils.save_config(utils.config)
        try:
            await self.bot.tree.sync()
        except Exception:
            pass
        created_count = 0
        utils.ensure_guild_config_dir()
        if os.path.exists(utils.GUILD_CONFIG_DIR):
            for config_file in os.listdir(utils.GUILD_CONFIG_DIR):
                if not config_file.startswith("guild_") or not config_file.endswith(".json"):
                    continue
                guild_id_str = config_file.replace("guild_", "").replace(".json", "")
                try:
                    guild_config = await asyncio.to_thread(utils.load_guild_config, guild_id_str)
                    guild = self.bot.get_guild(int(guild_id_str))
                    if not guild or "pack_channel_mode" not in guild_config:
                        continue
                    category = discord.utils.get(guild.categories, name=series_name)
                    if not category:
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                        }
                        category = await guild.create_category(series_name, overwrites=overwrites)
                    channel_name = series_name.lower().replace(" ", "-") + "-packs"
                    if not discord.utils.get(category.text_channels, name=channel_name):
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                        }
                        await category.create_text_channel(channel_name, overwrites=overwrites)
                    if "pack_channel_map" not in guild_config:
                        guild_config["pack_channel_map"] = {}
                    utils.save_guild_config(guild_id_str, guild_config)
                    created_count += 1
                except Exception as e:
                    print(f"[AutoSync] Error creating series in guild {guild_id_str}: {e}")
        return created_count

    async def _auto_add_pack(self, pack_name: str, series: str) -> int:
        pack_lower = pack_name.lower().strip()
        if pack_lower in [p.lower() for p in utils.PACKS]:
            return 0
        if series not in utils.config["series"]:
            return 0
        utils.config["series"][series].append(pack_name)
        utils.update_packs(utils.config)
        utils.config["packs"] = utils.PACKS
        utils.save_config(utils.config)
        try:
            await self.bot.tree.sync()
        except Exception:
            pass
        created_count = 0
        utils.ensure_guild_config_dir()
        if os.path.exists(utils.GUILD_CONFIG_DIR):
            for config_file in os.listdir(utils.GUILD_CONFIG_DIR):
                if not config_file.startswith("guild_") or not config_file.endswith(".json"):
                    continue
                guild_id_str = config_file.replace("guild_", "").replace(".json", "")
                try:
                    guild_config = await asyncio.to_thread(utils.load_guild_config, guild_id_str)
                    guild = self.bot.get_guild(int(guild_id_str))
                    if not guild or "pack_channel_mode" not in guild_config:
                        continue
                    pack_mode = guild_config.get("pack_channel_mode", "series")
                    category = discord.utils.get(guild.categories, name=series)
                    if not category:
                        continue
                    if pack_mode == "series":
                        channel_name = series.lower().replace(" ", "-") + "-packs"
                        target_channel = discord.utils.get(category.text_channels, name=channel_name)
                        if not target_channel:
                            overwrites = {
                                guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                            }
                            target_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                        for p in utils.config["series"][series]:
                            if "pack_channel_map" not in guild_config:
                                guild_config["pack_channel_map"] = {}
                            guild_config["pack_channel_map"][p.lower()] = {
                                "channel_id": target_channel.id,
                                "source_channel_ids": guild_config.get("default_source_channel_ids", [])
                            }
                    else:
                        channel_name = pack_lower + "-pack"
                        target_channel = discord.utils.get(category.text_channels, name=channel_name)
                        if not target_channel:
                            overwrites = {
                                guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                            }
                            target_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                        if "pack_channel_map" not in guild_config:
                            guild_config["pack_channel_map"] = {}
                        guild_config["pack_channel_map"][pack_lower] = {
                            "channel_id": target_channel.id,
                            "source_channel_ids": guild_config.get("default_source_channel_ids", [])
                        }
                    utils.save_guild_config(guild_id_str, guild_config)
                    created_count += 1
                except Exception as e:
                    print(f"[AutoSync] Error adding pack to guild {guild_id_str}: {e}")
        return created_count

    async def _fetch_packdata(self, session: aiohttp.ClientSession, url: str) -> str | None:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    print(f"[AutoSync] {url} returned HTTP {resp.status}")
                    return None
                return await resp.text(encoding="utf-8-sig")
        except Exception as e:
            print(f"[AutoSync] Failed to fetch {url}: {e}")
            return None

    def _parse_packdata(self, text: str) -> list[tuple[str, str]]:
        results = []
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("Pack:"):
                continue
            parts = line[5:].split("|")
            if len(parts) < 2:
                continue
            pack_name = parts[0].strip()
            series_letter = parts[1].strip().upper()
            results.append((pack_name, series_letter + "-Series"))
        return results

    async def _run_pack_scan(self) -> tuple[list[str], list[str]]:
        async with aiohttp.ClientSession() as session:
            text1, text2 = await asyncio.gather(
                self._fetch_packdata(session, PACKDATA_URL),
                self._fetch_packdata(session, PACKDATA_URL_2),
            )

        if not text1 and not text2:
            raise RuntimeError("Both packdata.dat sources failed to respond")

        seen = set()
        entries = []
        for text in (text1, text2):
            if not text:
                continue
            for pack_name, series_name in self._parse_packdata(text):
                key = (pack_name.lower(), series_name.lower())
                if key not in seen:
                    seen.add(key)
                    entries.append((pack_name, series_name))

        new_series = []
        new_packs = []

        for pack_name, series_name in entries:
            if series_name.lower() not in [s.lower() for s in utils.config["series"]]:
                count = await self._auto_add_series(series_name)
                new_series.append(series_name)
                print(f"[AutoSync] New series '{series_name}' added, created in {count} guilds")
                await asyncio.sleep(1)

            if pack_name.lower() not in [p.lower() for p in utils.PACKS]:
                count = await self._auto_add_pack(pack_name, series_name)
                new_packs.append(pack_name)
                print(f"[AutoSync] New pack '{pack_name}' ({series_name}) added, created in {count} guilds")
                await asyncio.sleep(1)

        return new_series, new_packs

    @tasks.loop(hours=1)
    async def auto_pack_sync(self):
        try:
            new_series, new_packs = await self._run_pack_scan()

            if new_series or new_packs:
                await utils.log_error_to_webhook(
                    "**Auto-Sync:** Added " + str(len(new_series)) + " series (" + (", ".join(new_series) or "none") + ") "
                    "and " + str(len(new_packs)) + " packs (" + (", ".join(new_packs) or "none") + ")",
                    command_name="auto_pack_sync"
                )
                try:
                    owner_id = utils.config.get("owner_id")
                    if owner_id:
                        owner = await self.bot.fetch_user(int(owner_id))
                        embed = _build_scan_result_embed(new_series, new_packs, triggered_by="auto")
                        await owner.send(embed=embed)
                except Exception as dm_err:
                    print(f"[AutoSync] Failed to DM owner: {dm_err}")
        except Exception as e:
            print(f"[AutoSync] Error: {e}")

    @auto_pack_sync.before_loop
    async def before_auto_pack_sync(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(PacksCog(bot))
