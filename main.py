import discord
from discord.ext import commands
import asyncio
import logging
from typing import List, Dict, Optional
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

# Rate limit tracking
class RateLimitTracker:
    def __init__(self):
        self.rate_limits: Dict[str, Dict] = {}
        self.global_rate_limit: Optional[float] = None
        self.retry_after: Optional[float] = None

    def update_route_limit(self, route: str, limit: int, remaining: int, reset: float):
        self.rate_limits[route] = {
            'limit': limit,
            'remaining': remaining,
            'reset': reset
        }

    def update_global_limit(self, retry_after: float):
        self.global_rate_limit = datetime.now().timestamp() + retry_after
        self.retry_after = retry_after

    def should_retry(self) -> bool:
        if self.global_rate_limit and datetime.now().timestamp() < self.global_rate_limit:
            return False
        return True

    def get_retry_after(self) -> Optional[float]:
        if self.global_rate_limit:
            return max(0, self.global_rate_limit - datetime.now().timestamp())
        return None

class KruzBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None,  # Disable default help command
            reconnect=True,  # Enable auto-reconnect
            max_messages=10000  # Increase message cache to help with latency
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
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.rate_limit_tracker = RateLimitTracker()
        self.rate_limit_retries = 0
        self.max_rate_limit_retries = 3

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

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        """Handle any uncaught errors"""
        error = kwargs.get('error')
        if isinstance(error, discord.HTTPException):
            if error.status == 429:  # Rate limit
                retry_after = float(error.retry_after)
                self.rate_limit_tracker.update_global_limit(retry_after)
                logger.warning(f"Rate limit hit. Retry after {retry_after} seconds")
                
                if self.rate_limit_retries < self.max_rate_limit_retries:
                    self.rate_limit_retries += 1
                    await asyncio.sleep(retry_after)
                    try:
                        await self.close()
                        await self.start(TOKEN)
                    except Exception as e:
                        logger.error(f"Failed to reconnect after rate limit: {e}")
                else:
                    logger.critical("Max rate limit retries reached")
                    await self.close()
            else:
                logger.error(f"HTTP error in {event_method}: {error}")
        else:
            logger.error(f"Uncaught error in {event_method}: {args} {kwargs}")
            if self.reconnect_attempts < self.max_reconnect_attempts:
                self.reconnect_attempts += 1
                try:
                    await self.close()
                    await self.start(TOKEN)
                except Exception as e:
                    logger.error(f"Failed to reconnect: {e}")
            else:
                logger.critical("Max reconnection attempts reached")

    async def on_socket_raw_receive(self, msg):
        """Monitor websocket latency and handle rate limits"""
        if self.ws:
            latency = self.ws.latency
            if latency > 5:  # If latency is over 5 seconds
                logger.warning(f"High websocket latency detected: {latency:.2f}s")
                if latency > 15:  # If latency is over 15 seconds
                    logger.error("Extreme latency detected, attempting reconnect")
                    await self.close()
                    await self.start(TOKEN)

            # Check for rate limit headers
            if hasattr(msg, 'headers'):
                retry_after = msg.headers.get('Retry-After')
                if retry_after:
                    retry_after = float(retry_after)
                    self.rate_limit_tracker.update_global_limit(retry_after)
                    logger.warning(f"Rate limit detected in websocket. Retry after {retry_after} seconds")
                    await asyncio.sleep(retry_after)

    async def on_resumed(self):
        """Handle successful reconnection"""
        logger.info("Session resumed successfully")
        self.reconnect_attempts = 0
        self.rate_limit_retries = 0

    async def on_disconnect(self):
        """Handle disconnection"""
        logger.warning("Bot disconnected from Discord")
    
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

    async def close(self) -> None:
        """Cleanup and close the bot properly"""
        try:
            # Close any active sessions in cogs
            for cog in self.cogs.values():
                if hasattr(cog, 'reddit'):
                    await cog.reddit.close()
                if hasattr(cog, 'session'):
                    await cog.session.close()
            
            # Call parent close
            await super().close()
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

async def main():
    """Main entry point"""
    try:
        async with KruzBot() as bot:
            await bot.start(TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot shutdown by user")
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
