"""
Validation Views für God Packs und Traded Cards.
"""
import discord
from config import load_guild_config, save_guild_config


class GodPackValidationView(discord.ui.View):
    """View für God Pack Validierung mit Valid/Invalid Buttons."""
    def __init__(self, embed: discord.Embed, original_message: discord.Message = None, guild_id: str = None):
        super().__init__(timeout=None)
        self.embed = embed
        self.original_message = original_message
        self.disabled = False
        self.guild_id = guild_id
        self.allowed_role_id = load_guild_config(guild_id).get("validator_role_id") if guild_id else None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not hasattr(member, "roles"):
            await interaction.response.send_message("⛔ Error during role check.", ephemeral=True)
            return False

        if not self.allowed_role_id:
            await interaction.response.send_message("⛔ No validator role configured for this server. Please set one using /setvalidatorrole.", ephemeral=True)
            return False

        if not any(role.id == self.allowed_role_id for role in member.roles):
            await interaction.response.send_message("⛔ You do not have permission for this.", ephemeral=True)
            return False

        if self.disabled:
            await interaction.response.send_message("❌ This action has already been completed.", ephemeral=True)
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
        await interaction.response.send_message("✅ Marked as valid.", ephemeral=True)
        guild_config = load_guild_config(self.guild_id)
        if 'stats' not in guild_config:
            guild_config['stats'] = {
                'godpacks': {'total': 0, 'valid': 0, 'invalid': 0},
                'general': {'total': 0, 'valid': 0, 'invalid': 0}
            }
        guild_config['stats']['godpacks']['valid'] += 1
        save_guild_config(self.guild_id, guild_config)
        
        # Import hier um zirkuläre Imports zu vermeiden
        from main import update_stats_message
        await update_stats_message(self.guild_id)
        
        if "validation_messages" in guild_config and str(self.original_message.id) in guild_config["validation_messages"]:
            del guild_config["validation_messages"][str(self.original_message.id)]
            save_guild_config(self.guild_id, guild_config)

    @discord.ui.button(label="❌ Invalid", style=discord.ButtonStyle.danger, custom_id="godpack_invalid")
    async def invalid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.embed.color = discord.Color.red()
        await self.disable_all_buttons(interaction)
        await interaction.response.send_message("❌ Marked as invalid.", ephemeral=True)
        guild_config = load_guild_config(self.guild_id)
        if 'stats' not in guild_config:
            guild_config['stats'] = {
                'godpacks': {'total': 0, 'valid': 0, 'invalid': 0},
                'general': {'total': 0, 'valid': 0, 'invalid': 0}
            }
        guild_config['stats']['godpacks']['invalid'] += 1
        save_guild_config(self.guild_id, guild_config)
        
        # Import hier um zirkuläre Imports zu vermeiden
        from main import update_stats_message
        await update_stats_message(self.guild_id)
        
        if "validation_messages" in guild_config and str(self.original_message.id) in guild_config["validation_messages"]:
            del guild_config["validation_messages"][str(self.original_message.id)]
            save_guild_config(self.guild_id, guild_config)


class TradedModal(discord.ui.Modal, title="Mark as Traded - Enter Card Details"):
    """Modal für Traded Card Details."""
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

        # Update the embed with traded card details
        embed = self.original_message.embeds[0]
        embed.add_field(
            name="✅ Traded Card",
            value=self.card_input.value,
            inline=False
        )
        embed.color = discord.Color.green()

        # Disable the view
        self.view.disabled = True
        for child in self.view.children:
            child.disabled = True

        # Edit the original message
        await self.original_message.edit(embed=embed, view=self.view)

        # Increment stats
        guild_config = load_guild_config(self.guild_id)
        if 'stats' not in guild_config:
            guild_config['stats'] = {
                'godpacks': {'total': 0, 'valid': 0, 'invalid': 0},
                'general': {'total': 0, 'valid': 0, 'invalid': 0}
            }
        guild_config['stats']['general']['valid'] += 1
        save_guild_config(self.guild_id, guild_config)
        
        from main import update_stats_message
        await update_stats_message(self.guild_id)

        if "validation_messages" in guild_config and str(self.original_message.id) in guild_config["validation_messages"]:
            del guild_config["validation_messages"][str(self.original_message.id)]
            save_guild_config(self.guild_id, guild_config)

        await interaction.followup.send("✅ Marked as traded with card details added.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(f"Traded modal error: {error}")
        await interaction.response.send_message("An error occurred.", ephemeral=True)


class TradedView(discord.ui.View):
    """View für Traded Button (für Save 4 Trade Cards)."""
    def __init__(self, embed: discord.Embed, original_message: discord.Message = None, guild_id: str = None):
        super().__init__(timeout=None)
        self.embed = embed
        self.original_message = original_message
        self.disabled = False
        self.guild_id = guild_id
        self.allowed_role_id = load_guild_config(guild_id).get("validator_role_id") if guild_id else None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not hasattr(member, "roles"):
            await interaction.response.send_message("⛔ Error during role check.", ephemeral=True)
            return False

        if not self.allowed_role_id:
            await interaction.response.send_message("⛔ No validator role configured.", ephemeral=True)
            return False

        if not any(role.id == self.allowed_role_id for role in member.roles):
            await interaction.response.send_message("⛔ Permission denied.", ephemeral=True)
            return False

        if self.disabled:
            await interaction.response.send_message("❌ This action has already been completed.", ephemeral=True)
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
        self.original_message = None
        self.guild_id = None
        self.view = None

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Update the embed with traded card details
        embed = self.original_message.embeds[0]  # Assume first embed
        embed.add_field(
            name="✅ Traded Card",
            value=self.card_input.value,
            inline=False
        )
        embed.color = discord.Color.green()

        # Disable the view
        self.view.disabled = True
        for child in self.view.children:
            child.disabled = True

        # Edit the original message
        await self.original_message.edit(embed=embed, view=self.view)

        # Increment stats
        guild_config = load_guild_config(self.guild_id)
        if 'stats' not in guild_config:
            guild_config['stats'] = {
                'godpacks': {'total': 0, 'valid': 0, 'invalid': 0},
                'general': {'total': 0, 'valid': 0, 'invalid': 0}
            }
        guild_config['stats']['general']['valid'] += 1
        save_guild_config(self.guild_id, guild_config)
        
        # Import hier um zirkuläre Imports zu vermeiden
        from main import update_stats_message
        await update_stats_message(self.guild_id)

        # Remove from validation messages
        if "validation_messages" in guild_config and str(self.original_message.id) in guild_config["validation_messages"]:
            del guild_config["validation_messages"][str(self.original_message.id)]
            save_guild_config(self.guild_id, guild_config)

        # Ephemeral confirmation
        await interaction.followup.send("✅ Marked as traded with card details added to embed.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(f"Traded modal error: {error}")
        await interaction.response.send_message("An error occurred during traded submission.", ephemeral=True)


class TradedView(discord.ui.View):
    """View für Traded Button (für Save 4 Trade Cards)."""
    def __init__(self, embed: discord.Embed, original_message: discord.Message = None, guild_id: str = None):
        super().__init__(timeout=None)
        self.embed = embed
        self.original_message = original_message
        self.disabled = False
        self.guild_id = guild_id
        self.allowed_role_id = load_guild_config(guild_id).get("validator_role_id") if guild_id else None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not hasattr(member, "roles"):
            await interaction.response.send_message("⛔ Error during role check.", ephemeral=True)
            return False

        if not self.allowed_role_id:
            await interaction.response.send_message("⛔ No validator role configured for this server. Please set one using /setvalidatorrole.", ephemeral=True)
            return False

        if not any(role.id == self.allowed_role_id for role in member.roles):
            await interaction.response.send_message("⛔ You do not have permission for this.", ephemeral=True)
            return False

        if self.disabled:
            await interaction.response.send_message("❌ This action has already been completed.", ephemeral=True)
            return False

        return True

    async def disable_all_buttons(self, interaction: discord.Interaction):
        self.disabled = True
        for child in self.children:
            child.disabled = True
        await self.original_message.edit(embed=self.embed, view=self)

    @discord.ui.button(label="✅ Traded", style=discord.ButtonStyle.success, custom_id="traded")
    async def traded_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Create and configure modal
        modal = TradedModal()
        modal.original_message = self.original_message
        modal.guild_id = self.guild_id
        modal.view = self

        # Show the modal
        await interaction.response.send_modal(modal)
