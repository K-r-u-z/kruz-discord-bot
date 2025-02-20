import discord
from discord.ext import commands
import asyncio
import signal # Might use this later
from config import TOKEN, GUILD_ID, BOT_SETTINGS
from datetime import datetime
import asyncpraw
from discord.ext import tasks
import logging


# Constants
GUILD_ID = discord.Object(id=GUILD_ID)

# Client Setup
class Client(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        self.initial_extensions = [
            'cogs.commands',
            'cogs.games',
            'cogs.moderation',
            'cogs.memes',
            'cogs.settings'
        ]
    
    async def setup_hook(self):
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                print(f"Loaded extension {extension}")
            except Exception as e:
                print(f"Failed to load extension {extension}: {e}")
                # Add error reporting to a log file
                self._log_error(f"Extension load error: {extension}", e)

        try:
            synced = await self.tree.sync(guild=GUILD_ID)
            print(f"Synced {len(synced)} commands")
        except Exception as e:
            print(f"Error syncing commands: {e}")
    
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        
        # Get status settings
        status_type = getattr(discord.ActivityType, BOT_SETTINGS["status"]["type"].lower())
        status_name = BOT_SETTINGS["status"]["name"].format(server_name=BOT_SETTINGS["server_name"])
        bot_status = getattr(discord.Status, BOT_SETTINGS["status"]["status"].lower())
        
        await self.change_presence(
            status=bot_status,
            activity=discord.Activity(
                type=status_type,
                name=status_name
            )
        )
        
    def _log_error(self, context, error):
        with open('error.log', 'a') as f:
            f.write(f"{datetime.now()}: {context} - {str(error)}\n")

async def main():
    bot = Client()
    try:
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if not bot.is_closed():
            await shutdown(bot)
            print("Bot has been shut down.")

async def shutdown(bot):
    """Cleanup tasks before shutdown"""
    print("Shutting down...")
    
    # Cancel all tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Close bot connection
    await bot.close()

@tasks.loop(minutes=5)
async def health_check():
    """Monitor bot health"""
    try:
        # Check Discord connection
        if not bot.is_ready():
            logger.warning("Bot not ready - attempting reconnect")
            await bot.close()
            await bot.start(TOKEN)
            
        # Check Reddit API
        async with asyncpraw.Reddit(...) as reddit:
            await reddit.user.me()
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot has been shut down by keyboard interrupt.")
    except Exception as e:
        print(f"Fatal error: {e}")
