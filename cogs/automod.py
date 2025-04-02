import discord
from discord.ext import commands
from discord import app_commands
import re
from typing import Optional, Dict, List, Set
import json
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings_file = 'data/automod_settings.json'
        self.settings = self._load_settings()
        self.warnings = {}  # Store warnings per user: {user_id: warning_count}
        
        # Initialize regex patterns
        self.url_pattern = re.compile(r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)')
        self.invite_pattern = re.compile(r'discord\.gg/[a-zA-Z0-9-]+')
        self.emoji_pattern = re.compile(r'<a?:\w+:\d+>')
        
        # Message tracking for spam detection
        self.message_history: Dict[int, List[Dict]] = {}  # channel_id -> list of messages
        self.max_history = 10  # Keep last 10 messages per channel
        
    def _load_settings(self) -> Dict:
        """Load automod settings from file or create defaults"""
        try:
            os.makedirs('data', exist_ok=True)
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    # Ensure all required fields exist
                    if "rules" not in settings:
                        settings["rules"] = {}
                    if "spam" not in settings["rules"]:
                        settings["rules"]["spam"] = {}
                    if "warning_limit" not in settings["rules"]["spam"]:
                        settings["rules"]["spam"]["warning_limit"] = 5
                    return settings
            
            default_settings = {
                "enabled": False,
                "log_channel": None,
                "rules": {
                    "spam": {
                        "enabled": True,
                        "max_messages": 5,
                        "time_window": 5,  # seconds
                        "punishment": "delete",  # delete, warn, mute
                        "warning_limit": 5  # Number of warnings before ban
                    },
                    "advertising": {
                        "enabled": True,
                        "block_invites": True,
                        "block_urls": True,
                        "punishment": "delete"
                    },
                    "text_filter": {
                        "enabled": True,
                        "banned_words": [],
                        "punishment": "delete"
                    },
                    "caps": {
                        "enabled": True,
                        "threshold": 0.7,  # 70% caps
                        "min_length": 10,
                        "punishment": "delete"
                    },
                    "emoji_spam": {
                        "enabled": True,
                        "max_emojis": 5,
                        "punishment": "delete"
                    }
                },
                "whitelist": {
                    "roles": [],
                    "channels": []
                }
            }
            
            with open(self.settings_file, 'w') as f:
                json.dump(default_settings, f, indent=4)
            return default_settings
            
        except Exception as e:
            logger.error(f"Error loading automod settings: {e}")
            return {}

    def _save_settings(self):
        """Save current settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving automod settings: {e}")

    async def _log_violation(self, guild: discord.Guild, message: discord.Message, 
                           rule: str, details: str, action_taken: str):
        """Log automod violations to the configured channel"""
        if not self.settings.get("log_channel"):
            return
            
        try:
            channel = guild.get_channel(self.settings["log_channel"])
            if not channel:
                return
                
            embed = discord.Embed(
                title="🚫 AutoMod Violation",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="Rule", value=rule, inline=False)
            embed.add_field(name="User", value=f"{message.author.mention} ({message.author.id})", inline=True)
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            embed.add_field(name="Action Taken", value=action_taken, inline=True)
            embed.add_field(name="Details", value=details, inline=False)
            
            if message.content:
                embed.add_field(name="Message Content", value=message.content[:1000], inline=False)
                
            await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error logging automod violation: {e}")

    async def _handle_violation(self, message: discord.Message, rule: str, 
                              details: str, punishment: str) -> bool:
        """Handle automod violations with appropriate punishments"""
        try:
            if punishment == "delete":
                try:
                    await message.delete()
                except:
                    pass
                await self._log_violation(message.guild, message, rule, details, "Message Deleted")
                return True
                
            elif punishment == "warn":
                # Get current warning count
                user_id = message.author.id
                self.warnings[user_id] = self.warnings.get(user_id, 0) + 1
                warning_count = self.warnings[user_id]
                warning_limit = self.settings["rules"]["spam"]["warning_limit"]
                
                # Send warning to user
                try:
                    await message.author.send(
                        f"⚠️ **Warning from {message.guild.name}**\n"
                        f"You have been warned for violating the following rule:\n"
                        f"**{rule}**: {details}\n"
                        f"Warning count: {warning_count}/{warning_limit}\n"
                        f"Please make sure to follow the server rules to avoid further action."
                    )
                except discord.Forbidden:
                    logger.error("Failed to send warning DM: User has DMs disabled")
                except Exception as e:
                    logger.error(f"Failed to send warning DM: {e}")
                
                try:
                    await message.delete()
                except:
                    pass
                    
                await self._log_violation(message.guild, message, rule, details, f"User Warned ({warning_count}/{warning_limit})")
                
                # Check if user should be banned
                if warning_count >= warning_limit:
                    try:
                        await message.author.ban(reason=f"AutoMod: Reached maximum warnings ({warning_limit})")
                        await self._log_violation(
                            message.guild, 
                            message, 
                            "Warning System", 
                            f"User reached maximum warnings ({warning_count}/{warning_limit})", 
                            "User Banned"
                        )
                        # Reset warnings after ban
                        self.warnings[user_id] = 0
                    except discord.Forbidden:
                        logger.error("Failed to ban user: Missing permissions")
                        await self._log_violation(
                            message.guild, 
                            message, 
                            "Warning System", 
                            f"User reached maximum warnings ({warning_count}/{warning_limit})", 
                            "Ban Failed - Missing Permissions"
                        )
                    except Exception as e:
                        logger.error(f"Failed to ban user: {e}")
                        await self._log_violation(
                            message.guild, 
                            message, 
                            "Warning System", 
                            f"User reached maximum warnings ({warning_count}/{warning_limit})", 
                            "Ban Failed - Error"
                        )
                
                return True
                
            elif punishment == "mute":
                # Implement mute system here
                try:
                    await message.delete()
                except:
                    pass
                await self._log_violation(message.guild, message, rule, details, "User Muted")
                return True
                
            elif punishment == "ban":
                try:
                    # Delete the message first
                    try:
                        await message.delete()
                    except:
                        pass
                    # Then ban the user
                    await message.author.ban(reason=f"AutoMod: {rule} - {details}")
                    await self._log_violation(message.guild, message, rule, details, "User Banned")
                    return True
                except discord.Forbidden:
                    logger.error("Failed to ban user: Missing permissions")
                    await self._log_violation(message.guild, message, rule, details, "Ban Failed - Missing Permissions")
                    return False
                except Exception as e:
                    logger.error(f"Failed to ban user: {e}")
                    await self._log_violation(message.guild, message, rule, details, "Ban Failed - Error")
                    return False
                
            return False
            
        except Exception as e:
            logger.error(f"Error handling automod violation: {e}")
            return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle incoming messages for automod checks"""
        if not self.settings.get("enabled"):
            return
            
        # Skip bot messages and whitelisted users/roles/channels
        if message.author.bot:
            return
            
        # Check whitelist
        if any(role.id in self.settings["whitelist"]["roles"] for role in message.author.roles):
            return
        if message.channel.id in self.settings["whitelist"]["channels"]:
            return
            
        # Initialize message history for channel if needed
        if message.channel.id not in self.message_history:
            self.message_history[message.channel.id] = []
            
        # Add message to history
        self.message_history[message.channel.id].append({
            "timestamp": datetime.utcnow().timestamp(),
            "content": message.content,
            "author": message.author.id,
            "id": message.id
        })
        
        # Trim history
        if len(self.message_history[message.channel.id]) > self.max_history:
            self.message_history[message.channel.id].pop(0)
            
        # Check for spam
        if self.settings["rules"]["spam"]["enabled"]:
            recent_messages = [
                msg for msg in self.message_history[message.channel.id]
                if msg["author"] == message.author.id and
                datetime.utcnow().timestamp() - msg["timestamp"] <= self.settings["rules"]["spam"]["time_window"]
            ]
            
            if len(recent_messages) >= self.settings["rules"]["spam"]["max_messages"]:
                # Get the oldest message timestamp
                oldest_timestamp = min(msg["timestamp"] for msg in recent_messages)
                
                try:
                    # Fetch messages in bulk using channel history
                    messages_to_delete = []
                    async for msg in message.channel.history(
                        limit=100,  # Discord's max limit
                        after=datetime.fromtimestamp(oldest_timestamp),
                        before=datetime.utcnow()
                    ):
                        if msg.author.id == message.author.id:
                            messages_to_delete.append(msg)
                    
                    # Delete messages in chunks of 100
                    for i in range(0, len(messages_to_delete), 100):
                        chunk = messages_to_delete[i:i + 100]
                        try:
                            await message.channel.delete_messages(chunk)
                        except discord.HTTPException as e:
                            logger.error(f"Failed to delete message chunk: {e}")
                            # Try to delete messages individually as fallback
                            for msg in chunk:
                                try:
                                    await msg.delete()
                                except:
                                    pass
                        
                except Exception as e:
                    logger.error(f"Failed to delete spam messages: {e}")
                
                # Clear the message history for this user in this channel
                self.message_history[message.channel.id] = [
                    msg for msg in self.message_history[message.channel.id]
                    if msg["author"] != message.author.id
                ]
                
                # Log only one violation
                await self._handle_violation(
                    message,
                    "Spam",
                    f"User sent {len(recent_messages)} messages in {self.settings['rules']['spam']['time_window']} seconds",
                    self.settings["rules"]["spam"]["punishment"]
                )
                return
                
        # Check for advertising
        if self.settings["rules"]["advertising"]["enabled"]:
            if self.settings["rules"]["advertising"]["block_invites"]:
                if self.invite_pattern.search(message.content):
                    await self._handle_violation(
                        message,
                        "Advertising",
                        "Discord invite link detected",
                        self.settings["rules"]["advertising"]["punishment"]
                    )
                    return
                    
            if self.settings["rules"]["advertising"]["block_urls"]:
                if self.url_pattern.search(message.content):
                    await self._handle_violation(
                        message,
                        "Advertising",
                        "URL detected",
                        self.settings["rules"]["advertising"]["punishment"]
                    )
                    return
                    
        # Check for banned words
        if self.settings["rules"]["text_filter"]["enabled"]:
            for word in self.settings["rules"]["text_filter"]["banned_words"]:
                if word.lower() in message.content.lower():
                    await self._handle_violation(
                        message,
                        "Text Filter",
                        f"Banned word detected: {word}",
                        self.settings["rules"]["text_filter"]["punishment"]
                    )
                    return
                    
        # Check for excessive caps
        if self.settings["rules"]["caps"]["enabled"]:
            if len(message.content) >= self.settings["rules"]["caps"]["min_length"]:
                caps_count = sum(1 for c in message.content if c.isupper())
                if caps_count / len(message.content) >= self.settings["rules"]["caps"]["threshold"]:
                    await self._handle_violation(
                        message,
                        "Excessive Caps",
                        f"Message contains {caps_count}/{len(message.content)} uppercase characters",
                        self.settings["rules"]["caps"]["punishment"]
                    )
                    return
                    
        # Check for emoji spam
        if self.settings["rules"]["emoji_spam"]["enabled"]:
            emoji_count = len(self.emoji_pattern.findall(message.content))
            if emoji_count > self.settings["rules"]["emoji_spam"]["max_emojis"]:
                await self._handle_violation(
                    message,
                    "Emoji Spam",
                    f"Message contains {emoji_count} emojis",
                    self.settings["rules"]["emoji_spam"]["punishment"]
                )
                return

    @app_commands.command(name="automod")
    @app_commands.default_permissions(administrator=True)
    async def automod(self, interaction: discord.Interaction):
        """Configure AutoMod settings"""
        logger.info("AutoMod command triggered")
        await interaction.response.send_message("Loading AutoMod settings...", ephemeral=True)
        
        # Create settings view
        view = AutoModSettingsView(self)
        await interaction.edit_original_response(
            content="AutoMod Settings",
            view=view
        )

    @app_commands.command(name="warningreset")
    @app_commands.default_permissions(administrator=True)
    async def warningreset(self, interaction: discord.Interaction, user: discord.Member):
        """Reset a user's warning count"""
        try:
            user_id = user.id
            if user_id in self.warnings:
                self.warnings[user_id] = 0
                await interaction.response.send_message(
                    f"✅ Reset warning count for {user.mention}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"ℹ️ {user.mention} has no warnings to reset",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error resetting warnings: {e}")
            await interaction.response.send_message(
                "❌ Failed to reset warnings",
                ephemeral=True
            )

    @app_commands.command(name="warnings")
    @app_commands.default_permissions(administrator=True)
    async def warnings(self, interaction: discord.Interaction, user: discord.Member):
        """Check a user's warning count"""
        try:
            user_id = user.id
            warning_count = self.warnings.get(user_id, 0)
            warning_limit = self.settings["rules"]["spam"]["warning_limit"]
            await interaction.response.send_message(
                f"⚠️ {user.mention} has {warning_count}/{warning_limit} warnings",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error checking warnings: {e}")
            await interaction.response.send_message(
                "❌ Failed to check warnings",
                ephemeral=True
            )

class AutoModSettingsView(discord.ui.View):
    def __init__(self, cog: AutoMod):
        super().__init__(timeout=180)
        self.cog = cog
        
        # Add buttons for different settings
        self.add_item(EnableDisableButton(cog))
        self.add_item(LogChannelButton(cog))
        self.add_item(SpamSettingsButton(cog))
        self.add_item(AdvertisingSettingsButton(cog))
        self.add_item(TextFilterButton(cog))
        self.add_item(WhitelistButton(cog))

class EnableDisableButton(discord.ui.Button):
    def __init__(self, cog: AutoMod):
        super().__init__(
            label="Enable/Disable",
            style=discord.ButtonStyle.primary,
            emoji="⚡"
        )
        self.cog = cog
        
    async def callback(self, interaction: discord.Interaction):
        self.cog.settings["enabled"] = not self.cog.settings["enabled"]
        self.cog._save_settings()
        
        status = "enabled" if self.cog.settings["enabled"] else "disabled"
        await interaction.response.send_message(
            f"AutoMod has been {status}!",
            ephemeral=True
        )

class LogChannelButton(discord.ui.Button):
    def __init__(self, cog: AutoMod):
        super().__init__(
            label="Set Log Channel",
            style=discord.ButtonStyle.secondary,
            emoji="📝"
        )
        self.cog = cog
        
    async def callback(self, interaction: discord.Interaction):
        self.cog.settings["log_channel"] = interaction.channel_id
        self.cog._save_settings()
        
        await interaction.response.send_message(
            f"Log channel set to {interaction.channel.mention}!",
            ephemeral=True
        )

class SpamSettingsButton(discord.ui.Button):
    def __init__(self, cog: AutoMod):
        super().__init__(
            label="Spam Settings",
            style=discord.ButtonStyle.secondary,
            emoji="🚫"
        )
        self.cog = cog
        
    async def callback(self, interaction: discord.Interaction):
        modal = SpamSettingsModal(self.cog)
        await interaction.response.send_modal(modal)

class SpamSettingsModal(discord.ui.Modal):
    def __init__(self, cog: AutoMod):
        super().__init__(title="Spam Settings")
        self.cog = cog
        
        # Ensure warning_limit exists in settings
        if "warning_limit" not in self.cog.settings["rules"]["spam"]:
            self.cog.settings["rules"]["spam"]["warning_limit"] = 5
            self.cog._save_settings()
        
        # Add input fields
        self.add_item(discord.ui.TextInput(
            label="Max Messages",
            placeholder="Enter max messages (default: 5)",
            default=str(self.cog.settings["rules"]["spam"].get("max_messages", 5))
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Time Window (seconds)",
            placeholder="Enter time window (default: 5)",
            default=str(self.cog.settings["rules"]["spam"].get("time_window", 5))
        ))
        
        # Add text input for punishment
        self.add_item(discord.ui.TextInput(
            label="Punishment",
            placeholder="Enter punishment (delete/warn/mute/ban)",
            default=self.cog.settings["rules"]["spam"].get("punishment", "delete")
        ))
        
        # Add text input for warning limit
        self.add_item(discord.ui.TextInput(
            label="Warning Limit",
            placeholder="Enter warning limit before ban (default: 5)",
            default=str(self.cog.settings["rules"]["spam"].get("warning_limit", 5))
        ))
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.cog.settings["rules"]["spam"]["max_messages"] = int(self.children[0].value)
            self.cog.settings["rules"]["spam"]["time_window"] = int(self.children[1].value)
            self.cog.settings["rules"]["spam"]["punishment"] = self.children[2].value.lower()
            self.cog.settings["rules"]["spam"]["warning_limit"] = int(self.children[3].value)
            
            self.cog._save_settings()
            
            await interaction.response.send_message(
                "Spam settings updated successfully!",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Invalid input! Please enter valid numbers and punishment type.",
                ephemeral=True
            )

class AdvertisingSettingsButton(discord.ui.Button):
    def __init__(self, cog: AutoMod):
        super().__init__(
            label="Advertising Settings",
            style=discord.ButtonStyle.secondary,
            emoji="🔗"
        )
        self.cog = cog
        
    async def callback(self, interaction: discord.Interaction):
        modal = AdvertisingSettingsModal(self.cog)
        await interaction.response.send_modal(modal)

class AdvertisingSettingsModal(discord.ui.Modal):
    def __init__(self, cog: AutoMod):
        super().__init__(title="Advertising Settings")
        self.cog = cog
        
        # Add text inputs for boolean options
        self.add_item(discord.ui.TextInput(
            label="Block Discord Invites",
            placeholder="true/false",
            default=str(cog.settings["rules"]["advertising"]["block_invites"]).lower()
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Block URLs",
            placeholder="true/false",
            default=str(cog.settings["rules"]["advertising"]["block_urls"]).lower()
        ))
        
        # Add text input for punishment
        self.add_item(discord.ui.TextInput(
            label="Punishment",
            placeholder="Enter punishment (delete/warn/mute/ban)",
            default=cog.settings["rules"]["advertising"]["punishment"]
        ))
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.cog.settings["rules"]["advertising"]["block_invites"] = self.children[0].value.lower() == "true"
            self.cog.settings["rules"]["advertising"]["block_urls"] = self.children[1].value.lower() == "true"
            self.cog.settings["rules"]["advertising"]["punishment"] = self.children[2].value.lower()
            
            self.cog._save_settings()
            
            await interaction.response.send_message(
                "Advertising settings updated successfully!",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Invalid input! Please enter valid boolean values and punishment type.",
                ephemeral=True
            )

class TextFilterButton(discord.ui.Button):
    def __init__(self, cog: AutoMod):
        super().__init__(
            label="Text Filter",
            style=discord.ButtonStyle.secondary,
            emoji="🔍"
        )
        self.cog = cog
        
    async def callback(self, interaction: discord.Interaction):
        modal = TextFilterModal(self.cog)
        await interaction.response.send_modal(modal)

class TextFilterModal(discord.ui.Modal):
    def __init__(self, cog: AutoMod):
        super().__init__(title="Text Filter Settings")
        self.cog = cog
        
        # Add text input for banned words
        self.add_item(discord.ui.TextInput(
            label="Banned Words",
            placeholder="Enter banned words (comma-separated)",
            default=",".join(cog.settings["rules"]["text_filter"]["banned_words"])
        ))
        
        # Add text input for punishment
        self.add_item(discord.ui.TextInput(
            label="Punishment",
            placeholder="Enter punishment (delete/warn/mute/ban)",
            default=cog.settings["rules"]["text_filter"]["punishment"]
        ))
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.cog.settings["rules"]["text_filter"]["banned_words"] = [
                word.strip() for word in self.children[0].value.split(",")
                if word.strip()
            ]
            self.cog.settings["rules"]["text_filter"]["punishment"] = self.children[1].value.lower()
            
            self.cog._save_settings()
            
            await interaction.response.send_message(
                "Text filter settings updated successfully!",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Invalid input! Please check your settings.",
                ephemeral=True
            )

class WhitelistButton(discord.ui.Button):
    def __init__(self, cog: AutoMod):
        super().__init__(
            label="Whitelist",
            style=discord.ButtonStyle.secondary,
            emoji="✅"
        )
        self.cog = cog
        
    async def callback(self, interaction: discord.Interaction):
        modal = WhitelistModal(self.cog)
        await interaction.response.send_modal(modal)

class WhitelistModal(discord.ui.Modal):
    def __init__(self, cog: AutoMod):
        super().__init__(title="Whitelist Settings")
        self.cog = cog
        
        # Add text inputs for role and channel IDs
        self.add_item(discord.ui.TextInput(
            label="Whitelisted Roles",
            placeholder="Enter role IDs (comma-separated)",
            default=",".join(map(str, cog.settings["whitelist"]["roles"]))
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Whitelisted Channels",
            placeholder="Enter channel IDs (comma-separated)",
            default=",".join(map(str, cog.settings["whitelist"]["channels"]))
        ))
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.cog.settings["whitelist"]["roles"] = [
                int(role_id.strip()) for role_id in self.children[0].value.split(",")
                if role_id.strip()
            ]
            self.cog.settings["whitelist"]["channels"] = [
                int(channel_id.strip()) for channel_id in self.children[1].value.split(",")
                if channel_id.strip()
            ]
            
            self.cog._save_settings()
            
            await interaction.response.send_message(
                "Whitelist settings updated successfully!",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Invalid input! Please enter valid role and channel IDs.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    logger.info("Setting up AutoMod cog...")
    try:
        await bot.add_cog(AutoMod(bot))
        logger.info("AutoMod cog loaded successfully")
        
        # Sync commands for this cog
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
        
        # Log all registered commands
        for cmd in bot.tree.get_commands():
            logger.info(f"Registered command: {cmd.name}")
            
    except Exception as e:
        logger.error(f"Error setting up AutoMod cog: {e}")
        raise e 