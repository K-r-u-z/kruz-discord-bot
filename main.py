import discord
from discord.ext import commands
import asyncio
import logging
from typing import List
from datetime import datetime
from config import TOKEN, GUILD_ID, BOT_SETTINGS

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class CustomFormatter(logging.Formatter):
    """Custom formatter that uses colors and better formatting"""
    
    # Colors and styles
    grey = "\x1b[38;1m"
    purple = "\x1b[35;1m"
    yellow = "\x1b[33;1m"
    red = "\x1b[31;1m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    # Format for different log levels
    FORMATS = {
        logging.DEBUG: grey + "[DEBUG] %(message)s" + reset,
        logging.INFO: purple + "[INFO] %(message)s" + reset,
        logging.WARNING: yellow + "[WARNING] %(message)s" + reset,
        logging.ERROR: red + "[ERROR] %(message)s" + reset,
        logging.CRITICAL: bold_red + "[CRITICAL] %(message)s" + reset
    }

    def format(self, record):
        # Add timestamp in a cleaner format
        record.timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Clean up the module name
        if "discord." in record.name:
            record.name = record.name.replace("discord.", "")
        elif "cogs." in record.name:
            record.name = record.name.replace("cogs.", "")
        
        # Get the format for this log level
        log_fmt = self.FORMATS.get(record.levelno)
        
        # Create a base formatter with our format
        formatter = logging.Formatter(
            f"%(timestamp)s {self.grey}%(name)s:{self.reset} {log_fmt}"
        )
        
        return formatter.format(record)

handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())
# Set a higher log level to filter out most discord.py internal messages
logging.getLogger('discord').setLevel(logging.WARNING)
logger.addHandler(handler)

class KruzBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None  # Disable default help command
        )
        
        self.initial_extensions: List[str] = [
            'cogs.embeds',
            'cogs.moderation',
            'cogs.memes',
            'cogs.settings',
            'cogs.welcome',
            'cogs.freegames'
            
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
            # Sync commands with guild
            synced = await self.tree.sync(guild=self.guild)
            logger.info(f"Synced {len(synced)} commands")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
    async def on_ready(self) -> None:
        """Handle bot ready event"""
        logger.info(f"Logged in as {self.user}")
        
        try:
            # Set bot status from settings
            presence_info = BOT_SETTINGS.get("presence", {})
            status_name = presence_info.get("activity", "").format(
                server_name=BOT_SETTINGS.get("server_name")
            )
            
            # Get status type
            parts = status_name.split(maxsplit=1)
            if len(parts) < 2:
                activity = discord.Game(name=status_name)
            else:
                activity_type = parts[0].lower()
                activity_name = parts[1]
                
                activity_types = {
                    "playing": discord.ActivityType.playing,
                    "watching": discord.ActivityType.watching,
                    "listening": discord.ActivityType.listening,
                    "competing": discord.ActivityType.competing
                }
                
                if activity_type in activity_types:
                    activity = discord.Activity(
                        type=activity_types[activity_type],
                        name=activity_name
                    )
                else:
                    activity = discord.Game(name=status_name)
            
            # Set presence
            presence_status = getattr(
                discord.Status,
                presence_info.get("status", "online").lower(),
                discord.Status.online
            )
            
            await self.change_presence(
                status=presence_status,
                activity=activity
            )
        except Exception as e:
            logger.error(f"Failed to set bot presence: {e}")
    
    def _log_error(self, context: str, error: Exception) -> None:
        """Log errors to file and console"""
        error_msg = f"{datetime.now()}: {context} - {str(error)}"
        logger.error(error_msg)
        
        # Could also add file logging here if needed
        with open('error.log', 'a', encoding='utf-8') as f:
            f.write(f"{error_msg}\n")

    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context) -> None:
        """Sync all slash commands"""
        try:
            await ctx.send("Syncing commands...")
            await self.tree.sync(guild=self.guild)
            await ctx.send("Successfully synced slash commands!")
        except Exception as e:
            await ctx.send(f"Failed to sync commands: {e}")

async def main():
    """Main entry point"""
    try:
        bot = KruzBot()
        await bot.start(TOKEN)
    except Exception as e:
        logger.error(f"Fatal error occurred: {e}")
        raise e

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
