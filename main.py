import discord
from discord.ext import commands
import asyncio
from config import TOKEN, GUILD_ID, BOT_SETTINGS

# Constants
GUILD = discord.Object(id=GUILD_ID)

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
        self._health_check_task = None
    
    async def start_health_check(self):
        """Start the health check loop"""
        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def stop_health_check(self):
        """Stop the health check loop"""
        if self._health_check_task is not None:
            self._health_check_task.cancel()
            self._health_check_task = None
    
    async def _health_check_loop(self):
        """Health check loop implementation"""
        while True:
            try:
                # Check Discord connection
                if not self.is_ready():
                    await self.close()
                    await self.start(TOKEN)
            except Exception:
                pass
            await asyncio.sleep(300)  # 5 minutes

    async def setup_hook(self):
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                print(f"Loaded extension {extension}")
            except Exception as e:
                print(f"Failed to load extension {extension}: {e}")

        try:
            synced = await self.tree.sync(guild=GUILD)
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
        
        # Start health check after bot is ready
        await self.start_health_check()

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

async def shutdown(bot):
    """Cleanup tasks before shutdown"""
    # Stop health check
    await bot.stop_health_check()
    
    # Cancel all tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Close bot connection
    await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot has been shut down by keyboard interrupt.")
    except Exception as e:
        print(f"Fatal error: {e}")
