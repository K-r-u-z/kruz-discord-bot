import discord
from discord import app_commands, ui
from discord.ext import commands
import logging
from typing import Optional
from config import GUILD_ID
import os
import json

logger = logging.getLogger(__name__)
GUILD = discord.Object(id=GUILD_ID)

class VoiceChannelView(discord.ui.View):
    def __init__(self, cog: 'VoiceChannels', user: discord.Member):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        
        # Create buttons
        self.create_button = discord.ui.Button(
            label="Create Channel",
            style=discord.ButtonStyle.primary,
            custom_id="create_channel"
        )
        self.create_button.callback = self.create_channel_callback
        self.add_item(self.create_button)
        
        self.delete_button = discord.ui.Button(
            label="Delete Channel",
            style=discord.ButtonStyle.danger,
            custom_id="delete_channel",
            disabled=True
        )
        self.delete_button.callback = self.delete_channel_callback
        self.add_item(self.delete_button)
        
        # Add rename button
        self.rename_button = discord.ui.Button(
            label="Rename Channel",
            style=discord.ButtonStyle.secondary,
            custom_id="rename_channel",
            disabled=True
        )
        self.rename_button.callback = self.rename_channel_callback
        self.add_item(self.rename_button)
        
        # Check if user has a channel and update button states
        self.update_button_states()

    def update_button_states(self):
        """Update button states based on whether user has a channel"""
        has_channel = False
        # Check if user has a bot-created channel
        if str(self.user.id) in self.cog.settings.get("user_channels", {}):
            has_channel = True
        
        self.delete_button.disabled = not has_channel
        self.rename_button.disabled = not has_channel

    def get_user_channel(self):
        """Get the user's private channel created by the bot"""
        # Check if user has a bot-created channel
        if str(self.user.id) in self.cog.settings.get("user_channels", {}):
            channel_id = self.cog.settings["user_channels"][str(self.user.id)]
            return self.user.guild.get_channel(channel_id)
        return None

    async def create_channel_callback(self, interaction: discord.Interaction):
        # Check if category is set up
        if not self.cog.category_id:
            await interaction.response.send_message(
                "Private voice channels are not set up yet. Please contact an administrator.",
                ephemeral=True
            )
            return
            
        # Get the category
        category = interaction.guild.get_channel(self.cog.category_id)
        if not category:
            await interaction.response.send_message(
                "The category for private voice channels was not found. Please contact an administrator.",
                ephemeral=True
            )
            return
            
        # Check if user already has a bot-created private channel
        if self.get_user_channel():
            await interaction.response.send_message(
                "You already have a private voice channel created by the bot!",
                ephemeral=True
            )
            return
        
        try:
            # Create private voice channel with proper permissions
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=False),
                interaction.user: discord.PermissionOverwrite(
                    connect=True, 
                    manage_channels=True,
                    view_channel=True,
                    manage_permissions=True
                ),
                interaction.guild.me: discord.PermissionOverwrite(
                    connect=True, 
                    manage_channels=True,
                    view_channel=True,
                    manage_permissions=True
                )
            }
            
            channel = await interaction.guild.create_voice_channel(
                name=f"🔒 {interaction.user.name}'s Channel",
                category=category,
                overwrites=overwrites
            )
            
            # Store the channel ID in settings
            if "user_channels" not in self.cog.settings:
                self.cog.settings["user_channels"] = {}
            self.cog.settings["user_channels"][str(interaction.user.id)] = channel.id
            self.cog._save_settings()
            
            # Update button states
            self.update_button_states()
            
            # Create new embed with updated channel info
            embed = discord.Embed(
                title="🎤 Voice Channel Management",
                description="Use the buttons below to manage your private voice channel. You can manage permissions directly through Discord's interface.",
                color=self.cog.embed_color
            )
            embed.add_field(
                name="Your Channel",
                value=f"{channel.mention}",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to create voice channels. Please contact an administrator.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error creating voice channel: {e}")
            await interaction.response.send_message(
                "An error occurred while creating your voice channel.",
                ephemeral=True
            )

    async def delete_channel_callback(self, interaction: discord.Interaction):
        # Get user's channel
        user_channel = self.get_user_channel()
        if not user_channel:
            await interaction.response.send_message(
                "Your private channel was not found!",
                ephemeral=True
            )
            return
        
        try:
            # Send response first
            await interaction.response.send_message(
                "Your private voice channel has been deleted!",
                ephemeral=True
            )
            
            # Remove channel from settings
            if str(interaction.user.id) in self.cog.settings.get("user_channels", {}):
                del self.cog.settings["user_channels"][str(interaction.user.id)]
                self.cog._save_settings()
            
            # Then delete the channel
            await user_channel.delete()
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to delete the channel. Please contact an administrator.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error deleting voice channel: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while deleting your channel.",
                    ephemeral=True
                )
                
    async def rename_channel_callback(self, interaction: discord.Interaction):
        # Get user's channel
        user_channel = self.get_user_channel()
        if not user_channel:
            await interaction.response.send_message(
                "Your private channel was not found!",
                ephemeral=True
            )
            return
        
        # Create a modal for renaming the channel
        class RenameModal(discord.ui.Modal, title="Rename Your Voice Channel"):
            new_name = discord.ui.TextInput(
                label="New Channel Name",
                placeholder="Enter a new name for your channel",
                required=True,
                max_length=100
            )
            
            def __init__(self, cog, view):
                super().__init__()
                self.cog = cog
                self.view = view
            
            async def on_submit(self, interaction: discord.Interaction):
                try:
                    # Update the channel name
                    await user_channel.edit(name=f"🔒 {self.new_name.value}")
                    
                    # Update the embed with the new channel name
                    embed = discord.Embed(
                        title="🎤 Voice Channel Management",
                        description="Use the buttons below to manage your private voice channel. You can manage permissions directly through Discord's interface.",
                        color=self.cog.embed_color
                    )
                    embed.add_field(
                        name="Your Channel",
                        value=f"{user_channel.mention}",
                        inline=False
                    )
                    
                    await interaction.response.edit_message(embed=embed, view=self.view)
                    
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "I don't have permission to rename the channel. Please contact an administrator.",
                        ephemeral=True
                    )
                except Exception as e:
                    logger.error(f"Error renaming voice channel: {e}")
                    await interaction.response.send_message(
                        "An error occurred while renaming your channel.",
                        ephemeral=True
                    )
        
        # Show the modal to the user
        modal = RenameModal(self.cog, self)
        await interaction.response.send_modal(modal)

class VoiceChannels(commands.Cog):
    """Cog for managing private voice channels"""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.embed_color = discord.Color.blue()
        
        # Store the leveling cog reference
        self.leveling_cog = None
        
        # Store the category ID for private voice channels
        self.category_id = None
        
        # Load settings
        self.settings_file = 'data/voice_settings.json'
        self.settings = self._load_settings()
        if 'category_id' in self.settings:
            self.category_id = self.settings['category_id']
        
        # Ensure user_channels exists in settings
        if 'user_channels' not in self.settings:
            self.settings['user_channels'] = {}
            self._save_settings()

    def _load_settings(self) -> dict:
        """Load settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading voice settings: {e}")
            return {}

    def _save_settings(self) -> None:
        """Save settings to file"""
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving voice settings: {e}")

    async def cog_load(self) -> None:
        # Get the leveling cog reference
        self.leveling_cog = self.bot.get_cog("Leveling")

    @app_commands.command(
        name="voicesetup",
        description="Set up the category for private voice channels"
    )
    @app_commands.guilds(GUILD)
    @app_commands.default_permissions(administrator=True)
    async def voice_setup(
        self,
        interaction: discord.Interaction
    ) -> None:
        """Set up the category for private voice channels"""
        # Create category select menu
        select = discord.ui.Select(
            placeholder="Select a category for private voice channels",
            options=[
                discord.SelectOption(
                    label=category.name,
                    value=str(category.id),
                    description=f"Use {category.name} for private voice channels"
                )
                for category in sorted(interaction.guild.categories, key=lambda c: c.name)
            ]
        )
        
        async def select_callback(interaction: discord.Interaction):
            try:
                category_id = int(select.values[0])
                category = interaction.guild.get_channel(category_id)
                
                # Save the category ID
                self.category_id = category_id
                self.settings['category_id'] = category_id
                self._save_settings()
                
                await interaction.response.send_message(
                    f"Private voice channels will now be created in {category.mention}!",
                    ephemeral=True
                )
                
            except Exception as e:
                logger.error(f"Error setting up voice category: {e}")
                await interaction.response.send_message(
                    "An error occurred while setting up the category.",
                    ephemeral=True
                )
        
        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        
        await interaction.response.send_message(
            "Select a category for private voice channels:",
            view=view,
            ephemeral=True
        )

    @app_commands.command(
        name="voice",
        description="Manage your private voice channel"
    )
    @app_commands.guilds(GUILD)
    async def voice_management(
        self,
        interaction: discord.Interaction
    ) -> None:
        """Manage your private voice channel"""
        # Check if leveling system is enabled
        if self.leveling_cog and self.leveling_cog.settings.get("enabled", True):
            # Check if user has the milestone role
            role_rewards = self.leveling_cog.settings.get("role_rewards", {})
            level_10_role_id = role_rewards.get("10")
            
            if not level_10_role_id:
                await interaction.response.send_message(
                    "The level 10 role reward has not been set up yet. Please contact an administrator.",
                    ephemeral=True
                )
                return
                
            level_10_role = interaction.guild.get_role(level_10_role_id)
            if not level_10_role:
                await interaction.response.send_message(
                    "The level 10 role reward could not be found. Please contact an administrator.",
                    ephemeral=True
                )
                return
                
            if level_10_role not in interaction.user.roles:
                await interaction.response.send_message(
                    f"You don't have the required role for voice channel management. {level_10_role.name} required",
                    ephemeral=True
                )
                return
        
        # Create embed
        embed = discord.Embed(
            title="🎤 Voice Channel Management",
            description="Use the buttons below to manage your private voice channel. You can manage permissions directly through Discord's interface.",
            color=self.embed_color
        )
        
        # Add channel info if user has a bot-created channel
        if str(interaction.user.id) in self.settings.get("user_channels", {}):
            channel_id = self.settings["user_channels"][str(interaction.user.id)]
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                embed.add_field(
                    name="Your Channel",
                    value=f"{channel.mention}",
                    inline=False
                )
        
        # Create view
        view = VoiceChannelView(self, interaction.user)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceChannels(bot)) 