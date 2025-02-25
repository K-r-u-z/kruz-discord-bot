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

class BaseSettingsView(discord.ui.View):
    def __init__(self, cog: 'Settings', previous_view=None):
        super().__init__(timeout=120)
        self.cog = cog
        self.previous_view = previous_view

    @discord.ui.button(label="◀️ Back", style=discord.ButtonStyle.gray, row=4)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.previous_view:
            # Create settings embed
            presence_info = self.cog.settings.get("presence", {})
            embed = discord.Embed(
                title="Bot Settings",
                description="Current settings:",
                color=self.cog.embed_color
            )
            embed.add_field(
                name="Server Name",
                value=self.cog.settings.get("server_name", "Not set"),
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
                value=f"#{self.cog.settings.get('embed_color', '2F3136')[2:]}",
                inline=False
            )
            
            await interaction.response.edit_message(
                embed=embed,
                view=self.previous_view
            )

class SettingsView(BaseSettingsView):
    def __init__(self, cog: 'Settings'):
        super().__init__(cog, None)
        self.remove_item(self.back_button)

    @discord.ui.button(label="📝 Change Server Name", style=discord.ButtonStyle.primary)
    async def change_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ServerNameModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🎨 Change Color", style=discord.ButtonStyle.primary)
    async def change_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ColorModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🎮 Change Activity", style=discord.ButtonStyle.primary)
    async def change_activity(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ActivityModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔵 Change Status", style=discord.ButtonStyle.primary)
    async def change_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = StatusView(self.cog, self)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Change Status",
                description="Select a status:",
                color=self.cog.embed_color
            ),
            view=view
        )

class StatusView(BaseSettingsView):
    def __init__(self, cog: 'Settings', previous_view):
        super().__init__(cog, previous_view)
        self.add_status_buttons()

    def add_status_buttons(self):
        statuses = [
            ("🟢 Online", "online"),
            ("🟡 Idle", "idle"),
            ("🔴 Do Not Disturb", "dnd"),
            ("⚫ Invisible", "invisible")
        ]
        
        for label, status in statuses:
            button = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.secondary,
                custom_id=f"status_{status}"
            )
            button.callback = self.make_callback(status)
            self.add_item(button)

    def make_callback(self, status: str):
        async def callback(interaction: discord.Interaction):
            if not "presence" in self.cog.settings:
                self.cog.settings["presence"] = {"status": "online", "activity": ""}
            
            self.cog.settings["presence"]["status"] = status
            self.cog._save_settings()
            await self.cog._update_bot_presence()
            
            await interaction.response.send_message(
                f"Bot status updated to: **{status}**",
                ephemeral=True
            )
        return callback

class ServerNameModal(discord.ui.Modal, title="Change Server Name"):
    name = discord.ui.TextInput(
        label="Server Name",
        placeholder="Enter new server name",
        required=True
    )

    def __init__(self, cog: 'Settings'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        self.cog.settings["server_name"] = self.name.value
        self.cog._save_settings()
        await self.cog._update_bot_presence()
        
        await interaction.response.send_message(
            f"Server name updated to: **{self.name.value}**",
            ephemeral=True
        )

class ColorModal(discord.ui.Modal, title="Change Embed Color"):
    color = discord.ui.TextInput(
        label="Color (hex)",
        placeholder="Enter color in format: 0xRRGGBB",
        required=True
    )

    def __init__(self, cog: 'Settings'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        if not self.color.value.startswith("0x") or len(self.color.value) != 8:
            await interaction.response.send_message(
                "Color must be in format: `0xRRGGBB`",
                ephemeral=True
            )
            return
        
        self.cog.settings["embed_color"] = self.color.value
        self.cog.embed_color = int(self.color.value, 16)
        self.cog._save_settings()
        
        await interaction.response.send_message(
            f"Embed color updated to: `#{self.color.value[2:]}`",
            ephemeral=True
        )

class ActivityModal(discord.ui.Modal, title="Change Bot Activity"):
    activity = discord.ui.TextInput(
        label="Activity",
        placeholder="Type: playing/watching/listening/competing + text",
        required=True
    )

    def __init__(self, cog: 'Settings'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        if not "presence" in self.cog.settings:
            self.cog.settings["presence"] = {"status": "online", "activity": ""}
        
        self.cog.settings["presence"]["activity"] = self.activity.value
        self.cog._save_settings()
        await self.cog._update_bot_presence()
        
        await interaction.response.send_message(
            f"Bot activity updated to: **{self.activity.value}**",
            ephemeral=True
        )

class Settings(commands.Cog):
    """Cog for managing bot settings"""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.settings_file = 'data/bot_settings.json'
        self.settings = self._load_settings()
        self.embed_color = int(self.settings.get("embed_color", "0x2F3136"), 16)
        
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

    @app_commands.command(
        name="settings",
        description="⚙️ Configure bot settings"
    )
    @app_commands.guilds(GUILD)
    @app_commands.checks.has_permissions(administrator=True)
    async def settings_command(self, interaction: discord.Interaction):
        """Manage bot settings"""
        # Create settings embed
        presence_info = self.settings.get("presence", {})
        embed = discord.Embed(
            title="Bot Settings",
            description="Current settings:",
            color=self.embed_color
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
        
        view = SettingsView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Settings(bot)) 