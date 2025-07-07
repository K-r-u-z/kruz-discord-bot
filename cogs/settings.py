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
            embed.add_field(
                name="Ban Log Channel",
                value=self._get_ban_log_display(),
                inline=False
            )
            
            await interaction.response.edit_message(
                embed=embed,
                view=self.previous_view
            )

    def _get_ban_log_display(self) -> str:
        """Get the display text for ban log channel"""
        moderation_settings = self.cog.settings.get("moderation", {})
        ban_log_channel_id = moderation_settings.get("ban_log_channel_id")
        
        if ban_log_channel_id:
            channel = self.cog.bot.get_channel(ban_log_channel_id)
            if channel:
                return f"<#{ban_log_channel_id}>"
            else:
                return f"Channel not found (ID: {ban_log_channel_id})"
        else:
            return "Not set"

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

    @discord.ui.button(label="📋 Ban Log Channel", style=discord.ButtonStyle.primary)
    async def ban_log_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = BanLogChannelView(self.cog, self)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Ban Log Channel Settings",
                description="Configure the channel for ban/unban logs:",
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

class BanLogChannelView(BaseSettingsView):
    def __init__(self, cog: 'Settings', previous_view):
        super().__init__(cog, previous_view)
        self.add_ban_log_dropdown()

    def add_ban_log_dropdown(self):
        # Get current ban log channel
        moderation_settings = self.cog.settings.get("moderation", {})
        current_channel_id = moderation_settings.get("ban_log_channel_id")
        
        # Get guild and create dropdown for all text channels
        guild = self.cog.bot.get_guild(GUILD_ID)
        if guild and guild.me:
            # Get all text channels where bot has permission to send messages
            text_channels = [c for c in guild.text_channels if c.permissions_for(guild.me).send_messages]
            
            # Create options for dropdown
            options = []
            
            # Add "Disable Ban Log" option
            options.append(discord.SelectOption(
                label="❌ Disable Ban Log",
                description="Turn off ban logging",
                value="disable",
                emoji="❌"
            ))
            
            # If current channel is set, add it first (even if it's not in the main list)
            if current_channel_id:
                current_channel = guild.get_channel(current_channel_id)
                if current_channel and isinstance(current_channel, discord.TextChannel):
                    options.append(discord.SelectOption(
                        label=f"#{current_channel.name} (Current)",
                        description=f"Currently selected - Channel ID: {current_channel.id}",
                        value=str(current_channel.id),
                        emoji="✅"
                    ))
            
            # Calculate how many more channels we can add
            max_additional_channels = 25 - len(options)  # Discord limit minus what we already have
            
            if max_additional_channels > 0:
                # Prioritize channels that are likely to be used for logs
                log_related_keywords = ['log', 'mod', 'admin', 'staff', 'ban', 'kick', 'warn', 'audit']
                
                # Sort channels by relevance (log-related first, then alphabetically)
                def channel_sort_key(channel):
                    if channel.id == current_channel_id:
                        return -1  # Current channel should be first
                    name_lower = channel.name.lower()
                    # Check if channel name contains log-related keywords
                    for keyword in log_related_keywords:
                        if keyword in name_lower:
                            return 0  # Log-related channels next
                    return 1  # Other channels last
                
                sorted_channels = sorted(text_channels, key=channel_sort_key)
                
                # Add channels to options (respecting the limit)
                added_channels = set()
                
                for channel in sorted_channels:
                    if len(options) >= 25:  # Hard Discord limit
                        break
                    if channel.id != current_channel_id:  # Don't add current channel twice
                        added_channels.add(channel.id)
                        options.append(discord.SelectOption(
                            label=f"#{channel.name}",
                            description=f"Channel ID: {channel.id}",
                            value=str(channel.id),
                            emoji="📝"
                        ))
                
                # If we have more channels than can fit, add a note (but only if we have room)
                if len(text_channels) > len(added_channels) and len(options) < 25:
                    options.append(discord.SelectOption(
                        label="📋 More Channels Available",
                        description=f"Showing {len(added_channels)} of {len(text_channels)} channels. Use /setbanlog for full list.",
                        value="more_channels",
                        emoji="📋"
                    ))
            
            # Create the dropdown
            dropdown = discord.ui.Select(
                placeholder=f"Select a channel for ban logs... ({len(options)-1} channels available)",
                options=options,
                custom_id="banlog_dropdown"
            )
            dropdown.callback = self.dropdown_callback
            self.add_item(dropdown)

    async def dropdown_callback(self, interaction: discord.Interaction):
        # Get the selected value from the dropdown
        if not interaction.data or "values" not in interaction.data:
            await interaction.response.send_message("❌ Error: No selection made", ephemeral=True)
            return
            
        selected_value = interaction.data["values"][0]
        
        # Ensure moderation section exists
        if "moderation" not in self.cog.settings:
            self.cog.settings["moderation"] = {}
        
        if selected_value == "disable":
            self.cog.settings["moderation"]["ban_log_channel_id"] = None
            self.cog._save_settings()
            
            await interaction.response.send_message(
                "✅ Ban log channel disabled",
                ephemeral=True
            )
        elif selected_value == "more_channels":
            # Show information about using the direct command
            await interaction.response.send_message(
                "📋 **Too many channels to display!**\n\n"
                "You can use the `/setbanlog` command directly to set the ban log channel:\n"
                "• `/setbanlog #channel-name` - Set to a specific channel\n"
                "• `/setbanlog none` - Disable ban logging\n\n"
                "Or try the dropdown again - it prioritizes log-related channels.",
                ephemeral=True
            )
        else:
            try:
                channel_id = int(selected_value)
                self.cog.settings["moderation"]["ban_log_channel_id"] = channel_id
                self.cog._save_settings()
                
                channel = self.cog.bot.get_channel(channel_id)
                if isinstance(channel, discord.TextChannel):
                    await interaction.response.send_message(
                        f"✅ Ban log channel set to: {channel.mention}",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"✅ Ban log channel set to: <#{channel_id}>",
                        ephemeral=True
                    )
            except ValueError:
                await interaction.response.send_message("❌ Error: Invalid channel ID", ephemeral=True)

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

    def _get_ban_log_display(self) -> str:
        """Get the display text for ban log channel"""
        moderation_settings = self.settings.get("moderation", {})
        ban_log_channel_id = moderation_settings.get("ban_log_channel_id")
        
        if ban_log_channel_id:
            channel = self.bot.get_channel(ban_log_channel_id)
            if channel:
                return f"<#{ban_log_channel_id}>"
            else:
                return f"Channel not found (ID: {ban_log_channel_id})"
        else:
            return "Not set"

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
        embed.add_field(
            name="Ban Log Channel",
            value=self._get_ban_log_display(),
            inline=False
        )
        
        view = SettingsView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Settings(bot)) 