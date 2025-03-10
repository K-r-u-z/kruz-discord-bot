import discord
from discord.ext import commands
import asyncio
import logging
from typing import List, Dict, Optional, Tuple
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
        # Track rate limits per bucket
        self.buckets: Dict[str, Dict] = {}
        # Track route to bucket mapping
        self.route_buckets: Dict[str, str] = {}
        # Global rate limit tracking
        self.global_rate_limit: Optional[float] = None
        # Track message rate limits per channel
        self.message_limits: Dict[str, Dict] = {}
        logger.info("Discord rate limit tracking system initialized")
        logger.info(
            "Discord Rate Limits:\n"
            "  • Messages: 5 per 5s per channel\n"
            "  • Global: 50 messages per second\n"
            "  • Guild operations: Varies by endpoint\n"
            "  • Bucket-based tracking enabled"
        )
        
    def _parse_reset_time(self, reset_after: Optional[float] = None, reset_time: Optional[float] = None) -> float:
        """Calculate reset time from either reset-after or reset timestamp"""
        if reset_after is not None:
            return datetime.now().timestamp() + float(reset_after)
        elif reset_time is not None:
            return float(reset_time)
        return datetime.now().timestamp() + 60  # Default 60s fallback

    def update_bucket(self, headers: Dict[str, str], route: str) -> None:
        """Update rate limit info from response headers"""
        try:
            bucket = headers.get('X-RateLimit-Bucket')
            if not bucket:
                return

            # Map route to bucket
            self.route_buckets[route] = bucket
            
            # Update bucket information
            limit = int(headers.get('X-RateLimit-Limit', 0))
            remaining = int(headers.get('X-RateLimit-Remaining', 0))
            reset = self._parse_reset_time(
                reset_after=headers.get('X-RateLimit-Reset-After'),
                reset_time=headers.get('X-RateLimit-Reset')
            )
            scope = headers.get('X-RateLimit-Scope', 'user')
            
            # Check if this is a message endpoint
            is_message_endpoint = 'messages' in route.lower()
            endpoint_type = "Message Endpoint" if is_message_endpoint else "General Endpoint"
            
            self.buckets[bucket] = {
                'limit': limit,
                'remaining': remaining,
                'reset': reset,
                'scope': scope,
                'last_updated': datetime.now().timestamp(),
                'is_message': is_message_endpoint
            }

            # Log rate limit status with more context
            reset_time = datetime.fromtimestamp(reset).strftime('%H:%M:%S')
            logger.info(
                f"Discord Rate Limit Status ({endpoint_type}):\n"
                f"  • Route: {route}\n"
                f"  • Bucket: {bucket}\n"
                f"  • Limit: {limit}\n"
                f"  • Remaining: {remaining}\n"
                f"  • Reset at: {reset_time}\n"
                f"  • Scope: {scope}"
            )

            # Special handling for message endpoints
            if is_message_endpoint and remaining < 3:  # Warning earlier for messages
                logger.warning(
                    f"Discord Message Rate Limit Warning:\n"
                    f"  • Only {remaining}/{limit} messages remaining\n"
                    f"  • Route: {route}\n"
                    f"  • Resets at {reset_time}"
                )
            # General warning if running low
            elif remaining < 5:
                logger.warning(
                    f"Discord Rate Limit Warning:\n"
                    f"  • Only {remaining}/{limit} requests remaining\n"
                    f"  • Route: {route}\n"
                    f"  • Resets at {reset_time}"
                )

        except Exception as e:
            logger.error(f"Error updating Discord rate limit bucket: {e}")

    def update_global_limit(self, retry_after: float) -> None:
        """Update global rate limit"""
        self.global_rate_limit = datetime.now().timestamp() + float(retry_after)
        reset_time = datetime.fromtimestamp(self.global_rate_limit).strftime('%H:%M:%S')
        logger.warning(
            f"Discord Global Rate Limit Hit:\n"
            f"  • Cooling down for {retry_after:.2f} seconds\n"
            f"  • Will reset at {reset_time}\n"
            f"  • All requests will be paused"
        )

    def get_bucket_info(self, route: str) -> Optional[Dict]:
        """Get rate limit info for a route"""
        bucket = self.route_buckets.get(route)
        if bucket:
            return self.buckets.get(bucket)
        return None

    def should_retry(self, route: str) -> Tuple[bool, Optional[float]]:
        """Check if a request should be retried and get wait time"""
        now = datetime.now().timestamp()
        
        # Check global rate limit
        if self.global_rate_limit and now < self.global_rate_limit:
            wait_time = self.global_rate_limit - now
            reset_time = datetime.fromtimestamp(self.global_rate_limit).strftime('%H:%M:%S')
            logger.info(
                f"Global rate limit check for {route}:\n"
                f"  • Must wait {wait_time:.2f}s\n"
                f"  • Reset at {reset_time}"
            )
            return False, wait_time
            
        # Check bucket-specific rate limit
        bucket_info = self.get_bucket_info(route)
        if bucket_info:
            remaining = bucket_info['remaining']
            reset_time = datetime.fromtimestamp(bucket_info['reset']).strftime('%H:%M:%S')
            
            if remaining == 0 and now < bucket_info['reset']:
                wait_time = bucket_info['reset'] - now
                logger.info(
                    f"Rate limit check for {route}:\n"
                    f"  • No requests remaining\n"
                    f"  • Must wait {wait_time:.2f}s\n"
                    f"  • Reset at {reset_time}"
                )
                return False, wait_time
                
            if remaining < 1:
                wait_time = bucket_info['reset'] - now
                logger.info(
                    f"Rate limit check for {route}:\n"
                    f"  • {remaining} requests remaining\n"
                    f"  • Must wait {wait_time:.2f}s\n"
                    f"  • Reset at {reset_time}"
                )
                return False, wait_time
            
            logger.info(
                f"Rate limit check for {route}:\n"
                f"  • {remaining} requests remaining\n"
                f"  • Resets at {reset_time}"
            )
        else:
            logger.info(f"No rate limit info for route: {route}")
        
        return True, None

    async def handle_rate_limit(self, error: discord.HTTPException) -> bool:
        """Handle rate limit error and return True if handled"""
        if error.status == 429:
            headers = error.response.headers
            retry_after = float(headers.get('Retry-After', 60))
            is_global = headers.get('X-RateLimit-Global', 'false').lower() == 'true'
            scope = headers.get('X-RateLimit-Scope', 'user')
            bucket = headers.get('X-RateLimit-Bucket', 'unknown')
            
            reset_time = datetime.fromtimestamp(
                datetime.now().timestamp() + retry_after
            ).strftime('%H:%M:%S')
            
            if is_global:
                self.update_global_limit(retry_after)
                logger.warning(
                    f"Discord Global Rate Limit Hit:\n"
                    f"  • Scope: {scope}\n"
                    f"  • Retry after: {retry_after:.2f}s\n"
                    f"  • Reset at: {reset_time}\n"
                    f"  • Global cooldown initiated"
                )
            else:
                # Update bucket information
                self.update_bucket(headers, error.response.url.path)
                endpoint_type = "Message Endpoint" if 'messages' in error.response.url.path.lower() else "General Endpoint"
                logger.warning(
                    f"Discord Rate Limit Hit ({endpoint_type}):\n"
                    f"  • Scope: {scope}\n"
                    f"  • Bucket: {bucket}\n"
                    f"  • Retry after: {retry_after:.2f}s\n"
                    f"  • Reset at: {reset_time}\n"
                    f"  • Route: {error.response.url.path}"
                )
            
            # Use exponential backoff for retries
            backoff_retry = min(retry_after * 1.5, 300)  # Cap at 5 minutes
            logger.info(
                f"Applying Discord rate limit backoff:\n"
                f"  • Base retry: {retry_after:.2f}s\n"
                f"  • With backoff: {backoff_retry:.2f}s"
            )
            await asyncio.sleep(backoff_retry)
            return True
            
        return False

    async def before_request(self, route: str) -> bool:
        """Check rate limits before making a request"""
        logger.info(f"Checking Discord rate limits for: {route}")
        should_proceed, wait_time = self.should_retry(route)
        if not should_proceed:
            logger.warning(
                f"Discord Rate Limit Prevention:\n"
                f"  • Route: {route}\n"
                f"  • Waiting: {wait_time:.2f}s\n"
                f"  • Type: {'Message' if 'messages' in route.lower() else 'General'}"
            )
            await asyncio.sleep(wait_time)
        return should_proceed

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
        logger.info("Rate limit tracking system initialized for bot")

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
                handled = await self.rate_limit_tracker.handle_rate_limit(error)
                if handled and self.rate_limit_retries < self.max_rate_limit_retries:
                    self.rate_limit_retries += 1
                    try:
                        # Retry the operation that failed
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

            # Update rate limit tracking from headers
            if isinstance(msg, dict) and 'headers' in msg:
                headers = msg['headers']
                route = msg.get('route', '')
                
                # Update bucket information from headers
                self.rate_limit_tracker.update_bucket(headers, route)
                
                # Handle rate limit if present
                if 'Retry-After' in headers:
                    retry_after = float(headers['Retry-After'])
                    is_global = headers.get('X-RateLimit-Global', 'false').lower() == 'true'
                    
                    if is_global:
                        self.rate_limit_tracker.update_global_limit(retry_after)
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
