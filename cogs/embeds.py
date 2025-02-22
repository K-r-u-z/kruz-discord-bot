import discord
from discord import app_commands
from discord.ext import commands
from config import GUILD_ID, BOT_SETTINGS
import time
from typing import Optional, Dict, Any, List
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

    def _save_json(self, filepath: str, data: Dict, encoding: str = None) -> None:
        """Save data to JSON file"""
        try:
            with open(filepath, 'w', encoding=encoding) as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving JSON file {filepath}: {e}")

    def save_embed_contents(self) -> None:
        """Save embed contents to file"""
        try:
            self._save_json(self.contents_file, self.embed_contents, encoding='utf-8')
        except Exception as e:
            logger.error(f"Error saving embed contents: {e}")

    async def _check_cooldown(self, user_id: int) -> bool:
        """Check if user is on cooldown"""
        current_time = time.time()
        if user_id in self._command_cooldowns:
            if current_time - self._command_cooldowns[user_id] < self._cooldown_duration:
                return False
        self._command_cooldowns[user_id] = current_time
        return True

    @app_commands.command(
        name="kruzembeds",
        description="📝 Create and manage embedded messages"
    )
    @app_commands.guilds(GUILD)
    @app_commands.describe(
        action="Choose what to do",
        category="Category name (e.g. rules, info)",
        name="Name of specific embed (required for edit/create)",
        channel="Channel to post the embed in (optional, uses current channel by default)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="📝 Create/Edit", value="edit"),
        app_commands.Choice(name="🗑️ Delete", value="delete"),
        app_commands.Choice(name="📋 List All", value="list"),
        app_commands.Choice(name="📤 Post", value="post"),
        app_commands.Choice(name="🔄 Refresh All", value="refresh")
    ])
    async def kruzembeds(
        self,
        interaction: discord.Interaction,
        action: str,
        category: Optional[str] = None,
        name: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None
    ) -> None:
        """Manage embedded messages"""
        try:
            if action == "refresh":
                # Refresh all embeds
                await self._refresh_all_embeds(interaction)
                return
            
            if action == "edit":
                if not name:
                    await interaction.response.send_message(
                        "Please specify a name for the embed!",
                        ephemeral=True
                    )
                    return
                # Create/edit specific embed
                await self._create_new_embed(interaction, category, name)
            elif action == "delete":
                # Delete embed or category
                await self._delete_embed(interaction, category, name)
            elif action == "list":
                # List all embeds
                await self._list_embeds(interaction, category)
            elif action == "post":
                # Use current channel if none specified
                target_channel = channel or interaction.channel
                # Post embed(s)
                await self._post_embeds(interaction, category, name, target_channel)
        except Exception as e:
            logger.error(f"Error in kruzembeds command: {e}")
            await interaction.response.send_message(
                "An error occurred while managing embeds.",
                ephemeral=True
            )

    async def _create_embed(
        self,
        category: str,
        name: str
    ) -> Optional[discord.Embed]:
        """Create a single embed from stored content"""
        try:
            if category in self.embed_contents and name in self.embed_contents[category]:
                content = self.embed_contents[category][name]
                
                embed = discord.Embed(
                    title=content.get("title"),
                    description=content.get("content", ""),
                    color=EMBED_COLOR
                )
                
                if content.get("footer"):
                    embed.set_footer(text=content["footer"])
                    
                return embed
                
            return None
            
        except Exception as e:
            logger.error(f"Error creating embed: {e}")
            return None

    async def _list_embeds(
        self,
        interaction: discord.Interaction,
        category: Optional[str] = None
    ) -> None:
        """List all embeds or embeds in a category"""
        try:
            if not self.embed_contents:
                await interaction.response.send_message(
                    "No embeds found!",
                    ephemeral=True
                )
                return

            if category and category in self.embed_contents:
                # List embeds in specific category
                embeds = self.embed_contents[category]
                embed = discord.Embed(
                    title=f"📋 Embeds in {category}",
                    color=EMBED_COLOR
                )
                
                for name, content in embeds.items():
                    title = content.get("title", "No title")
                    desc = content.get("content", "")
                    preview = desc[:100] + "..." if len(desc) > 100 else desc
                    embed.add_field(
                        name=f"📄 {name}",
                        value=f"**Title:** {title}\n**Preview:** {preview}",
                        inline=False
                    )
            else:
                # List all categories
                embed = discord.Embed(
                    title="📋 Embed Categories",
                    color=EMBED_COLOR
                )
                
                for category_name, embeds in self.embed_contents.items():
                    embed.add_field(
                        name=f"📁 {category_name}",
                        value=f"Contains {len(embeds)} embed(s)",
                        inline=True
                    )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error listing embeds: {e}")
            await interaction.response.send_message(
                "An error occurred while listing embeds.",
                ephemeral=True
            )

    async def _post_embeds(
        self,
        interaction: discord.Interaction,
        category: str,
        name: Optional[str] = None,
        channel: discord.TextChannel = None
    ) -> None:
        """Post embed(s) to channel"""
        try:
            if category not in self.embed_contents:
                await interaction.response.send_message(
                    f"Category '{category}' not found!",
                    ephemeral=True
                )
                return

            # Create and send embeds
            if name:
                # Post specific embed
                embed = await self._create_embed(category, name)
                if embed:
                    message = await channel.send(embed=embed)
                    # Store message ID for individual embed
                    if category not in self.message_ids:
                        self.message_ids[category] = {}
                    self.message_ids[category][name] = str(message.id)
                    self.save_message_ids()
            else:
                # Post all embeds in category
                embeds = []
                for embed_name in self.embed_contents[category]:
                    embed = await self._create_embed(category, embed_name)
                    if embed:
                        embeds.append(embed)

                if embeds:
                    message = await channel.send(embeds=embeds)
                    # Store message ID for category
                    self.message_ids[category] = str(message.id)
                    self.save_message_ids()

            await interaction.response.send_message(
                "Successfully posted embed(s)!",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error posting embeds: {e}")
            await interaction.response.send_message(
                "An error occurred while posting embeds.",
                ephemeral=True
            )

    async def _create_new_embed(
        self,
        interaction: discord.Interaction,
        category: str,
        name: str
    ) -> None:
        """Create a new embed"""
        try:
            # Initialize category if it doesn't exist
            if category not in self.embed_contents:
                self.embed_contents[category] = {}

            # Get existing content if editing
            existing = self.embed_contents[category].get(name, {})

            class EmbedModal(discord.ui.Modal):
                def __init__(self):
                    super().__init__(title=f"Create/Edit Embed: {category}/{name}")
                    
                    self.title_input = discord.ui.TextInput(
                        label="Title",
                        style=discord.TextStyle.short,
                        placeholder="Enter title...",
                        required=False,
                        default=existing.get("title", "")
                    )
                    
                    self.content = discord.ui.TextInput(
                        label="Content",
                        style=discord.TextStyle.paragraph,
                        placeholder="Enter content...",
                        required=True,
                        default=existing.get("content", "")
                    )
                    
                    self.footer = discord.ui.TextInput(
                        label="Footer (optional)",
                        style=discord.TextStyle.paragraph,
                        placeholder="Enter footer text... (supports multiple lines)",
                        required=False,
                        default=existing.get("footer", ""),
                        max_length=2048
                    )
                    
                    self.add_item(self.title_input)
                    self.add_item(self.content)
                    self.add_item(self.footer)

                async def on_submit(self, interaction: discord.Interaction):
                    try:
                        # Store the embed
                        self.cog.embed_contents[category][name] = {
                            "title": self.title_input.value if self.title_input.value else None,
                            "content": self.content.value,
                            "footer": self.footer.value if self.footer.value else None
                        }
                        
                        # Save changes
                        self.cog.save_embed_contents()
                        
                        # Update existing message if any
                        if category in self.cog.message_ids:
                            channel_id = interaction.channel_id
                            await self.cog._update_category_message(category, channel_id)
                        
                        await interaction.response.send_message(
                            f"Successfully saved embed {category}/{name}!",
                            ephemeral=True
                        )
                    except Exception as e:
                        logger.error(f"Error saving embed: {e}")
                        await interaction.response.send_message(
                            "An error occurred while saving the embed.",
                            ephemeral=True
                        )

            modal = EmbedModal()
            modal.cog = self
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in create/edit embed: {e}")
            await interaction.response.send_message(
                "An error occurred while creating/editing the embed.",
                ephemeral=True
            )

    async def _delete_embed(
        self,
        interaction: discord.Interaction,
        category: str,
        name: Optional[str] = None
    ) -> None:
        """Delete an embed or category"""
        try:
            if category not in self.embed_contents:
                await interaction.response.send_message(
                    f"Category '{category}' not found!",
                    ephemeral=True
                )
                return

            if name:
                # Delete specific embed
                if name in self.embed_contents[category]:
                    del self.embed_contents[category][name]
                    self.save_embed_contents()
                    
                    # Update the message if category still exists
                    if self.embed_contents[category]:
                        if category in self.message_ids:
                            await self._update_category_message(category, interaction.channel_id)
                    else:
                        # If category is now empty, delete it
                        del self.embed_contents[category]
                        if category in self.message_ids:
                            del self.message_ids[category]
                            self.save_message_ids()
                    
                    await interaction.response.send_message(
                        f"Successfully deleted embed {category}/{name}!",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"Embed '{name}' not found in category '{category}'!",
                        ephemeral=True
                    )
            else:
                # Delete entire category
                del self.embed_contents[category]
                self.save_embed_contents()
                
                # Remove message ID if it exists
                if category in self.message_ids:
                    del self.message_ids[category]
                    self.save_message_ids()
                
                await interaction.response.send_message(
                    f"Successfully deleted category '{category}'!",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error deleting embed: {e}")
            await interaction.response.send_message(
                "An error occurred while deleting.",
                ephemeral=True
            )

    async def _update_category_message(self, category: str, channel_id: int) -> None:
        """Update existing message for a category"""
        try:
            if category not in self.message_ids:
                return

            channel = self.bot.get_channel(channel_id)
            if not channel:
                return

            # Handle both old (string) and new (dict) message ID formats
            message_id_data = self.message_ids[category]
            if isinstance(message_id_data, dict):
                # Create a list of items to avoid modification during iteration
                items = list(message_id_data.items())
                for name, msg_id in items:
                    try:
                        message = await channel.fetch_message(int(msg_id))
                        embed = await self._create_embed(category, name)
                        if embed:
                            await message.edit(embed=embed)
                    except discord.NotFound:
                        # Message was deleted, remove from tracking
                        if name in self.message_ids[category]:
                            del self.message_ids[category][name]
            else:
                # Old format where we store a single message ID for category
                try:
                    message = await channel.fetch_message(int(message_id_data))
                    # Create all embeds for the category
                    embeds = []
                    for name in self.embed_contents[category]:
                        embed = await self._create_embed(category, name)
                        if embed:
                            embeds.append(embed)
                    if embeds:
                        await message.edit(embeds=embeds)
                except discord.NotFound:
                    # Message was deleted, remove from tracking
                    del self.message_ids[category]

            # Clean up empty categories
            if category in self.message_ids and not self.message_ids[category]:
                del self.message_ids[category]
                self.save_message_ids()

        except Exception as e:
            logger.error(f"Error updating category message: {e}")

    def save_message_ids(self) -> None:
        """Save message IDs to file"""
        try:
            self._save_json(self.ids_file, self.message_ids)
        except Exception as e:
            logger.error(f"Error saving message IDs: {e}")

    async def _refresh_all_embeds(self, interaction: discord.Interaction) -> None:
        """Refresh all tracked embed messages"""
        try:
            if not self.message_ids:
                await interaction.response.send_message(
                    "No embeds to refresh!",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                "Refreshing all embeds...",
                ephemeral=True
            )

            updated_count = 0
            failed_count = 0
            
            # Create a copy of the message IDs to iterate over
            categories_to_update = list(self.message_ids.items())

            for category, message_id in categories_to_update:
                if category in self.embed_contents:
                    try:
                        await self._update_category_message(category, interaction.channel_id)
                        updated_count += 1
                    except Exception as e:
                        logger.error(f"Error refreshing category {category}: {e}")
                        failed_count += 1

            status = f"Refresh complete! Updated {updated_count} embed message(s)"
            if failed_count > 0:
                status += f", {failed_count} failed"

            await interaction.followup.send(status, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in refresh all embeds: {e}")
            await interaction.followup.send(
                "An error occurred while refreshing embeds.",
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