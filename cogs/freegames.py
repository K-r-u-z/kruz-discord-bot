import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import logging
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from config import GUILD_ID, BOT_SETTINGS, FREESTUFF_API_KEY
import time

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

# Add new settings defaults
CURRENCIES = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£"
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
        "currency": "EUR",  # Default currency
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
            if not self.cog.cached_games:
                await interaction.response.edit_message(
                    content="No free games found at the moment!",
                    embed=None,
                    view=self
                )
                return

            # Show first game and add navigation buttons
            self.current_game_index = 0
            embed = self.cog._create_game_embed(self.cog.cached_games[0])
            view = GameListView(self.cog, self.cog.cached_games, self)
            await interaction.response.edit_message(embed=embed, view=view)
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
            
            self.cog.settings.update({
                "channel_id": channel.id,
                "enabled": True
            })
            self.cog._save_settings()
            
            if not self.cog.announce_games.is_running():
                self.cog.announce_games.start()
            
            await interaction.response.edit_message(
                content=f"✅ Free games announcements will now be sent to {channel.mention}!",
                view=self
            )
        except Exception as e:
            logger.error(f"Error in setup channel: {e}")
            await interaction.response.send_message(
                "Failed to setup channel!",
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
        
        if not current_state:
            self.cog.announce_games.start()
        else:
            self.cog.announce_games.cancel()
            
        await interaction.response.send_message(
            f"Free games announcements {'enabled' if not current_state else 'disabled'}!",
            ephemeral=True
        )

    @discord.ui.button(label="🧪 Test", style=discord.ButtonStyle.secondary)
    async def test(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.settings.get("channel_id"):
            await interaction.response.send_message(
                "Please set up a channel first!",
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(self.cog.settings["channel_id"])
        if not channel:
            await interaction.response.send_message(
                "Announcement channel not found! Please setup the channel again.",
                ephemeral=True
            )
            return
        
        test_game = {
            "title": "Test Game",
            "store": "steam",
            "org_price": {"dollar": 19.99},
            "urls": {"default": "https://store.steampowered.com"},
            "description": "This is a test announcement to verify your settings.",
            "thumbnail": {
                "org": "https://cdn.discordapp.com/emojis/1073161249006821406.webp",
                "blank": "https://cdn.discordapp.com/emojis/1073161249006821406.webp",
                "full": "https://cdn.discordapp.com/emojis/1073161249006821406.webp",
                "tags": "https://cdn.discordapp.com/emojis/1073161249006821406.webp"
            },
            "rating": 0.95,
            "until": int(datetime.now().timestamp()) + 86400,
            "copyright": "Test Publisher",
            "worth": 19.99
        }
        embed = self.cog._create_game_embed(test_game)
        await channel.send(embed=embed)
        await interaction.response.send_message(
            "Test message sent!",
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

class FreeGames(commands.Cog):
    """Cog for announcing free games using FreeStuff API"""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.settings_file = 'data/freegames_settings.json'
        self.embed_color = int(BOT_SETTINGS["embed_color"], 16)
        self.settings = self._load_settings()
        self.session: Optional[aiohttp.ClientSession] = None
        self.api_key = FREESTUFF_API_KEY
        self.cached_games = self.settings.get("cached_games", [])
        
        # Start announcement task if enabled
        if self.settings.get("enabled", False):
            self.announce_games.start()

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
                "cached_games": [],  # Make sure this is included
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
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving free games settings: {e}")

    async def cog_load(self) -> None:
        """Initialize aiohttp session when cog loads"""
        self.session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        """Cleanup when cog unloads"""
        if self.session:
            await self.session.close()
        if self.announce_games.is_running():
            self.announce_games.cancel()

    def _format_price(self, price: float) -> str:
        """Format price with currency symbol"""
        currency = self.settings["filters"]["currency"]
        symbol = CURRENCIES.get(currency, "€")  # Get correct symbol for current currency
        return f"{symbol}{price:.2f}"

    def _create_game_embed(self, game: Dict[str, Any]) -> discord.Embed:
        """Create embed for game announcement"""
        store = game.get("store", "").lower()
        store_name = STORE_DISPLAY_NAMES.get(store, store.title())
        store_icon = STORE_ICONS.get(store)
        
        # Format price with current currency setting
        original_price = self._format_price(game.get("org_price", {}).get("dollar", 0))
        
        # Create description with proper formatting
        description = (
            f"> {game.get('description', 'No description available.')}\n\n"
            f"~~{original_price}~~ **Free** until {datetime.fromtimestamp(game.get('until', 0)).strftime('%m/%d/%Y')}\u2000\u2000"
        )
        if rating := game.get("rating"):
            description += f"★ {rating * 10:.1f}/10"
        
        # Add links section with proper spacing
        urls = game.get("urls", {})
        description += "\n\n"
        if browser_url := urls.get("browser"):
            description += f"[**Open in browser ↗**]({browser_url})\u2000\u2000\u2000"
        if client_url := urls.get("client"):
            description += f"[**Open in {store_name} Client ↗**]({client_url})"

        embed = discord.Embed(
            title=game.get("title"),
            description=description,
            color=self.embed_color,
            url=game.get("urls", {}).get("default", "")  # Add URL to title
        )
        
        # Set store icon as thumbnail (right side)
        if store_icon:
            embed.set_thumbnail(url=store_icon)
        
        # Set game image
        if thumbnail_data := game.get("thumbnail"):
            if isinstance(thumbnail_data, dict):
                if image_url := thumbnail_data.get("full") or thumbnail_data.get("org"):
                    embed.set_image(url=image_url)
        
        # Set publisher in footer
        if publisher := game.get("copyright"):
            embed.set_footer(text=f"© {publisher}")
        
        return embed

    @tasks.loop(minutes=15)
    async def announce_games(self) -> None:
        """Check for and announce new free games"""
        if not self.session or not self.api_key:
            return
            
        try:
            # Validate channel
            if not (channel := self.bot.get_channel(self.settings.get("channel_id"))):
                logger.error("Free games announcement channel not found")
                return

            headers = {"Authorization": f"Basic {self.api_key}"}
            
            # Test API connection
            if not await self._make_api_request("https://api.freestuffbot.xyz/v1/ping", headers):
                return

            # Get free games list
            games_response = await self._make_api_request("https://api.freestuffbot.xyz/v1/games/free", headers)
            if not games_response or not games_response.get("success"):
                return
                
            games = games_response.get("data", [])
            logger.info(f"Received {len(games)} game IDs")

            announced = self.settings.get("announced_games", [])
            game_details = []

            # Get game details
            for game_id in games:
                if not isinstance(game_id, (int, str)) or game_id in ["success", "data"]:
                    continue
                    
                if str(game_id) not in announced:
                    if game_info := await self._get_game_details(game_id, headers):
                        game_details.append(game_info)

            # Update cache and announce new games
            await self._update_cache_and_announce(game_details, channel, announced)

        except Exception as e:
            logger.error(f"Error in free games announcement task: {e}")

    async def _update_cache_and_announce(
        self, 
        game_details: List[Dict], 
        channel: discord.TextChannel,
        announced: List[str]
    ) -> None:
        """Update cache and announce new games"""
        try:
            current_time = int(time.time())
            filters = self.settings.get("filters", DEFAULT_SETTINGS["filters"])
            
            # Keep existing non-expired games
            existing_games = [
                game for game in self.cached_games
                if game.get("until", 0) > current_time
            ]
            
            # Add new games to cache and announce
            existing_ids = {game.get("id") for game in existing_games}
            for game in game_details:
                if (game and 
                    game.get("until", 0) > current_time and
                    game.get("id") not in existing_ids and
                    game.get("store", "").lower() in filters.get("stores", []) and
                    (game.get("rating", 0) * 10) >= filters.get("min_rating", 0) and
                    game.get("org_price", {}).get("dollar", 0) >= filters.get("min_price", 0)
                ):
                    existing_games.append(game)
                    existing_ids.add(game.get("id"))
                    
                    if str(game.get("id")) not in announced:
                        try:
                            embed = self._create_game_embed(game)
                            content = "@everyone" if filters.get("notify_roles") else None
                            await channel.send(content=content, embed=embed)
                            announced.append(str(game.get("id")))
                        except Exception as e:
                            logger.error(f"Error announcing game {game.get('id')}: {e}")
            
            # Update cache
            self.cached_games = existing_games
            self.settings["cached_games"] = existing_games
            
            # Update settings
            self.settings["announced_games"] = announced[-100:]
            self._save_settings()
            
            logger.info(f"Updated cache with {len(existing_games)} games")
        except Exception as e:
            logger.error(f"Error updating cache and announcing: {e}")

    @announce_games.before_loop
    async def before_announce(self):
        await self.bot.wait_until_ready()

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
        """List all currently free games from cache"""
        try:
            await interaction.response.defer()
            
            if not self.cached_games:
                await interaction.followup.send("No free games found at the moment!", ephemeral=True)
                return

            logger.info(f"Displaying {len(self.cached_games)} cached games")
            
            for game in self.cached_games:
                embed = self._create_game_embed(game)
                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error listing free games: {e}")
            await interaction.followup.send("An error occurred while fetching free games!", ephemeral=True)

    async def _make_api_request(self, url: str, headers: Dict[str, str], timeout: int = 10) -> Optional[Dict]:
        """Make an API request with proper error handling"""
        try:
            async with self.session.get(url, headers=headers, timeout=timeout) as resp:
                if resp.status == 429:  # Rate limit
                    retry_after = int(resp.headers.get('Retry-After', 60))
                    logger.info(f"Rate limited, retry after {retry_after} seconds")
                    return None
                
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"API request failed: {resp.status} - {error_text}")
                    return None
                    
                return await resp.json()
        except Exception as e:
            logger.error(f"API request error: {e}")
            return None

    async def _get_game_details(self, game_id: str, headers: Dict[str, str]) -> Optional[Dict]:
        """Fetch details for a specific game"""
        url = f"https://api.freestuffbot.xyz/v1/game/{game_id}/info"
        response = await self._make_api_request(url, headers)
        
        if response and response.get("success"):
            return response.get("data", {}).get(str(game_id))
        return None

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
                currency = filters.get("currency", "EUR")
                symbol = CURRENCIES.get(currency, "€")
                
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
        currency = filters.get("currency", "EUR")
        symbol = CURRENCIES.get(currency, "€")
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
        current = filters.get("currency", "EUR")
        
        options = [
            discord.SelectOption(
                label=f"{curr} ({symbol})",
                value=curr,
                default=curr == current
            ) for curr, symbol in CURRENCIES.items()
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
        symbol = CURRENCIES.get(currency, "€")
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
    currency = filters.get("currency", "EUR")
    symbol = CURRENCIES.get(currency, "€")
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