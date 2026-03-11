import discord
import asyncio
import utils


class GodPackValidationView(discord.ui.View):
    def __init__(self, embed: discord.Embed, original_message: discord.Message = None, guild_id: str = None):
        super().__init__(timeout=None)
        self.embed = embed
        self.original_message = original_message
        self.disabled = False
        self.guild_id = guild_id
        self.allowed_role_id = utils.load_guild_config(guild_id).get("validator_role_id") if guild_id else None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not hasattr(member, "roles"):
            await interaction.followup.send("⛔ Error during role check.", ephemeral=True)
            return False
        if not self.allowed_role_id:
            await interaction.followup.send("⛔ No validator role configured for this server. Please set one using /setvalidatorrole.", ephemeral=True)
            return False
        if not any(role.id == self.allowed_role_id for role in member.roles):
            await interaction.followup.send("⛔ You do not have permission for this.", ephemeral=True)
            return False
        if self.disabled:
            await interaction.followup.send("❌ This action has already been completed.", ephemeral=True)
            return False
        return True

    async def disable_all_buttons(self, interaction: discord.Interaction):
        self.disabled = True
        for child in self.children:
            child.disabled = True
        await self.original_message.edit(embed=self.embed, view=self)

    @discord.ui.button(label="✅ Valid", style=discord.ButtonStyle.success, custom_id="godpack_valid")
    async def valid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.embed.color = discord.Color.green()
        await self.disable_all_buttons(interaction)
        await interaction.followup.send("✅ Marked as valid.", ephemeral=True)
        guild_config = utils.load_guild_config(self.guild_id)
        if 'stats' not in guild_config:
            guild_config['stats'] = {'godpacks': {'total': 0, 'valid': 0, 'invalid': 0}, 'general': {'total': 0, 'valid': 0, 'invalid': 0}}
        guild_config['stats']['godpacks']['valid'] += 1
        utils.save_guild_config(self.guild_id, guild_config)
        await utils.update_stats_message(self.guild_id)
        if "validation_messages" in guild_config and str(self.original_message.id) in guild_config["validation_messages"]:
            del guild_config["validation_messages"][str(self.original_message.id)]
            utils.save_guild_config(self.guild_id, guild_config)

    @discord.ui.button(label="❌ Invalid", style=discord.ButtonStyle.danger, custom_id="godpack_invalid")
    async def invalid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.embed.color = discord.Color.red()
        await self.disable_all_buttons(interaction)
        await interaction.followup.send("❌ Marked as invalid.", ephemeral=True)
        guild_config = utils.load_guild_config(self.guild_id)
        if 'stats' not in guild_config:
            guild_config['stats'] = {'godpacks': {'total': 0, 'valid': 0, 'invalid': 0}, 'general': {'total': 0, 'valid': 0, 'invalid': 0}}
        guild_config['stats']['godpacks']['invalid'] += 1
        utils.save_guild_config(self.guild_id, guild_config)
        await utils.update_stats_message(self.guild_id)
        if "validation_messages" in guild_config and str(self.original_message.id) in guild_config["validation_messages"]:
            del guild_config["validation_messages"][str(self.original_message.id)]
            utils.save_guild_config(self.guild_id, guild_config)


class TradedModal(discord.ui.Modal, title="Mark as Traded - Enter Card Details"):
    card_input = discord.ui.TextInput(
        label="Traded Card",
        style=discord.TextStyle.short,
        placeholder="e.g., Pikachu VMAX",
        required=True,
        max_length=100
    )

    def __init__(self):
        super().__init__()
        self.original_message = None
        self.guild_id = None
        self.view = None

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = self.original_message.embeds[0]
        embed.add_field(name="✅ Traded Card", value=self.card_input.value, inline=False)
        embed.color = discord.Color.green()
        self.view.disabled = True
        for child in self.view.children:
            child.disabled = True
        await self.original_message.edit(embed=embed, view=self.view)

        guild_config = utils.load_guild_config(self.guild_id)
        if 'stats' not in guild_config:
            guild_config['stats'] = {'godpacks': {'total': 0, 'valid': 0, 'invalid': 0}, 'general': {'total': 0, 'valid': 0, 'invalid': 0}}
        guild_config['stats']['general']['valid'] += 1
        utils.save_guild_config(self.guild_id, guild_config)
        await utils.update_stats_message(self.guild_id)

        if "validation_messages" in guild_config and str(self.original_message.id) in guild_config["validation_messages"]:
            del guild_config["validation_messages"][str(self.original_message.id)]
            utils.save_guild_config(self.guild_id, guild_config)

        await interaction.followup.send("✅ Marked as traded with card details added to embed.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(f"Traded modal error: {error}")
        await interaction.followup.send("An error occurred during traded submission.", ephemeral=True)


class TradedView(discord.ui.View):
    def __init__(self, embed: discord.Embed, original_message: discord.Message = None, guild_id: str = None):
        super().__init__(timeout=None)
        self.embed = embed
        self.original_message = original_message
        self.disabled = False
        self.guild_id = guild_id
        self.allowed_role_id = utils.load_guild_config(guild_id).get("validator_role_id") if guild_id else None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not hasattr(member, "roles"):
            await interaction.followup.send("⛔ Error during role check.", ephemeral=True)
            return False
        if not self.allowed_role_id:
            await interaction.followup.send("⛔ No validator role configured for this server. Please set one using /setvalidatorrole.", ephemeral=True)
            return False
        if not any(role.id == self.allowed_role_id for role in member.roles):
            await interaction.followup.send("⛔ You do not have permission for this.", ephemeral=True)
            return False
        if self.disabled:
            await interaction.followup.send("❌ This action has already been completed.", ephemeral=True)
            return False
        return True

    async def disable_all_buttons(self, interaction: discord.Interaction):
        self.disabled = True
        for child in self.children:
            child.disabled = True
        await self.original_message.edit(embed=self.embed, view=self)

    @discord.ui.button(label="✅ Traded", style=discord.ButtonStyle.success, custom_id="traded")
    async def traded_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TradedModal()
        modal.original_message = self.original_message
        modal.guild_id = self.guild_id
        modal.view = self
        await interaction.response.send_modal(modal)
