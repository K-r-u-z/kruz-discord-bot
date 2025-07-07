import discord
from discord.ext import commands
from discord import app_commands
import re
from typing import Optional, Dict, List, Set
import json
import os
from datetime import datetime
import logging
from config import BOT_SETTINGS

logger = logging.getLogger(__name__)

class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings_file = 'data/automod_settings.json'
        
        # Initialize trusted domains first (before loading settings)
        self.trusted_domains = {
            # Mainstream news and media
            'bbc.com', 'bbc.co.uk', 'cnn.com', 'reuters.com', 'ap.org', 'npr.org',
            'nytimes.com', 'washingtonpost.com', 'wsj.com', 'usatoday.com',
            'abcnews.go.com', 'cbsnews.com', 'nbcnews.com', 'foxnews.com',
            'msnbc.com', 'pbs.org', 'nbc.com', 'abc.com', 'cbs.com', 'fox.com',
            
            # Tech and social media
            'youtube.com', 'youtu.be', 'twitter.com', 'x.com', 'facebook.com',
            'instagram.com', 'reddit.com', 'linkedin.com', 'github.com',
            'stackoverflow.com', 'medium.com', 'dev.to', 'techcrunch.com',
            'wired.com', 'theverge.com', 'arstechnica.com', 'engadget.com',
            
            # Educational and reference
            'wikipedia.org', 'wikimedia.org', 'khanacademy.org', 'coursera.org',
            'edx.org', 'udemy.com', 'skillshare.com', 'ted.com',
            'scholar.google.com', 'researchgate.net', 'arxiv.org',
            
            # Government and official
            'gov', 'mil', 'edu', 'org', 'net', 'com',
            
            # Gaming and entertainment
            'steam.com', 'steampowered.com', 'epicgames.com', 'ea.com',
            'ubisoft.com', 'activision.com', 'nintendo.com', 'playstation.com',
            'xbox.com', 'twitch.tv', 'discord.com', 'spotify.com', 'netflix.com',
            'amazon.com', 'hulu.com', 'disneyplus.com', 'hbo.com',
            
            # Shopping and services
            'amazon.com', 'ebay.com', 'etsy.com', 'paypal.com', 'stripe.com',
            'shopify.com', 'woocommerce.com', 'squarespace.com', 'wix.com',
            
            # Development and tools
            'google.com', 'googleapis.com', 'microsoft.com', 'azure.com',
            'aws.amazon.com', 'cloudflare.com', 'heroku.com', 'vercel.com',
            'netlify.com', 'gitlab.com', 'bitbucket.org', 'docker.com',
            'kubernetes.io', 'terraform.io', 'ansible.com', 'jenkins.io',
            
            # Additional trusted domains
            'mozilla.org', 'webkit.org', 'chromium.org', 'nodejs.org',
            'python.org', 'java.com', 'oracle.com', 'adobe.com', 'autodesk.com',
            'blender.org', 'gimp.org', 'inkscape.org', 'audacityteam.org',
            'vim.org', 'emacs.org', 'atom.io', 'code.visualstudio.com',
            'jetbrains.com', 'eclipse.org', 'apache.org', 'nginx.org',
            'mysql.com', 'postgresql.org', 'mongodb.com', 'redis.io',
            'elastic.co', 'kibana.org', 'grafana.com', 'prometheus.io'
        }
        
        # Now load settings (which may update trusted_domains)
        self.settings = self._load_settings()
        self.user_warnings = {}  # Store warnings per user: {user_id: warning_count}
        
        # Initialize regex patterns
        self.url_pattern = re.compile(r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)')
        self.bare_domain_pattern = re.compile(r'\b(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)')
        self.invite_pattern = re.compile(r'discord\.gg/[a-zA-Z0-9-]+')
        self.emoji_pattern = re.compile(r'<a?:\w+:\d+>')
        
        # Suspicious patterns that indicate sketchy links
        self.suspicious_patterns = [
            r'bit\.ly', r'tinyurl\.com', r'goo\.gl', r't\.co', r'is\.gd',
            r'v\.gd', r'cli\.gs', r'ow\.ly', r'j\.mp', r'rb\.gy',
            r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}',  # IP addresses
            r'[a-zA-Z0-9-]+\.(tk|ml|ga|cf|gq)',  # Free domains
            r'[a-zA-Z0-9-]+\.(xyz|top|club|site|online|tech|app)',  # Suspicious TLDs
            r'[a-zA-Z0-9-]+\.(ru|cn|br|in|pk|ng|za|eg|ma|dz|tn|ly|sd|so|et|ke|ug|tz|rw|bi|mg|mz|zm|zw|bw|na|sz|ls|st|sc|mu|km|yt|re|io|sh|ac|ta|bv|hm|gs|fk|ai|aw|bl|bm|io|ky|ms|pn|tc|vg|wf|yt)',  # Suspicious country codes
        ]
        
        # Compile suspicious patterns
        self.suspicious_regex = re.compile('|'.join(self.suspicious_patterns), re.IGNORECASE)
        
        # Message tracking for spam detection
        self.message_history: Dict[int, List[Dict]] = {}  # channel_id -> list of messages
        self.max_history = 10  # Keep last 10 messages per channel

    def _is_trusted_domain(self, url: str) -> bool:
        """Check if a URL is from a trusted domain"""
        try:
            from urllib.parse import urlparse
            
            # Add scheme if missing (for bare domains like bit.ly/abc)
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            parsed = urlparse(url.lower())
            domain = parsed.netloc.replace('www.', '')
            
            # Check if domain is in trusted list
            if domain in self.trusted_domains:
                return True
                
            # Check if any part of the domain matches trusted patterns
            for trusted in self.trusted_domains:
                if trusted in domain or domain.endswith('.' + trusted):
                    return True
                    
            return False
        except Exception as e:
            logger.error(f"Error checking trusted domain: {e}")
            return False

    def _is_suspicious_link(self, url: str) -> bool:
        """Check if a URL matches suspicious patterns"""
        try:
            # Check for suspicious patterns
            if self.suspicious_regex.search(url):
                logger.info(f"URL matched suspicious regex: {url}")
                return True
                
            # Check for IP addresses
            from urllib.parse import urlparse
            
            # Add scheme if missing (for bare domains like bit.ly/abc)
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            
            # Check if domain is an IP address
            import ipaddress
            try:
                ipaddress.ip_address(domain)
                logger.info(f"Domain is IP address: {domain}")
                return True
            except ValueError:
                pass
                
            # Check for URL shorteners (often used for malicious links)
            url_shorteners = self.settings.get("rules", {}).get("link_filter", {}).get("url_shorteners", [])
            
            if domain.lower() in url_shorteners:
                logger.info(f"Domain {domain} is a URL shortener, blocking")
                return True
                
            # Check for very long or random-looking domains
            if len(domain) > 50 or domain.count('.') > 3:
                logger.info(f"Domain is too long or has too many dots: {domain}")
                return True
                
            # Check for domains with many numbers (often suspicious)
            if sum(c.isdigit() for c in domain) > len(domain) * 0.3:
                logger.info(f"Domain has too many numbers: {domain}")
                return True
                
            return False
        except Exception as e:
            logger.error(f"Error checking suspicious link: {e}")
            return True  # Err on the side of caution
        
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
                    
                    # Ensure link_filter settings exist
                    if "link_filter" not in settings["rules"]:
                        settings["rules"]["link_filter"] = {
                            "enabled": True,
                            "block_suspicious": True,
                            "allow_trusted_only": False,
                            "punishment": "delete",
                            "url_shorteners": [
                                "bit.ly", "tinyurl.com", "goo.gl", "t.co", "is.gd", "v.gd", "ow.ly",
                                "buff.ly", "adf.ly", "sh.st", "adfly.com", "shorte.st", "shorten.ws",
                                "tiny.cc", "short.to", "moourl.com", "x.co", "snipurl.com", "shorturl.com",
                                "budurl.com", "ping.fm", "post.ly", "just.as", "bkite.com", "snipr.com",
                                "short.ie", "kl.am", "wp.me", "rubyurl.com", "om.ly", "to.ly", "bit.do",
                                "t.umblr.com", "canonicalurl.com", "snurl.com", "ity.im", "q.gs", "po.st",
                                "bc.vc", "twitthis.com", "u.to", "j.mp", "buzurl.com", "cutt.us", "u.bb",
                                "yourls.org", "xlinkz.net", "a.gy", "qr.net", "1url.com", "tweez.me",
                                "vzturl.com", "7vd.cn", "virl.ws", "qr.ae", "adsby.pl", "Digg.com",
                                "redd.it", "tr.im", "Bookmark.com"
                            ]
                        }
                    # Ensure url_shorteners exists in link_filter
                    elif "url_shorteners" not in settings["rules"]["link_filter"]:
                        settings["rules"]["link_filter"]["url_shorteners"] = [
                            "bit.ly", "tinyurl.com", "goo.gl", "t.co", "is.gd", "v.gd", "ow.ly",
                            "buff.ly", "adf.ly", "sh.st", "adfly.com", "shorte.st", "shorten.ws",
                            "tiny.cc", "short.to", "moourl.com", "x.co", "snipurl.com", "shorturl.com",
                            "budurl.com", "ping.fm", "post.ly", "just.as", "bkite.com", "snipr.com",
                            "short.ie", "kl.am", "wp.me", "rubyurl.com", "om.ly", "to.ly", "bit.do",
                            "t.umblr.com", "canonicalurl.com", "snurl.com", "ity.im", "q.gs", "po.st",
                            "bc.vc", "twitthis.com", "u.to", "j.mp", "buzurl.com", "cutt.us", "u.bb",
                            "yourls.org", "xlinkz.net", "a.gy", "qr.net", "1url.com", "tweez.me",
                            "vzturl.com", "7vd.cn", "virl.ws", "qr.ae", "adsby.pl", "Digg.com",
                            "redd.it", "tr.im", "Bookmark.com"
                        ]
                    
                    # Load trusted domains from settings if they exist
                    if "trusted_domains" in settings:
                        self.trusted_domains = set(settings["trusted_domains"])
                    else:
                        # Use default trusted domains if none saved
                        settings["trusted_domains"] = list(self.trusted_domains)
                    
                    return settings
            
            default_settings = {
                "enabled": False,
                "log_channel": None,
                "trusted_domains": list(self.trusted_domains),
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
                    "link_filter": {
                        "enabled": True,
                        "block_suspicious": True,
                        "allow_trusted_only": False,
                        "punishment": "delete",
                        "url_shorteners": [
                            "bit.ly", "tinyurl.com", "goo.gl", "t.co", "is.gd", "v.gd", "ow.ly",
                            "buff.ly", "adf.ly", "sh.st", "adfly.com", "shorte.st", "shorten.ws",
                            "tiny.cc", "short.to", "moourl.com", "x.co", "snipurl.com", "shorturl.com",
                            "budurl.com", "ping.fm", "post.ly", "just.as", "bkite.com", "snipr.com",
                            "short.ie", "kl.am", "wp.me", "rubyurl.com", "om.ly", "to.ly", "bit.do",
                            "t.umblr.com", "canonicalurl.com", "snurl.com", "ity.im", "q.gs", "po.st",
                            "bc.vc", "twitthis.com", "u.to", "j.mp", "buzurl.com", "cutt.us", "u.bb",
                            "yourls.org", "xlinkz.net", "a.gy", "qr.net", "1url.com", "tweez.me",
                            "vzturl.com", "7vd.cn", "virl.ws", "qr.ae", "adsby.pl", "Digg.com",
                            "redd.it", "tr.im", "Bookmark.com"
                        ]
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
            # Update trusted domains in settings before saving
            self.settings["trusted_domains"] = list(self.trusted_domains)
            
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving automod settings: {e}")

    async def _send_ban_log(self, embed: discord.Embed, action_type: str) -> None:
        """Send ban log to the configured channel"""
        try:
            # Get ban log channel ID from settings
            ban_log_channel_id = BOT_SETTINGS.get("moderation", {}).get("ban_log_channel_id")
            
            if not ban_log_channel_id:
                logger.info("No ban log channel configured, skipping automod ban log")
                return
            
            # Get the channel
            channel = self.bot.get_channel(ban_log_channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                logger.warning(f"Ban log channel {ban_log_channel_id} not found or not a text channel")
                return
            
            # Send the log message
            await channel.send(embed=embed)
            logger.info(f"Sent automod {action_type} log to channel {channel.name}")
            
        except Exception as e:
            logger.error(f"Error sending automod ban log: {e}")

    async def _log_violation(self, guild: Optional[discord.Guild], message: discord.Message, 
                           rule: str, details: str, action_taken: str):
        """Log automod violations to the configured channel"""
        log_channel_id = self.settings.get("log_channel")
        
        if not log_channel_id:
            logger.info("No log channel configured, skipping automod violation log")
            return
            
        if not guild:
            logger.warning("No guild available for logging automod violation")
            return
            
        try:
            # Get the log channel using bot.get_channel instead of guild.get_channel
            channel = self.bot.get_channel(log_channel_id)
            if not channel:
                logger.warning(f"Log channel {log_channel_id} not found")
                return
                
            if not isinstance(channel, discord.TextChannel):
                logger.warning(f"Log channel {log_channel_id} is not a text channel")
                return
                
            embed = discord.Embed(
                title="🚫 AutoMod Violation",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="Rule", value=rule, inline=False)
            embed.add_field(name="User", value=f"{message.author.mention} ({message.author.id})", inline=True)
            
            # Handle different channel types
            if isinstance(message.channel, discord.TextChannel):
                channel_mention = message.channel.mention
            else:
                channel_mention = str(message.channel.id)
                
            embed.add_field(name="Channel", value=channel_mention, inline=True)
            embed.add_field(name="Action Taken", value=action_taken, inline=True)
            embed.add_field(name="Details", value=details, inline=False)
            
            if message.content:
                embed.add_field(name="Message Content", value=message.content[:1000], inline=False)
                
            await channel.send(embed=embed)
            logger.info(f"Sent automod violation log to channel {channel.name} ({channel.id})")
            
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
                self.user_warnings[user_id] = self.user_warnings.get(user_id, 0) + 1
                warning_count = self.user_warnings[user_id]
                warning_limit = self.settings["rules"]["spam"]["warning_limit"]
                
                # Send warning to user
                try:
                    guild_name = message.guild.name if message.guild else "Unknown Server"
                    await message.author.send(
                        f"⚠️ **Warning from {guild_name}**\n"
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
                        if isinstance(message.author, discord.Member) and message.guild:
                            await message.author.ban(reason=f"AutoMod: Reached maximum warnings ({warning_limit})")
                            
                            # Send ban log to configured channel
                            log_embed = discord.Embed(
                                title="🔨 User Auto-Banned (Warning System)",
                                description=(
                                    f"**User:** {message.author.mention} (`{message.author.id}`)\n"
                                    f"**Banned By:** AutoMod System\n"
                                    f"**Reason:** Reached maximum warnings ({warning_count}/{warning_limit})\n"
                                    f"**Channel:** {message.channel.mention if isinstance(message.channel, discord.TextChannel) else str(message.channel.id)}\n"
                                    f"**Trigger:** {rule} - {details}"
                                ),
                                color=discord.Color.red(),
                                timestamp=datetime.utcnow()
                            )
                            log_embed.set_footer(text=f"User ID: {message.author.id} | AutoMod Warning System")
                            
                            await self._send_ban_log(log_embed, "warning-system-ban")
                            
                            await self._log_violation(
                                message.guild, 
                                message, 
                                "Warning System", 
                                f"User reached maximum warnings ({warning_count}/{warning_limit})", 
                                "User Banned"
                            )
                            # Reset warnings after ban
                            self.user_warnings[user_id] = 0
                        else:
                            logger.error("Cannot ban user: Not a member or no guild")
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
                    if isinstance(message.author, discord.Member) and message.guild:
                        await message.guild.ban(message.author, reason=f"AutoMod: {rule} - {details}")
                        
                        # Send ban log to configured channel
                        log_embed = discord.Embed(
                            title="🔨 User Auto-Banned (Rule Violation)",
                            description=(
                                f"**User:** {message.author.mention} (`{message.author.id}`)\n"
                                f"**Banned By:** AutoMod System\n"
                                f"**Rule:** {rule}\n"
                                f"**Reason:** {details}\n"
                                f"**Channel:** {message.channel.mention if isinstance(message.channel, discord.TextChannel) else str(message.channel.id)}"
                            ),
                            color=discord.Color.red(),
                            timestamp=datetime.utcnow()
                        )
                        log_embed.set_footer(text=f"User ID: {message.author.id} | AutoMod Rule Violation")
                        
                        await self._send_ban_log(log_embed, "rule-violation-ban")
                        
                        await self._log_violation(message.guild, message, rule, details, "User Banned")
                        return True
                    else:
                        logger.error("Cannot ban user: Not a member or no guild")
                        return False
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
            
        # Skip bot messages
        if message.author.bot:
            return
            
        # Check if user/channel is whitelisted (for non-link filtering)
        is_whitelisted = (
            any(role.id in self.settings["whitelist"]["roles"] for role in message.author.roles) or
            message.channel.id in self.settings["whitelist"]["channels"]
        )
            
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
            
        # Check for spam (skip if whitelisted)
        if not is_whitelisted and self.settings["rules"]["spam"]["enabled"]:
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
                
        # Check for advertising (skip if whitelisted)
        if not is_whitelisted and self.settings["rules"]["advertising"]["enabled"]:
            # Only check if message might contain invites or URLs
            content_lower = message.content.lower()
            has_potential_ads = (
                'discord.gg' in content_lower or
                'http' in content_lower or
                'www.' in content_lower
            )
            
            if has_potential_ads:
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
                    
        # Check for sketchy links - BLOCK EVERYONE including admins and owner
        if self.settings["rules"]["link_filter"]["enabled"]:
            # Only check messages that might contain links (URLs, domains, or suspicious patterns)
            content_lower = message.content.lower()
            has_potential_links = (
                'http' in content_lower or 
                'www.' in content_lower or
                '.' in content_lower or  # Basic domain check
                any(pattern.replace('\\', '').replace('.', '') in content_lower for pattern in self.suspicious_patterns)
            )
            
            if has_potential_links:
                # Find both full URLs and bare domains
                full_urls = self.url_pattern.findall(message.content)
                bare_domains = self.bare_domain_pattern.findall(message.content)
                
                # Combine and deduplicate URLs
                all_urls = list(set(full_urls + bare_domains))
                
                for url in all_urls:
                    # Skip if it's a Discord invite
                    if self.invite_pattern.search(url):
                        continue
                    
                    # Check if domain is trusted FIRST - trusted domains should never be blocked
                    is_trusted = self._is_trusted_domain(url)
                    
                    if is_trusted:
                        # Trusted domains are allowed - no logging needed
                        continue
                        
                    # If allow_trusted_only is enabled, block untrusted domains
                    if self.settings["rules"]["link_filter"]["allow_trusted_only"]:
                        logger.info(f"Blocking untrusted domain: {url}")
                        await self._handle_violation(
                            message,
                            "Link Filter",
                            f"Untrusted domain detected: {url}",
                            self.settings["rules"]["link_filter"]["punishment"]
                        )
                        return
                    
                    # Only check for suspicious patterns if domain is not trusted
                    is_suspicious = self._is_suspicious_link(url)
                    
                    if is_suspicious:
                        logger.info(f"Blocking suspicious link: {url}")
                        await self._handle_violation(
                            message,
                            "Link Filter",
                            f"Suspicious link detected: {url}",
                            self.settings["rules"]["link_filter"]["punishment"]
                        )
                        return
                    
        # Check for banned words (skip if whitelisted)
        if not is_whitelisted and self.settings["rules"]["text_filter"]["enabled"]:
            # Only check if there are banned words configured
            banned_words = self.settings["rules"]["text_filter"]["banned_words"]
            if banned_words:
                content_lower = message.content.lower()
                for word in banned_words:
                    if word.lower() in content_lower:
                        await self._handle_violation(
                            message,
                            "Text Filter",
                            f"Banned word detected: {word}",
                            self.settings["rules"]["text_filter"]["punishment"]
                        )
                        return
                    
        # Check for excessive caps (skip if whitelisted)
        if not is_whitelisted and self.settings["rules"]["caps"]["enabled"]:
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
                    
        # Check for emoji spam (skip if whitelisted)
        if not is_whitelisted and self.settings["rules"]["emoji_spam"]["enabled"]:
            # Only check if message contains emoji characters
            if '<' in message.content and '>' in message.content:
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
            if user_id in self.user_warnings:
                self.user_warnings[user_id] = 0
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
            warning_count = self.user_warnings.get(user_id, 0)
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
        self.add_item(LinkFilterButton(cog))
        self.add_item(TextFilterButton(cog))
        self.add_item(TrustedLinksButton(cog))
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

class LinkFilterButton(discord.ui.Button):
    def __init__(self, cog: AutoMod):
        super().__init__(
            label="Link Filter",
            style=discord.ButtonStyle.secondary,
            emoji="🔗"
        )
        self.cog = cog
        
    async def callback(self, interaction: discord.Interaction):
        modal = LinkFilterModal(self.cog)
        await interaction.response.send_modal(modal)

class LinkFilterModal(discord.ui.Modal, title="Link Filter Settings"):
    def __init__(self, cog: AutoMod):
        super().__init__()
        self.cog = cog
        
        # Get link filter settings with fallbacks
        link_filter_settings = cog.settings.get("rules", {}).get("link_filter", {})
        
        self.enabled = discord.ui.TextInput(
            label="Enable Link Filter",
            placeholder="true/false",
            default=str(link_filter_settings.get("enabled", True)).lower(),
            required=True,
            max_length=5
        )
        
        self.block_suspicious = discord.ui.TextInput(
            label="Block Suspicious Links",
            placeholder="true/false",
            default=str(link_filter_settings.get("block_suspicious", True)).lower(),
            required=True,
            max_length=5
        )
        
        self.allow_trusted_only = discord.ui.TextInput(
            label="Allow Trusted Domains Only",
            placeholder="true/false (if true, only trusted domains allowed)",
            default=str(link_filter_settings.get("allow_trusted_only", False)).lower(),
            required=True,
            max_length=5
        )
        
        self.punishment = discord.ui.TextInput(
            label="Punishment",
            placeholder="delete/warn/mute/ban",
            default=link_filter_settings.get("punishment", "delete"),
            required=True,
            max_length=10
        )
        
        self.add_item(self.enabled)
        self.add_item(self.block_suspicious)
        self.add_item(self.allow_trusted_only)
        self.add_item(self.punishment)
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Update settings
            self.cog.settings["rules"]["link_filter"]["enabled"] = self.enabled.value.lower() == "true"
            self.cog.settings["rules"]["link_filter"]["block_suspicious"] = self.block_suspicious.value.lower() == "true"
            self.cog.settings["rules"]["link_filter"]["allow_trusted_only"] = self.allow_trusted_only.value.lower() == "true"
            self.cog.settings["rules"]["link_filter"]["punishment"] = self.punishment.value.lower()
            
            # Save settings
            self.cog._save_settings()
            
            await interaction.response.send_message(
                "✅ Link filter settings updated successfully!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error saving link filter settings: {e}")
            await interaction.response.send_message("❌ Failed to save link filter settings", ephemeral=True)

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

class TrustedLinksButton(discord.ui.Button):
    def __init__(self, cog: AutoMod):
        super().__init__(
            label="Trusted Links",
            style=discord.ButtonStyle.secondary,
            emoji="✅"
        )
        self.cog = cog
        
    async def callback(self, interaction: discord.Interaction):
        modal = TrustedLinksModal(self.cog)
        await interaction.response.send_modal(modal)

class TrustedLinksModal(discord.ui.Modal):
    def __init__(self, cog: AutoMod):
        super().__init__(title="Trusted Links Settings")
        self.cog = cog
        
        # Add text inputs for trusted domains
        self.trusted_domains_input = discord.ui.TextInput(
            label="Trusted Domains",
            placeholder="Enter trusted domains (comma-separated)",
            default=",".join(cog.trusted_domains),
            style=discord.TextStyle.paragraph,
            required=False
        )
        
        self.add_item(self.trusted_domains_input)
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse the trusted domains from the input
            domains_input = self.trusted_domains_input.value.strip()
            if domains_input:
                new_domains = [
                    domain.strip().lower() for domain in domains_input.split(",")
                    if domain.strip()
                ]
                self.cog.trusted_domains = set(new_domains)
            else:
                self.cog.trusted_domains = set()
            
            # Save the settings
            self.cog._save_settings()
            
            await interaction.response.send_message(
                f"✅ Trusted links updated successfully! ({len(self.cog.trusted_domains)} domains)",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error updating trusted links: {e}")
            await interaction.response.send_message(
                "❌ Failed to update trusted links. Please check your input.",
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