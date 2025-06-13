import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import logging
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from config import GUILD_ID, BOT_SETTINGS, FREESTUFF_REST_API_KEY, FREESTUFF_PUBLIC_KEY, YOUR_WEBHOOK_URL
import time
import re

logger = logging.getLogger(__name__)
GUILD = discord.Object(id=GUILD_ID)

# Store configuration
STORE_ICONS = {
    "steam": "https://cdn.discordapp.com/emojis/1073161249006821406.webp",
    "epic": "https://cdn.discordapp.com/emojis/1073161237652848670.webp",
    "gog": "https://cdn.discordapp.com/emojis/1073161243067899924.webp",
    "humble": "https://cdn.discordapp.com/emojis/1073161245387014174.webp",
    "itch": "https://cdn.discordapp.com/emojis/1073161246947942440.webp",
    "origin": "https://cdn.discordapp.com/emojis/1073161248088334356.webp",
    "uplay": "https://cdn.discordapp.com/emojis/1073161250638725191.webp",
    "battlenet": "https://cdn.discordapp.com/emojis/1073161239041347604.webp"
}

STORE_DISPLAY_NAMES = {
    "battlenet": "Battle.net",
    "uplay": "Ubisoft",
    "gog": "GOG",
    "itch": "itch.io"
}

# Replace the CURRENCIES dict with all currencies from the provided FreeStuff payload
FREESTUFF_CURRENCIES = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "BRL": "R$",
    "BGN": "лв",
    "PLN": "zł",
    "HUF": "Ft",
    "BTC": "₿"
}

DEFAULT_SETTINGS = {
    "enabled": False,
    "channel_id": None,
    "announced_games": [],
    "webhook_secret": None,
    "cached_games": [],
    "filters": {
        "min_rating": 0,  # Minimum rating to announce (0-10)
        "min_price": 0,   # Minimum original price to announce
        "currency": "USD",  # Default currency
        "stores": ["steam", "epic", "gog", "humble", "itch", "origin", "uplay", "battlenet"],  # Enabled stores
        "notify_roles": []  # List of role IDs to ping
    }
}

# Custom Exceptions
class FreeGamesError(Exception):
    """Base exception for FreeGames cog"""
    pass

class ChannelNotFoundError(FreeGamesError):
    """Raised when announcement channel is not found"""
    pass

class APIError(FreeGamesError):
    """Raised when API request fails"""
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"API Error {status}: {message}")

class RateLimitError(APIError):
    """Raised when API rate limit is hit"""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(429, f"Rate limited, retry after {retry_after} seconds")

class BaseSettingsView(discord.ui.View):
    def __init__(self, cog: 'FreeGames', previous_view=None):
        super().__init__(timeout=120)
        self.cog = cog
        self.previous_view = previous_view

    @discord.ui.button(label="◀️ Back", style=discord.ButtonStyle.gray, row=4)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.previous_view:
            await interaction.response.edit_message(
                content=None,
                embed=discord.Embed(
                    title="Free Games Settings",
                    description="Click a button below to manage free games announcements:",
                    color=self.cog.embed_color
                ),
                view=self.previous_view
            )

class FreeGamesSettingsView(BaseSettingsView):
    def __init__(self, cog: 'FreeGames'):
        super().__init__(cog, None)
        self.remove_item(self.back_button)
        # Check if channel is already set
        self.has_channel = bool(cog.settings.get("channel_id"))
        
        # Update button labels based on current state
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.callback == self.setup_channel:
                item.label = "📌 Change Channel" if self.has_channel else "📌 Setup Channel"

    @discord.ui.button(label="📋 List Free Games", style=discord.ButtonStyle.primary)
    async def list_games(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.cog.show_free_games(interaction)
        except Exception as e:
            logger.error(f"Error listing free games: {e}")
            await interaction.response.edit_message(
                content="An error occurred while fetching free games!",
                embed=None,
                view=self
            )

    @discord.ui.button(label="📌 Change Channel", style=discord.ButtonStyle.secondary)
    async def setup_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            channel = interaction.channel
            current_channel_id = self.cog.settings.get("channel_id")
            
            # If channel is already set to this channel
            if current_channel_id == channel.id:
                await interaction.response.send_message(
                    f"❌ Free games announcements are already set to {channel.mention}!",
                    ephemeral=True
                )
                return
            
            # Check if bot has permissions
            if not channel.permissions_for(channel.guild.me).send_messages:
                await interaction.response.send_message(
                    f"❌ I don't have permission to send messages in {channel.mention}! Please grant me the 'Send Messages' permission.",
                    ephemeral=True
                )
                return
            
            # Verify we can actually send a message
            try:
                test_message = await channel.send("Testing channel access...", delete_after=1)
                await test_message.delete()
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ Failed to verify channel access: {str(e)}",
                    ephemeral=True
                )
                return
            
            self.cog.settings.update({
                "channel_id": channel.id,
                "enabled": True
            })
            self.cog._save_settings()
            
            logger.info(f"Set free games announcement channel to {channel.name} ({channel.id})")
            
            await interaction.response.edit_message(
                content=f"✅ Free games announcements will now be sent to {channel.mention}!",
                view=self
            )
        except Exception as e:
            logger.error(f"Error in setup channel: {e}")
            await interaction.response.send_message(
                f"Failed to setup channel: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(label="⚙️ Change Settings", style=discord.ButtonStyle.secondary)
    async def change_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Create settings embed and view
        embed = create_settings_embed(self.cog)
        view = SettingsConfigView(self.cog, self)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🔄 Toggle", style=discord.ButtonStyle.secondary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_state = self.cog.settings.get("enabled", False)
        self.cog.settings["enabled"] = not current_state
        self.cog._save_settings()
        
        logger.info(f"Free games announcements toggled to {'ENABLED' if not current_state else 'DISABLED'} by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(
            f"Free games announcements {'enabled' if not current_state else 'disabled'}!",
            ephemeral=True
        )

class GameListView(BaseSettingsView):
    def __init__(self, cog: 'FreeGames', games: List[Dict], previous_view=None):
        super().__init__(cog, previous_view)
        self.games = games
        self.current_index = 0
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if len(self.games) > 1:
            if self.current_index > 0:
                self.add_item(discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.primary, custom_id="prev"))
            if self.current_index < len(self.games) - 1:
                self.add_item(discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.primary, custom_id="next"))
        self.add_item(discord.ui.Button(label="◀️ Back to Menu", style=discord.ButtonStyle.gray, custom_id="back"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        custom_id = interaction.data.get("custom_id")
        if custom_id == "prev" and self.current_index > 0:
            self.current_index -= 1
        elif custom_id == "next" and self.current_index < len(self.games) - 1:
            self.current_index += 1
        elif custom_id == "back":
            await interaction.response.edit_message(
                content=None,
                embed=discord.Embed(
                    title="Free Games Settings",
                    description="Click a button below to manage free games announcements:",
                    color=self.cog.embed_color
                ),
                view=self.previous_view
            )
            return True

        self.update_buttons()
        embed = self.cog._create_game_embed(self.games[self.current_index])
        await interaction.response.edit_message(embed=embed, view=self)
        return True

class GameButtonsView(discord.ui.View):
    def __init__(self, urls: List[Dict[str, Any]], store_name: str):
        super().__init__(timeout=None)  # No timeout for persistent buttons
        
        # Add browser button
        browser_url = next((url.get("url") for url in urls if url.get("type") == "browser"), None)
        if browser_url:
            self.add_item(discord.ui.Button(
                label=f"View on {store_name}",
                url=browser_url,
                style=discord.ButtonStyle.link
            ))
        
        # Add client button
        client_url = next((url.get("url") for url in urls if url.get("type") == "client"), None)
        if client_url:
            self.add_item(discord.ui.Button(
                label=f"Open in {store_name} Client",
                url=client_url,
                style=discord.ButtonStyle.link
            ))

    def _create_game_embed(self, product: Dict[str, Any]) -> discord.Embed:
        """Create embed for game announcement"""
        store = product.get("store", "").lower()
        store_name = STORE_DISPLAY_NAMES.get(store, store.title())
        store_icon = STORE_ICONS.get(store)
        
        # Get price info for the selected currency
        filters = self.cog.settings.get("filters", DEFAULT_SETTINGS["filters"])
        currency = filters.get("currency", "USD").upper()
        prices = product.get("prices", [])
        price_obj = next((p for p in prices if p.get("currency", "").upper() == currency), None)
        if not price_obj and prices:
            price_obj = prices[0]
        if price_obj:
            original_price = self._format_price(price_obj.get("oldValue", 0), price_obj.get("currency", "USD"))
        else:
            original_price = self._format_price(0, currency)

        # Create description with proper formatting
        description = (
            f"> {product.get('description', 'No description available.')}\n\n"
        )

        # Add price and rating on the same line, spaced with em space
        price_line = f"~~{original_price}~~ **Free** until {datetime.fromtimestamp(product.get('until', 0)/1000).strftime('%m/%d/%Y')}"
        if rating := product.get("rating"):
            price_line += f"\u2003★ {rating * 10:.1f}/10"  # \u2003 is an em space
        description += price_line

        # Add clickable markdown links for browser/client, bolded and spaced far apart
        urls = product.get("urls", [])
        main_url = urls[0]["url"] if urls else None
        client_url = None
        if main_url and store == "steam":
            match = re.search(r'(?:app|a)/(\d+)', main_url)
            if match:
                app_id = match.group(1)
                client_url = f"https://freestuffbot.xyz/ext/open-client/steam/{app_id}"

        # Add links inline, bolded, and spaced with em spaces
        description += "\n\n"
        links = []
        if main_url:
            links.append(f"**[View on {store_name} ↗]({main_url})**")
        if client_url:
            links.append(f"**[Open in {store_name} Client ↗]({client_url})**")
        if links:
            description += f"\u2003\u2003".join(links)  # Two em spaces between links

        # Get the first image URL from the images array
        if "images" in product and product["images"]:
            sorted_images = sorted(product["images"], key=lambda x: x.get("priority", 0), reverse=True)
            image_url = sorted_images[0].get("url")
        else:
            image_url = None

        embed = discord.Embed(
            title=product.get("title"),
            description=description,
            color=self.embed_color,
            url=main_url or ""
        )
        
        if store_icon:
            embed.set_thumbnail(url=store_icon)
        
        # Set game image
        if image_url:
            embed.set_image(url=image_url)
        
        # Add tags below the image as a bolded line of inline code, no label
        tags = product.get("tags", [])
        if tags:
            tags_str = " ".join(f"`{tag}`" for tag in tags)
            embed.add_field(name="\u200b", value=f"**{tags_str}**", inline=False)
        
        publisher = product.get("copyright")
        if publisher:
            embed.set_footer(text=f"©️ {publisher}")

        return embed

    async def _post_announcement(self, channel: discord.TextChannel, content: Optional[str], embed: discord.Embed, product: Dict[str, Any]) -> bool:
        """Post announcement with rate limit handling"""
        max_retries = 3
        base_delay = 5.0
        route = f"channels/{channel.id}/messages"
        
        for attempt in range(max_retries):
            try:
                await self.bot.rate_limit_tracker.before_request(route)
                message = await channel.send(content=content, embed=embed)
                
                if hasattr(message, '_response'):
                    self.bot.rate_limit_tracker.update_bucket(
                        message._response.headers,
                        route
                    )
                
                return True
                
            except discord.HTTPException as e:
                if e.status == 429:
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries reached for announcement after rate limit")
                        return False
                    
                    await self.bot.rate_limit_tracker.handle_rate_limit(e)
                    continue
                else:
                    logger.error(f"HTTP error posting announcement: {e}")
                    return False
            except Exception as e:
                logger.error(f"Error posting announcement: {e}")
                return False

        return False

class FreeGames(commands.Cog):
    """Cog for announcing free games using FreeStuff API v2"""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.settings_file = 'data/freegames_settings.json'
        self.embed_color = int(BOT_SETTINGS["embed_color"], 16)
        self.settings = self._load_settings()
        self.session: Optional[aiohttp.ClientSession] = None
        self.api_key = FREESTUFF_REST_API_KEY
        self.cached_games = self.settings.get("cached_games", [])
        self.processed_requests = set(self.settings.get("processed_requests", []))
        self.webhook_url = os.getenv("YOUR_WEBHOOK_URL")
        self.webhook_secret = os.getenv("FREESTUFF_PUBLIC_KEY")
        
        # No need to start announcement task since we're using webhooks
        # The webhook handler is registered in cog_load

    def _load_settings(self) -> Dict[str, Any]:
        """Load free games settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    # Load cached games and filter out expired ones
                    current_time = int(time.time())
                    if "cached_games" in settings:
                        settings["cached_games"] = [
                            game for game in settings["cached_games"]
                            if game.get("until", 0) > current_time
                        ]
                    return settings
            
            # Default settings
            default_settings = {
                "enabled": False,
                "channel_id": None,
                "announced_games": [],
                "webhook_secret": None,
                "cached_games": [],
                "filters": DEFAULT_SETTINGS["filters"]
            }
            
            # Create data directory if it doesn't exist
            os.makedirs('data', exist_ok=True)
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, indent=4, ensure_ascii=False)
            
            return default_settings
            
        except Exception as e:
            logger.error(f"Error loading free games settings: {e}")
            return {}

    def _save_settings(self) -> None:
        """Save settings to file"""
        try:
            # Convert processed_requests set to list for JSON serialization
            self.settings["processed_requests"] = list(self.processed_requests)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving free games settings: {e}")

    @tasks.loop(minutes=1)
    async def webhook_check(self) -> None:
        """Check for new webhook data every minute"""
        try:
            # Check if channel is set up first
            if not self.settings.get("channel_id"):
                return

            if not self.webhook_url:
                logger.error("Webhook URL not configured")
                return

            # Extract token from webhook URL
            token = self.webhook_url.split('/')[-1]
            if not token:
                logger.error("Invalid webhook URL format")
                return
            
            # Get webhook data with increased limit to catch multiple new requests
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://webhook.site/token/{token}/requests?sorting=newest&page=1&per_page=10") as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch webhook data: {response.status}")
                        return

                    data = await response.json()
                    if not data or "data" not in data or not data["data"]:
                        return

                    # Process all requests in reverse order (oldest first)
                    for request in reversed(data["data"]):
                        request_id = request.get("uuid")
                        
                        # Check if we've already processed this request
                        if request_id in self.processed_requests:
                            continue

                        # Parse the content
                        try:
                            payload = json.loads(request["content"])
                        except json.JSONDecodeError:
                            logger.error("Invalid JSON in webhook payload")
                            continue

                        # Check if it's a test message from webhook.site
                        if "Webhook-Id" in request["headers"] and "Webhook-Timestamp" in request["headers"]:
                            # Process test message as a ping event
                            test_payload = {
                                "type": "fsb:event:ping",
                                "timestamp": datetime.utcnow().isoformat(),
                                "data": {
                                    "manual": True,
                                    "test": True,
                                    "webhook_id": request["headers"]["Webhook-Id"]
                                }
                            }
                            await self.handle_webhook(test_payload)
                            self.processed_requests.add(request_id)
                            self._save_settings()  # Save after adding new request ID
                            continue

                        # Process the webhook
                        event_type = payload.get("type")
                        if not event_type:
                            logger.error("No event type found in payload")
                            continue

                        await self.handle_webhook(payload)
                        self.processed_requests.add(request_id)
                        self._save_settings()  # Save after adding new request ID

                    # Keep the set of processed requests from getting too large
                    if len(self.processed_requests) > 1000:
                        self.processed_requests.clear()
                        self._save_settings()  # Save after clearing

        except Exception as e:
            logger.error(f"Error in webhook check: {e}")

    @webhook_check.before_loop
    async def before_webhook_check(self):
        """Wait for bot to be ready before starting webhook check"""
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle incoming webhook messages"""
        # Check if this is a webhook message from FreeStuff
        if not message.webhook_id:
            return

        try:
            # Get the webhook data from the message
            data = {
                "Webhook-Id": message.webhook_id,
                "Webhook-Timestamp": message.created_at.isoformat(),
                "Webhook-Signature": message.author.name,  # FreeStuff puts the signature in the author name
                "X-Compatibility-Date": message.author.discriminator,  # FreeStuff puts the compatibility date in the discriminator
                "payload": message.content  # The actual webhook payload is in the message content
            }

            # Process the webhook
            await self.handle_webhook(data)

        except Exception as e:
            logger.error(f"Error processing webhook message: {e}")

    async def handle_webhook(self, payload: Dict[str, Any]) -> None:
        """Handle incoming webhook data"""
        try:
            # Ignore if payload is not a dict or doesn't have required fields
            if not isinstance(payload, dict) or "type" not in payload:
                return

            event_type = payload.get("type")
            if not event_type:
                return

            if event_type == "fsb:event:ping":
                logger.info("Received ping from FreeStuff API")
                return

            if event_type == "fsb:event:announcement_created":
                products = payload.get("data", {}).get("resolvedProducts", [])
                if not products:
                    logger.error("No products in announcement")
                    return

                for product in products:
                    # Ensure all required fields are present
                    if "urls" not in product:
                        product["urls"] = []
                    if "images" not in product:
                        product["images"] = []
                    if "prices" not in product:
                        product["prices"] = [{"dollar": 0, "currency": "USD"}]
                    if "copyright" not in product:
                        product["copyright"] = ""
                    
                    await self._process_product(product)
                return

            if event_type == "fsb:event:product_updated":
                product = payload.get("data")
                if not product:
                    logger.error("No product data in webhook payload")
                    return

                # Ensure all required fields are present
                if "urls" not in product:
                    product["urls"] = []
                if "images" not in product:
                    product["images"] = []
                if "prices" not in product:
                    product["prices"] = [{"dollar": 0, "currency": "USD"}]
                if "copyright" not in product:
                    product["copyright"] = ""

                await self._process_product(product)
                return

            logger.error(f"Unknown event type: {event_type}")

        except Exception as e:
            logger.error(f"Error handling webhook: {e}")

    def _format_price(self, price: float, currency: str) -> str:
        # For BTC, don't divide by 100
        if currency.upper() == "BTC":
            return f"₿{price:.8f}"
        symbol = FREESTUFF_CURRENCIES.get(currency.upper(), "€")
        return f"{symbol}{price / 100:.2f}"

    def _create_game_embed(self, product: Dict[str, Any]) -> discord.Embed:
        """Create embed for game announcement"""
        store = product.get("store", "").lower()
        store_name = STORE_DISPLAY_NAMES.get(store, store.title())
        store_icon = STORE_ICONS.get(store)
        
        # Get price info for the selected currency
        filters = self.settings.get("filters", DEFAULT_SETTINGS["filters"])
        currency = filters.get("currency", "USD").upper()
        prices = product.get("prices", [])
        price_obj = next((p for p in prices if p.get("currency", "").upper() == currency), None)
        if not price_obj and prices:
            price_obj = prices[0]
        if price_obj:
            original_price = self._format_price(price_obj.get("oldValue", 0), price_obj.get("currency", "USD"))
        else:
            original_price = self._format_price(0, currency)

        # Create description with proper formatting
        description = (
            f"> {product.get('description', 'No description available.')}\n\n"
        )

        # Add price and rating on the same line, spaced with em space
        price_line = f"~~{original_price}~~ **Free** until {datetime.fromtimestamp(product.get('until', 0)/1000).strftime('%m/%d/%Y')}"
        if rating := product.get("rating"):
            price_line += f"\u2003★ {rating * 10:.1f}/10"  # \u2003 is an em space
        description += price_line

        # Add clickable markdown links for browser/client, bolded and spaced far apart
        urls = product.get("urls", [])
        main_url = urls[0]["url"] if urls else None
        client_url = None
        if main_url and store == "steam":
            match = re.search(r'(?:app|a)/(\d+)', main_url)
            if match:
                app_id = match.group(1)
                client_url = f"https://freestuffbot.xyz/ext/open-client/steam/{app_id}"

        # Add links inline, bolded, and spaced with em spaces
        description += "\n\n"
        links = []
        if main_url:
            links.append(f"**[View on {store_name} ↗]({main_url})**")
        if client_url:
            links.append(f"**[Open in {store_name} Client ↗]({client_url})**")
        if links:
            description += f"\u2003\u2003".join(links)  # Two em spaces between links

        # Get the first image URL from the images array
        if "images" in product and product["images"]:
            sorted_images = sorted(product["images"], key=lambda x: x.get("priority", 0), reverse=True)
            image_url = sorted_images[0].get("url")
        else:
            image_url = None

        embed = discord.Embed(
            title=product.get("title"),
            description=description,
            color=self.embed_color,
            url=main_url or ""
        )
        
        if store_icon:
            embed.set_thumbnail(url=store_icon)
        
        # Set game image
        if image_url:
            embed.set_image(url=image_url)
        
        # Add tags below the image as a bolded line of inline code, no label
        tags = product.get("tags", [])
        if tags:
            tags_str = " ".join(f"`{tag}`" for tag in tags)
            embed.add_field(name="\u200b", value=f"**{tags_str}**", inline=False)
        
        publisher = product.get("copyright")
        if publisher:
            embed.set_footer(text=f"©️ {publisher}")

        return embed

    async def _process_product(self, product: Dict[str, Any]) -> None:
        try:
            # First check if channel is set up
            channel_id = self.settings.get("channel_id")
            if not channel_id:
                logger.info("No announcement channel set up yet, skipping product")
                return

            # Check if product meets our filters
            filters = self.settings.get("filters", DEFAULT_SETTINGS["filters"])
            if (product.get("store", "").lower() not in filters.get("stores", []) or
                (product.get("rating", 0) * 10) < filters.get("min_rating", 0) or
                product.get("prices", [{}])[0].get("dollar", 0) < filters.get("min_price", 0)):
                return
            
            channel = None
            try:
                channel = self.bot.get_channel(channel_id)
                
                if not channel:
                    logger.info(f"Channel {channel_id} not in cache, attempting to fetch...")
                    channel = await self.bot.fetch_channel(channel_id)
            except discord.NotFound:
                logger.error(f"Channel {channel_id} not found. The channel may have been deleted.")
                return
            except discord.Forbidden:
                logger.error(f"Bot doesn't have access to channel {channel_id}")
                return
            except Exception as e:
                logger.error(f"Error fetching channel {channel_id}: {e}")
                return

            if not channel:
                logger.error(f"Failed to get channel {channel_id}")
                return

            if not channel.permissions_for(channel.guild.me).send_messages:
                logger.error(f"Bot doesn't have permission to send messages in channel {channel.name} ({channel_id})")
                return

            embed = self._create_game_embed(product)
            
            notify_roles = filters.get("notify_roles", [])
            role_mentions = []
            for role_id in notify_roles:
                if role_id != "everyone":
                    try:
                        role = channel.guild.get_role(int(role_id))
                        if role and role.mentionable:
                            role_mentions.append(role.mention)
                    except (ValueError, AttributeError):
                        continue
            
            content = " ".join(role_mentions) if role_mentions else None
            
            await self._post_announcement(channel, content, embed, product)
            if product not in self.cached_games:
                self.cached_games.append(product)
                self.settings["cached_games"] = self.cached_games
                self._save_settings()
            
        except Exception as e:
            logger.error(f"Error processing product: {e}")

    async def _post_announcement(self, channel: discord.TextChannel, content: Optional[str], embed: discord.Embed, product: Dict[str, Any]) -> bool:
        """Post announcement with rate limit handling"""
        max_retries = 3
        base_delay = 5.0
        route = f"channels/{channel.id}/messages"
        
        for attempt in range(max_retries):
            try:
                await self.bot.rate_limit_tracker.before_request(route)
                message = await channel.send(content=content, embed=embed)
                
                if hasattr(message, '_response'):
                    self.bot.rate_limit_tracker.update_bucket(
                        message._response.headers,
                        route
                    )
                
                return True
                
            except discord.HTTPException as e:
                if e.status == 429:
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries reached for announcement after rate limit")
                        return False
                    
                    await self.bot.rate_limit_tracker.handle_rate_limit(e)
                    continue
                else:
                    logger.error(f"HTTP error posting announcement: {e}")
                    return False
            except Exception as e:
                logger.error(f"Error posting announcement: {e}")
                return False

        return False

    async def fetch_current_free_games(self) -> List[Dict[str, Any]]:
        """Fetch currently free games from FreeStuff API"""
        try:
            if not self.api_key:
                logger.error("No API key configured")
                return []

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
            }

            # Updated API endpoint to the correct one
            async with self.session.get("https://api.freestuffbot.xyz/v2/games/current", headers=headers) as response:
                if response.status == 404:
                    logger.error("API endpoint not found. Please check the FreeStuff API documentation for the correct endpoint.")
                    return []
                elif response.status == 401:
                    logger.error("Invalid API key. Please check your FREESTUFF_REST_API_KEY in the .env file.")
                    return []
                elif response.status != 200:
                    logger.error(f"Failed to fetch games: {response.status} - {await response.text()}")
                    return []

                data = await response.json()
                current_time = int(time.time() * 1000)  # Convert to milliseconds
                
                # Filter for currently free games
                free_games = [
                    game for game in data.get("data", [])
                    if game.get("until", 0) > current_time and
                    game.get("prices", [{}])[0].get("dollar", 0) == 0
                ]
                
                logger.info(f"Found {len(free_games)} currently free games")
                return free_games

        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching free games: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from API: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching current free games: {e}")
            return []

    @app_commands.command(
        name="freegames",
        description="🎮 Free games commands"
    )
    @app_commands.guilds(GUILD)
    @app_commands.checks.has_permissions(administrator=True)
    async def freegames(
        self,
        interaction: discord.Interaction
    ) -> None:
        """Manage free games announcements"""
        embed = discord.Embed(
            title="Free Games Settings",
            description="Click a button below to manage free games announcements:",
            color=self.embed_color
        )
        view = FreeGamesSettingsView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_free_games(self, interaction: discord.Interaction) -> None:
        """List all currently free games from webhook.site"""
        try:
            await interaction.response.defer()
            
            if not self.webhook_url:
                await interaction.followup.send("No webhook URL configured!", ephemeral=True)
                return

            # Extract token from webhook URL
            token = self.webhook_url.split('/')[-1]
            if not token:
                await interaction.followup.send("Invalid webhook URL format!", ephemeral=True)
                return

            # Get webhook data with increased limit
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://webhook.site/token/{token}/requests?sorting=newest&page=1&per_page=50") as response:
                    if response.status != 200:
                        await interaction.followup.send("Failed to fetch webhook data!", ephemeral=True)
                        return

                    data = await response.json()
                    if not data or "data" not in data:
                        await interaction.followup.send("No webhook data found!", ephemeral=True)
                        return
                
                    # Process each request to find game announcements
                    game_announcements = []
                    for request in data.get("data", []):
                        try:
                            content = request.get("content")
                            if not content:
                                continue

                            payload = json.loads(content)
                            event_type = payload.get("type")
                            
                            if event_type == "fsb:event:announcement_created":
                                products = payload.get("data", {}).get("resolvedProducts", [])
                                for product in products:
                                    if product not in game_announcements:
                                        game_announcements.append(product)
                            elif event_type == "fsb:event:product_updated":
                                product = payload.get("data", {})
                                if product and product not in game_announcements:
                                    game_announcements.append(product)
                        except Exception as e:
                            logger.error(f"Error processing webhook request: {e}")
                            continue

                    if not game_announcements:
                        await interaction.followup.send("No free games found in webhook history!", ephemeral=True)
                        return

                    logger.info(f"Displaying {len(game_announcements)} free games from webhook history")
                    
                    # Send initial message to acknowledge the command
                    await interaction.followup.send("Here are the currently free games:", ephemeral=True)
                    
                    # Send each game in a separate message in the channel
                    channel = interaction.channel
                    for game in game_announcements:
                        embed = self._create_game_embed(game)
                        await channel.send(embed=embed)
                    
        except Exception as e:
            logger.error(f"Error listing free games: {e}")
            await interaction.followup.send("An error occurred while fetching free games!", ephemeral=True)

    async def cog_load(self) -> None:
        """Load settings and start webhook check task"""
        try:
            self.settings = self._load_settings()
            self.cached_games = self.settings.get("cached_games", [])
            if not self.webhook_url:
                logger.error("YOUR_WEBHOOK_URL not configured in environment variables")
            if not self.webhook_secret:
                logger.error("FREESTUFF_PUBLIC_KEY not configured in environment variables")
            # Start webhook check task
            self.webhook_check.start()
        except Exception as e:
            logger.error(f"Error loading FreeGames cog: {e}")
            raise e

    async def cog_unload(self) -> None:
        """Stop webhook check task when cog is unloaded"""
        try:
            if self.webhook_check.is_running():
                self.webhook_check.cancel()
            self._save_settings()  # Save settings before unloading
            self.processed_requests.clear()
        except Exception as e:
            logger.error(f"Error stopping webhook check task: {e}")

    def get_available_currencies(self):
        currencies = set()
        for game in self.cached_games:
            for price in game.get("prices", []):
                cur = price.get("currency", "").upper()
                if cur:
                    currencies.add(cur)
        # Always include the statically supported ones as fallback
        currencies.update(FREESTUFF_CURRENCIES.keys())
        return sorted(currencies)

class SettingsConfigView(BaseSettingsView):
    def __init__(self, cog: 'FreeGames', previous_view=None):
        super().__init__(cog, previous_view)

    @discord.ui.button(label="📊 Set Minimum Rating", style=discord.ButtonStyle.secondary)
    async def set_rating(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MinRatingModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="💰 Price Settings", style=discord.ButtonStyle.secondary)
    async def set_price(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PriceSettingsView(self.cog, self)
        await interaction.response.edit_message(
            embed=view.initial_embed,
            view=view
        )

    @discord.ui.button(label="🔔 Notification Settings", style=discord.ButtonStyle.secondary)
    async def notification_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = NotificationSettingsView(self.cog, self)
        view.update_role_select(interaction.guild)
        
        filters = self.cog.settings.get("filters", {})
        notify_roles = filters.get("notify_roles", [])
        
        roles_text = "__**Selected roles to ping:**__\n"
        if "everyone" in notify_roles:
            roles_text += "- @everyone\n"
        
        for role_id in notify_roles:
            if role_id != "everyone":
                if role := interaction.guild.get_role(int(role_id)):
                    roles_text += f"- {role.mention} {'🔔' if role.mentionable else ''}\n"
        
        if not notify_roles:
            roles_text += "*No roles selected*\n"
        
        await interaction.response.edit_message(
            content=roles_text,
            embed=None,
            view=view
        )

    @discord.ui.button(label="🏪 Store Settings", style=discord.ButtonStyle.secondary)
    async def store_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = StoreSettingsView(self.cog, self)
        await interaction.response.edit_message(
            content="Toggle stores to enable/disable:",
            embed=None,
            view=view
        )

class MinRatingModal(discord.ui.Modal, title="Set Minimum Rating"):
    min_rating = discord.ui.TextInput(
        label="Minimum Rating (0-10)",
        placeholder="Enter a number between 0 and 10",
        default="0"
    )

    def __init__(self, cog: 'FreeGames'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rating = float(self.min_rating.value)
            if 0 <= rating <= 10:
                filters = self.cog.settings.setdefault("filters", DEFAULT_SETTINGS["filters"])
                filters["min_rating"] = rating
                self.cog._save_settings()
                await interaction.response.send_message(f"Minimum rating set to {rating}/10!", ephemeral=True)
            else:
                await interaction.response.send_message("Please enter a number between 0 and 10!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Please enter a valid number!", ephemeral=True)

class PriceInputModal(discord.ui.Modal, title="Set Minimum Price"):
    min_price = discord.ui.TextInput(
        label="Minimum Original Price",
        placeholder="Only show games that normally cost more than this",
        default="0"
    )

    def __init__(self, cog: 'FreeGames'):
        super().__init__()
        self.cog = cog
        self.previous_view = None  # Will be set when modal is created

    async def on_submit(self, interaction: discord.Interaction):
        try:
            price = float(self.min_price.value)
            if price >= 0:
                filters = self.cog.settings.setdefault("filters", DEFAULT_SETTINGS["filters"])
                filters["min_price"] = price
                self.cog._save_settings()
                currency = filters.get("currency", "USD")
                symbol = FREESTUFF_CURRENCIES.get(currency, "$")
                
                # Update the price settings view
                embed = discord.Embed(
                    title="Price Settings",
                    description=f"Current currency: {currency} ({symbol})\nMinimum price: {symbol}{price:.2f}",
                    color=self.cog.embed_color
                )
                view = PriceSettingsView(self.cog, self.previous_view)
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message("Please enter a positive number!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Please enter a valid number!", ephemeral=True)

class PriceSettingsView(BaseSettingsView):
    def __init__(self, cog: 'FreeGames', previous_view=None):
        super().__init__(cog, previous_view)
        # Get current currency for display
        filters = cog.settings.get("filters", DEFAULT_SETTINGS["filters"])
        currency = filters.get("currency", "USD")
        symbol = FREESTUFF_CURRENCIES.get(currency, "$")
        price = filters.get("min_price", 0)
        
        # Add currency select with current selection
        currency_select = CurrencySelect(cog)
        currency_select.view_ref = self
        self.add_item(currency_select)
        
        # Add initial embed
        self.initial_embed = discord.Embed(
            title="Price Settings",
            description=f"Current currency: {currency} ({symbol})\nMinimum price: {symbol}{price:.2f}",
            color=cog.embed_color
        )

    @discord.ui.button(label="Set Minimum Price", style=discord.ButtonStyle.primary)
    async def set_price(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PriceInputModal(self.cog)
        modal.previous_view = self.previous_view
        await interaction.response.send_modal(modal)

class CurrencySelect(discord.ui.Select):
    def __init__(self, cog: 'FreeGames'):
        self.cog = cog
        self.view_ref = None  # Will store reference to parent view
        filters = cog.settings.get("filters", {})
        current = filters.get("currency", "USD")
        options = [
            discord.SelectOption(
                label=f"{curr} ({symbol})",
                value=curr,
                default=curr == current
            ) for curr, symbol in FREESTUFF_CURRENCIES.items()
        ]
        super().__init__(
            placeholder=f"Current: {current}",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        filters = self.cog.settings.setdefault("filters", DEFAULT_SETTINGS["filters"])
        filters["currency"] = self.values[0]
        self.cog._save_settings()
        
        # Create a new view with updated currency selection
        new_view = PriceSettingsView(self.cog, self.view_ref.previous_view)
        
        # Update the embed
        currency = self.values[0]
        symbol = FREESTUFF_CURRENCIES.get(currency, "$")
        price = filters.get("min_price", 0)
        embed = discord.Embed(
            title="Price Settings",
            description=f"Current currency: {currency} ({symbol})\nMinimum price: {symbol}{price:.2f}",
            color=self.cog.embed_color
        )
        
        await interaction.response.edit_message(
            embed=embed,
            view=new_view
        )

class RoleSelect(discord.ui.Select):
    def __init__(self, cog: 'FreeGames', guild: discord.Guild):
        self.cog = cog
        filters = cog.settings.get("filters", {})
        notify_roles = filters.get("notify_roles", [])
        
        # Get all server roles except @everyone
        available_roles = [
            role for role in guild.roles
            if not role.is_default() and not role.managed  # Exclude bot roles too
        ]
        
        # Start with @everyone option
        options = [
            discord.SelectOption(
                label="@everyone",
                value="everyone",
                default="everyone" in notify_roles
            )
        ]
        
        # Add top roles (by position) up to Discord's limit of 25 total options
        for role in sorted(available_roles, key=lambda r: r.position, reverse=True)[:24]:  # 24 to leave room for @everyone
            options.append(
                discord.SelectOption(
                    label=role.name,
                    emoji="🔔" if role.mentionable else None,
                    value=str(role.id),
                    default=str(role.id) in notify_roles
                )
            )
        
        super().__init__(
            placeholder="Select roles to ping",
            min_values=0,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        filters = self.cog.settings.setdefault("filters", DEFAULT_SETTINGS["filters"])
        filters["notify_roles"] = self.values
        self.cog._save_settings()
        
        # Update the message to show selected roles
        roles_text = "__**Selected roles to ping:**__\n"
        for value in self.values:
            if value == "everyone":
                roles_text += "- @everyone\n"
            else:
                role = interaction.guild.get_role(int(value))
                if role:
                    roles_text += f"- {role.mention} {'🔔' if role.mentionable else ''}\n"
        
        if not self.values:
            roles_text += "*No roles selected*\n"
        
        await interaction.response.edit_message(content=roles_text, view=self.view)

class StoreSettingsView(BaseSettingsView):
    def __init__(self, cog: 'FreeGames', previous_view=None):
        super().__init__(cog, previous_view)
        self.add_store_buttons()

    def add_store_buttons(self):
        filters = self.cog.settings.setdefault("filters", DEFAULT_SETTINGS["filters"])
        enabled_stores = filters.get("stores", [])
        
        for store in STORE_ICONS.keys():
            button = discord.ui.Button(
                label=STORE_DISPLAY_NAMES.get(store, store.title()),
                style=discord.ButtonStyle.success if store in enabled_stores else discord.ButtonStyle.danger,
                custom_id=f"store_{store}"
            )
            button.callback = self.make_callback(store)
            self.add_item(button)

    def make_callback(self, store: str):
        async def callback(interaction: discord.Interaction):
            filters = self.cog.settings.setdefault("filters", DEFAULT_SETTINGS["filters"])
            stores = filters.setdefault("stores", [])
            
            if store in stores:
                stores.remove(store)
                new_style = discord.ButtonStyle.danger
            else:
                stores.append(store)
                new_style = discord.ButtonStyle.success
                
            self.cog._save_settings()
            
            # Update button style
            for child in self.children:
                if child.custom_id == f"store_{store}":
                    child.style = new_style
                    break
            await interaction.response.edit_message(view=self)
        return callback

class NotificationSettingsView(BaseSettingsView):
    def __init__(self, cog: 'FreeGames', previous_view=None):
        super().__init__(cog, previous_view)
        # Add button for manual role input
        add_role_button = discord.ui.Button(
            label="➕ Add Role Manually",
            style=discord.ButtonStyle.secondary,
            custom_id="add_role_manual"
        )
        add_role_button.callback = self.add_role_manually
        self.add_item(add_role_button)

    def update_role_select(self, guild: discord.Guild):
        """Add role select after guild is available"""
        self.add_item(RoleSelect(self.cog, guild))

    async def add_role_manually(self, interaction: discord.Interaction):
        modal = RoleInputModal(self.cog, self)
        await interaction.response.send_modal(modal)

class RoleInputModal(discord.ui.Modal, title="Add Role by Name/ID"):
    role_input = discord.ui.TextInput(
        label="Role Name or ID",
        placeholder="Enter role name or ID",
        required=True
    )

    def __init__(self, cog: 'FreeGames', view):
        super().__init__()
        self.cog = cog
        self.parent_view = view

    async def on_submit(self, interaction: discord.Interaction):
        input_value = self.role_input.value.strip()
        guild = interaction.guild
        role = None

        # Try to find role by ID first
        if input_value.isdigit():
            role = guild.get_role(int(input_value))

        # If not found by ID, try to find by name
        if not role:
            role = discord.utils.get(guild.roles, name=input_value)

        if not role:
            await interaction.response.send_message(
                "❌ Role not found. Please check the name/ID and try again.",
                ephemeral=True
            )
            return

        # Update notify_roles in settings
        filters = self.cog.settings.setdefault("filters", DEFAULT_SETTINGS["filters"])
        notify_roles = set(filters.get("notify_roles", []))
        role_id = str(role.id)

        if role_id in notify_roles:
            notify_roles.remove(role_id)
            action = "removed from"
        else:
            notify_roles.add(role_id)
            action = "added to"

        filters["notify_roles"] = list(notify_roles)
        self.cog._save_settings()

        # Update the display
        await self._update_roles_display(interaction, role, action)

    async def _update_roles_display(self, interaction: discord.Interaction, role: discord.Role, action: str):
        filters = self.cog.settings.get("filters", {})
        notify_roles = filters.get("notify_roles", [])
        
        roles_text = "__**Selected roles to ping:**__\n"
        if "everyone" in notify_roles:
            roles_text += "- @everyone\n"
        
        for role_id in notify_roles:
            if role_id != "everyone":
                if guild_role := interaction.guild.get_role(int(role_id)):
                    roles_text += f"- {guild_role.mention} {'🔔' if guild_role.mentionable else ''}\n"
        
        if not notify_roles:
            roles_text += "*No roles selected*\n"
        
        await interaction.response.edit_message(
            content=f"✅ Role {role.mention} {action} notification list\n\n{roles_text}",
            view=self.parent_view
        )

def create_settings_embed(cog: 'FreeGames') -> discord.Embed:
    """Create an embed showing current settings"""
    settings = cog.settings
    filters = settings.get("filters", DEFAULT_SETTINGS["filters"])
    
    embed = discord.Embed(
        title="Free Games Settings",
        description="Current settings:",
        color=cog.embed_color
    )
    
    # Add fields for each setting
    embed.add_field(
        name="Channel",
        value=f"<#{settings.get('channel_id', 'Not set')}>",
        inline=True
    )
    embed.add_field(
        name="Status",
        value="✅ Enabled" if settings.get("enabled") else "❌ Disabled",
        inline=True
    )
    
    # Add filter settings
    currency = filters.get("currency", "USD")
    symbol = FREESTUFF_CURRENCIES.get(currency, "$")
    embed.add_field(
        name="Price Filter",
        value=f"Min: {symbol}{filters.get('min_price', 0):.2f}\nCurrency: {currency}",
        inline=True
    )
    embed.add_field(
        name="Rating Filter",
        value=f"Minimum: {filters.get('min_rating', 0)}/10",
        inline=True
    )
    
    # Show available currencies (static)
    currency_list = ", ".join([f"{c} ({s})" for c, s in FREESTUFF_CURRENCIES.items()])
    embed.add_field(
        name="Available Currencies",
        value=currency_list,
        inline=False
    )
    
    # Show notification settings
    notify_roles = filters.get("notify_roles", [])
    roles_text = "None" if not notify_roles else "\n".join([
        "- @everyone" if role == "everyone" else f"- <@&{role}>"
        for role in notify_roles
    ])
    embed.add_field(
        name="Notification Roles",
        value=roles_text,
        inline=False
    )
    
    # Show enabled stores
    enabled_stores = filters.get("stores", [])
    store_text = "\n".join([
        f"{'✅' if store in enabled_stores else '❌'} {STORE_DISPLAY_NAMES.get(store, store.title())}"
        for store in STORE_ICONS.keys()
    ])
    embed.add_field(
        name="Enabled Stores",
        value=store_text,
        inline=False
    )
    
    return embed

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FreeGames(bot)) 