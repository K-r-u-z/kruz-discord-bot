import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncpraw
import random
import asyncio
import async_timeout
import time
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, GUILD_ID, MEME_CHANNEL_ID, BOT_SETTINGS
import json
import os

# Convert hex color string to int
EMBED_COLOR = int(BOT_SETTINGS["embed_color"], 16)

GUILD = discord.Object(id=GUILD_ID)

class MemesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.meme_task_running = False
        self.max_stored_memes = 1000
        self.min_post_interval = 60

        # Channel for posting memes
        self.meme_channel_id = MEME_CHANNEL_ID

        # Load all persistent data from single file
        self.settings_file = 'meme_settings.json'
        self.load_settings()  # This loads everything: interval, time, blocked words, and posted memes

    def load_settings(self):
        """Load all meme settings from JSON file"""
        default_blocked_words = {
            # NSFW content
            'nsfw', 'nude', 'porn', 'sex', 'xxx', 'onlyfans', 'love', 'jerkoff', 'masturbation', 'masturbate', 'adult', 
            'explicit', 'lewd', 'uncensored', 'fetish', 'kink', 'bdsm', 'hentai', 'camgirl', 'stripper', 'escort',

            # Violence
            'gore', 'death', 'kill', 'murder', 'blood', 'suicide', 'dead', 'assault', 'abuse', 'torture', 'beating', 
            'gun', 'shooting', 'stab', 'execution', 'bomb', 'terrorist', 'hostage',

            # Hate speech/offensive
            'racist', 'racism', 'nazi', 'hate', 'slur', 'offensive', 'homophobic', 'transphobic', 'sexist', 'bigot', 
            'discrimination', 'xenophobia', 'misogyny', 'misandry',

            # Controversial topics
            'politics', 'political', 'gender', 'religion', 'religious', 'school', 'college', 'university', 'teacher', 
            'student', 'education', 'war', 'genocide', 'fascist', 'communism', 'capitalism', 'election', 'democrat', 
            'republican', 'Biden', 'Trump', 'BLM', 'woke', 'LGBT',

            # Potentially disturbing
            'disturbing', 'graphic', 'trigger', 'warning', 'sensitive', 'self-harm', 'cutting', 'abduction', 'kidnap', 
            'harassment', 'stalker', 'molestation', 'rape', 'incest', 'pedophile', 'trauma',

            # Illegal or unethical content
            'drugs', 'cocaine', 'meth', 'heroin', 'LSD', 'psychedelic', 'overdose', 'dealer', 'crime', 'fraud', 'scam',

            # Other potentially problematic words
            'mental illness', 'psychopath', 'sociopath', 'maniac', 'crazy', 'insane', 'conspiracy', '5G', 'flat earth', 
            'anti-vax', 'chemtrails'
        }

        default_settings = {
            "meme_interval": 30,
            "last_post_time": 0,
            "blocked_words": list(default_blocked_words),
            "posted_memes": []  # Add posted_memes to settings
        }
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.meme_interval = settings.get("meme_interval", default_settings["meme_interval"])
                    self.last_post_time = settings.get("last_post_time", default_settings["last_post_time"])
                    self.blocked_words = set(settings.get("blocked_words", default_settings["blocked_words"]))
                    self.posted_memes = set(settings.get("posted_memes", default_settings["posted_memes"]))
            else:
                # If file doesn't exist, create it with default settings
                self.meme_interval = default_settings["meme_interval"]
                self.last_post_time = default_settings["last_post_time"]
                self.blocked_words = default_blocked_words
                self.posted_memes = set()
                with open(self.settings_file, 'w') as f:
                    json.dump(default_settings, f, indent=4)
                print("Created new meme settings file with default values")

            # Add periodic cleanup of posted_memes
            if len(self.posted_memes) > self.max_stored_memes:
                # Keep only the most recent 500 memes instead of 1000
                self.max_stored_memes = 500
                self.posted_memes = set(list(self.posted_memes)[-self.max_stored_memes:])
        except Exception as e:
            print(f"Error loading meme settings: {e}")
            self.meme_interval = default_settings["meme_interval"]
            self.last_post_time = default_settings["last_post_time"]
            self.blocked_words = default_blocked_words
            self.posted_memes = set()

    def save_settings(self):
        """Save all meme settings to JSON file"""
        try:
            settings = {
                "meme_interval": self.meme_interval,
                "last_post_time": self.last_post_time,
                "blocked_words": list(self.blocked_words),
                "posted_memes": list(self.posted_memes)  # Add posted_memes to saved settings
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving meme settings: {e}")

    @tasks.loop(minutes=2)
    async def post_meme(self):
        current_time = time.time()
        if current_time - self.last_post_time < self.min_post_interval:
            return
            
        channel = self.bot.get_channel(self.meme_channel_id)
        if channel:
            try:
                async with async_timeout.timeout(60):
                    async with asyncpraw.Reddit(
                        client_id=REDDIT_CLIENT_ID,
                        client_secret=REDDIT_CLIENT_SECRET,
                        user_agent=REDDIT_USER_AGENT
                    ) as reddit:
                        safe_subreddits = ['meme']
                        subreddit = await reddit.subreddit(random.choice(safe_subreddits))
                        memes = []
                        
                        try:
                            async with async_timeout.timeout(30):
                                async for meme in subreddit.top(time_filter='day', limit=100):
                                    if len(memes) >= 25:
                                        break
                                    if self._is_valid_meme(meme):
                                        memes.append(meme)
                        except asyncio.TimeoutError:
                            print("Timeout while fetching memes")
                            return

                        if memes:
                            meme = random.choice(memes)
                            embed = discord.Embed(
                                title=meme.title,
                                url=f"https://reddit.com{meme.permalink}",
                                color=EMBED_COLOR
                            )
                            embed.set_image(url=meme.url)
                            embed.set_footer(text="See the top new memes on reddit!")
                            
                            await channel.send(embed=embed)
                            self.posted_memes.add(meme.id)
                            self.save_settings()  # Save everything after posting new meme
                            
                            # Trim the posted memes list if it gets too large
                            if len(self.posted_memes) >= self.max_stored_memes:
                                self.posted_memes = set(list(self.posted_memes)[-(self.max_stored_memes // 2):])
                                self.save_settings()  # Save after trimming
                        else:
                            print("No new unique memes found")
            
            except asyncio.TimeoutError:
                print("Reddit API request timed out")
                return
            except Exception as e:
                print(f"Error in post_meme: {e}")
                return
        
        self.last_post_time = current_time
        self.save_settings()  # Save the new last post time

    @post_meme.before_loop
    async def before_post_meme(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="kruzmemes",
        description="Control automatic meme posting"
    )
    @app_commands.guilds(GUILD)
    @app_commands.describe(
        action="Action to take",
        minutes="New interval in minutes (only used with 'interval' action)",
        word="Word to add/remove from blocklist (only used with add/remove actions)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable"),
        app_commands.Choice(name="status", value="status"),
        app_commands.Choice(name="interval", value="interval"),
        app_commands.Choice(name="addblockedkeyword", value="addblockedkeyword"),
        app_commands.Choice(name="removeblockedkeyword", value="removeblockedkeyword"),
        app_commands.Choice(name="listblockedkeywords", value="listblockedkeywords")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def toggle_meme_poster(
        self,
        interaction: discord.Interaction, 
        action: str,
        minutes: int = None,
        word: str = None
    ):
        try:
            if action == "status":
                status = "enabled" if self.meme_task_running else "disabled"
                await interaction.response.send_message(
                    f"Meme poster is currently {status}. Posting interval: {self.meme_interval} minutes",
                    ephemeral=True
                )
                return

            if action == "interval":
                if minutes is None:
                    await interaction.response.send_message(
                        "Please specify the number of minutes for the interval.",
                        ephemeral=True
                    )
                    return
                
                if minutes < 1:
                    await interaction.response.send_message(
                        "Interval must be at least 1 minute.",
                        ephemeral=True
                    )
                    return
                
                self.meme_interval = minutes
                self.save_settings()  # Save the new interval
                
                if self.post_meme.is_running():
                    self.post_meme.cancel()
                    await asyncio.sleep(0.1)
                    self.post_meme.change_interval(minutes=minutes)
                    self.post_meme.start()
                
                await interaction.response.send_message(
                    f"Meme posting interval updated to {minutes} minutes.",
                    ephemeral=True
                )
                return

            if action == "addblockedkeyword":
                if word is None:
                    await interaction.response.send_message(
                        "Please specify a word to add to the blocklist.",
                        ephemeral=True
                    )
                    return
                
                word = word.lower().strip()
                if word in self.blocked_words:
                    await interaction.response.send_message(
                        f"The word '{word}' is already in the blocklist.",
                        ephemeral=True
                    )
                    return
                
                self.blocked_words.add(word)
                self.save_settings()
                
                await interaction.response.send_message(
                    f"Added '{word}' to the meme filter blocklist. Total blocked words: {len(self.blocked_words)}",
                    ephemeral=True
                )
                return

            if action == "removeblockedkeyword":
                if word is None:
                    await interaction.response.send_message(
                        "Please specify a word to remove from the blocklist.",
                        ephemeral=True
                    )
                    return
                
                word = word.lower().strip()
                if word not in self.blocked_words:
                    await interaction.response.send_message(
                        f"The word '{word}' is not in the blocklist.",
                        ephemeral=True
                    )
                    return
                
                self.blocked_words.remove(word)
                self.save_settings()
                
                await interaction.response.send_message(
                    f"Removed '{word}' from the meme filter blocklist. Total blocked words: {len(self.blocked_words)}",
                    ephemeral=True
                )
                return

            if action == "listblockedkeywords":
                sorted_words = sorted(self.blocked_words)
                embeds = []
                for i in range(0, len(sorted_words), 20):
                    chunk = sorted_words[i:i + 20]
                    embed = discord.Embed(
                        title=f"Blocked Words ({i+1}-{min(i+20, len(sorted_words))} of {len(sorted_words)})",
                        description="\n".join(f"• {word}" for word in chunk),
                        color=EMBED_COLOR
                    )
                    embeds.append(embed)
                
                await interaction.response.send_message(
                    embeds=embeds,
                    ephemeral=True
                )
                return

            if action == "enable":
                if not self.post_meme.is_running():
                    self.post_meme.change_interval(minutes=self.meme_interval)
                    self.post_meme.start()
                    self.meme_task_running = True
                    
                    await interaction.response.send_message(
                        f"Meme poster enabled. Memes will be posted every {self.meme_interval} minutes.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "Meme poster is already running.",
                        ephemeral=True
                    )

            elif action == "disable":
                if self.post_meme.is_running():
                    self.post_meme.cancel()
                    self.meme_task_running = False
                    await interaction.response.send_message(
                        "Meme poster disabled.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "Meme poster is already disabled.",
                        ephemeral=True
                    )
        
        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again later.",
                    ephemeral=True
                )
            print(f"Error in kruzmemes command: {e}")

    @toggle_meme_poster.error
    async def meme_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "You need administrator permissions to use this command.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "You need administrator permissions to use this command.",
                        ephemeral=True
                    )
            except:
                pass

    def _is_valid_meme(self, meme):
        title_lower = meme.title.lower()
        return (meme.url.endswith(('.jpg', '.jpeg', '.png', '.gif'))
                and meme.id not in self.posted_memes
                and not meme.over_18
                and not any(word in title_lower for word in self.blocked_words)
                and not meme.spoiler)

async def setup(bot):
    await bot.add_cog(MemesCog(bot)) 