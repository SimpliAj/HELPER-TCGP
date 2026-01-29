"""
Setup Command - Main /setup mit SetupView und Integration aller Setup Views
"""
import discord
from discord import app_commands
from discord.ext import commands
from config import load_guild_config, save_guild_config
from utils import OLD_TO_NEW_CHANNEL_NAMES
from views.setup_views import ModeView


class SetupCommand(commands.Cog):
    def __init__(self, bot, config, OWNER_ID):
        self.bot = bot
        self.config = config
        self.OWNER_ID = OWNER_ID
    
    @app_commands.command(name="setup", description="Automated setup for bot channels and configurations (Admin only)")
    async def setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        member = interaction.guild.get_member(interaction.user.id)
        if member is None or not member.guild_permissions.administrator:
            embed = discord.Embed(
                title="Error",
                description="You need administrator permissions to use this command.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        guild = interaction.guild
        guild_id = str(guild.id)

        embed = discord.Embed(
            title="🚀 Bot Setup Wizard",
            description=(
                "This will create categories and channels for your TCGP server:\n"
                "**Categories & Channels:**\n"
                "• **Save 4 Trade** (individual channels for each filter)\n"
                "• **God Packs** (#god-pack, #invalid-god-pack)\n"
                "• **Detection** (#crown, #immersive)\n"
                "• **A-Series** / **B-Series** (pack channels based on your mode choice)\n\n"
                "**Required Bot Permissions:** Manage Channels, Manage Roles\n\n"
                "Click **✅ Agree** to start."
            ),
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url="https://i.imgur.com/T0KX069.png")

        class SetupView(discord.ui.View):
            def __init__(self, original_user, parent_cog):
                super().__init__(timeout=300)
                self.original_user = original_user
                self.parent_cog = parent_cog

            @discord.ui.button(label="✅ Agree & Setup", style=discord.ButtonStyle.success, emoji="✅")
            async def agree(self, inter: discord.Interaction, button: discord.ui.Button):
                if inter.user != self.original_user:
                    await inter.response.defer()
                    return

                await inter.response.defer(ephemeral=True)

                try:
                    guild_config = load_guild_config(guild_id)

                    # Ensure B-Series exists
                    if "B-Series" not in self.parent_cog.config["series"]:
                        self.parent_cog.config["series"]["B-Series"] = []

                    category_configs = {
                        "Save 4 Trade": {
                            "keywords": ["one star", "three diamond", "four diamond ex", "gimmighoul", "shiny", "rainbow", "full art", "trainer"],
                            "channel_prefix": "save-4-trade-"
                        },
                        "God Packs": {
                            "keywords": ["god pack", "invalid god pack"],
                            "channel_prefix": "god-packs-"
                        },
                        "Detection": {
                            "keywords": ["crown", "immersive"],
                            "channel_prefix": "detection-"
                        },
                        "A-Series": {
                            "series": "A-Series",
                            "channel_name": "a-series"
                        },
                        "B-Series": {
                            "series": "B-Series",
                            "channel_name": "b-series"
                        }
                    }

                    created_channels = {}
                    for cat_name, cfg in category_configs.items():
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                        }
                        category = discord.utils.get(guild.categories, name=cat_name)
                        if not category:
                            category = await guild.create_category(cat_name, overwrites=overwrites)
                        created_channels[cat_name] = category

                    # Create keyword channels
                    keyword_channel_map = {}
                    created_keyword_channels = 0
                    for cat_name, cfg in category_configs.items():
                        if "keywords" in cfg:
                            category = created_channels[cat_name]
                            for keyword in cfg["keywords"]:
                                clean_name = keyword.lower().replace(" ", "-").replace("invalid god pack", "invalid-god-pack")
                                old_channel_name = f"{cfg['channel_prefix']}{clean_name}"
                                channel_name = OLD_TO_NEW_CHANNEL_NAMES.get(old_channel_name, clean_name)
                                existing_channel = discord.utils.get(category.text_channels, name=channel_name)
                                if not existing_channel:
                                    overwrites = {
                                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                                    }
                                    existing_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                                    created_keyword_channels += 1
                                old_channel = discord.utils.get(category.text_channels, name=old_channel_name)
                                if old_channel and old_channel.name != channel_name:
                                    await old_channel.edit(name=channel_name)
                                keyword_channel_map[keyword.lower()] = {
                                    "channel_id": existing_channel.id,
                                    "source_channel_ids": []
                                }

                    guild_config["keyword_channel_map"] = keyword_channel_map
                    
                    # Pre-create default pack channels (series mode)
                    created_pack_channels = 0
                    for cat_name, cfg in category_configs.items():
                        if "series" in cfg:
                            category = created_channels[cat_name]
                            series_name = cfg["series"]
                            global_series_packs = self.parent_cog.config.get("series", {}).get(series_name, [])
                            if global_series_packs:
                                channel_name = f"{series_name.lower().replace(' ', '-')}-packs"
                                existing_channel = discord.utils.get(category.text_channels, name=channel_name)
                                if not existing_channel:
                                    overwrites = {
                                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                                        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                                    }
                                    existing_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
                                    created_pack_channels += 1
                                if "pack_channel_map" not in guild_config:
                                    guild_config["pack_channel_map"] = {}
                                for pack in global_series_packs:
                                    guild_config["pack_channel_map"][pack.lower()] = {
                                        "channel_id": existing_channel.id,
                                        "source_channel_ids": []
                                    }

                    save_guild_config(guild_id, guild_config)

                    # Show Mode Choice
                    mode_embed = discord.Embed(
                        title="✅ Categories Created! – Step 1: Choose Pack Mode",
                        description=f"Created {created_keyword_channels} filter channels + {created_pack_channels} default pack channels.\n\n"
                                    "Select mode to finalize pack channels:\n\n"
                                    "**One Channel per Series:** Uses #a-series-packs, etc.\n"
                                    "**One Channel per Pack:** Creates individual #pack-pack channels.",
                        color=discord.Color.orange()
                    )
                    mode_view = ModeView(self.original_user, guild_id, created_channels, self.parent_cog.config)
                    await inter.followup.send(embed=mode_embed, view=mode_view)

                    setup_embed = discord.Embed(
                        title="✅ Setup In Progress!",
                        description=f"Categories & channels created. Finalizing packs next.",
                        color=discord.Color.green()
                    )
                    await inter.edit_original_response(embed=setup_embed, view=None)

                except discord.Forbidden:
                    error_msg = "Bot lacks 'Manage Channels' permission."
                    error_embed = discord.Embed(
                        title="❌ Permission Error",
                        description=error_msg,
                        color=discord.Color.red()
                    )
                    await inter.followup.send(embed=error_embed, ephemeral=True)
                    from webhooks import log_permission_warning_to_webhook
                    await log_permission_warning_to_webhook(self.parent_cog.config, self.parent_cog.bot.BERLIN_TZ, error_msg, guild_id, "setup")
                except Exception as e:
                    error_msg = f"Setup error: {str(e)}"
                    error_embed = discord.Embed(
                        title="❌ Setup Failed",
                        description=error_msg,
                        color=discord.Color.red()
                    )
                    await inter.followup.send(embed=error_embed, ephemeral=True)
                    from webhooks import log_error_to_webhook
                    await log_error_to_webhook(self.parent_cog.config, self.parent_cog.bot.BERLIN_TZ, error_msg, guild_id, "setup")

        view = SetupView(interaction.user, self)
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(SetupCommand(bot, bot.config, bot.OWNER_ID))
