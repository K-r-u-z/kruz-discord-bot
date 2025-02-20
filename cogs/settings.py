import discord
from discord import app_commands
from discord.ext import commands
import json
import logging
from typing import Dict, Any, Optional
from config import GUILD_ID, BOT_SETTINGS
import asyncio
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class SettingsCog(commands.Cog):
    """Cog for managing bot settings and configuration"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.settings_file = 'data/bot_settings.json'
        self._settings_lock = asyncio.Lock()
        self._last_save = 0
        self._save_delay = 5  # seconds
        self.valid_status_types = {
            "playing", "streaming", "listening", 
            "watching", "competing"
        }
        self.valid_bot_statuses = {
            "online", "idle", "dnd", "invisible"
        }

    async def _delayed_save(self, settings: Dict[str, Any]) -> None:
        """Batch save operations with rate limiting"""
        try:
            # Create data directory if it doesn't exist
            os.makedirs('data', exist_ok=True)
            
            async with self._settings_lock:
                current_time = datetime.now().timestamp()
                if current_time - self._last_save < self._save_delay:
                    return
                
                self._last_save = current_time
                await self._save_to_disk(settings)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            raise

    async def _save_to_disk(self, settings: Dict[str, Any]) -> None:
        """Save settings to disk with error handling"""
        try:
            async with self._settings_lock:
                with open(self.settings_file, 'w') as f:
                    json.dump(settings, f, indent=4)
                logger.info("Settings saved successfully")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            raise

    @app_commands.command(
        name="kruzbot",
        description="Manage bot settings"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(
        action="Action to take",
        value="New value to set",
        status_type="Type of status (for status action)",
        status_text="Status message (supports {server_name} placeholder)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="setname", value="setname"),
        app_commands.Choice(name="setstatus", value="setstatus"),
        app_commands.Choice(name="setcolor", value="setcolor"),
        app_commands.Choice(name="settings", value="settings")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def manage_settings(
        self,
        interaction: discord.Interaction,
        action: str,
        value: Optional[str] = None,
        status_type: Optional[str] = None,
        status_text: Optional[str] = None
    ) -> None:
        """
        Manage bot settings and configuration
        
        Args:
            interaction: The interaction that triggered the command
            action: The setting to modify
            value: New value for the setting
            status_type: Type of status activity
            status_text: Status message text
        """
        try:
            if action == "settings":
                await self._show_current_settings(interaction)
                return

            if action == "setname":
                await self._update_server_name(interaction, value)
                return

            if action == "setstatus":
                await self._update_status(interaction, status_type, status_text, value)
                return

            if action == "setcolor":
                await self._update_embed_color(interaction, value)
                return

        except Exception as e:
            logger.error(f"Error in manage_settings command: {e}")
            await interaction.response.send_message(
                "An error occurred while updating settings.",
                ephemeral=True
            )

    async def _show_current_settings(self, interaction: discord.Interaction) -> None:
        """Display current bot settings"""
        try:
            embed = discord.Embed(
                title="Bot Settings",
                description="Current bot configuration",
                color=int(BOT_SETTINGS["embed_color"], 16)
            )
            
            embed.add_field(
                name="Server Name", 
                value=f"`{BOT_SETTINGS['server_name']}`",
                inline=False
            )
            
            status_info = BOT_SETTINGS['status']
            embed.add_field(
                name="Status", 
                value=(
                    f"Type: `{status_info['type']}`\n"
                    f"Text: `{status_info['name']}`\n"
                    f"Status: `{status_info['status']}`"
                ),
                inline=False
            )
            
            embed.add_field(
                name="Embed Color",
                value=f"`{BOT_SETTINGS['embed_color']}`",
                inline=False
            )
            
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error showing settings: {e}")
            raise

    async def _update_server_name(
        self,
        interaction: discord.Interaction,
        new_name: Optional[str]
    ) -> None:
        """Update server name setting"""
        if not new_name:
            await interaction.response.send_message(
                "Please provide a new server name.",
                ephemeral=True
            )
            return
        
        try:
            BOT_SETTINGS["server_name"] = new_name
            await self._delayed_save(BOT_SETTINGS)
            
            # Update bot status if it contains server name
            status_name = BOT_SETTINGS["status"]["name"].format(
                server_name=new_name
            )
            
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=getattr(
                        discord.ActivityType,
                        BOT_SETTINGS["status"]["type"].lower()
                    ),
                    name=status_name
                )
            )
            
            await interaction.response.send_message(
                f"Server name updated to: `{new_name}`",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error updating server name: {e}")
            raise

    async def _update_status(
        self,
        interaction: discord.Interaction,
        status_type: Optional[str],
        status_text: Optional[str],
        value: Optional[str]
    ) -> None:
        """Update bot status"""
        if not status_type or not status_text:
            await interaction.response.send_message(
                "Please provide both status type and text.",
                ephemeral=True
            )
            return

        status_type = status_type.lower()
        if status_type not in self.valid_status_types:
            await interaction.response.send_message(
                f"Invalid status type. Valid types: {', '.join(self.valid_status_types)}",
                ephemeral=True
            )
            return

        BOT_SETTINGS["status"]["type"] = status_type
        BOT_SETTINGS["status"]["name"] = status_text
        if value and value.lower() in self.valid_bot_statuses:
            BOT_SETTINGS["status"]["status"] = value.lower()

        await self._delayed_save(BOT_SETTINGS)

        # Update bot's status
        status_name = status_text.format(server_name=BOT_SETTINGS["server_name"])
        await self.bot.change_presence(
            status=getattr(discord.Status, BOT_SETTINGS["status"]["status"]),
            activity=discord.Activity(
                type=getattr(discord.ActivityType, status_type),
                name=status_name
            )
        )
        await interaction.response.send_message(
            f"Bot status updated!\nType: {status_type}\nText: {status_text}",
            ephemeral=True
        )

    async def _update_embed_color(
        self,
        interaction: discord.Interaction,
        value: Optional[str]
    ) -> None:
        """Update bot embed color"""
        if not value or not value.startswith("0x"):
            await interaction.response.send_message(
                "Please provide a valid hex color (e.g., 0xbc69f0)",
                ephemeral=True
            )
            return

        try:
            # Test if it's a valid hex color
            int(value, 16)
            BOT_SETTINGS["embed_color"] = value
            await self._delayed_save(BOT_SETTINGS)
            await interaction.response.send_message(
                f"Embed color updated to: {value}",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Invalid hex color format. Please use format: 0xbc69f0",
                ephemeral=True
            )

    @manage_settings.error
    async def settings_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ) -> None:
        """Handle errors in the settings command"""
        try:
            if isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message(
                    "You need administrator permissions to manage bot settings.",
                    ephemeral=True
                )
            else:
                logger.error(f"Unexpected error in settings command: {error}")
                await interaction.response.send_message(
                    "An unexpected error occurred.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error handling settings command error: {e}")

async def setup(bot: commands.Bot) -> None:
    """Set up the Settings cog"""
    try:
        await bot.add_cog(SettingsCog(bot))
        logger.info("Settings cog loaded successfully")
    except Exception as e:
        logger.error(f"Error loading Settings cog: {e}")
        raise 