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
        self.settings_file = 'data/meme_settings.json'
        self.meme_channel_id = MEME_CHANNEL_ID
        self.is_posting = False
        self.max_stored_memes = 1000
        
        # Default blocked words
        self.default_blocked_words = [
            # NSFW content
            'nsfw', 'nude', 'porn', 'sex', 'xxx', 'onlyfans', 'love', 'jerkoff', 
            'masturbation', 'masturbate', 'adult', 'explicit', 'lewd', 'uncensored', 
            'fetish', 'kink', 'bdsm', 'hentai', 'camgirl', 'stripper', 'escort',

            # Violence
            'gore', 'death', 'kill', 'murder', 'blood', 'suicide', 'dead', 'assault',
            'abuse', 'torture', 'beating', 'gun', 'shooting', 'stab', 'execution',
            'bomb', 'terrorzist', 'hostage',

            # Hate speech/offensive
            'racist', 'racism', 'nazi', 'hate', 'slur', 'offensive', 'homophobic',
            'transphobic', 'sexist', 'bigot', 'discrimination', 'xenophobia',
            'misogyny', 'misandry',

            # Controversial topics
            'politics', 'political', 'gender', 'religion', 'religious', 'school',
            'college', 'university', 'teacher', 'student', 'education', 'war',
            'genocide', 'fascist', 'communism', 'capitalism', 'election', 'democrat',
            'republican', 'Biden', 'Trump', 'BLM', 'woke', 'LGBT',

            # Potentially disturbing
            'disturbing', 'graphic', 'trigger', 'warning', 'sensitive', 'self-harm',
            'cutting', 'abduction', 'kidnap', 'harassment', 'stalker', 'molestation',
            'rape', 'incest', 'pedophile', 'trauma',

            # Illegal or unethical content
            'drugs', 'cocaine', 'meth', 'heroin', 'LSD', 'psychedelic', 'overdose',
            'dealer', 'crime', 'fraud', 'scam',

            # Other potentially problematic words
            'mental illness', 'psychopath', 'sociopath', 'maniac', 'crazy', 'insane',
            'conspiracy', '5G', 'flat earth', 'anti-vax', 'chemtrails'
        ]
        
        # Load settings
        self.settings = self.load_settings()
        self.meme_interval = self.settings.get('meme_interval', 60)
        self.last_post_time = self.settings.get('last_post_time', 0)
        self.blocked_words = set(self.settings.get('blocked_words', self.default_blocked_words))
        self.posted_memes = set(self.settings.get('posted_memes', []))
        self.meme_task_running = False
        
        # Initialize Reddit client
        self.reddit = self.setup_reddit()
        logger.info("MemesCog initialized successfully")

    def load_settings(self) -> Dict[str, Any]:
        """Load meme settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            
            # Create default settings if file doesn't exist
            default_settings = {
                "meme_interval": 60,
                "last_post_time": 0,
                "blocked_words": self.default_blocked_words,  # Use default blocked words
                "posted_memes": []
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
                "blocked_words": self.default_blocked_words,  # Use default blocked words here too
                "posted_memes": []
            }

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

    @app_commands.command(
        name="kruzmemes",
        description="🎭 Manage meme poster settings"
    )
    @app_commands.guilds(GUILD)
    @app_commands.describe(
        action="Choose what to do",
        interval="Set posting interval (minutes)",
        keywords="Keywords to block/unblock (comma separated)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="🔄 Toggle", value="toggle"),
        app_commands.Choice(name="🚫 Block Words", value="block"),
        app_commands.Choice(name="✨ Unblock Words", value="unblock"),
        app_commands.Choice(name="📋 List Blocked", value="list")
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
            if action == "toggle":
                # Toggle meme posting
                if self.meme_task_running:
                    self.post_meme.cancel()
                    self.meme_task_running = False
                    self.is_posting = False
                    await interaction.response.send_message("Meme poster has been disabled!", ephemeral=True)
                else:
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
                    await interaction.response.send_message(
                        f"Meme poster has been enabled! Posting every {self.meme_interval} minutes.", 
                        ephemeral=True
                    )
                return

            elif action == "list":
                # Create embed to show blocked words
                embed = discord.Embed(
                    title="🚫 Blocked Words",
                    description="Currently blocked words for meme filtering:",
                    color=EMBED_COLOR
                )
                
                # Sort blocked words alphabetically
                sorted_words = sorted(self.blocked_words)
                
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
                
                embed.set_footer(text=f"Total blocked words: {len(self.blocked_words)}")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

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