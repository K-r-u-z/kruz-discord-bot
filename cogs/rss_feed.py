import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import feedparser
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from config import GUILD_ID
import ssl
import html  # Add this import for HTML entity decoding
import re  # Add this import for HTML tag stripping
import asyncio

logger = logging.getLogger(__name__)
GUILD = discord.Object(id=GUILD_ID)

DEFAULT_SETTINGS = {
    "enabled": False,
    "feeds": [],  # List of feed configurations
    "last_entries": {},  # Store last processed entry for each feed
    "channel_colors": {},  # Store colors for each channel
    "channel_mentions": {},  # Store role mentions for each channel
    "check_interval": 15,  # Default check interval in minutes
    "processed_entries": {},  # Track processed entries by feed URL
    "max_processed_entries": 100  # Maximum number of entries to remember per feed
}

class RSSFeedError(Exception):
    """Base exception for RSS Feed cog"""
    pass

class FeedConfigView(discord.ui.View):
    def __init__(self, cog: 'RSSFeed'):
        super().__init__(timeout=60)
        self.cog = cog
        
        # Update the toggle button based on current state
        enabled = cog.settings.get("enabled", False)
        self.toggle_rss_system.label = f"{'🛑 Disable' if enabled else '▶️ Enable'} RSS System"
        self.toggle_rss_system.style = discord.ButtonStyle.success if enabled else discord.ButtonStyle.danger

    @discord.ui.button(label="➕ Add Feed", style=discord.ButtonStyle.primary)
    async def add_feed(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = AddFeedView(self.cog)
        await interaction.response.send_message(
            "Let's add a new RSS feed! Click the button below to start.",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="📋 List Feeds", style=discord.ButtonStyle.secondary)
    async def list_feeds(self, interaction: discord.Interaction, button: discord.ui.Button):
        feeds = self.cog.settings.get("feeds", [])
        if not feeds:
            await interaction.response.send_message("No feeds configured!", ephemeral=True)
            return

        embed = discord.Embed(
            title="Configured RSS Feeds",
            color=discord.Color.blue()
        )
        
        # Add current status and check interval to the embed
        status = "Enabled" if self.cog.settings.get("enabled", False) else "Disabled"
        interval = self.cog.settings.get("check_interval", 15)
        max_history = self.cog.settings.get("max_processed_entries", 100)
        current_history = len(self.cog.settings.get("processed_entries", {}).get(feeds[0]["url"], []))
        
        embed.add_field(
            name="System Status",
            value=f"**Status:** {status}\n**Check Interval:** {interval} minutes\n**Entry History:** {current_history}/{max_history}",
            inline=False
        )
        
        # Group feeds by channel
        channel_feeds = {}
        for feed in feeds:
            channel_id = feed["channel_id"]
            if channel_id not in channel_feeds:
                channel_feeds[channel_id] = []
            channel_feeds[channel_id].append(feed)

        for channel_id, channel_feed_list in channel_feeds.items():
            channel = interaction.guild.get_channel(channel_id)
            channel_name = channel.mention if channel else "Unknown Channel"
            color = self.cog.settings.get("channel_colors", {}).get(str(channel_id), "0x0000FF")
            
            # Get role mentions for this channel
            role_mentions = self.cog.settings.get("channel_mentions", {}).get(str(channel_id), [])
            mention_text = "No role mentions" if not role_mentions else ", ".join([f"<@&{role_id}>" for role_id in role_mentions])
            
            feed_list = "\n".join([f"• {feed['name']} ({feed['url']})" for feed in channel_feed_list])
            embed.add_field(
                name=f"{channel_name} (Color: #{color[2:]})",
                value=f"**Role Mentions:** {mention_text}\n\n**Feeds:**\n{feed_list}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="✏️ Edit Feed", style=discord.ButtonStyle.secondary)
    async def edit_feed(self, interaction: discord.Interaction, button: discord.ui.Button):
        feeds = self.cog.settings.get("feeds", [])
        if not feeds:
            await interaction.response.send_message("No feeds to edit!", ephemeral=True)
            return

        options = [
            discord.SelectOption(
                label=feed["name"],
                value=str(i),
                description=feed["url"]
            ) for i, feed in enumerate(feeds)
        ]

        select = EditFeedSelect(options, self.cog)
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Select a feed to edit:", view=view, ephemeral=True)

    @discord.ui.button(label="🎨 Set Channel Color", style=discord.ButtonStyle.secondary)
    async def set_channel_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Get all channels that have feeds
        channel_ids = set(feed["channel_id"] for feed in self.cog.settings.get("feeds", []))
        if not channel_ids:
            await interaction.response.send_message("No feeds configured to set channel colors!", ephemeral=True)
            return

        options = []
        for channel_id in channel_ids:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                current_color = self.cog.settings.get("channel_colors", {}).get(str(channel_id), "0x0000FF")
                options.append(
                    discord.SelectOption(
                        label=f"#{channel.name}",
                        value=str(channel_id),
                        description=f"Current color: #{current_color[2:]}"
                    )
                )

        select = ChannelColorSelect(options, self.cog)
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Select a channel to set its color:", view=view, ephemeral=True)

    @discord.ui.button(label="📢 Set Role Mentions", style=discord.ButtonStyle.secondary)
    async def set_role_mentions(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Get all channels that have feeds
        channel_ids = set(feed["channel_id"] for feed in self.cog.settings.get("feeds", []))
        if not channel_ids:
            await interaction.response.send_message("No feeds configured to set role mentions!", ephemeral=True)
            return

        options = []
        for channel_id in channel_ids:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                current_mentions = self.cog.settings.get("channel_mentions", {}).get(str(channel_id), [])
                mention_count = len(current_mentions)
                options.append(
                    discord.SelectOption(
                        label=f"#{channel.name}",
                        value=str(channel_id),
                        description=f"Current mentions: {mention_count}"
                    )
                )

        select = RoleMentionSelect(options, self.cog)
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Select a channel to manage role mentions:", view=view, ephemeral=True)

    @discord.ui.button(label="⏱️ Set Check Interval", style=discord.ButtonStyle.secondary)
    async def set_check_interval(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CheckIntervalModal(self.cog)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="🔄 Toggle RSS System", style=discord.ButtonStyle.danger)
    async def toggle_rss_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Toggle the enabled state
        current_state = self.cog.settings.get("enabled", False)
        new_state = not current_state
        self.cog.settings["enabled"] = new_state
        self.cog._save_settings()
        
        # Update the task state
        if new_state:
            if not self.cog.check_feeds.is_running():
                self.cog.check_feeds.start()
            status_text = "enabled"
            button.style = discord.ButtonStyle.success
            button.label = "🛑 Disable RSS System"
        else:
            if self.cog.check_feeds.is_running():
                self.cog.check_feeds.cancel()
            status_text = "disabled"
            button.style = discord.ButtonStyle.danger
            button.label = "▶️ Enable RSS System"
            
        await interaction.response.send_message(
            f"✅ RSS feed system has been {status_text}.",
            ephemeral=True
        )
        
    @discord.ui.button(label="🧹 Manage Duplicates", style=discord.ButtonStyle.secondary, row=1)
    async def manage_duplicates(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DuplicatesManagementView(self.cog)
        await interaction.response.send_message(
            "Manage duplicate post detection settings:",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="📢 Post Latest", style=discord.ButtonStyle.success, row=1)
    async def post_latest(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        current_channel_feeds = [
            feed for feed in self.cog.settings.get("feeds", [])
            if feed["channel_id"] == interaction.channel.id
        ]
        
        if not current_channel_feeds:
            await interaction.followup.send("No feeds configured for this channel!", ephemeral=True)
            return

        success_count = 0
        skip_count = 0
        error_count = 0
        error_messages = []

        for feed_config in current_channel_feeds:
            try:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                connector = aiohttp.TCPConnector(ssl=ssl_context)
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                    async with session.get(feed_config["url"]) as response:
                        if response.status != 200:
                            error_messages.append(f"Failed to fetch {feed_config['name']}: HTTP {response.status}")
                            error_count += 1
                            continue
                        
                        content = await response.text()
                        feed = feedparser.parse(content)
                        
                        if not feed.entries:
                            error_messages.append(f"No entries found in {feed_config['name']}")
                            error_count += 1
                            continue

                        latest_entry = feed.entries[0]
                        
                        # Check for duplicate titles
                        if self.cog._is_duplicate_entry(feed_config["url"], latest_entry.id):
                            skip_count += 1
                            error_messages.append(f"Skipped duplicate post: '{latest_entry.title}' from {feed_config['name']}")
                            continue
                            
                        # Get role mentions for this channel
                        role_mentions = self.cog.settings.get("channel_mentions", {}).get(str(feed_config["channel_id"]), [])
                        mention_text = " ".join([f"<@&{role_id}>" for role_id in role_mentions])
                        
                        embed, view = self.cog._create_feed_embed(latest_entry, feed_config["name"], feed_config["channel_id"])
                        # Send mentions and embed in the same message
                        await interaction.channel.send(content=mention_text if mention_text else None, embed=embed, view=view)
                        self.cog._add_processed_entry(feed_config["url"], latest_entry.id)
                        success_count += 1

            except Exception as e:
                error_messages.append(f"Error with {feed_config['name']}: {str(e)}")
                error_count += 1

        response = f"Posted latest entries:\n✅ Success: {success_count}\n⏭️ Skipped duplicates: {skip_count}\n❌ Failed: {error_count}"
        if error_messages:
            response += "\n\nDetails:\n" + "\n".join(f"• {msg}" for msg in error_messages)

        await interaction.edit_original_response(content=response)

class AddFeedView(discord.ui.View):
    def __init__(self, cog: 'RSSFeed'):
        super().__init__(timeout=60)  # Reduced to 1 minute
        self.cog = cog
        self.feed_name = None
        self.feed_url = None

    @discord.ui.button(label="Enter Feed Name", style=discord.ButtonStyle.primary)
    async def enter_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = FeedNameModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Enter Feed URL", style=discord.ButtonStyle.secondary)
    async def enter_url(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = FeedURLModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Select Channel", style=discord.ButtonStyle.success)
    async def select_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.feed_name or not self.feed_url:
            await interaction.response.send_message(
                "Please enter both the feed name and URL first!",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                async with session.get(self.feed_url) as response:
                    if response.status != 200:
                        await interaction.followup.send(
                            f"Failed to fetch feed: HTTP {response.status}",
                            ephemeral=True
                        )
                        return
                    content = await response.text()
                    feed = feedparser.parse(content)
                    if not feed.entries:
                        await interaction.followup.send(
                            "Invalid RSS feed: No entries found",
                            ephemeral=True
                        )
                        return

            view = ChannelSelectView(self.cog, self.feed_name, self.feed_url)
            await interaction.followup.send(
                "Select a channel for the feed:",
                view=view,
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"Failed to validate feed URL: {str(e)}",
                ephemeral=True
            )

class FeedNameModal(discord.ui.Modal, title="Enter Feed Name"):
    name = discord.ui.TextInput(
        label="Feed Name",
        placeholder="Enter a name for this feed",
        required=True,
        max_length=100
    )

    def __init__(self, view: AddFeedView):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.view.feed_name = self.name.value
        await interaction.response.send_message(
            f"✅ Feed name set to: {self.name.value}",
            ephemeral=True
        )

class FeedURLModal(discord.ui.Modal, title="Enter Feed URL"):
    url = discord.ui.TextInput(
        label="Feed URL",
        placeholder="Enter the RSS feed URL",
        required=True,
        max_length=4000  # Increased from default to handle longer URLs
    )

    def __init__(self, view: AddFeedView):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.view.feed_url = self.url.value
        await interaction.response.send_message(
            f"✅ Feed URL set to: {self.url.value}",
            ephemeral=True
        )

class EditFeedSelect(discord.ui.Select):
    def __init__(self, options: List[discord.SelectOption], cog: 'RSSFeed'):
        super().__init__(
            placeholder="Select a feed to edit",
            options=options,
            min_values=1,
            max_values=1
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        feed_index = int(self.values[0])
        feed = self.cog.settings["feeds"][feed_index]
        
        view = EditFeedView(self.cog, feed_index, feed)
        await interaction.response.send_message(
            f"Editing feed: {feed['name']}\nSelect what you want to edit:",
            view=view,
            ephemeral=True
        )

class EditFeedView(discord.ui.View):
    def __init__(self, cog: 'RSSFeed', feed_index: int, feed: Dict):
        super().__init__(timeout=60)
        self.cog = cog
        self.feed_index = feed_index
        self.feed = feed

    @discord.ui.button(label="Edit Name", style=discord.ButtonStyle.primary)
    async def edit_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditFeedNameModal(self.cog, self.feed_index, self.feed)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit URL", style=discord.ButtonStyle.primary)
    async def edit_url(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditFeedURLModal(self.cog, self.feed_index, self.feed)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit Channel", style=discord.ButtonStyle.primary)
    async def edit_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ChannelSelectView(self.cog, self.feed["name"], self.feed["url"], self.feed_index, self.feed)
        await interaction.response.send_message(
            "Select a new channel for the feed:",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="Edit Color", style=discord.ButtonStyle.primary)
    async def edit_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditFeedColorModal(self.cog, self.feed_index, self.feed)
        await interaction.response.send_modal(modal)

class EditFeedNameModal(discord.ui.Modal, title="Edit Feed Name"):
    def __init__(self, cog: 'RSSFeed', feed_index: int, feed: Dict):
        super().__init__()
        self.cog = cog
        self.feed_index = feed_index
        self.feed = feed
        self.name = discord.ui.TextInput(
            label="Feed Name",
            placeholder="Enter the new name for the feed",
            default=feed["name"],
            required=True,
            max_length=100
        )
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction):
        self.cog.settings["feeds"][self.feed_index]["name"] = self.name.value
        self.cog._save_settings()
        await interaction.response.send_message(f"✅ Feed name updated to: {self.name.value}", ephemeral=True)

class EditFeedURLModal(discord.ui.Modal, title="Edit Feed URL"):
    def __init__(self, cog: 'RSSFeed', feed_index: int, feed: Dict):
        super().__init__()
        self.cog = cog
        self.feed_index = feed_index
        self.feed = feed
        self.url = discord.ui.TextInput(
            label="Feed URL",
            placeholder="Enter the new URL for the feed",
            default=feed["url"],
            required=True,
            max_length=4000
        )
        self.add_item(self.url)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                async with session.get(self.url.value) as response:
                    if response.status != 200:
                        await interaction.followup.send(
                            f"❌ Invalid RSS feed: HTTP {response.status}",
                            ephemeral=True
                        )
                        return
                    
                    content = await response.text()
                    feed = feedparser.parse(content)
                    if not feed.entries:
                        await interaction.followup.send(
                            "❌ Invalid RSS feed: No entries found",
                            ephemeral=True
                        )
                        return

            self.cog.settings["feeds"][self.feed_index]["url"] = self.url.value
            self.cog._save_settings()
            await interaction.followup.send(f"✅ Feed URL updated to: {self.url.value}", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to validate feed URL: {str(e)}",
                ephemeral=True
            )

class EditFeedColorModal(discord.ui.Modal, title="Edit Feed Color"):
    def __init__(self, cog: 'RSSFeed', feed_index: int, feed: Dict):
        super().__init__()
        self.cog = cog
        self.feed_index = feed_index
        self.feed = feed
        
        # Get current color, remove 0x prefix if present, and ensure it's 6 characters
        current_color = feed.get("color", "0x0000FF")
        if current_color.startswith("0x"):
            current_color = current_color[2:]
        # Pad with zeros if needed
        current_color = current_color.zfill(6)
        
        self.color = discord.ui.TextInput(
            label="Embed Color (Hex)",
            placeholder="Enter hex color code (e.g., FF0000 for red)",
            default=current_color,
            required=True,
            max_length=6,
            min_length=6
        )
        self.add_item(self.color)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate hex color
            color = self.color.value.upper()
            if not all(c in "0123456789ABCDEF" for c in color):
                await interaction.response.send_message(
                    "❌ Invalid color code. Please use only hex characters (0-9, A-F).",
                    ephemeral=True
                )
                return

            # Ensure color is 6 characters
            color = color.zfill(6)
            
            self.cog.settings["feeds"][self.feed_index]["color"] = f"0x{color}"
            self.cog._save_settings()
            await interaction.response.send_message(
                f"✅ Feed color updated to: #{color}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to update color: {str(e)}",
                ephemeral=True
            )

class ChannelSelectView(discord.ui.View):
    def __init__(self, cog: 'RSSFeed', feed_name: str, feed_url: str, feed_index: int = None, existing_feed: Dict = None):
        super().__init__(timeout=60)
        self.cog = cog
        self.feed_name = feed_name
        self.feed_url = feed_url
        self.feed_index = feed_index
        self.existing_feed = existing_feed
        self.add_item(ChannelSelect(cog, feed_name, feed_url, feed_index, existing_feed))

class ChannelSelect(discord.ui.Select):
    def __init__(self, cog: 'RSSFeed', feed_name: str, feed_url: str, feed_index: int = None, existing_feed: Dict = None):
        self.cog = cog
        self.feed_name = feed_name
        self.feed_url = feed_url
        self.feed_index = feed_index
        self.existing_feed = existing_feed
        
        options = []
        for guild in cog.bot.guilds:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    options.append(
                        discord.SelectOption(
                            label=f"#{channel.name}",
                            value=str(channel.id),
                            description=f"Channel in {guild.name}"
                        )
                    )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No available channels",
                    value="none",
                    description="No channels where the bot has permission to send messages"
                )
            )

        super().__init__(
            placeholder="Select a channel for the feed",
            options=options[:25],
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            if self.values[0] == "none":
                await interaction.response.send_message(
                    "❌ No channels available where the bot has permission to send messages.",
                    ephemeral=True
                )
                return

            channel_id = int(self.values[0])
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message(
                    "❌ Selected channel not found!",
                    ephemeral=True
                )
                return

            if self.feed_index is not None and self.existing_feed is not None:
                # Editing existing feed
                self.cog.settings["feeds"][self.feed_index]["channel_id"] = channel.id
                self.cog._save_settings()
                await interaction.response.send_message(
                    f"✅ Updated channel for feed '{self.feed_name}' to {channel.mention}!",
                    ephemeral=True
                )
            else:
                # Adding new feed
                feeds = self.cog.settings.get("feeds", [])
                feeds.append({
                    "name": self.feed_name,
                    "url": self.feed_url,
                    "channel_id": channel.id,
                    "color": "0x0000FF"  # Default blue color
                })
                self.cog.settings["feeds"] = feeds
                self.cog._save_settings()

                await interaction.response.send_message(
                    f"✅ Added feed '{self.feed_name}' to {channel.mention}!",
                    ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

class FeedSelect(discord.ui.Select):
    def __init__(self, options: List[discord.SelectOption], cog: 'RSSFeed'):
        super().__init__(
            placeholder="Select a feed to remove",
            options=options
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        try:
            index = int(self.values[0])
            feeds = self.cog.settings.get("feeds", [])
            removed_feed = feeds.pop(index)
            self.cog.settings["feeds"] = feeds
            self.cog._save_settings()

            await interaction.response.send_message(
                f"✅ Removed feed '{removed_feed['name']}'!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error removing feed: {e}")
            await interaction.response.send_message(
                f"Failed to remove feed: {str(e)}",
                ephemeral=True
            )

class ChannelColorSelect(discord.ui.Select):
    def __init__(self, options: List[discord.SelectOption], cog: 'RSSFeed'):
        super().__init__(
            placeholder="Select a channel to set its color",
            options=options,
            min_values=1,
            max_values=1
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        channel_id = self.values[0]
        modal = ChannelColorModal(self.cog, channel_id)
        await interaction.response.send_modal(modal)

class ChannelColorModal(discord.ui.Modal, title="Set Channel Color"):
    def __init__(self, cog: 'RSSFeed', channel_id: str):
        super().__init__()
        self.cog = cog
        self.channel_id = channel_id
        
        # Get current color
        current_color = cog.settings.get("channel_colors", {}).get(channel_id, "0x0000FF")
        if current_color.startswith("0x"):
            current_color = current_color[2:]
        
        self.color = discord.ui.TextInput(
            label="Embed Color (Hex)",
            placeholder="Enter hex color code (e.g., FF0000 for red)",
            default=current_color,
            required=True,
            max_length=6,
            min_length=6
        )
        self.add_item(self.color)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate hex color
            color = self.color.value.upper()
            if not all(c in "0123456789ABCDEF" for c in color):
                await interaction.response.send_message(
                    "❌ Invalid color code. Please use only hex characters (0-9, A-F).",
                    ephemeral=True
                )
                return

            # Ensure color is 6 characters
            color = color.zfill(6)
            
            # Update the channel color
            if "channel_colors" not in self.cog.settings:
                self.cog.settings["channel_colors"] = {}
            self.cog.settings["channel_colors"][self.channel_id] = f"0x{color}"
            self.cog._save_settings()

            channel = interaction.guild.get_channel(int(self.channel_id))
            channel_name = channel.mention if channel else f"Channel {self.channel_id}"
            
            await interaction.response.send_message(
                f"✅ Updated color for {channel_name} to: #{color}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to update color: {str(e)}",
                ephemeral=True
            )

class RoleMentionSelect(discord.ui.Select):
    def __init__(self, options: List[discord.SelectOption], cog: 'RSSFeed'):
        super().__init__(
            placeholder="Select a channel to manage role mentions",
            options=options,
            min_values=1,
            max_values=1
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        channel_id = self.values[0]
        view = RoleMentionView(self.cog, channel_id)
        await interaction.response.send_message(
            "Select roles to mention for this channel's RSS feeds:",
            view=view,
            ephemeral=True
        )

class RoleMentionView(discord.ui.View):
    def __init__(self, cog: 'RSSFeed', channel_id: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.channel_id = channel_id
        
        # Get current mentions
        current_mentions = cog.settings.get("channel_mentions", {}).get(channel_id, [])
        
        # Add role selection
        self.add_item(RoleSelect(cog, channel_id, current_mentions))
        
        # Add clear button
        self.add_item(ClearMentionsButton(cog, channel_id))

class RoleSelect(discord.ui.Select):
    def __init__(self, cog: 'RSSFeed', channel_id: str, current_mentions: List[str]):
        self.cog = cog
        self.channel_id = channel_id
        
        # Get all roles from the guild
        roles = cog.bot.get_guild(GUILD_ID).roles
        # Filter out @everyone and roles higher than the bot's highest role
        bot_member = cog.bot.get_guild(GUILD_ID).get_member(cog.bot.user.id)
        bot_top_role = bot_member.top_role
        
        options = []
        for role in roles:
            if role.name != "@everyone" and role < bot_top_role:
                options.append(
                    discord.SelectOption(
                        label=role.name,
                        value=str(role.id),
                        default=str(role.id) in current_mentions
                    )
                )
        
        super().__init__(
            placeholder="Select roles to mention",
            options=options,
            min_values=0,
            max_values=len(options)
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            # Update the channel mentions
            if "channel_mentions" not in self.cog.settings:
                self.cog.settings["channel_mentions"] = {}
            
            self.cog.settings["channel_mentions"][self.channel_id] = self.values
            self.cog._save_settings()
            
            # Create mention text
            mention_text = ", ".join([f"<@&{role_id}>" for role_id in self.values]) if self.values else "No roles selected"
            
            await interaction.response.send_message(
                f"✅ Updated role mentions for this channel:\n{mention_text}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to update role mentions: {str(e)}",
                ephemeral=True
            )

class ClearMentionsButton(discord.ui.Button):
    def __init__(self, cog: 'RSSFeed', channel_id: str):
        super().__init__(
            label="Clear All Mentions",
            style=discord.ButtonStyle.danger
        )
        self.cog = cog
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        try:
            if "channel_mentions" in self.cog.settings:
                if self.channel_id in self.cog.settings["channel_mentions"]:
                    del self.cog.settings["channel_mentions"][self.channel_id]
                    self.cog._save_settings()
            
            await interaction.response.send_message(
                "✅ Cleared all role mentions for this channel",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to clear role mentions: {str(e)}",
                ephemeral=True
            )

class CheckIntervalModal(discord.ui.Modal, title="Set RSS Check Interval"):
    def __init__(self, cog: 'RSSFeed'):
        super().__init__()
        self.cog = cog
        
        # Get current interval
        current_interval = cog.settings.get("check_interval", 15)
        
        self.interval = discord.ui.TextInput(
            label="Check Interval (minutes)",
            placeholder="Enter interval in minutes (minimum 5)",
            default=str(current_interval),
            required=True,
            min_length=1,
            max_length=3
        )
        self.add_item(self.interval)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            interval = int(self.interval.value)
            if interval < 5:
                await interaction.response.send_message(
                    "❌ Interval must be at least 5 minutes to avoid rate limits.",
                    ephemeral=True
                )
                return
            
            # Update the interval in settings
            self.cog.settings["check_interval"] = interval
            self.cog._save_settings()
            
            # Restart the task with the new interval
            if self.cog.check_feeds.is_running():
                self.cog.check_feeds.cancel()
                
            # Wait for the task to fully cancel
            await asyncio.sleep(0.5)
            
            # Start with new interval
            self.cog.check_feeds.change_interval(minutes=interval)
            self.cog.check_feeds.start()
            
            await interaction.response.send_message(
                f"✅ RSS check interval updated to {interval} minutes.",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number for the interval.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to update interval: {str(e)}",
                ephemeral=True
            )

class DuplicatesManagementView(discord.ui.View):
    def __init__(self, cog: 'RSSFeed'):
        super().__init__(timeout=60)
        self.cog = cog
        
    @discord.ui.button(label="🧹 Clear Title History", style=discord.ButtonStyle.danger)
    async def clear_title_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Clear the title history
        self.cog.settings["processed_entries"] = {}
        self.cog._save_settings()
        
        await interaction.response.send_message(
            "✅ Title history has been cleared. Duplicate detection will start fresh.",
            ephemeral=True
        )
        
    @discord.ui.button(label="⚙️ Set History Size", style=discord.ButtonStyle.secondary)
    async def set_history_size(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TitleHistorySizeModal(self.cog)
        await interaction.response.send_modal(modal)
        
class TitleHistorySizeModal(discord.ui.Modal, title="Set Title History Size"):
    def __init__(self, cog: 'RSSFeed'):
        super().__init__()
        self.cog = cog
        
        # Get current size
        current_size = cog.settings.get("max_processed_entries", 100)
        
        self.size = discord.ui.TextInput(
            label="History Size",
            placeholder="Enter maximum number of entries to remember",
            default=str(current_size),
            required=True,
            min_length=1,
            max_length=4
        )
        self.add_item(self.size)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            size = int(self.size.value)
            if size < 10:
                await interaction.response.send_message(
                    "❌ History size must be at least 10 to be effective.",
                    ephemeral=True
                )
                return
            
            # Update the history size
            self.cog.settings["max_processed_entries"] = size
            
            self.cog._save_settings()
            
            await interaction.response.send_message(
                f"✅ Title history size updated to {size}.",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number for the history size.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to update history size: {str(e)}",
                ephemeral=True
            )

class RSSFeed(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.settings = self._load_settings()
        self.check_feeds.start()

    def _load_settings(self) -> Dict:
        try:
            if os.path.exists("data/rss_settings.json"):
                with open("data/rss_settings.json", "r") as f:
                    return json.load(f)
            return DEFAULT_SETTINGS.copy()
        except Exception:
            return DEFAULT_SETTINGS.copy()

    def _save_settings(self) -> None:
        try:
            os.makedirs("data", exist_ok=True)
            with open("data/rss_settings.json", "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception:
            pass

    def _is_duplicate_entry(self, feed_url: str, entry_id: str) -> bool:
        """Check if an entry has been processed before."""
        processed_entries = self.settings.get("processed_entries", {}).get(feed_url, [])
        return entry_id in processed_entries

    def _add_processed_entry(self, feed_url: str, entry_id: str) -> None:
        """Add an entry to the processed entries list and maintain max size."""
        if "processed_entries" not in self.settings:
            self.settings["processed_entries"] = {}
            
        if feed_url not in self.settings["processed_entries"]:
            self.settings["processed_entries"][feed_url] = []
            
        processed_entries = self.settings["processed_entries"][feed_url]
        processed_entries.append(entry_id)
        
        # Keep only the most recent entries
        max_entries = self.settings.get("max_processed_entries", 100)
        if len(processed_entries) > max_entries:
            self.settings["processed_entries"][feed_url] = processed_entries[-max_entries:]

    @tasks.loop(minutes=15)
    async def check_feeds(self) -> None:
        if not self.settings.get("enabled", False):
            return

        total_new_entries = 0
        
        for feed_config in self.settings.get("feeds", []):
            try:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                connector = aiohttp.TCPConnector(ssl=ssl_context)
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                    async with session.get(feed_config["url"]) as response:
                        if response.status != 200:
                            continue
                        
                        content = await response.text()
                        feed = feedparser.parse(content)

                        if not feed.entries:
                            continue

                        # Get the most recent entry
                        latest_entry = feed.entries[0]
                        
                        # Check if we've already processed this entry
                        if self._is_duplicate_entry(feed_config["url"], latest_entry.id):
                            continue
                        
                        channel = self.bot.get_channel(feed_config["channel_id"])
                        if channel:
                            # Get role mentions for this channel
                            role_mentions = self.settings.get("channel_mentions", {}).get(str(feed_config["channel_id"]), [])
                            mention_text = " ".join([f"<@&{role_id}>" for role_id in role_mentions])
                            
                            embed, view = self._create_feed_embed(latest_entry, feed_config["name"], feed_config["channel_id"])
                            await channel.send(content=mention_text if mention_text else None, embed=embed, view=view)
                            
                            # Mark this entry as processed
                            self._add_processed_entry(feed_config["url"], latest_entry.id)
                            total_new_entries += 1

            except Exception as e:
                continue

        self._save_settings()

    def _create_feed_embed(self, entry, feed_name: str, channel_id: int) -> discord.Embed:
        # Get the channel color, default to blue if not set
        color = self.settings.get("channel_colors", {}).get(str(channel_id), "0x0000FF")
        color_int = int(color, 16)
        
        # Clean up description by decoding HTML entities and removing HTML tags
        description = None
        if hasattr(entry, "description"):
            # First decode HTML entities
            description = html.unescape(entry.description)
            # Remove HTML tags
            description = re.sub(r'<[^>]+>', '', description)
            # Remove "Continue Reading" and similar phrases
            description = re.sub(r'Continue Reading.*$', '', description, flags=re.IGNORECASE)
            # Remove "Table of Contents" and similar sections
            description = re.sub(r'Table of Contents.*$', '', description, flags=re.IGNORECASE)
            # Remove multiple spaces
            description = re.sub(r'\s+', ' ', description)
            # Remove multiple newlines
            description = re.sub(r'\n\s*\n', '\n\n', description)
            # Clean up the text
            description = description.strip()
            
            # Limit description to around 468 characters, ensuring we don't cut words
            if len(description) > 468:
                # Find the last space before the 468 character limit
                last_space = description[:468].rfind(' ')
                if last_space != -1:
                    description = description[:last_space] + "..."
                else:
                    description = description[:468] + "..."
        
        embed = discord.Embed(
            title=html.unescape(entry.title),  # Also clean up the title
            url=entry.link,
            description=description,
            color=color_int
        )
        
        embed.set_author(name=feed_name)
        
        # Get website name from the link
        try:
            from urllib.parse import urlparse
            website = urlparse(entry.link).netloc
            website = website.replace('www.', '')
        except:
            website = feed_name
        
        # Set footer with timestamp and website
        if hasattr(entry, "published"):
            try:
                published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
                embed.timestamp = published
                embed.set_footer(text=f"Posted on {website}")
            except:
                embed.set_footer(text=f"Posted on {website}")
        else:
            embed.set_footer(text=f"Posted on {website}")

        # Enhanced image extraction logic
        image_url = None

        # 1. Check media_content (common in RSS feeds)
        if hasattr(entry, "media_content") and entry.media_content:
            for media in entry.media_content:
                if media.get("type", "").startswith("image/"):
                    image_url = media.get("url")
                    break

        # 2. Check links (common in Atom feeds)
        if not image_url and hasattr(entry, "links"):
            for link in entry.links:
                if link.get("type", "").startswith("image/"):
                    image_url = link.get("href")
                    break

        # 3. Check enclosures (common in podcast feeds)
        if not image_url and hasattr(entry, "enclosures"):
            for enclosure in entry.enclosures:
                if enclosure.get("type", "").startswith("image/"):
                    image_url = enclosure.get("href")
                    break

        # 4. Check for image tags in content
        if not image_url and hasattr(entry, "content"):
            for content in entry.content:
                if "img" in content.value.lower():
                    # Extract image URL from img tag
                    img_match = re.search(r'<img[^>]+src="([^">]+)"', content.value)
                    if img_match:
                        image_url = img_match.group(1)

        # 5. Check for image tags in description
        if not image_url and hasattr(entry, "description"):
            img_match = re.search(r'<img[^>]+src="([^">]+)"', entry.description)
            if img_match:
                image_url = img_match.group(1)

        # 6. Check for image tags in summary
        if not image_url and hasattr(entry, "summary"):
            img_match = re.search(r'<img[^>]+src="([^">]+)"', entry.summary)
            if img_match:
                image_url = img_match.group(1)

        # 7. Check for image tags in content_encoded
        if not image_url and hasattr(entry, "content_encoded"):
            img_match = re.search(r'<img[^>]+src="([^">]+)"', entry.content_encoded)
            if img_match:
                image_url = img_match.group(1)

        # 8. Check for image tags in content:encoded
        if not image_url and hasattr(entry, "content_encoded"):
            img_match = re.search(r'<img[^>]+src="([^">]+)"', entry.content_encoded)
            if img_match:
                image_url = img_match.group(1)

        # 9. Check for image tags in itunes:image
        if not image_url and hasattr(entry, "itunes_image"):
            image_url = entry.itunes_image.get("href")

        # 10. Check for image tags in media:thumbnail
        if not image_url and hasattr(entry, "media_thumbnail"):
            for thumbnail in entry.media_thumbnail:
                if thumbnail.get("url"):
                    image_url = thumbnail.get("url")
                    break

        # Set the image if we found one
        if image_url:
            # Clean up the image URL (remove any HTML entities)
            image_url = html.unescape(image_url)
            # Ensure the URL is absolute
            if not image_url.startswith(('http://', 'https://')):
                try:
                    from urllib.parse import urljoin
                    image_url = urljoin(entry.link, image_url)
                except:
                    pass
            embed.set_image(url=image_url)

        # Add a "Read More" button that links to the article
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Read More", url=entry.link, style=discord.ButtonStyle.url))

        return embed, view

    @check_feeds.before_loop
    async def before_check_feeds(self):
        await self.bot.wait_until_ready()
        interval = self.settings.get("check_interval", 15)
        self.check_feeds.change_interval(minutes=interval)

    @app_commands.command(
        name="rss",
        description="📰 RSS Feed commands"
    )
    @app_commands.guilds(GUILD)
    @app_commands.checks.has_permissions(administrator=True)
    async def rss(self, interaction: discord.Interaction) -> None:
        view = FeedConfigView(self)
        await interaction.response.send_message(
            "RSS Feed Configuration",
            view=view,
            ephemeral=True
        )

    async def cog_load(self) -> None:
        pass

    async def cog_unload(self) -> None:
        self.check_feeds.cancel()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RSSFeed(bot), guild=GUILD) 