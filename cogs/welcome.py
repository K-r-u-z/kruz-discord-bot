import discord
from discord import app_commands, ui
from discord.ext import commands
import logging
from config import GUILD_ID, BOT_SETTINGS
from typing import Optional, Dict, Any
import json
import os

logger = logging.getLogger(__name__)
GUILD = discord.Object(id=GUILD_ID)

class WelcomeMessageModal(ui.Modal):
    """Modal for editing welcome messages"""
    
    def __init__(self, cog: 'Welcome', welcome_config: dict) -> None:
        super().__init__(title="Edit Welcome Message")
        self.cog = cog

        # Get current values from config
        message_config = welcome_config.get("message", {})
        
        self.title_input = ui.TextInput(
            label="Title",
            placeholder="Welcome to {server_name}!",
            default=message_config.get("title", ""),
            style=discord.TextStyle.short,
            max_length=256,
            required=True
        )

        self.description_input = ui.TextInput(
            label="Description",
            placeholder="Write your welcome message here",
            default=message_config.get("description", ""),
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=True
        )

        self.footer_input = ui.TextInput(
            label="Footer (Optional)",
            placeholder="User ID: {user_id}",
            default=message_config.get("footer", ""),
            style=discord.TextStyle.short,
            max_length=2048,
            required=False
        )
        
        for item in [self.title_input, self.description_input, self.footer_input]:
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

class Welcome(commands.Cog):
    """Cog for handling welcome messages"""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.settings_file = 'data/welcome_settings.json'
        self.embed_color = int(BOT_SETTINGS["embed_color"], 16)
        self.welcome_config = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """Load welcome settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            default_settings = {
                "channel_id": None,
                "enabled": True,
                "message": {
                    "title": "Welcome to {server_name}! 👋",
                    "description": "Edit your welcome message with `/welcome edit`. View the formatting guide with `/welcome formatting.`",
                    "footer": "We currently have {member_count} Members! (Editable)"
                }
            }
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, indent=4, ensure_ascii=False)
            
            return default_settings
            
        except Exception as e:
            logger.error(f"Error loading welcome settings: {e}")
            return {}

    def _save_settings(self) -> None:
        """Save welcome settings to file"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.welcome_config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving welcome settings: {e}")

    def _format_welcome_message(self, member: discord.Member) -> Dict[str, str]:
        """Format welcome message with placeholders"""
        config = self.welcome_config.get("message", {})
        
        # Base format dictionary
        format_dict = {
            "server_name": member.guild.name,
            "user_name": str(member),
            "display_name": member.display_name,
            "user_id": member.id,
            "member_count": member.guild.member_count
        }

        # Special handling for mentions in title
        title_dict = format_dict.copy()
        title_dict["user_mention"] = member.display_name

        # Normal format dict for description and footer
        format_dict["user_mention"] = member.mention

        return {
            "title": config.get("title", "Welcome!").format(**title_dict),
            "description": config.get("description", "Welcome to the server!").format(**format_dict),
            "footer": config.get("footer", "").format(**format_dict)  # No formatting handling needed
        }

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Handle new member joins"""
        try:
            # Handle autorole
            autorole = self.welcome_config.get("autorole", {})
            if autorole.get("enabled", False):
                role_id = autorole.get("role_id")
                if role_id:
                    role = member.guild.get_role(role_id)
                    if role:
                        await member.add_roles(role)
                        logger.info(f"Added role {role.name} to {member}")

            # Handle welcome message
            if not self.welcome_config.get("enabled", True):
                return

            channel_id = self.welcome_config.get("channel_id")
            if not channel_id:
                logger.warning("Welcome channel not set. Use /welcome channel to set it up.")
                return

            channel = self.bot.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                return

            message = self._format_welcome_message(member)
            embed = discord.Embed(
                title=message["title"],
                description=message["description"],
                color=self.embed_color
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=message["footer"])  # Allow all formatting

            await channel.send(embed=embed)
            logger.info(f"Sent welcome message for {member}")

        except Exception as e:
            logger.error(f"Error handling member join: {e}")

    @app_commands.command(
        name="welcome",
        description="⚙️ Configure welcome message settings"
    )
    @app_commands.guilds(GUILD)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        setting="Choose what to configure",
        value="New value for the setting"
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="👋 Test Welcome", value="test"),
        app_commands.Choice(name="📝 Edit Message", value="edit"),
        app_commands.Choice(name="⚙️ Setup Channel", value="setup"),
        app_commands.Choice(name="📋 Show Format", value="formatting"),
        app_commands.Choice(name="🔄 Toggle", value="toggle")
    ])
    async def welcome_settings(
        self,
        interaction: discord.Interaction,
        setting: str,
        value: Optional[str] = None
    ) -> None:
        """Configure welcome message settings"""
        try:
            if setting == "setup":
                # Use the current channel
                self.welcome_config["channel_id"] = interaction.channel_id
                self.welcome_config["enabled"] = True  # Enable welcome messages by default
                self._save_settings()
                
                await interaction.response.send_message(
                    f"✅ Welcome messages will now be sent in this channel!\nUse `/welcome test` to preview the message.",
                    ephemeral=True
                )
                return

            if setting == "test":
                # Check if channel is set
                if not self.welcome_config.get("channel_id"):
                    await interaction.response.send_message(
                        "Welcome channel not set! Please use `/welcome channel #channel` to set up the welcome channel first.",
                        ephemeral=True
                    )
                    return

                await self.on_member_join(interaction.user)
                await interaction.response.send_message("Sent test welcome message!", ephemeral=True)
                return

            if setting == "show":
                # Get current channel
                channel_id = self.welcome_config.get("channel_id")
                channel = interaction.guild.get_channel(channel_id) if channel_id else None
                channel_info = channel.mention if channel else "No channel set"

                # Get current status
                is_enabled = self.welcome_config.get("enabled", True)
                status = "✅ Welcome messages are enabled" if is_enabled else "❌ Welcome messages are disabled"

                embed = discord.Embed(
                    title="Welcome Message Settings",
                    description=f"{status}\nChannel: {channel_info}",
                    color=self.embed_color
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            if setting == "formatting":
                format_info = (
                    "**Available placeholders:**\n"
                    "`{user_mention}` - Mentions the new member\n"
                    "`{user_name}` - Member's username\n"
                    "`{display_name}` - Member's display name\n"
                    "`{user_id}` - Member's ID\n"
                    "`{server_name}` - Server name\n"
                    "`{member_count}` - Current member count\n\n"
                    "**Text Formatting (Title & Description only):**\n"
                    "`**text**` - **Bold**\n"
                    "`__text__` - __Underline__\n"
                    "`*text*` - *Italic*\n"
                    "`***text***` - ***Bold Italic***\n"
                    "`__*text*__` - __*Underline Italic*__\n"
                    "`**__text__**` - **__Bold Underline__**\n"
                    "`***__text__***` - ***__Bold Italic Underline__***\n"
                    "\\`text\\` - `Inline Code`\n\n"
                    "Note: Footer text does not support formatting\n\n"
                    f"**Current Title:**\n{self.welcome_config['message']['title']}\n\n"
                    f"**Current Description:**\n{self.welcome_config['message']['description']}\n\n"
                    f"**Current Footer:**\n{self.welcome_config['message']['footer']}"
                )
                
                embed = discord.Embed(title="Welcome Message Format", description=format_info, color=self.embed_color)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            if setting == "edit":
                modal = WelcomeMessageModal(self, self.welcome_config)
                await interaction.response.send_modal(modal)
                await modal.wait()

                # Get footer value or empty string if not provided
                footer = modal.footer_input.value.strip() if modal.footer_input.value else ""

                self.welcome_config["message"] = {
                    "title": modal.title_input.value,
                    "description": modal.description_input.value,
                    "footer": footer
                }
                
                self._save_settings()
                await interaction.followup.send(
                    "Welcome message updated! Use `/welcome test` to preview.",
                    ephemeral=True
                )
                return

            # Replace enable/disable with toggle
            if setting == "toggle":
                current_state = self.welcome_config.get("enabled", True)
                self.welcome_config["enabled"] = not current_state
                
                new_state = "enabled" if not current_state else "disabled"
                response = f"Welcome messages {new_state}!"
                
                self._save_settings()
                await interaction.response.send_message(response, ephemeral=True)
                return

            # Remove the old enable/disable blocks
            if setting == "enable":
                if self.welcome_config.get("enabled", True):
                    await interaction.response.send_message("Welcome messages are already enabled!", ephemeral=True)
                    return
                self.welcome_config["enabled"] = True
                response = "Welcome messages enabled!"

            elif setting == "disable":
                if not self.welcome_config.get("enabled", True):
                    await interaction.response.send_message("Welcome messages are already disabled!", ephemeral=True)
                    return
                self.welcome_config["enabled"] = False
                response = "Welcome messages disabled!"

            else:
                response = "Invalid setting or missing required value!"

            self._save_settings()
            await interaction.response.send_message(response, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in welcome settings: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("An error occurred while updating settings", ephemeral=True)
            else:
                await interaction.followup.send("An error occurred while updating settings", ephemeral=True)

    @app_commands.command(
        name="autorole",
        description="🎭 Configure automatic role assignment"
    )
    @app_commands.guilds(GUILD)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        action="Choose what to do",
        role="Role to assign to new members"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="👀 Show Settings", value="show"),
        app_commands.Choice(name="✨ Set Role", value="set"),
        app_commands.Choice(name="🔄 Toggle", value="toggle")
    ])
    async def autorole_settings(
        self,
        interaction: discord.Interaction,
        action: str,
        role: Optional[discord.Role] = None
    ) -> None:
        """Configure autorole settings"""
        try:
            if "autorole" not in self.welcome_config:
                self.welcome_config["autorole"] = {
                    "enabled": False,
                    "role_id": None
                }

            if action == "show":
                # Get current role
                role_id = self.welcome_config["autorole"].get("role_id")
                role = interaction.guild.get_role(role_id) if role_id else None
                role_info = role.mention if role else "No role set"

                # Get current status
                is_enabled = self.welcome_config["autorole"].get("enabled", False)
                status = "✅ Autorole is enabled" if is_enabled else "❌ Autorole is disabled"

                embed = discord.Embed(
                    title="Autorole Settings",
                    description=f"{status}\nRole: {role_info}",
                    color=self.embed_color
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            if action == "toggle":
                current_state = self.welcome_config["autorole"].get("enabled", False)
                if not self.welcome_config["autorole"]["role_id"] and not current_state:
                    await interaction.response.send_message(
                        "Please set a role first using `/autorole set @role`",
                        ephemeral=True
                    )
                    return
                    
                self.welcome_config["autorole"]["enabled"] = not current_state
                new_state = "enabled" if not current_state else "disabled"
                self._save_settings()
                await interaction.response.send_message(f"Autorole {new_state}!", ephemeral=True)
                return

            if action == "set":
                if not role:
                    await interaction.response.send_message(
                        "Please specify a role!",
                        ephemeral=True
                    )
                    return
                
                # Update role and enable autorole
                self.welcome_config["autorole"].update({
                    "role_id": role.id,
                    "enabled": True
                })
                response = f"Autorole set and enabled for {role.mention}"

            else:
                response = "Invalid action!"

            self._save_settings()
            await interaction.response.send_message(response, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in autorole settings: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while updating autorole settings",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "An error occurred while updating autorole settings",
                    ephemeral=True
                )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
    logger.info("Welcome cog loaded successfully")