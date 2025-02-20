import discord
from discord import app_commands
from discord.ext import commands
import json
from config import GUILD_ID, BOT_SETTINGS
import time
import asyncio

GUILD = discord.Object(id=GUILD_ID)
VALID_STATUS_TYPES = ["playing", "streaming", "listening", "watching", "competing"]
VALID_BOT_STATUSES = ["online", "idle", "dnd", "invisible"]

class SettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings_file = 'bot_settings.json'
        self._settings_cache = None
        self._last_save = 0
        self._save_delay = 5  # seconds

    async def _delayed_save(self, settings):
        """Batch save operations"""
        current_time = time.time()
        if current_time - self._last_save < self._save_delay:
            return
        
        self._last_save = current_time
        await asyncio.to_thread(self._save_to_disk, settings)

    def _save_to_disk(self, settings):
        """Actual file I/O operation"""
        with open(self.settings_file, 'w') as f:
            json.dump(settings, f, indent=4)

    def save_settings(self, settings):
        """Save settings to file and return True if successful"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving bot settings: {e}")
            return False

    @app_commands.command(
        name="kruzbot",
        description="Manage bot settings"
    )
    @app_commands.guilds(GUILD)
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
        value: str = None,
        status_type: str = None,
        status_text: str = None
    ):
        try:
            if action == "settings":
                # Show current settings
                embed = discord.Embed(
                    title="Bot Settings",
                    description="Current bot configuration",
                    color=int(BOT_SETTINGS["embed_color"], 16)
                )
                embed.add_field(
                    name="Server Name", 
                    value=BOT_SETTINGS["server_name"],
                    inline=False
                )
                embed.add_field(
                    name="Status", 
                    value=f"Type: {BOT_SETTINGS['status']['type']}\n"
                          f"Text: {BOT_SETTINGS['status']['name']}\n"
                          f"Status: {BOT_SETTINGS['status']['status']}",
                    inline=False
                )
                embed.add_field(
                    name="Embed Color",
                    value=BOT_SETTINGS["embed_color"],
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            if action == "setname":
                if not value:
                    await interaction.response.send_message(
                        "Please provide a new server name.",
                        ephemeral=True
                    )
                    return
                
                BOT_SETTINGS["server_name"] = value
                if self.save_settings(BOT_SETTINGS):
                    await interaction.response.send_message(
                        f"Server name updated to: {value}",
                        ephemeral=True
                    )
                    # Update bot status if it contains server name
                    status_name = BOT_SETTINGS["status"]["name"].format(server_name=value)
                    await self.bot.change_presence(
                        activity=discord.Activity(
                            type=getattr(discord.ActivityType, BOT_SETTINGS["status"]["type"].lower()),
                            name=status_name
                        )
                    )
                return

            if action == "setstatus":
                if not status_type or not status_text:
                    await interaction.response.send_message(
                        "Please provide both status type and text.",
                        ephemeral=True
                    )
                    return

                status_type = status_type.lower()
                if status_type not in VALID_STATUS_TYPES:
                    await interaction.response.send_message(
                        f"Invalid status type. Valid types: {', '.join(VALID_STATUS_TYPES)}",
                        ephemeral=True
                    )
                    return

                BOT_SETTINGS["status"]["type"] = status_type
                BOT_SETTINGS["status"]["name"] = status_text
                if value and value.lower() in VALID_BOT_STATUSES:
                    BOT_SETTINGS["status"]["status"] = value.lower()

                if self.save_settings(BOT_SETTINGS):
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
                return

            if action == "setcolor":
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
                    if self.save_settings(BOT_SETTINGS):
                        await interaction.response.send_message(
                            f"Embed color updated to: {value}",
                            ephemeral=True
                        )
                except ValueError:
                    await interaction.response.send_message(
                        "Invalid hex color format. Please use format: 0xbc69f0",
                        ephemeral=True
                    )

        except Exception as e:
            await interaction.response.send_message(
                "An error occurred while updating settings.",
                ephemeral=True
            )
            print(f"Error in manage_settings command: {e}")

    @manage_settings.error
    async def settings_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need administrator permissions to manage bot settings.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(SettingsCog(bot)) 