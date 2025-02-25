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
        try:
            # Get footer value or empty string if not provided
            footer = self.footer_input.value.strip() if self.footer_input.value else ""

            # Update welcome config with new message
            self.cog.welcome_config["message"] = {
                "title": self.title_input.value,
                "description": self.description_input.value,
                "footer": footer
            }
            
            # Save the changes
            self.cog._save_settings()

            # Show updated settings
            embed = create_welcome_embed(self.cog)
            view = WelcomeSettingsView(self.cog)
            
            await interaction.response.edit_message(
                embed=embed,
                view=view
            )
            
            await interaction.followup.send(
                "✅ Welcome message updated! Use the test button to preview.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error saving welcome message: {e}")
            await interaction.response.send_message(
                "An error occurred while saving the welcome message.",
                ephemeral=True
            )

class BaseSettingsView(discord.ui.View):
    def __init__(self, cog: 'Welcome', previous_view=None):
        super().__init__(timeout=120)
        self.cog = cog
        self.previous_view = previous_view

    @discord.ui.button(label="◀️ Back", style=discord.ButtonStyle.gray, row=4)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.previous_view:
            await interaction.response.edit_message(
                embed=create_welcome_embed(self.cog),
                view=self.previous_view
            )

class WelcomeSettingsView(BaseSettingsView):
    def __init__(self, cog: 'Welcome'):
        super().__init__(cog, None)
        self.remove_item(self.back_button)

    @discord.ui.button(label="📌 Setup Channel", style=discord.ButtonStyle.primary)
    async def setup_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            channel = interaction.channel
            current_channel_id = self.cog.welcome_config.get("channel_id")
            
            # Check if channel is already set
            if current_channel_id == channel.id:
                await interaction.response.send_message(
                    f"❌ Welcome channel is already set to {channel.mention}!",
                    ephemeral=True
                )
                return
            
            self.cog.welcome_config["channel_id"] = channel.id
            self.cog.welcome_config["enabled"] = True
            self.cog._save_settings()
            
            await interaction.response.send_message(
                f"✅ Welcome messages will now be sent in {channel.mention}!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error setting welcome channel: {e}")
            await interaction.response.send_message(
                "Failed to setup welcome channel!",
                ephemeral=True
            )

    @discord.ui.button(label="📋 Show Format", style=discord.ButtonStyle.secondary)
    async def show_format(self, interaction: discord.Interaction, button: discord.ui.Button):
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
            "Note: Footer text does not support formatting"
        )
        
        embed = discord.Embed(
            title="Welcome Message Format",
            description=format_info,
            color=self.cog.embed_color
        )
        
        # Add current message preview
        config = self.cog.welcome_config.get("message", {})
        embed.add_field(
            name="Current Message",
            value=(
                f"**Title:**\n{config.get('title', 'Not set')}\n\n"
                f"**Description:**\n{config.get('description', 'Not set')}\n\n"
                f"**Footer:**\n{config.get('footer', 'Not set')}"
            ),
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📝 Edit Message", style=discord.ButtonStyle.primary)
    async def edit_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WelcomeMessageModal(self.cog, self.cog.welcome_config)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="👋 Send Test", style=discord.ButtonStyle.success)
    async def send_test(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.welcome_config.get("channel_id"):
            await interaction.response.send_message(
                "Please set up a welcome channel first!",
                ephemeral=True
            )
            return

        await self.cog.on_member_join(interaction.user)
        await interaction.response.send_message(
            "Sent test welcome message!",
            ephemeral=True
        )

    @discord.ui.button(label="🔄 Toggle", style=discord.ButtonStyle.secondary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_state = self.cog.welcome_config.get("enabled", True)
        self.cog.welcome_config["enabled"] = not current_state
        self.cog._save_settings()
        
        await interaction.response.send_message(
            f"Welcome messages {'disabled' if current_state else 'enabled'}!",
            ephemeral=True
        )

def create_welcome_embed(cog: 'Welcome') -> discord.Embed:
    """Create the welcome settings overview embed"""
    channel_id = cog.welcome_config.get("channel_id")
    channel = cog.bot.get_channel(channel_id) if channel_id else None
    is_enabled = cog.welcome_config.get("enabled", True)
    
    embed = discord.Embed(
        title="Welcome Settings",
        description="Current welcome message settings:",
        color=cog.embed_color
    )
    
    embed.add_field(
        name="Status",
        value="✅ Enabled" if is_enabled else "❌ Disabled",
        inline=False
    )
    
    embed.add_field(
        name="Channel",
        value=channel.mention if channel else "Not set",
        inline=False
    )
    
    message = cog.welcome_config.get("message", {})
    if message:
        embed.add_field(
            name="Current Message",
            value=(
                f"**Title:**\n{message.get('title', 'Not set')}\n\n"
                f"**Description:**\n{message.get('description', 'Not set')}\n\n"
                f"**Footer:**\n{message.get('footer', 'Not set')}"
            ),
            inline=False
        )
    
    return embed

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
                    "description": "Edit your welcome message with by clicking the options in /welcome.`",
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
    async def welcome_settings(self, interaction: discord.Interaction):
        """Configure welcome message settings"""
        embed = create_welcome_embed(self)
        view = WelcomeSettingsView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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