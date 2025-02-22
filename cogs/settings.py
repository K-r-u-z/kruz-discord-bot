import discord
from discord import app_commands
from discord.ext import commands
import logging
from config import GUILD_ID, BOT_SETTINGS
import json
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)
GUILD = discord.Object(id=GUILD_ID)

class Settings(commands.Cog):
    """Cog for managing bot settings"""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.settings_file = 'data/bot_settings.json'
        self.settings = self._load_settings()
        
        # Schedule presence update after bot is ready
        self.bot.loop.create_task(self._initial_presence_update())

    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return BOT_SETTINGS
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            return BOT_SETTINGS

    def _save_settings(self) -> None:
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

    async def _update_bot_presence(self) -> None:
        """Update bot's presence based on current settings"""
        try:
            presence_info = self.settings.get("presence", {})
            status = presence_info.get("status", "online").lower()
            activity_text = presence_info.get("activity", "")
            
            # Format activity text with server name
            if activity_text:
                activity_text = activity_text.format(
                    server_name=self.settings.get("server_name", "Server")
                )
            
            # Get presence status
            presence_status = getattr(
                discord.Status,
                status,
                discord.Status.online
            )
            
            # Handle activity
            if activity_text:
                parts = activity_text.split(maxsplit=1)
                if len(parts) < 2:
                    activity = discord.Game(name=activity_text)
                else:
                    activity_type = parts[0].lower()
                    activity_name = parts[1]
                    
                    activity_types = {
                        "playing": discord.ActivityType.playing,
                        "watching": discord.ActivityType.watching,
                        "listening": discord.ActivityType.listening,
                        "competing": discord.ActivityType.competing
                    }
                    
                    if activity_type in activity_types:
                        activity = discord.Activity(
                            type=activity_types[activity_type],
                            name=activity_name
                        )
                    else:
                        activity = discord.Game(name=activity_text)
            else:
                activity = None
            
            await self.bot.change_presence(
                activity=activity,
                status=presence_status
            )
            logger.info(f"Updated bot presence: {activity_text} ({status})")
        except Exception as e:
            logger.error(f"Error updating bot presence: {e}")

    async def _initial_presence_update(self) -> None:
        """Update presence once bot is ready"""
        await self.bot.wait_until_ready()
        await self._update_bot_presence()

    @app_commands.command(name="settings", description="View or modify bot settings")
    @app_commands.guilds(GUILD)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        action="Choose what to do with settings",
        value="New value for the setting"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="📋 Show Settings", value="show"),
        app_commands.Choice(name="📝 Change Server Name", value="set_name"),
        app_commands.Choice(name="🎨 Change Color", value="set_color"),
        app_commands.Choice(name="🎮 Change Activity", value="set_activity"),
        app_commands.Choice(name="🔵 Change Status", value="set_presence")
    ])
    @app_commands.describe(
        action="Choose what to do with settings",
        value="New value for the setting (activity will need text after type)"
    )
    async def settings_command(
        self,
        interaction: discord.Interaction,
        action: str,
        value: Optional[str] = None
    ) -> None:
        """Manage bot settings"""
        try:
            if action == "show":
                # Format current settings
                presence_info = self.settings.get("presence", {})
                embed = discord.Embed(
                    title="Bot Settings",
                    color=int(self.settings.get("embed_color", "0x2F3136"), 16)
                )
                embed.add_field(
                    name="Server Name",
                    value=self.settings.get("server_name", "Not set"),
                    inline=False
                )
                embed.add_field(
                    name="Presence",
                    value=f"Status: {presence_info.get('status', 'online')}\n"
                          f"Activity: {presence_info.get('activity', 'Not set')}",
                    inline=False
                )
                embed.add_field(
                    name="Embed Color",
                    value=f"#{self.settings.get('embed_color', '2F3136')[2:]}",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            if action == "set_presence":
                if not value:
                    choices = ["online", "idle", "dnd", "invisible"]
                    formatted_choices = "\n".join(f"• `{choice}`" for choice in choices)
                    await interaction.response.send_message(
                        f"Please choose a presence status:\n{formatted_choices}",
                        ephemeral=True
                    )
                    return
                
                value = value.lower()
                if value not in ["online", "idle", "dnd", "invisible"]:
                    await interaction.response.send_message(
                        "Invalid status! Choose: `online`, `idle`, `dnd`, or `invisible`",
                        ephemeral=True
                    )
                    return

            elif action == "set_activity":
                if not value:
                    activity_types = ["playing", "watching", "listening", "competing"]
                    formatted_types = "\n".join(f"• `{type} <text>`" for type in activity_types)
                    examples = [
                        "`playing Minecraft`",
                        "`watching over {server_name}`",
                        "`listening to music`",
                        "`competing in tournaments`"
                    ]
                    await interaction.response.send_message(
                        f"Please provide an activity type and text:\n\n"
                        f"**Available Types:**\n{formatted_types}\n\n"
                        f"**Examples:**\n" + "\n".join(examples),
                        ephemeral=True
                    )
                    return

            if action == "set_name":
                self.settings["server_name"] = value
                response = f"Server name updated to: **{value}**"
                await self._update_bot_presence()  # Update presence after name change

            elif action == "set_color":
                # Validate color format
                if not value.startswith("0x") or len(value) != 8:
                    await interaction.response.send_message(
                        "Color must be in format: `0xRRGGBB`",
                        ephemeral=True
                    )
                    return
                
                self.settings["embed_color"] = value
                response = f"Embed color updated to: `#{value[2:]}`"

            elif action == "set_activity":
                if not value:
                    await interaction.response.send_message(
                        "Please provide an activity!\n"
                        "Format: `<type> <text>`\n"
                        "Types: `playing`, `watching`, `listening`, `competing`\n"
                        "Example: `watching over {server_name}`",
                        ephemeral=True
                    )
                    return

                # Update activity text
                if not "presence" in self.settings:
                    self.settings["presence"] = {"status": "online", "activity": ""}
                
                self.settings["presence"]["activity"] = value
                await self._update_bot_presence()
                response = f"Bot activity updated to: **{value}**"

            elif action == "set_presence":
                valid_statuses = ["online", "idle", "dnd", "invisible"]
                if not value or value.lower() not in valid_statuses:
                    await interaction.response.send_message(
                        "Please provide a valid status!\n"
                        "Available statuses: `online`, `idle`, `dnd`, `invisible`",
                        ephemeral=True
                    )
                    return

                if not "presence" in self.settings:
                    self.settings["presence"] = {"status": "online", "activity": ""}
                
                status = value.lower()
                self.settings["presence"]["status"] = status
                await self._update_bot_presence()
                response = f"Bot presence updated to: **{status}**"

            else:
                response = "Invalid action!"

            # Save and respond
            self._save_settings()
            await interaction.response.send_message(response, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in settings command: {e}")
            await interaction.response.send_message(
                "An error occurred while updating settings",
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Settings(bot))
    logger.info("Settings cog loaded successfully") 