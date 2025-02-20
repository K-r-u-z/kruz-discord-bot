import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncpraw
import random
import asyncio
import async_timeout
import time
import logging
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, GUILD_ID, MEME_CHANNEL_ID, BOT_SETTINGS
import json
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Convert hex color string to int
EMBED_COLOR = int(BOT_SETTINGS["embed_color"], 16)

GUILD = discord.Object(id=GUILD_ID)

class MemesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.meme_task_running = False
        self.is_posting = False
        self.max_stored_memes = 1000
        self.min_post_interval = 60
        self.meme_channel_id = MEME_CHANNEL_ID
        
        # Load settings
        self.settings_file = 'data/meme_settings.json'
        self.settings = self.load_settings()
        self.meme_interval = self.settings.get('meme_interval', 20)
        self.last_post_time = self.settings.get('last_post_time', 0)
        self.blocked_words = set(self.settings.get('blocked_words', []))  # Use set for O(1) lookups
        self.posted_memes = set(self.settings.get('posted_memes', []))
        
        # Initialize Reddit client
        self.reddit = self.setup_reddit()
        logger.info("MemesCog initialized successfully")

    def load_settings(self) -> Dict[str, Any]:
        """Load settings with error handling and validation"""
        try:
            # Create data directory if it doesn't exist
            os.makedirs('data', exist_ok=True)
            
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    if self._validate_settings(settings):
                        return settings
            logger.warning("Creating new settings file with defaults")
            return self._get_default_settings()
        except Exception as e:
            logger.error(f"Error loading meme settings: {e}")
            return self._get_default_settings()

    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings"""
        return {
            'meme_interval': 20,
            'last_post_time': 0,
            'blocked_words': [],
            'posted_memes': []
        }

    def _validate_settings(self, settings: Dict[str, Any]) -> bool:
        """Validate settings structure"""
        required_fields = {'meme_interval', 'last_post_time', 'blocked_words', 'posted_memes'}
        return all(field in settings for field in required_fields)

    def save_settings(self) -> None:
        """Save settings with error handling"""
        try:
            settings = {
                "meme_interval": self.meme_interval,
                "last_post_time": self.last_post_time,
                "blocked_words": list(self.blocked_words),
                "posted_memes": list(self.posted_memes)
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save meme settings: {e}")

    @tasks.loop(minutes=2)
    async def post_meme(self) -> None:
        """Main meme posting loop with error handling"""
        if self.is_posting:
            return
            
        try:
            self.is_posting = True
            
            if not await self._should_post():
                return
                
            channel = self.bot.get_channel(self.meme_channel_id)
            if not channel:
                raise ValueError("Meme channel not found")

            async with async_timeout.timeout(30):
                meme = await self._fetch_and_filter_meme()
                if meme:
                    await self._post_meme_to_channel(channel, meme)
                
        except asyncio.TimeoutError:
            logger.error("Timeout in meme posting loop")
        except Exception as e:
            logger.error(f"Error in meme posting loop: {e}")
        finally:
            self.is_posting = False

    @post_meme.before_loop
    async def before_post_meme(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="kruzmemes", description="Manage meme poster settings")
    @app_commands.guilds(GUILD)
    @app_commands.describe(
        action="Action to perform",
        interval="Set the interval between memes (in minutes, default 20)",
        keywords="Keywords to block/unblock (separate multiple with commas)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Enable", value="enable"),
        app_commands.Choice(name="Disable", value="disable"),
        app_commands.Choice(name="Block Keywords", value="block"),
        app_commands.Choice(name="Unblock Keywords", value="unblock")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def manage_memes(
        self, 
        interaction: discord.Interaction,
        action: str,
        interval: Optional[int] = None,
        keywords: Optional[str] = None
    ):
        try:
            if action == "disable":
                # Stop the task
                self.post_meme.cancel()
                self.meme_task_running = False
                self.is_posting = False
                print("\033[91m" + "Kruz Memes has been disabled!" + "\033[0m")  # Red text
                await interaction.response.send_message("Meme poster has been disabled!", ephemeral=True)
                
            elif action == "enable":
                # Update interval if provided
                if interval is not None:
                    if interval < 1:
                        await interaction.response.send_message("Interval must be at least 1 minute!", ephemeral=True)
                        return
                    self.meme_interval = interval
                    self.settings['meme_interval'] = interval
                    self.save_settings()

                # Start the task
                self.post_meme.change_interval(minutes=self.meme_interval)
                self.post_meme.start()
                self.meme_task_running = True
                print("\033[92m" + f"Kruz Memes has been enabled! Posting every {self.meme_interval} minutes." + "\033[0m")  # Green text
                await interaction.response.send_message(
                    f"Meme poster has been enabled! Posting every {self.meme_interval} minutes.", 
                    ephemeral=True
                )

            elif action == "block":
                if not keywords:
                    await interaction.response.send_message("Please provide keywords to block!", ephemeral=True)
                    return
                    
                # Split keywords by commas and clean whitespace
                new_keywords = [k.strip().lower() for k in keywords.split(",")]
                
                # Add new keywords to blocked words
                added = []
                for keyword in new_keywords:
                    if keyword and keyword not in self.blocked_words:
                        self.blocked_words.add(keyword)
                        added.append(keyword)
                
                # Save settings
                self.settings['blocked_words'] = list(self.blocked_words)
                self.save_settings()
                
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

            elif action == "unblock":
                if not keywords:
                    await interaction.response.send_message("Please provide keywords to unblock!", ephemeral=True)
                    return
                    
                # Split keywords by commas and clean whitespace
                keywords_to_remove = [k.strip().lower() for k in keywords.split(",")]
                
                # Remove keywords from blocked words
                removed = []
                for keyword in keywords_to_remove:
                    if keyword in self.blocked_words:
                        self.blocked_words.remove(keyword)
                        removed.append(keyword)
                
                # Save settings
                self.settings['blocked_words'] = list(self.blocked_words)
                self.save_settings()
                
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

        except Exception as e:
            print(f"Error in kruzmemes command: {e}")
            await interaction.response.send_message(f"Error in kruzmemes command: {str(e)}", ephemeral=True)

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

async def setup(bot):
    await bot.add_cog(MemesCog(bot)) 