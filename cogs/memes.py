import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncpraw
import random
import asyncio
import async_timeout
import time
import logging
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, GUILD_ID, BOT_SETTINGS
import json
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Convert hex color string to int
EMBED_COLOR = int(BOT_SETTINGS["embed_color"], 16)

GUILD = discord.Object(id=GUILD_ID)

# Add at the top of the file with other constants
DEFAULT_BLOCKED_WORDS = [
    "onlyfans", "democrat", "harassment", "kink", "discrimination", "woke", "meth", 
    "cutting", "anti-vax", "sexist", "genocide", "bdsm", "hostage", "LGBT", "suicide",
    "university", "psychopath", "school", "gun", "5G", "assault", "nazi", "trauma",
    "transphobic", "gore", "disturbing", "communism", "execution", "racist", "xenophobia",
    "xxx", "fascist", "capitalism", "sensitive", "insane", "adult", "LSD", "teacher",
    "lewd", "racism", "graphic", "self-harm", "nsfw", "drugs", "war", "terrorist",
    "sex", "misandry", "dealer", "dead", "fetish", "incest", "maniac", "overdose",
    "republican", "jerkoff", "hate", "beating", "offensive", "stalker", "shooting",
    "bomb", "hentai", "religion", "conspiracy", "kidnap", "love", "psychedelic",
    "Biden", "crazy", "kill", "fraud", "trigger", "misogyny", "masturbate", "camgirl",
    "political", "molestation", "blood", "bigot", "uncensored", "religious",
    "masturbation", "cocaine", "scam", "abduction", "death", "election", "rape",
    "flat earth", "BLM", "explicit", "Trump", "politics", "college", "mental illness",
    "gender", "education", "homophobic", "slur", "pedophile", "torture", "nude",
    "abuse", "escort", "chemtrails", "heroin", "porn", "warning", "crime", "stripper",
    "stab", "student", "murder", "sociopath"
]

class BaseSettingsView(discord.ui.View):
    def __init__(self, cog: 'MemesCog', previous_view=None):
        super().__init__(timeout=120)
        self.cog = cog
        self.previous_view = previous_view

    @discord.ui.button(label="◀️ Back", style=discord.ButtonStyle.gray, row=4)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.previous_view:
            await interaction.response.edit_message(
                content=None,
                embed=discord.Embed(
                    title="Meme Settings",
                    description="Click a button below to manage meme settings:",
                    color=EMBED_COLOR
                ),
                view=self.previous_view
            )

class MemeSettingsView(BaseSettingsView):
    def __init__(self, cog: 'MemesCog'):
        super().__init__(cog, None)
        self.remove_item(self.back_button)

    @discord.ui.button(label="🔄 Toggle", style=discord.ButtonStyle.primary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.cog.meme_task_running:
            self.cog.post_meme.cancel()
            self.cog.meme_task_running = False
            self.cog.is_posting = False
            await interaction.response.send_message("Meme poster has been disabled!", ephemeral=True)
        else:
            self.cog.post_meme.change_interval(minutes=self.cog.meme_interval)
            self.cog.post_meme.start()
            self.cog.meme_task_running = True
            await interaction.response.send_message(
                f"Meme poster has been enabled! Posting every {self.cog.meme_interval} minutes.",
                ephemeral=True
            )

    @discord.ui.button(label="🚫 Block Words", style=discord.ButtonStyle.danger)
    async def block_words(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BlockWordsModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="✨ Unblock Words", style=discord.ButtonStyle.success)
    async def unblock_words(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = UnblockWordsModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📋 List Blocked", style=discord.ButtonStyle.secondary)
    async def list_blocked(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Create embed to show blocked words
        embed = discord.Embed(
            title="🚫 Blocked Words",
            description="Currently blocked words for meme filtering:",
            color=EMBED_COLOR
        )
        
        # Sort blocked words alphabetically
        sorted_words = sorted(self.cog.blocked_words)
        
        # Split into chunks of 15 words per field
        chunk_size = 15
        for i in range(0, len(sorted_words), chunk_size):
            chunk = sorted_words[i:i + chunk_size]
            field_name = f"Words {i+1}-{min(i+chunk_size, len(sorted_words))}"
            field_value = "• " + "\n• ".join(chunk)
            embed.add_field(
                name=field_name,
                value=field_value,
                inline=False
            )
        
        embed.set_footer(text=f"Total blocked words: {len(self.cog.blocked_words)}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📌 Setup Channel", style=discord.ButtonStyle.secondary)
    async def setup_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            channel = interaction.channel
            current_channel_id = self.cog.meme_channel_id
            
            # Check if channel is already set to this channel
            if current_channel_id == channel.id:
                await interaction.response.send_message(
                    f"❌ Meme channel is already set to {channel.mention}!",
                    ephemeral=True
                )
                return
            
            self.cog.meme_channel_id = channel.id
            self.cog.settings['meme_channel_id'] = channel.id
            self.cog.save_settings()
            
            await interaction.response.send_message(
                f"✅ Meme channel set to {channel.mention}!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error setting meme channel: {e}")
            await interaction.response.send_message(
                "Failed to set meme channel!",
                ephemeral=True
            )

    @discord.ui.button(label="⏱️ Set Interval", style=discord.ButtonStyle.secondary)
    async def set_interval(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = IntervalModal(self.cog)
        await interaction.response.send_modal(modal)

class BlockWordsModal(discord.ui.Modal, title="Block Words"):
    keywords = discord.ui.TextInput(
        label="Words to Block",
        placeholder="Enter words separated by commas",
        style=discord.TextStyle.paragraph,
        required=True
    )

    def __init__(self, cog: 'MemesCog'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        # Split keywords by commas and clean whitespace
        new_keywords = [k.strip().lower() for k in self.keywords.value.split(",")]
        
        # Add new keywords to blocked words
        added = []
        for keyword in new_keywords:
            if keyword and keyword not in self.cog.blocked_words:
                self.cog.blocked_words.add(keyword)
                added.append(keyword)
        
        # Save settings
        self.cog.settings['blocked_words'] = list(self.cog.blocked_words)
        self.cog.save_settings()
        
        if added:
            await interaction.response.send_message(
                f"Added blocked keywords: {', '.join(added)}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "All specified keywords were already blocked.",
                ephemeral=True
            )

class UnblockWordsModal(discord.ui.Modal, title="Unblock Words"):
    keywords = discord.ui.TextInput(
        label="Words to Unblock",
        placeholder="Enter words separated by commas",
        style=discord.TextStyle.paragraph,
        required=True
    )

    def __init__(self, cog: 'MemesCog'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        # Split keywords by commas and clean whitespace
        keywords_to_remove = [k.strip().lower() for k in self.keywords.value.split(",")]
        
        # Remove keywords from blocked words
        removed = []
        for keyword in keywords_to_remove:
            if keyword in self.cog.blocked_words:
                self.cog.blocked_words.remove(keyword)
                removed.append(keyword)
        
        # Save settings
        self.cog.settings['blocked_words'] = list(self.cog.blocked_words)
        self.cog.save_settings()
        
        if removed:
            await interaction.response.send_message(
                f"Removed blocked keywords: {', '.join(removed)}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "None of the specified keywords were in the blocked list.",
                ephemeral=True
            )

class IntervalModal(discord.ui.Modal, title="Set Posting Interval"):
    interval = discord.ui.TextInput(
        label="Interval (minutes)",
        placeholder="Enter number of minutes between posts",
        default="60",
        required=True
    )

    def __init__(self, cog: 'MemesCog'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_interval = int(self.interval.value)
            if new_interval < 1:
                await interaction.response.send_message(
                    "Interval must be at least 1 minute!",
                    ephemeral=True
                )
                return

            self.cog.meme_interval = new_interval
            self.cog.settings['meme_interval'] = new_interval
            self.cog.save_settings()

            if self.cog.meme_task_running:
                self.cog.post_meme.change_interval(minutes=new_interval)

            await interaction.response.send_message(
                f"Posting interval updated to {new_interval} minutes!",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number!",
                ephemeral=True
            )

class MemesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.settings_file = 'data/meme_settings.json'
        self.is_posting = False
        self.max_stored_memes = 1000
        
        # Load settings
        self.settings = self._load_settings()
        self.meme_channel_id = self.settings.get('meme_channel_id')
        self.meme_interval = self.settings.get('meme_interval', 60)
        self.last_post_time = self.settings.get('last_post_time', 0)
        self.blocked_words = set(self.settings.get('blocked_words', []))
        self.posted_memes = set(self.settings.get('posted_memes', []))
        self.meme_task_running = False
        
        # Initialize Reddit client
        self.reddit = self.setup_reddit()
        
        # Start meme task if it was enabled
        if self.settings.get('enabled', False):
            self.bot.loop.create_task(self._start_meme_task())

    def _load_settings(self) -> Dict[str, Any]:
        """Load meme settings from file"""
        try:
            # Create data directory if it doesn't exist
            os.makedirs('data', exist_ok=True)
            
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            
            # Create default settings if file doesn't exist
            default_settings = {
                "meme_interval": 60,
                "last_post_time": 0,
                "blocked_words": DEFAULT_BLOCKED_WORDS,  # Add default blocked words
                "posted_memes": [],
                "meme_channel_id": None,
                "enabled": False  # Add enabled state
            }
            
            # Save default settings
            with open(self.settings_file, 'w') as f:
                json.dump(default_settings, f, indent=4)
            
            return default_settings
            
        except Exception as e:
            logger.error(f"Error loading meme settings: {e}")
            return {
                "meme_interval": 60,
                "last_post_time": 0,
                "blocked_words": DEFAULT_BLOCKED_WORDS,  # Add default blocked words here too
                "posted_memes": [],
                "meme_channel_id": None,
                "enabled": False  # Add enabled state here too
            }

    def save_settings(self) -> None:
        """Save settings with error handling"""
        try:
            settings = {
                "meme_interval": self.meme_interval,
                "last_post_time": self.last_post_time,
                "blocked_words": list(self.blocked_words),
                "posted_memes": list(self.posted_memes),
                "meme_channel_id": self.meme_channel_id,
                "enabled": self.meme_task_running  # Save enabled state
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save meme settings: {e}")

    @tasks.loop(minutes=2)
    async def post_meme(self) -> None:
        if self.is_posting or not self.meme_channel_id:
            return
        
        try:
            self.is_posting = True
            
            if not await self._should_post():
                return
                
            channel = self.bot.get_channel(self.meme_channel_id)
            if not channel:
                logger.error("Meme channel not found")
                return

            async with async_timeout.timeout(30):
                meme = await self._fetch_and_filter_meme()
                if meme:
                    await self._post_meme_to_channel(channel, meme)
                
        except Exception as e:
            logger.error(f"Error in meme posting loop: {e}")
        finally:
            self.is_posting = False

    @post_meme.before_loop
    async def before_post_meme(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="kruzmemes",
        description="🎭 Manage meme poster settings"
    )
    @app_commands.guilds(GUILD)
    @app_commands.checks.has_permissions(administrator=True)
    async def manage_memes(self, interaction: discord.Interaction):
        """Manage meme poster settings"""
        embed = discord.Embed(
            title="Meme Settings",
            description="Click a button below to manage meme settings:",
            color=EMBED_COLOR
        )
        view = MemeSettingsView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    def _is_valid_meme(self, meme):
        title_lower = meme.title.lower()
        return (meme.url.endswith(('.jpg', '.jpeg', '.png', '.gif'))
                and meme.id not in self.posted_memes
                and not meme.over_18
                and not any(word in title_lower for word in self.blocked_words)
                and not meme.spoiler)

    async def _should_post(self) -> bool:
        """Check if enough time has passed to post a new meme"""
        current_time = time.time()
        if current_time - self.last_post_time < self.meme_interval * 60:  # Convert minutes to seconds
            return False
            
        self.last_post_time = current_time
        self.save_settings()  # Save the new last_post_time
        return True

    def setup_reddit(self) -> asyncpraw.Reddit:
        """Initialize Reddit client"""
        try:
            return asyncpraw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                user_agent=REDDIT_USER_AGENT
            )
        except Exception as e:
            logger.error(f"Failed to initialize Reddit client: {e}")
            raise

    async def _fetch_and_filter_meme(self) -> Optional[Any]:
        """Fetch and filter memes from Reddit"""
        safe_subreddits = ['meme']
        try:
            subreddit = await self.reddit.subreddit(random.choice(safe_subreddits))
            memes: List[Any] = []
            
            async with async_timeout.timeout(30):
                async for meme in subreddit.top(time_filter='day', limit=100):
                    if len(memes) >= 25:
                        break
                    if self._is_valid_meme(meme):
                        memes.append(meme)
                        
            if not memes:
                logger.warning("No valid memes found")
                return None
                
            return random.choice(memes)
            
        except asyncio.TimeoutError:
            logger.error("Timeout while fetching memes from Reddit")
        except Exception as e:
            logger.error(f"Error fetching memes: {e}")
        return None

    async def _post_meme_to_channel(self, channel: discord.TextChannel, meme: Any) -> None:
        """Post meme to Discord channel"""
        try:
            embed = discord.Embed(
                title=meme.title,
                url=f"https://reddit.com{meme.permalink}",
                color=int(BOT_SETTINGS["embed_color"], 16)
            )
            embed.set_image(url=meme.url)
            embed.set_footer(text="See the top new memes on reddit!")
            
            await channel.send(embed=embed)
            self.posted_memes.add(meme.id)
            
            # Trim posted memes if needed
            if len(self.posted_memes) >= self.max_stored_memes:
                self.posted_memes = set(list(self.posted_memes)[-self.max_stored_memes:])
            
            self.save_settings()
            logger.info(f"Successfully posted meme: {meme.id}")
            
        except Exception as e:
            logger.error(f"Error posting meme: {e}")
            raise

    async def _start_meme_task(self):
        """Helper method to start meme task after bot is ready"""
        await self.bot.wait_until_ready()
        self.post_meme.change_interval(minutes=self.meme_interval)
        self.post_meme.start()
        self.meme_task_running = True
        logger.info("Meme task started automatically based on saved settings")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemesCog(bot)) 