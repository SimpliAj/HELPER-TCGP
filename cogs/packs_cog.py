import discord
from discord.ext import commands
from discord import app_commands
import os
import utils


class PacksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="addseries", description="Fügt eine neue Series zur Konfiguration hinzu (DEV only)")
    @app_commands.describe(series_name="Der Name der neuen Series (z.B. 'B-Series')")
    async def addseries(self, interaction: discord.Interaction, series_name: str):
        await interaction.response.defer(ephemeral=True)
        if not await utils.owner_only(interaction):
            return

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
                        guild_config = utils.load_guild_config(guild_id_str)
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

    @app_commands.command(name="addpack", description="Fügt ein neues Pack zur Liste hinzu (Owner only)")
    @app_commands.describe(pack_name="Der Name des neuen Packs (z.B. 'neuespack')", series="Die Series, in die das Pack hinzugefügt werden soll")
    @app_commands.autocomplete(series=utils.autocomplete_series)
    async def addpack(self, interaction: discord.Interaction, pack_name: str, series: str = "A-Series"):
        await interaction.response.defer(ephemeral=True)
        if not await utils.owner_only(interaction):
            return

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
                guild_config = utils.load_guild_config(guild_id_str)
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

    @app_commands.command(name="removepack", description="Entfernt ein Pack aus der Liste (Owner only)")
    @app_commands.describe(pack_name="Der Name des zu entfernenden Packs")
    @app_commands.autocomplete(pack_name=utils.autocomplete_packs)
    async def removepack(self, interaction: discord.Interaction, pack_name: str):
        await interaction.response.defer(ephemeral=True)
        if not await utils.owner_only(interaction):
            return

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
                guild_config = utils.load_guild_config(guild_id_str)
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

    @app_commands.command(name="removeseries", description="Removes a series globally and deletes all channels/category in all setup guilds (Owner only)")
    @app_commands.describe(series_name="The name of the series to remove (e.g., 'B-Series')")
    @app_commands.autocomplete(series_name=utils.autocomplete_series)
    async def removeseries(self, interaction: discord.Interaction, series_name: str):
        await interaction.response.defer(ephemeral=True)
        if not await utils.owner_only(interaction):
            return

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
                guild_config = utils.load_guild_config(guild_id_str)
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

    @app_commands.command(name="createpackcategory", description="Create a category for a pack with Save 4 Trade channels (Admin only)")
    @app_commands.autocomplete(pack=utils.autocomplete_packs)
    async def createpackcategory(self, interaction: discord.Interaction, pack: str):
        await interaction.response.defer(ephemeral=True)
        member = interaction.guild.get_member(interaction.user.id)
        if not member.guild_permissions.administrator:
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
        guild_config = utils.load_guild_config(guild_id)

        category_name = f"{pack.title()} - Save 4 Trade"
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            }
            try:
                category = await guild.create_category(category_name, overwrites=overwrites)
            except discord.Forbidden:
                embed = discord.Embed(title="Error", description="Bot lacks permissions to create categories. Please grant **Manage Channels** permission.", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            except Exception as e:
                embed = discord.Embed(title="Error", description=f"Failed to create category: {str(e)}", color=discord.Color.red())
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        created_channels = []
        for keyword in utils.SAVE4TRADE_KEYWORDS:
            channel_name = keyword.lower().replace(" ", "-")
            channel = discord.utils.get(category.text_channels, name=channel_name)
            if not channel:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                }
                try:
                    channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
                    created_channels.append(channel.mention)
                except Exception as e:
                    print(f"Error creating channel {channel_name}: {e}")
                    continue
            else:
                created_channels.append(f"{channel.mention} (existed)")

        if "pack_specific_categories" not in guild_config:
            guild_config["pack_specific_categories"] = {}
        guild_config["pack_specific_categories"][pack_lower] = {"category_id": category.id, "channels": {}}

        for keyword in utils.SAVE4TRADE_KEYWORDS:
            channel_name = keyword.lower().replace(" ", "-")
            channel = discord.utils.get(category.text_channels, name=channel_name)
            if channel:
                guild_config["pack_specific_categories"][pack_lower]["channels"][keyword.lower()] = channel.id

        utils.save_guild_config(guild_id, guild_config)

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
                        if msg.author.bot:
                            continue
                        message_content = msg.content.lower()
                        if not re.search(r'\b' + re.escape(content_lower) + r'\b', message_content):
                            continue
                        for keyword in utils.SAVE4TRADE_KEYWORDS:
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


async def setup(bot: commands.Bot):
    await bot.add_cog(PacksCog(bot))
