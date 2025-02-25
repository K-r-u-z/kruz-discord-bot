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

# First define BaseSettingsView
class BaseSettingsView(discord.ui.View):
    def __init__(self, cog: 'ServerCommands', previous_view=None):
        super().__init__(timeout=120)
        self.cog = cog
        self.previous_view = previous_view

    @discord.ui.button(label="◀️ Back", style=discord.ButtonStyle.gray, row=4)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.previous_view:
            await interaction.response.edit_message(
                content=None,
                embed=discord.Embed(
                    title="Embed Settings",
                    description="Click a button below to manage server embeds:",
                    color=EMBED_COLOR
                ),
                view=self.previous_view
            )

# Then define PostSelectionView
class PostSelectionView(BaseSettingsView):
    def __init__(self, cog: 'ServerCommands', previous_view):
        super().__init__(cog, previous_view)
        self.add_category_buttons()

    def add_category_buttons(self):
        for category in self.cog.embed_contents.keys():
            button = discord.ui.Button(
                label=category,
                style=discord.ButtonStyle.primary,
                custom_id=f"post_{category}"
            )
            button.callback = self.make_callback(category)
            self.add_item(button)

    def make_callback(self, category: str):
        async def callback(interaction: discord.Interaction):
            embeds = self.cog.embed_contents[category]
            view = PostEmbedNameView(self.cog, self, category)
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title=f"Post {category} Embed",
                    description="Select an embed to post:",
                    color=EMBED_COLOR
                ),
                view=view
            )
        return callback

class EmbedSettingsView(BaseSettingsView):
    def __init__(self, cog: 'ServerCommands'):
        super().__init__(cog, None)
        self.remove_item(self.back_button)
        self.main_embed = discord.Embed(
            title="Embed Settings",
            description="• 📝 Create - Create a new embed\n"
                       "• ✏️ Edit - Modify existing embeds\n"
                       "• 📋 List All - View all embeds\n"
                       "• 📤 Post - Post an embed to channel\n"
                       "• 🗑️ Delete - Remove embeds or categories\n"
                       "• 🔄 Refresh All - Update all posted embeds",
            color=EMBED_COLOR
        )

    @discord.ui.button(label="📝 Create", style=discord.ButtonStyle.primary)
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CreateEmbedModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DeleteSelectionView(self.cog, self)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Delete Embed",
                description="Select what to delete:",
                color=EMBED_COLOR
            ),
            view=view
        )

    @discord.ui.button(label="📋 List All", style=discord.ButtonStyle.secondary)
    async def list_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog._list_embeds(interaction)

    @discord.ui.button(label="📤 Post", style=discord.ButtonStyle.success)
    async def post(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PostSelectionView(self.cog, self)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Post Embed",
                description="Select what to post:",
                color=EMBED_COLOR
            ),
            view=view
        )

    @discord.ui.button(label="🔄 Refresh All", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog._refresh_all_embeds(interaction)

    @discord.ui.button(label="✏️ Edit", style=discord.ButtonStyle.primary)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.embed_contents:
            await interaction.response.send_message(
                "No embeds available to edit!",
                ephemeral=True
            )
            return

        view = EditEmbedView(self.cog, self)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Edit Embed",
                description="Select a category to edit:",
                color=EMBED_COLOR
            ),
            view=view
        )

class PostEmbedView(BaseSettingsView):
    def __init__(self, cog: 'ServerCommands', previous_view):
        super().__init__(cog, previous_view)
        self.add_category_buttons()

    def add_category_buttons(self):
        for category in self.cog.embed_contents.keys():
            button = discord.ui.Button(
                label=category,
                style=discord.ButtonStyle.primary,
                custom_id=f"post_{category}"
            )
            button.callback = self.make_callback(category)
            self.add_item(button)

    def make_callback(self, category: str):
        async def callback(interaction: discord.Interaction):
            embeds = self.cog.embed_contents[category]
            view = PostEmbedNameView(self.cog, self, category)
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title=f"Post {category} Embed",
                    description="Select an embed to post:",
                    color=EMBED_COLOR
                ),
                view=view
            )
        return callback

class PostEmbedNameView(BaseSettingsView):
    def __init__(self, cog: 'ServerCommands', previous_view, category: str):
        super().__init__(cog, previous_view)
        self.category = category
        self.add_embed_buttons()

    def add_embed_buttons(self):
        # Add individual embed buttons
        for name in self.cog.embed_contents[self.category].keys():
            button = discord.ui.Button(
                label=name,
                style=discord.ButtonStyle.primary,
                custom_id=f"post_{self.category}_{name}"
            )
            button.callback = self.make_callback(name)
            self.add_item(button)

        # Add "Post All" button
        post_all = discord.ui.Button(
            label="📑 Post All",
            style=discord.ButtonStyle.success,
            custom_id=f"post_all_{self.category}"
        )
        post_all.callback = self.post_all_callback
        self.add_item(post_all)

    def make_callback(self, name: str):
        async def callback(interaction: discord.Interaction):
            try:
                await self.cog._post_embeds(interaction, self.category, name, interaction.channel)
            except Exception as e:
                logger.error(f"Error posting embed: {e}")
                await interaction.followup.send("Error posting embed", ephemeral=True)
        return callback

    async def post_all_callback(self, interaction: discord.Interaction):
        try:
            await self.cog._post_embeds(interaction, self.category, channel=interaction.channel)
        except Exception as e:
            logger.error(f"Error posting all embeds: {e}")
            await interaction.followup.send("Error posting all embeds", ephemeral=True)

class EditEmbedView(BaseSettingsView):
    def __init__(self, cog: 'ServerCommands', previous_view):
        super().__init__(cog, previous_view)
        self.add_category_buttons()

    def add_category_buttons(self):
        for category in self.cog.embed_contents.keys():
            button = discord.ui.Button(
                label=category,
                style=discord.ButtonStyle.primary,
                custom_id=f"edit_{category}"
            )
            button.callback = self.make_callback(category)
            self.add_item(button)

    def make_callback(self, category: str):
        async def callback(interaction: discord.Interaction):
            embeds = self.cog.embed_contents[category]
            view = EditEmbedNameView(self.cog, self, category)
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title=f"Edit {category} Embed",
                    description="Select an embed to edit:",
                    color=EMBED_COLOR
                ),
                view=view
            )
        return callback

class EditEmbedNameView(BaseSettingsView):
    def __init__(self, cog: 'ServerCommands', previous_view, category: str):
        super().__init__(cog, previous_view)
        self.category = category
        self.add_embed_buttons()

    def add_embed_buttons(self):
        for name in self.cog.embed_contents[self.category].keys():
            button = discord.ui.Button(
                label=name,
                style=discord.ButtonStyle.primary,
                custom_id=f"edit_{self.category}_{name}"
            )
            button.callback = self.make_callback(name)
            self.add_item(button)

    def make_callback(self, name: str):
        async def callback(interaction: discord.Interaction):
            embed_data = self.cog.embed_contents[self.category][name]
            modal = CreateEmbedModal(
                self.cog,
                category=self.category,
                name=name,
                title=embed_data["title"],
                content=embed_data["content"],
                footer=embed_data.get("footer", "")
            )
            await interaction.response.send_modal(modal)
        return callback

class CreateEmbedModal(discord.ui.Modal):
    def __init__(self, cog: 'ServerCommands', category=None, name=None, title=None, content=None, footer=None):
        super().__init__(title="Create/Edit Embed")
        self.cog = cog
        
        self.category_input = discord.ui.TextInput(
            label="Category",
            placeholder="e.g. rules, info",
            required=True,
            default=category or "",
            style=discord.TextStyle.short
        )
        
        self.name_input = discord.ui.TextInput(
            label="Name",
            placeholder="Name of the embed",
            required=True,
            default=name or "",
            style=discord.TextStyle.short
        )
        
        self.title_input = discord.ui.TextInput(
            label="Title",
            placeholder="Enter title...",
            required=False,
            default=title or "",
            style=discord.TextStyle.short
        )
        
        self.content = discord.ui.TextInput(
            label="Content",
            placeholder="Enter content...",
            required=True,
            default=content or "",
            style=discord.TextStyle.paragraph
        )
        
        self.footer = discord.ui.TextInput(
            label="Footer (optional)",
            placeholder="Enter footer text... (supports multiple lines)",
            required=False,
            max_length=2048,
            style=discord.TextStyle.paragraph
        )
        
        for item in [self.category_input, self.name_input, self.title_input, self.content, self.footer]:
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Store the embed
            category = self.category_input.value.lower()
            name = self.name_input.value.lower()
            
            if category not in self.cog.embed_contents:
                self.cog.embed_contents[category] = {}
                
            self.cog.embed_contents[category][name] = {
                "title": self.title_input.value,
                "content": self.content.value,
                "footer": self.footer.value if self.footer.value else None
            }
            
            self.cog.save_embed_contents()

            # Update posted embed if it exists
            if category in self.cog.message_ids:
                try:
                    await self.cog._update_category_message(category, interaction.channel_id)
                    await interaction.response.send_message(
                        f"Successfully saved and updated embed {category}/{name}!", 
                        ephemeral=True
                    )
                except Exception as e:
                    logger.error(f"Error updating posted embed: {e}")
                    await interaction.response.send_message(
                        f"Embed saved but failed to update posted message: {str(e)}", 
                        ephemeral=True
                    )
            else:
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
        self.embed_color = EMBED_COLOR

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
        name="embed",
        description="📝 Manage server embeds"
    )
    @app_commands.guilds(GUILD)
    @app_commands.checks.has_permissions(administrator=True)
    async def embed_command(self, interaction: discord.Interaction) -> None:
        """Manage server embeds"""
        embed = discord.Embed(
            title="Embed Settings",
            description="Click a button below to manage server embeds:",
            color=EMBED_COLOR
        )
        view = EmbedSettingsView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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
                    title=content.get("title", name),
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

            # Create all embeds for the category
            embeds = []
            if name:
                # Post specific embed
                embed = discord.Embed(
                    title=self.embed_contents[category][name].get("title"),
                    description=self.embed_contents[category][name].get("content"),
                    color=self.embed_color
                )
                if self.embed_contents[category][name].get("footer"):
                    embed.set_footer(text=self.embed_contents[category][name]["footer"])
                embeds.append(embed)
            else:
                # Post all embeds in category
                for embed_name in self.embed_contents[category]:
                    embed = discord.Embed(
                        title=self.embed_contents[category][embed_name].get("title"),
                        description=self.embed_contents[category][embed_name].get("content"),
                        color=self.embed_color
                    )
                    if self.embed_contents[category][embed_name].get("footer"):
                        embed.set_footer(text=self.embed_contents[category][embed_name]["footer"])
                    embeds.append(embed)

            # Send all embeds in one message
            message = await channel.send(embeds=embeds)
            
            # Store message ID
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
                        placeholder="Enter title...",
                        required=False,
                        default=existing.get("title", ""),
                        style=discord.TextStyle.short
                    )
                    
                    self.content = discord.ui.TextInput(
                        label="Content",
                        placeholder="Enter content...",
                        required=True,
                        default=existing.get("content", ""),
                        style=discord.TextStyle.paragraph
                    )
                    
                    self.footer = discord.ui.TextInput(
                        label="Footer (optional)",
                        placeholder="Enter footer text... (supports multiple lines)",
                        required=False,
                        default=existing.get("footer", ""),
                        max_length=2048,
                        style=discord.TextStyle.paragraph
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
                        
                        embed = discord.Embed(
                            title="Embed Settings",
                            description="Click a button below to manage server embeds:",
                            color=EMBED_COLOR
                        )
                        view = EmbedSettingsView(self.cog)
                        await interaction.response.send_message(
                            embed=embed,
                            view=view,
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
            logger.error(f"Error saving embed: {e}")
            raise

    async def _delete_embed(
        self,
        interaction: discord.Interaction,
        category: str,
        name: Optional[str] = None
    ) -> None:
        """Delete an embed or category"""
        try:
            if category not in self.embed_contents:
                await interaction.edit_original_response(
                    embed=discord.Embed(
                        title="Error",
                        description=f"Category '{category}' not found!",
                        color=EMBED_COLOR
                    ),
                    view=EmbedSettingsView(self)
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
                    
                    await interaction.followup.send(
                        f"Successfully deleted embed {category}/{name}!",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
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
                
                await interaction.followup.send(
                    f"Successfully deleted category '{category}'!",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error deleting embed: {e}")
            await interaction.followup.send(
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

            message_id = self.message_ids[category]
            try:
                message = await channel.fetch_message(int(message_id))
                
                # Create all embeds for the category
                embeds = []
                for name in self.embed_contents[category]:
                    embed = discord.Embed(
                        title=self.embed_contents[category][name].get("title"),
                        description=self.embed_contents[category][name].get("content"),
                        color=self.embed_color
                    )
                    if self.embed_contents[category][name].get("footer"):
                        embed.set_footer(text=self.embed_contents[category][name]["footer"])
                    embeds.append(embed)

                # Update the message with all embeds
                await message.edit(embeds=embeds)
                
            except discord.NotFound:
                # Message was deleted, remove from tracking
                del self.message_ids[category]
                self.save_message_ids()

        except Exception as e:
            logger.error(f"Error updating category message: {e}")
            raise

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
            to_remove = []
            
            # Store categories to remove after iteration
            for category, message_id in dict(self.message_ids).items():
                if category in self.embed_contents:
                    try:
                        await self._update_category_message(category, interaction.channel_id)
                        updated_count += 1
                    except discord.NotFound:
                        # Add to removal list if message not found
                        to_remove.append(category)
                        failed_count += 1
                    except Exception as e:
                        logger.error(f"Error refreshing category {category}: {e}")
                        failed_count += 1

            # Remove any invalid message IDs after iteration
            for category in to_remove:
                del self.message_ids[category]
            if to_remove:
                self._save_json(self.ids_file, self.message_ids)

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

class DeleteSelectionView(BaseSettingsView):
    def __init__(self, cog: 'ServerCommands', previous_view):
        super().__init__(cog, previous_view)
        self.add_category_buttons()

    def add_category_buttons(self):
        for category in self.cog.embed_contents.keys():
            # Add button for each category
            button = discord.ui.Button(
                label=category,
                style=discord.ButtonStyle.primary,
                custom_id=f"delete_{category}"
            )
            button.callback = self.make_callback(category)
            self.add_item(button)

            # Add delete category button
            delete_cat_button = discord.ui.Button(
                label=f"Delete {category} Category",
                style=discord.ButtonStyle.danger,
                custom_id=f"delete_category_{category}"
            )
            delete_cat_button.callback = self.make_category_callback(category)
            self.add_item(delete_cat_button)

    def make_callback(self, category: str):
        async def callback(interaction: discord.Interaction):
            view = DeleteEmbedNameView(self.cog, self, category)
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title=f"Delete {category} Embed",
                    description="Select an embed to delete:",
                    color=EMBED_COLOR
                ),
                view=view
            )
        return callback

    def make_category_callback(self, category: str):
        async def callback(interaction: discord.Interaction):
            confirm_view = DeleteConfirmView(self.cog, self, category)
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="Confirm Delete",
                    description=f"Are you sure you want to delete the entire '{category}' category?\n"
                               "This will delete all embeds in this category!",
                    color=EMBED_COLOR
                ),
                view=confirm_view
            )
        return callback

class DeleteEmbedNameView(BaseSettingsView):
    def __init__(self, cog: 'ServerCommands', previous_view, category: str):
        super().__init__(cog, previous_view)
        self.category = category
        self.add_embed_buttons()

    def add_embed_buttons(self):
        for name in self.cog.embed_contents[self.category].keys():
            button = discord.ui.Button(
                label=name,
                style=discord.ButtonStyle.danger,
                custom_id=f"delete_{self.category}_{name}"
            )
            button.callback = self.make_callback(name)
            self.add_item(button)

    def make_callback(self, name: str):
        async def callback(interaction: discord.Interaction):
            confirm_view = DeleteConfirmView(self.cog, self.previous_view, self.category, name)
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="Confirm Delete",
                    description=f"Are you sure you want to delete '{name}' from '{self.category}'?",
                    color=EMBED_COLOR
                ),
                view=confirm_view
            )
        return callback

class DeleteConfirmView(BaseSettingsView):
    def __init__(self, cog: 'ServerCommands', previous_view, category: str, name: str = None):
        super().__init__(cog, previous_view)
        self.category = category
        self.name = name

    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Edit the current message to show "deleting" status
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Deleting...",
                description="Please wait while the embed is being deleted.",
                color=EMBED_COLOR
            ),
            view=None
        )

        await self.cog._delete_embed(interaction, self.category, self.name)
        # Return to main menu
        embed = discord.Embed(
            title="Embed Settings",
            description="Click a button below to manage server embeds:",
            color=EMBED_COLOR
        )
        view = EmbedSettingsView(self.cog)
        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Return to previous menu
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Delete Cancelled",
                description="Deletion was cancelled.",
                color=EMBED_COLOR
            ),
            view=self.previous_view
        )

class CategorySelectionView(BaseSettingsView):
    def __init__(self, cog: 'ServerCommands', previous_view):
        super().__init__(cog, previous_view)
        
        self.category_input = discord.ui.TextInput(
            label="Category",
            placeholder="e.g. rules, info",
            required=True
        )
        self.name_input = discord.ui.TextInput(
            label="Name",
            placeholder="Name of the embed",
            required=True
        )

    async def on_submit(self, interaction: discord.Interaction):
        category = self.category_input.value.lower()
        name = self.name_input.value.lower()
        await self.cog._create_new_embed(interaction, category, name)

async def setup(bot: commands.Bot) -> None:
    """Set up the Commands cog"""
    await bot.add_cog(ServerCommands(bot)) 