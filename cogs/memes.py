import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncpraw
import random
import asyncio
import async_timeout
import time
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, GUILD_ID

GUILD = discord.Object(id=GUILD_ID)

class MemesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.meme_task_running = False
        self.meme_interval = 30  # Default interval in minutes
        self.posted_memes = set()  # Track all posted memes
        self.max_stored_memes = 1000  # Configuration variable
        self.last_post_time = 0
        self.min_post_interval = 60  # Minimum seconds between posts
        # Add list of words to filter
        self.blocked_words = {
            # NSFW content
            'nsfw', 'nude', 'porn', 'sex', 'xxx', 'onlyfans', 'love', 'jerkoff', 'masturbation', 'maasturbate',
            
            # Violence
            'gore', 'death', 'kill', 'murder', 'blood', 'suicide', 'dead',
            
            # Hate speech/offensive
            'racist', 'racism', 'nazi', 'hate', 'slur', 'offensive',
            
            # Controversial topics
            'politics', 'political', 'religion', 'religious', 'school', 'college', 'university', 'teacher', 'student', 'education',
            
            # Potentially disturbing
            'disturbing', 'graphic', 'trigger', 'warning', 'sensitive',
        }

    @tasks.loop(minutes=2)
    async def post_meme(self):
        current_time = time.time()
        if current_time - self.last_post_time < self.min_post_interval:
            return
            
        channel = self.bot.get_channel(1339588141044203551)
        if channel:
            try:
                async with async_timeout.timeout(60):  # Increase timeout to 60 seconds
                    async with asyncpraw.Reddit(
                        client_id=REDDIT_CLIENT_ID,
                        client_secret=REDDIT_CLIENT_SECRET,
                        user_agent=REDDIT_USER_AGENT
                    ) as reddit:
                        safe_subreddits = ['memes']
                        subreddit = await reddit.subreddit(random.choice(safe_subreddits))
                        memes = []
                        
                        try:
                            async with async_timeout.timeout(30):
                                async for meme in subreddit.top(time_filter='day', limit=500):
                                    # Add content filtering
                                    title_lower = meme.title.lower()
                                    if (meme.url.endswith(('.jpg', '.jpeg', '.png', '.gif'))
                                        and meme.id not in self.posted_memes
                                        and not meme.over_18  # Filter NSFW posts
                                        and not any(word in title_lower for word in self.blocked_words)
                                        and not meme.spoiler):  # Filter spoiler posts
                                        memes.append(meme)
                                    if len(memes) >= 50:  # Still only keep up to 50 unique memes
                                        break
                        except asyncio.TimeoutError:
                            print("Timeout while fetching memes")
                            return

                        if memes:
                            meme = random.choice(memes)
                            embed = discord.Embed(
                                title=meme.title,
                                url=f"https://reddit.com{meme.permalink}",
                                color=0xbc69f0
                            )
                            embed.set_image(url=meme.url)
                            embed.set_footer(text="See the top new memes on reddit!")
                            
                            await channel.send(embed=embed)
                            self.posted_memes.add(meme.id)
                            
                            if len(self.posted_memes) >= self.max_stored_memes:
                                self.posted_memes = set(list(self.posted_memes)[-(self.max_stored_memes // 2):])
                        else:
                            print("No new unique memes found")
            
            except asyncio.TimeoutError:
                print("Reddit API request timed out")
                return
            except Exception as e:
                print(f"Error in post_meme: {e}")
                return
        
        self.last_post_time = current_time

    @post_meme.before_loop
    async def before_post_meme(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="memeposter",
        description="Enable/disable automatic meme posting"
    )
    @app_commands.guilds(GUILD)
    @app_commands.describe(
        action="Action to take: 'enable', 'disable', or 'status'"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable"),
        app_commands.Choice(name="status", value="status")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def toggle_meme_poster(
        self,
        interaction: discord.Interaction, 
        action: str
    ):
        try:
            if action == "status":
                status = "enabled" if self.meme_task_running else "disabled"
                await interaction.response.send_message(
                    f"Meme poster is currently {status}. Posting interval: {self.meme_interval} minutes",
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
            print(f"Error in memeposter command: {e}")

    @app_commands.command(
        name="memeinterval",
        description="Change the meme posting interval"
    )
    @app_commands.guilds(GUILD)
    @app_commands.describe(
        minutes="New interval in minutes (minimum 1)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def change_meme_interval(
        self,
        interaction: discord.Interaction, 
        minutes: int
    ):
        try:
            await interaction.response.defer(ephemeral=True)
            
            if minutes < 1:
                await interaction.followup.send(
                    "Interval must be at least 1 minute.",
                    ephemeral=True
                )
                return
            
            self.meme_interval = minutes
            
            if self.post_meme.is_running():
                self.post_meme.cancel()
                await asyncio.sleep(0.1)
                self.post_meme.change_interval(minutes=minutes)
                self.post_meme.start()
            
            await interaction.followup.send(
                f"Meme posting interval updated to {minutes} minutes.",
                ephemeral=True
            )
        
        except Exception as e:
            try:
                await interaction.followup.send(
                    "An error occurred. Please try again later.",
                    ephemeral=True
                )
            except:
                pass
            print(f"Error in memeinterval command: {e}")

    @toggle_meme_poster.error
    @change_meme_interval.error
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

async def setup(bot):
    await bot.add_cog(MemesCog(bot)) 