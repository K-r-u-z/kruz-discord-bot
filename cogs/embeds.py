import discord
from discord import app_commands
from discord.ext import commands
from config import GUILD_ID, BOT_SETTINGS
import time
from typing import Optional, Dict, Any, List, Union
import json
import os
import logging

logger = logging.getLogger(__name__)

# Convert hex color string to int
EMBED_COLOR = int(BOT_SETTINGS["embed_color"], 16)

GUILD = discord.Object(id=GUILD_ID)

class ServerCommands(commands.Cog):
    """Cog for managing server commands and embeds"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._command_cooldowns: Dict[int, float] = {}
        self._cooldown_duration = 5  # seconds
        
        # File paths
        self.ids_file = 'data/embedded_messages_ids.json'
        self.contents_file = 'data/embed_contents.json'
        
        # Load data
        self.message_ids = self.load_message_ids()
        self.embed_contents = self.load_embed_contents()
        self.migrate_embed_contents()

    def load_message_ids(self) -> Dict[str, Any]:
        """Load message IDs from file with error handling"""
        try:
            # Create data directory if it doesn't exist
            os.makedirs('data', exist_ok=True)
            
            if os.path.exists(self.ids_file):
                with open(self.ids_file, 'r') as f:
                    return json.load(f)
            
            # Create empty file if not exists
            empty_ids: Dict[str, Any] = {}
            self._save_json(self.ids_file, empty_ids)
            return empty_ids
            
        except Exception as e:
            logger.error(f"Error loading message IDs: {e}")
            return {}

    def load_embed_contents(self) -> Dict[str, Any]:
        """Load embed contents from file with error handling"""
        try:
            if os.path.exists(self.contents_file):
                with open(self.contents_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            # Create empty file if not exists
            empty_contents: Dict[str, Any] = {}
            self._save_json(self.contents_file, empty_contents, encoding='utf-8')
            return empty_contents
            
        except Exception as e:
            logger.error(f"Error loading embed contents: {e}")
            return {}

    def _save_json(
        self,
        filename: str,
        data: Dict[str, Any],
        encoding: Optional[str] = None
    ) -> None:
        """Save data to JSON file with error handling"""
        try:
            kwargs = {}
            if encoding:
                kwargs['encoding'] = encoding
            
            with open(filename, 'w', **kwargs) as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Error saving to {filename}: {e}")
            raise

    def save_message_ids(self) -> None:
        """Save message IDs to file"""
        try:
            self._save_json(self.ids_file, self.message_ids)
        except Exception as e:
            logger.error(f"Error saving message IDs: {e}")

    def save_embed_contents(self) -> None:
        """Save embed contents to file"""
        try:
            self._save_json(self.contents_file, self.embed_contents, encoding='utf-8')
        except Exception as e:
            logger.error(f"Error saving embed contents: {e}")

    async def store_message_id(
        self,
        message_type: str,
        message_id: str,
        embed_name: Optional[str] = None
    ) -> None:
        """Store a message ID with validation
        
        Args:
            message_type: Category of the message
            message_id: Discord message ID to store
            embed_name: Optional name for the embed
        """
        try:
            if not message_type or not message_id:
                raise ValueError("message_type and message_id are required")
            
            if message_type == "rules":
                self.message_ids["rules"] = message_id
            else:
                if message_type not in self.message_ids:
                    self.message_ids[message_type] = {}
                if embed_name:
                    self.message_ids[message_type][embed_name] = message_id
                else:
                    self.message_ids[message_type] = message_id
            
            self.save_message_ids()
            
        except Exception as e:
            logger.error(f"Error storing message ID: {e}")
            raise

    async def _check_cooldown(self, user_id: int) -> bool:
        """Check if user is on cooldown
        
        Args:
            user_id: Discord user ID to check
            
        Returns:
            bool: True if user can use command, False if on cooldown
        """
        current_time = time.time()
        if user_id in self._command_cooldowns:
            if current_time - self._command_cooldowns[user_id] < self._cooldown_duration:
                return False
        self._command_cooldowns[user_id] = current_time
        return True

    async def get_current_content(
        self,
        embed_category: str,
        embed_name: str
    ) -> Dict[str, Optional[str]]:
        """Get the current content for a specific embed
        
        Args:
            embed_category: Category of the embed
            embed_name: Name of the embed
            
        Returns:
            Dict containing content and optional footer
        """
        try:
            if embed_category in self.embed_contents:
                if embed_name in self.embed_contents[embed_category]:
                    content = self.embed_contents[embed_category][embed_name]
                    if isinstance(content, dict):
                        return {
                            "content": content.get("content", ""),
                            "footer": content.get("footer", "")[:100] if content.get("footer") else None
                        }
                    # Handle old string format
                    return {
                        "content": content,
                        "footer": None
                    }
            return {"content": "", "footer": None}
            
        except Exception as e:
            logger.error(f"Error getting embed content: {e}")
            return {"content": "", "footer": None}

    def migrate_embed_contents(self) -> None:
        """Migrate old string content format to new dict format"""
        try:
            modified = False
            for category in self.embed_contents:
                for name in self.embed_contents[category].copy():
                    content = self.embed_contents[category][name]
                    if isinstance(content, str):
                        self.embed_contents[category][name] = {
                            "content": content,
                            "footer": None
                        }
                        modified = True
            
            if modified:
                self.save_embed_contents()
                logger.info("Successfully migrated embed contents to new format")
            
        except Exception as e:
            logger.error(f"Error migrating embed contents: {e}")

    async def _create_rules_embeds(self) -> List[discord.Embed]:
        """Create rules embeds
        
        Returns:
            List of discord.Embed objects for rules
        """
        rules = self.embed_contents.get("rules", {})
        embeds = []
        
        # Create welcome embed first
        if "welcome" in rules:
            embed = await self._create_welcome_embed(rules["welcome"])
            if embed:
                embeds.append(embed)
        
        # Add rule sections in order
        rule_names = sorted([name for name in rules.keys() if name != "welcome"])
        for i, name in enumerate(rule_names):
            is_last = (i == len(rule_names) - 1)
            embed = await self._create_rule_section_embed(
                rules[name],
                is_last_section=is_last
            )
            if embed:
                embeds.append(embed)
                    
        return embeds

    async def _create_welcome_embed(
        self,
        content: Union[Dict[str, Any], str]
    ) -> Optional[discord.Embed]:
        """Create welcome section embed"""
        try:
            description = (
                content["content"] if isinstance(content, dict)
                else content
            )
            footer = (
                content.get("footer") if isinstance(content, dict)
                else None
            )
            
            embed = discord.Embed(
                title=f"{BOT_SETTINGS['server_name']} Rules",
                description=description,
                              color=EMBED_COLOR
        )
            
            if footer:
                embed.set_footer(text=footer.replace("\\n", "\n"))
                
            return embed
            
        except Exception as e:
            logger.error(f"Error creating welcome embed: {e}")
            return None

    async def _create_rule_section_embed(
        self,
        content: Union[Dict[str, Any], str],
        is_last_section: bool = False
    ) -> Optional[discord.Embed]:
        """Create numbered rule section embed"""
        try:
            description = (
                content["content"] if isinstance(content, dict)
                else content
            )
            footer = (
                content.get("footer") if isinstance(content, dict)
                else None
            )
            
            embed = discord.Embed(
                description=description,
                color=EMBED_COLOR
            )
            
            if footer:
                embed.set_footer(text=footer.replace("\\n", "\n"))
            elif is_last_section:
                embed.set_footer(
                    text=f"Thank you for following our server rules,\n{BOT_SETTINGS['server_name']}"
                )
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating rule section embed: {e}")
            return None

    @app_commands.command(
        name="rules",
        description="Display server rules"
    )
    @app_commands.guilds(GUILD)
    async def get_rules(self, interaction: discord.Interaction) -> None:
        """Display server rules command"""
        try:
            if not await self._check_cooldown(interaction.user.id):
                await interaction.response.send_message(
                    "Please wait a few seconds before using this command again.",
                    ephemeral=True
                )
                return

            # Try to delete old message
            await self._delete_old_message("rules", interaction)

            # Create rule embeds
            embeds = await self._create_rules_embeds()
            if not embeds:
                await interaction.response.send_message(
                    "No rules content found! Please create rules first.",
                    ephemeral=True
                )
                return
            
            # Send rules
            await interaction.response.defer(ephemeral=True)
            message = await interaction.channel.send(embeds=embeds)
            
            # Store message ID
            await self.store_message_id("rules", str(message.id))
            await interaction.delete_original_response()
            
        except Exception as e:
            logger.error(f"Error in rules command: {e}")
            await interaction.response.send_message(
                "An error occurred while displaying rules.",
                ephemeral=True
            )

    async def _delete_old_message(
        self,
        message_type: str,
        interaction: discord.Interaction
    ) -> None:
        """Delete old message of given type if it exists"""
        try:
            message_id = self.message_ids.get(message_type)
            if message_id:
                channel = interaction.channel
                try:
                    old_message = await channel.fetch_message(int(message_id))
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass  # Message already deleted or no permission
                    
        except Exception as e:
            logger.error(f"Error deleting old message: {e}")

    async def _create_channel_embeds(self) -> List[discord.Embed]:
        """Create channel index embeds
        
        Returns:
            List of discord.Embed objects for channel index
        """
        channels = self.embed_contents.get("channels", {})
        embeds = []
        
        # Order of sections
        sections = ["info", "chat", "news", "offtopic", "games", "gaming"]
        
        for section in sections:
            if section in channels:
                embed = await self._create_channel_section_embed(channels[section])
                if embed:
                    embeds.append(embed)
                    
        return embeds

    async def _create_channel_section_embed(
        self,
        content: Union[Dict[str, Any], str]
    ) -> Optional[discord.Embed]:
        """Create channel section embed"""
        try:
            description = (
                content["content"] if isinstance(content, dict)
                else content
            )
            footer = (
                content.get("footer") if isinstance(content, dict)
                else None
            )
            
            embed = discord.Embed(
                description=description,
                color=EMBED_COLOR
            )
            
            if footer:
                embed.set_footer(text=footer.replace("\\n", "\n"))
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating channel section embed: {e}")
            return None

    @app_commands.command(
        name="channels",
        description="Display server channel index"
    )
    @app_commands.guilds(GUILD)
    async def get_channels(self, interaction: discord.Interaction) -> None:
        """Display server channel index command"""
        try:
            if not await self._check_cooldown(interaction.user.id):
                await interaction.response.send_message(
                    "Please wait a few seconds before using this command again.",
                    ephemeral=True
                )
                return

            # Try to delete old message
            await self._delete_old_message("channels", interaction)

            # Create channel embeds
            embeds = await self._create_channel_embeds()
            if not embeds:
                await interaction.response.send_message(
                    "No channel index content found! Please create channel index first.",
                    ephemeral=True
                )
                return

            # Send channel index
            await interaction.response.defer(ephemeral=True)
            message = await interaction.channel.send(embeds=embeds)
            
            # Store message ID
            await self.store_message_id("channels", str(message.id))
            await interaction.delete_original_response()
            
        except Exception as e:
            logger.error(f"Error in channels command: {e}")
            await interaction.response.send_message(
                "An error occurred while displaying channel index.",
                ephemeral=True
            )

    # Create the parent command group
    kruzembeds = app_commands.Group(
        name="kruzembeds",
        description="Manage server embeds",
        guild_ids=[GUILD_ID]
    )

    @kruzembeds.command(name="list", description="List all available embed categories")
    async def list_embed_categories(self, interaction: discord.Interaction) -> None:
        """List all available embed categories and their contents"""
        try:
            embed = discord.Embed(
                title="Available Embed Categories",
                description="All available embed categories and their contents",
                color=EMBED_COLOR
            )
            
            for category in sorted(self.embed_contents.keys()):
                embeds_list = sorted(self.embed_contents[category].keys())
                embeds_text = "\n".join(f"• {name}" for name in embeds_list)
                
                embed.add_field(
                    name=f"📁 {category.title()}",
                    value=embeds_text or "*No embeds*",
                    inline=False
                )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error listing embed categories: {e}")
            await interaction.response.send_message(
                "An error occurred while listing categories.",
                ephemeral=True
            )

    @kruzembeds.command(name="create", description="Create a new embed")
    @app_commands.describe(
        category="Category for the new embed",
        name="Name of the new embed",
        title="Title for the embed (optional)",
        content="Content for the embed",
        footer="Footer text (optional)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def create_embed(
        self,
        interaction: discord.Interaction,
        category: str,
        name: str,
        content: str,
        title: Optional[str] = None,
        footer: Optional[str] = None
    ) -> None:
        """Create a new embed"""
        try:
            # Initialize category if it doesn't exist
            if category not in self.embed_contents:
                self.embed_contents[category] = {}
            
            # Check if embed already exists
            if name in self.embed_contents[category]:
                await interaction.response.send_message(
                    f"An embed named '{name}' already exists in category '{category}'!",
                    ephemeral=True
                )
                return

            # Format content
            formatted_content = {
                "content": f"**{title}**\n{content}" if title else content,
                "footer": footer
            }
            
            # Store the content
            self.embed_contents[category][name] = formatted_content
            self.save_embed_contents()
            
            # Create and send the embed
            embed = await self._create_embed(category, name, formatted_content)
            if not embed:
                raise ValueError("Failed to create embed")
                
            message = await interaction.channel.send(embed=embed)
            
            # Store message ID
            if category not in self.message_ids:
                self.message_ids[category] = {}
            self.message_ids[category][name] = str(message.id)
            self.save_message_ids()

            await interaction.response.send_message(
                f"Successfully created embed '{name}' in category '{category}'!",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error creating embed: {e}")
            await interaction.response.send_message(
                "An error occurred while creating the embed.",
                ephemeral=True
            )

    async def _create_embed(
        self,
        category: str,
        name: str,
        content: Optional[Dict[str, Any]] = None
    ) -> Optional[discord.Embed]:
        """Create an embed from content"""
        try:
            if not content:
                if category not in self.embed_contents or name not in self.embed_contents[category]:
                    logger.error(f"Content not found for {category}/{name}")
                    return None
                content = self.embed_contents[category][name]

            # Special handling for rules category
            if category == "rules":
                embed = await self._create_rule_section_embed(content)
                return embed
                
            # Normal embed handling
            description = content["content"]
            footer = content.get("footer")
            title = content.get("title")  # Get title, might be None
            
            embed = discord.Embed(
                description=description,
                color=EMBED_COLOR
            )
            
            # Only set title if it exists
            if title:
                embed.title = title
            
            if footer:
                embed.set_footer(text=footer.replace("\\n", "\n"))
                
            return embed
            
        except Exception as e:
            logger.error(f"Error creating embed: {e}")
            return None

    @kruzembeds.command(name="edit", description="Edit server embeds")
    @app_commands.describe(
        category="Category of embed to edit",
        name="Name of the embed to edit",
        update_id="Whether to update stored message ID",
        message_id="Message ID to update (optional)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def edit_embeds(
        self,
        interaction: discord.Interaction,
        category: str,
        name: Optional[str] = None,
        update_id: bool = False,
        message_id: Optional[str] = None
    ) -> None:
        """Edit server embeds command"""
        try:
            # Handle ID update for rules/channels
            if update_id and message_id and category in ["rules", "channels"]:
                self.message_ids[category] = message_id
                self.save_message_ids()
                await interaction.response.send_message(
                    f"Successfully updated message ID for {category}!",
                    ephemeral=True
                )
                return
                
            # Regular edit requires embed_name
            if not name:
                await interaction.response.send_message(
                    "Please provide an embed_name to edit content!",
                    ephemeral=True
                )
                return

            # Get current content
            current_content = await self.get_current_content(category, name)
            if not current_content:
                await interaction.response.send_message(
                    f"No content found for {category}/{name}!",
                    ephemeral=True
                )
                return

            # Create and send edit modal
            await self._show_edit_modal(
                interaction,
                category,
                name,
                current_content,
                message_id,
                update_id
            )

        except Exception as e:
            logger.error(f"Error in edit_embeds command: {e}")
            await interaction.response.send_message(
                "An error occurred while editing embed.",
                ephemeral=True
            )

    async def _show_edit_modal(
        self,
        interaction: discord.Interaction,
        category: str,
        name: str,
        current_content: Dict[str, Optional[str]],
        message_id: Optional[str],
        update_id: bool
    ) -> None:
        """Show edit modal for embed content"""
        
        class EditModal(discord.ui.Modal):
            def __init__(
                self,
                cog: ServerCommands,
                title: str = f"Edit {category.title()} - {name}"
            ) -> None:
                super().__init__(title=title)
                self.cog = cog
                
                # Get the stored content
                stored_content = cog.embed_contents[category][name]
                
                # Extract current content and title
                content = stored_content.get("content", "")
                footer = stored_content.get("footer", "")
                current_title = stored_content.get("title", "")  # Get stored title
                
                # Create form fields
                self.title_input = discord.ui.TextInput(
                    label="Title",
                    style=discord.TextStyle.short,
                    placeholder="Enter the title here...",
                    default=current_title,
                    required=False,
                    max_length=256
                )
                self.content = discord.ui.TextInput(
                    label="Content",
                    style=discord.TextStyle.paragraph,
                    placeholder="Enter the content here...",
                    default=content,
                    required=True,
                    max_length=4000
                )
                self.footer = discord.ui.TextInput(
                    label="Footer",
                    style=discord.TextStyle.paragraph,
                    placeholder="Enter footer text (optional)...",
                    default=footer if footer else "",
                    required=False,
                    max_length=100
                )
                
                # Add form fields
                self.add_item(self.title_input)
                self.add_item(self.content)
                self.add_item(self.footer)

            async def on_submit(self, interaction: discord.Interaction) -> None:
                try:
                    # Format content
                    title = str(self.title_input).strip() if self.title_input.value else None
                    content = str(self.content).replace("\\n", "\n")
                    footer = str(self.footer).replace("\\n", "\n") if self.footer.value else None
                    
                    # Store content without title in content field
                    formatted_content = {
                        "content": content,
                        "footer": footer,
                        "title": title  # Will be None if empty
                    }
                    
                    # Initialize category if it doesn't exist
                    if category not in self.cog.embed_contents:
                        self.cog.embed_contents[category] = {}
                    
                    # Store the content
                    self.cog.embed_contents[category][name] = formatted_content
                    self.cog.save_embed_contents()

                    # Update message if needed
                    success = await self._update_message(interaction, category, name, message_id)

                    await interaction.response.send_message(
                        f"Successfully updated {category}/{name}!",
                        ephemeral=True
                    )

                except Exception as e:
                    logger.error(f"Error in edit modal submit: {e}")
                    await interaction.response.send_message(
                        "An error occurred while saving changes.",
                        ephemeral=True
                    )

            async def _update_message(
                self,
                interaction: discord.Interaction,
                category: str,
                name: str,
                message_id: Optional[str]
            ) -> bool:
                """Update existing message with new content"""
                try:
                    # First try to get message ID from parameter
                    msg_id = message_id
                    
                    # If no message ID provided, try to get from stored IDs
                    if not msg_id:
                        if category == "rules":
                            msg_id = self.cog.message_ids.get("rules")
                            if msg_id:
                                # Create and update all rule embeds
                                embeds = await self.cog._create_rules_embeds()
                                if embeds:
                                    channel = interaction.channel
                                    message = await channel.fetch_message(int(msg_id))
                                    await message.edit(embeds=embeds)
                                    return True
                            return False
                        elif category == "channels":
                            msg_id = self.cog.message_ids.get("channels")
                        elif category in self.cog.message_ids:
                            # Check if it's a category post or individual embed
                            if isinstance(self.cog.message_ids[category], dict):
                                msg_id = self.cog.message_ids[category].get(name)
                            else:
                                # It's a category post, update all embeds
                                msg_id = self.cog.message_ids[category]
                                channel = interaction.channel
                                try:
                                    message = await channel.fetch_message(int(msg_id))
                                    embeds = []
                                    for embed_name in sorted(self.cog.embed_contents[category].keys()):
                                        embed = await self.cog._create_embed(category, embed_name)
                                        if embed:
                                            embeds.append(embed)
                                    if embeds:
                                        await message.edit(embeds=embeds)
                                        return True
                                except Exception as e:
                                    logger.error(f"Error updating category message: {e}")
                                return False

                    if not msg_id:
                        return False

                    # Get the channel and message
                    channel = interaction.channel
                    try:
                        message = await channel.fetch_message(int(msg_id))
                        
                        # Create new embed with updated content
                        if category == "rules":
                            return await self.cog.update_rules_message(interaction, msg_id)
                        elif category == "channels":
                            return await self.cog.update_channels_message(interaction, msg_id)
                        else:
                            embed = await self.cog._create_embed(category, name)
                            if embed:
                                await message.edit(embed=embed)
                                return True
                            
                    except discord.NotFound:
                        logger.warning(f"Message {msg_id} not found")
                    except discord.Forbidden:
                        logger.warning("Missing permissions to edit message")
                    return False

                except Exception as e:
                    logger.error(f"Error in _update_message: {e}")
                    return False

        # Show the modal
        await interaction.response.send_modal(EditModal(self))

    @kruzembeds.command(name="post", description="Post an embed or all embeds from a category")
    @app_commands.describe(
        category="Category of the embed(s)",
        name="Name of the specific embed to post (leave empty to post all from category)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def post_embed(
        self,
        interaction: discord.Interaction,
        category: str,
        name: Optional[str] = None
    ) -> None:
        """Post a specific embed or all embeds from a category"""
        try:
            if category not in self.embed_contents:
                await interaction.response.send_message(
                    f"Category '{category}' not found!",
                    ephemeral=True
                )
                return

            # Posting all embeds from category
            if name is None:
                embeds = []
                for embed_name in sorted(self.embed_contents[category].keys()):
                    embed = await self._create_embed(category, embed_name)
                    if embed:
                        embeds.append(embed)

                if not embeds:
                    await interaction.response.send_message(
                        f"No embeds found in category '{category}'!",
                        ephemeral=True
                    )
                    return

                # Delete old messages if they exist
                if category in self.message_ids:
                    if isinstance(self.message_ids[category], dict):
                        for old_name in self.message_ids[category]:
                            await self._delete_embed_message(interaction, category, old_name)
            else:
                await self._delete_embed_message(interaction, category)

            # Send all embeds
            message = await interaction.channel.send(embeds=embeds)
            
            # Store message ID for the category
            if isinstance(self.message_ids.get(category, {}), dict):
                # Convert from dict to single ID for category posts
                self.message_ids[category] = str(message.id)
            else:
                self.message_ids[category] = str(message.id)
            self.save_message_ids()

            await interaction.response.send_message(
                f"Successfully posted all embeds from category '{category}'!",
                ephemeral=True
            )
            return

            # Posting single embed
            if name not in self.embed_contents[category]:
                await interaction.response.send_message(
                    f"Embed '{name}' not found in category '{category}'!",
                    ephemeral=True
                )
                return
            
            # Create and send the embed
            embed = await self._create_embed(category, name)
            if not embed:
                raise ValueError("Failed to create embed")

            message = await interaction.channel.send(embed=embed)
            
            # Store message ID
            if category not in self.message_ids:
                self.message_ids[category] = {}
            self.message_ids[category][name] = str(message.id)
            self.save_message_ids()

            await interaction.response.send_message(
                f"Successfully posted embed '{name}' from category '{category}'!",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error posting embed: {e}")
            await interaction.response.send_message(
                "An error occurred while posting the embed.",
                ephemeral=True
            )

    @kruzembeds.command(name="delete", description="Delete an embed category or specific embed")
    @app_commands.describe(
        category="Category to delete from",
        name="Specific embed to delete (optional)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def delete_embed_category(
        self,
        interaction: discord.Interaction,
        category: str,
        name: Optional[str] = None
    ) -> None:
        """Delete an embed category or specific embed"""
        try:
            if category not in self.embed_contents:
                await interaction.response.send_message(
                    f"Category '{category}' not found!",
                    ephemeral=True
                )
                return

            if name:
                await self._delete_single_embed(
                    interaction,
                    category,
                    name
                )
            else:
                await self._delete_category(
                    interaction,
                    category
                )
                
        except Exception as e:
            logger.error(f"Error in delete command: {e}")
            await interaction.response.send_message(
                "An error occurred while deleting.",
                ephemeral=True
            )

    async def _delete_single_embed(
        self,
        interaction: discord.Interaction,
        category: str,
        name: str
    ) -> None:
        """Delete a single embed"""
        try:
            if name not in self.embed_contents[category]:
                await interaction.response.send_message(
                    f"Embed '{name}' not found in category '{category}'!",
                    ephemeral=True
                )
                return

            # Delete the embed content
            del self.embed_contents[category][name]
            self.save_embed_contents()

            # Update or delete messages based on category type
            if category == "rules":
                # Update the rules message with remaining rules
                msg_id = self.message_ids.get("rules")
                if msg_id:
                    await self.update_rules_message(interaction, msg_id)
            elif category == "channels":
                # Update the channels message with remaining channels
                msg_id = self.message_ids.get("channels")
                if msg_id:
                    await self.update_channels_message(interaction, msg_id)
            else:
                # For category posts, update the full message
                if isinstance(self.message_ids.get(category), str):
                    msg_id = self.message_ids[category]
                    channel = interaction.channel
                    try:
                        message = await channel.fetch_message(int(msg_id))
                        embeds = []
                        for embed_name in sorted(self.embed_contents[category].keys()):
                            embed = await self._create_embed(category, embed_name)
                            if embed:
                                embeds.append(embed)
                        if embeds:
                            await message.edit(embeds=embeds)
                        else:
                            await message.delete()
                            del self.message_ids[category]
                    except Exception as e:
                        logger.error(f"Error updating category message: {e}")
                else:
                    # Delete individual message
                    await self._delete_embed_message(interaction, category, name)
                    if category in self.message_ids and isinstance(self.message_ids[category], dict):
                        if name in self.message_ids[category]:
                            del self.message_ids[category][name]

            self.save_message_ids()

            await interaction.response.send_message(
                f"Successfully deleted embed '{name}' from category '{category}'!",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"Error deleting single embed: {e}")
            raise

    async def _delete_category(
        self,
        interaction: discord.Interaction,
        category: str
    ) -> None:
        """Delete an entire category"""
        try:
            # Delete all messages in the category
            if category in self.message_ids:
                if isinstance(self.message_ids[category], dict):
                    for name in self.message_ids[category]:
                        await self._delete_embed_message(interaction, category, name)
                else:
                    await self._delete_embed_message(interaction, category)

            # Delete the category
            del self.embed_contents[category]
            if category in self.message_ids:
                del self.message_ids[category]

            # Save changes
            self.save_embed_contents()
            self.save_message_ids()

            await interaction.response.send_message(
                f"Successfully deleted category '{category}' and all its embeds!",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error deleting category: {e}")
            raise

    async def _delete_embed_message(
        self,
        interaction: discord.Interaction,
        category: str,
        name: Optional[str] = None
    ) -> None:
        """Delete an embed message"""
        try:
            msg_id = None
            if name:
                if (category in self.message_ids and
                    isinstance(self.message_ids[category], dict)):
                    msg_id = self.message_ids[category].get(name)
            else:
                msg_id = self.message_ids.get(category)

            if msg_id:
                try:
                    message = await interaction.channel.fetch_message(int(msg_id))
                    await message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass  # Message already deleted or no permission
            
        except Exception as e:
            logger.error(f"Error deleting embed message: {e}")
            # Don't raise - non-critical error

    async def update_rules_message(
        self,
        interaction: discord.Interaction,
        message_id: str
    ) -> bool:
        """Update existing rules message with new content"""
        try:
            # Create rule embeds
            embeds = await self._create_rules_embeds()
            if not embeds:
                return False

            # Update the existing message
            channel = interaction.channel
            message = await channel.fetch_message(int(message_id))
            await message.edit(embeds=embeds)
            return True

        except Exception as e:
            logger.error(f"Error updating rules message: {e}")
            return False

    async def update_channels_message(
        self,
        interaction: discord.Interaction,
        message_id: str
    ) -> bool:
        """Update existing channels message with new content"""
        try:
            # Create channel embeds
            embeds = await self._create_channel_embeds()
            if not embeds:
                return False

            # Update the existing message
            channel = interaction.channel
            message = await channel.fetch_message(int(message_id))
            await message.edit(embeds=embeds)
            return True

        except Exception as e:
            logger.error(f"Error updating channels message: {e}")
            return False

    @app_commands.command(
        name="embed",
        description="📝 Create and manage embedded messages"
    )
    @app_commands.describe(
        action="Choose what to do",
        category="Category name for organizing embeds",
        name="Name of the embed",
        channel="Channel to send/edit the embed in"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="📝 Create New", value="create"),
        app_commands.Choice(name="✏️ Edit Existing", value="edit"),
        app_commands.Choice(name="🗑️ Delete", value="delete"),
        app_commands.Choice(name="📋 Show List", value="list"),
        app_commands.Choice(name="👀 Preview", value="preview")
    ])
    async def embed(self, interaction: discord.Interaction, action: str, category: str, name: str, channel: discord.TextChannel) -> None:
        """Create and manage embedded messages"""
        try:
            if not await self._check_cooldown(interaction.user.id):
                await interaction.response.send_message(
                    "Please wait a few seconds before using this command again.",
                    ephemeral=True
                )
                return

            if action == "create":
                await self.create_embed(interaction, category, name, "", None, None)
            elif action == "edit":
                await self.edit_embeds(interaction, category, name, False, None)
            elif action == "delete":
                await self.delete_embed_category(interaction, category, name)
            elif action == "list":
                await self.list_embed_categories(interaction)
            elif action == "preview":
                await self.get_current_content(category, name)

        except Exception as e:
            logger.error(f"Error in embed command: {e}")
            await interaction.response.send_message(
                "An error occurred while managing the embed.",
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    """Set up the Commands cog"""
    try:
        await bot.add_cog(ServerCommands(bot))
        logger.info("Commands cog loaded successfully")
    except Exception as e:
        logger.error(f"Error loading Commands cog: {e}")
        raise 