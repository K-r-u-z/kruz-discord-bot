import discord
from discord.ext import commands
import asyncio
import logging
from typing import List, Optional
from datetime import datetime
from config import TOKEN, GUILD_ID, BOT_SETTINGS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KruzBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None  # Disable default help command
        )
        
        self.initial_extensions: List[str] = [
            'cogs.commands',
            'cogs.moderation',
            'cogs.memes',
            'cogs.settings'
        ]
        
        self.guild = discord.Object(id=GUILD_ID)
        
    async def setup_hook(self) -> None:
        """Initialize bot extensions and sync commands"""
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}")
                self._log_error(f"Extension load error: {extension}", e)

        try:
            synced = await self.tree.sync(guild=self.guild)
            logger.info(f"Synced {len(synced)} commands")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
    async def on_ready(self) -> None:
        """Handle bot ready event"""
        logger.info(f"Logged in as {self.user}")
        
        try:
            # Set bot status
            status_type = getattr(discord.ActivityType, 
                                BOT_SETTINGS["status"]["type"].lower())
            status_name = BOT_SETTINGS["status"]["name"].format(
                server_name=BOT_SETTINGS["server_name"])
            bot_status = getattr(discord.Status, 
                               BOT_SETTINGS["status"]["status"].lower())
            
            await self.change_presence(
                status=bot_status,
                activity=discord.Activity(
                    type=status_type,
                    name=status_name
                )
            )
        except Exception as e:
            logger.error(f"Failed to set bot presence: {e}")
    
    def _log_error(self, context: str, error: Exception) -> None:
        """Log errors to file and console"""
        error_msg = f"{datetime.now()}: {context} - {str(error)}"
        logger.error(error_msg)
        
        # Could also add file logging here if needed
        # with open('error.log', 'a') as f:
        #     f.write(f"{error_msg}\n")

async def main() -> None:
    """Main entry point for the bot"""
    bot = KruzBot()
    
    try:
        async with bot:
            await bot.start(TOKEN)
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        await shutdown(bot)
    except discord.LoginFailure:
        logger.error("Failed to login. Please check your Discord token.")
    except Exception as e:
        logger.error(f"Fatal error occurred: {e}")
    finally:
        if not bot.is_closed():
            await shutdown(bot)

async def shutdown(bot: KruzBot) -> None:
    """Clean shutdown of the bot"""
    logger.info("Initiating shutdown sequence...")
    
    try:
        # Cancel all tasks
        tasks = [t for t in asyncio.all_tasks() 
                if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Close bot connection
        await bot.close()
        logger.info("Bot shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot terminated by keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
