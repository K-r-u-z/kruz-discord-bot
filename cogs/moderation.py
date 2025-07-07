import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging
from config import GUILD_ID, BOT_SETTINGS
import datetime

logger = logging.getLogger(__name__)

class Moderation(commands.Cog):
    """Cog for handling moderation commands and actions"""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.guild = discord.Object(id=GUILD_ID)
        self.embed_color = int(BOT_SETTINGS["embed_color"], 16)

    @app_commands.command(
        name="kruzwarn",
        description="⚠️ Issue a warning to a user"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(
        user="👤 The user to warn",
        rule="📜 The rule that was broken",
        reason="📝 Additional details about the warning"
    )
    @app_commands.checks.has_permissions(kick_members=True)
    async def warn_user(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        rule: str,
        reason: Optional[str] = None
    ) -> None:
        """
        Warn a user and send them a DM with the warning details.
        
        Args:
            interaction: The interaction that triggered the command
            user: The user to warn
            rule: The rule that was broken
            reason: Optional additional context about the warning
        """
        try:
            # Don't allow warning bots or self
            if user.bot:
                await interaction.response.send_message(
                    "Cannot warn bots!",
                    ephemeral=True
                )
                return
                
            if user == interaction.user:
                await interaction.response.send_message(
                    "You cannot warn yourself!",
                    ephemeral=True
                )
                return

            # Create warning embed
            warn_embed = discord.Embed(
                title="⚠️ Warning Issued",
                description=(
                    f"**User:** {user.mention}\n"
                    f"**Rule Broken:** {rule}\n"
                    f"**Warned By:** {interaction.user.mention}\n"
                    f"**Reason:** {reason if reason else 'No reason provided'}"
                ),
                color=self.embed_color
            )
            
            # Try to DM the user
            try:
                await user.send(embed=warn_embed)
                dm_status = "Warning sent via DM"
            except discord.Forbidden:
                dm_status = "Could not DM user (DMs disabled)"
            except Exception as e:
                logger.error(f"Error sending warning DM: {e}")
                dm_status = "Error sending DM"

            # Create log embed with additional info
            log_embed = discord.Embed(
                title="Warning Log",
                description=(
                    f"**Warning sent to:** {user.mention}\n"
                    f"**Rule Broken:** {rule}\n"
                    f"**Warned By:** {interaction.user.mention}\n"
                    f"**Reason:** {reason if reason else 'No reason provided'}\n"
                    f"**DM Status:** {dm_status}"
                ),
                color=self.embed_color,
                timestamp=interaction.created_at
            )
            
            # Send confirmation to moderator
            await interaction.response.send_message(
                embed=log_embed,
                ephemeral=True
            )
            
            # Could also log to a mod-log channel if desired
            # mod_log = interaction.guild.get_channel(MOD_LOG_CHANNEL_ID)
            # if mod_log:
            #     await mod_log.send(embed=log_embed)

        except Exception as e:
            logger.error(f"Error in warn command: {e}")
            await interaction.response.send_message(
                "An error occurred while processing the warning.",
                ephemeral=True
            )

    @warn_user.error
    async def warn_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ) -> None:
        """Handle errors in the warn command"""
        try:
            if isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message(
                    "You need the `Kick Members` permission to use this command!",
                    ephemeral=True
                )
            else:
                logger.error(f"Unexpected error in warn command: {error}")
                await interaction.response.send_message(
                    "An unexpected error occurred.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error handling warn command error: {e}")

    @app_commands.command(
        name="purge",
        description="🗑️ Delete multiple messages from a channel"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(
        amount="🔢 Number of messages to delete (1-100)",
        channel="📝 Channel to purge messages from (defaults to current channel)"
    )
    async def purge_messages(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100],
        channel: Optional[discord.TextChannel] = None
    ) -> None:
        """Purge messages from a channel"""
        await self._handle_purge(interaction, amount, channel)

    @app_commands.command(
        name="cls",
        description="🧹 Clear messages from a channel (defaults to 100)"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(
        amount="Number of messages to delete (1-100, defaults to 100)",
        channel="Channel to purge messages from (defaults to current channel)"
    )
    async def cls_messages(
        self,
        interaction: discord.Interaction,
        amount: Optional[app_commands.Range[int, 1, 100]] = 100,
        channel: Optional[discord.TextChannel] = None
    ) -> None:
        """Alias for purge command with default amount of 100"""
        await self._handle_purge(interaction, amount, channel)

    async def _handle_purge(
        self,
        interaction: discord.Interaction,
        amount: int,
        channel: Optional[discord.TextChannel] = None
    ) -> None:
        """Handle message purging logic"""
        try:
            # Defer the response since this might take a moment
            await interaction.response.defer(ephemeral=True)
            
            # Use current channel if none specified
            target_channel = channel or interaction.channel
            
            # Delete messages
            deleted = await target_channel.purge(
                limit=amount,
                reason=f"Purge command used by {interaction.user}"
            )
            
            # Handle no messages deleted
            if len(deleted) == 0:
                await interaction.followup.send(
                    "❌ No messages to delete!",
                    ephemeral=True
                )
                return
            
            # Send confirmation
            await interaction.followup.send(
                f"✅ Successfully deleted {len(deleted)} messages in {target_channel.mention}",
                ephemeral=True
            )
            
            # Log the action only if messages were deleted
            logger.info(
                f"{interaction.user} purged {len(deleted)} messages in #{target_channel.name}"
            )
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to delete messages in that channel",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error purging messages: {e}")
            await interaction.followup.send(
                "❌ An error occurred while purging messages",
                ephemeral=True
            )

    @purge_messages.error
    async def purge_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ) -> None:
        """Handle errors in the purge command"""
        try:
            if isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message(
                    "You need the `Manage Messages` permission to use this command!",
                    ephemeral=True
                )
            else:
                logger.error(f"Unexpected error in purge command: {error}")
                await interaction.response.send_message(
                    "An unexpected error occurred.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error handling purge command error: {e}")

    @cls_messages.error
    async def cls_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ) -> None:
        """Handle errors in the cls command"""
        try:
            if isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message(
                    "You need the `Manage Messages` permission to use this command!",
                    ephemeral=True
                )
            else:
                logger.error(f"Unexpected error in cls command: {error}")
                await interaction.response.send_message(
                    "An unexpected error occurred.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error handling cls command error: {e}")

    @app_commands.command(
        name="ban",
        description="🔨 Ban a user from the server"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(
        user="👤 The user to ban (ID, mention, or username)",
        reason="📝 Reason for the ban"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban_user(
        self,
        interaction: discord.Interaction,
        user: str,
        reason: Optional[str] = None
    ) -> None:
        """Ban a user from the server"""
        try:
            # Resolve the user from the string input
            user_to_ban = await self._resolve_user(interaction, user)
            
            if not user_to_ban:
                await interaction.response.send_message(
                    f"Could not find user: {user}\nPlease use a user ID, mention, or username.",
                    ephemeral=True
                )
                return

            # Don't allow banning bots or self
            if user_to_ban.bot:
                await interaction.response.send_message(
                    "Cannot ban bots!",
                    ephemeral=True
                )
                return
                
            if user_to_ban == interaction.user:
                await interaction.response.send_message(
                    "You cannot ban yourself!",
                    ephemeral=True
                )
                return

            # Check if user is already banned
            try:
                await interaction.guild.fetch_ban(user_to_ban)
                await interaction.response.send_message(
                    f"{user_to_ban.mention} is already banned!",
                    ephemeral=True
                )
                return
            except discord.NotFound:
                # User is not banned, proceed
                pass

            # Create ban embed
            ban_embed = discord.Embed(
                title="🔨 You have been banned!",
                description=(
                    f"**User:** {user_to_ban.mention}\n"
                    f"**Banned By:** {interaction.user.mention}\n"
                    f"**Reason:** {reason if reason else 'No reason provided'}"
                ),
                color=self.embed_color,
                timestamp=interaction.created_at
            )
            
            # Try to DM the user (only if they're a member)
            dm_status = "Could not DM user (not a member or DMs disabled)"
            if isinstance(user_to_ban, discord.Member):
                try:
                    await user_to_ban.send(embed=ban_embed)
                    dm_status = "Ban notification sent via DM"
                except discord.Forbidden:
                    dm_status = "Could not DM user (DMs disabled)"
                except Exception as e:
                    logger.error(f"Error sending ban DM: {e}")
                    dm_status = "Error sending DM"

            # Ban the user
            await interaction.guild.ban(user_to_ban, reason=reason or f"Banned by {interaction.user}")
            
            # Create confirmation embed
            confirm_embed = discord.Embed(
                title="🔨 User Banned",
                description=(
                    f"**User:** {user_to_ban.mention}\n"
                    f"**Banned By:** {interaction.user.mention}\n"
                    f"**Reason:** {reason if reason else 'No reason provided'}\n"
                    f"**DM Status:** {dm_status}"
                ),
                color=self.embed_color,
                timestamp=interaction.created_at
            )
            
            # Send confirmation
            await interaction.response.send_message(
                embed=confirm_embed,
                ephemeral=True
            )
            
            # Send ban log to configured channel
            log_embed = discord.Embed(
                title="🔨 User Banned",
                description=(
                    f"**User:** {user_to_ban.mention} (`{user_to_ban.id}`)\n"
                    f"**Banned By:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                    f"**Reason:** {reason if reason else 'No reason provided'}\n"
                    f"**DM Status:** {dm_status}\n"
                    f"**Channel:** {interaction.channel.mention}"
                ),
                color=self.embed_color,
                timestamp=interaction.created_at
            )
            log_embed.set_footer(text=f"User ID: {user_to_ban.id}")
            
            await self._send_ban_log(log_embed, "ban")
            
            # Log the ban
            logger.info(f"{interaction.user} banned {user_to_ban} for reason: {reason}")

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to ban users!",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                "User not found or not accessible.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in ban command: {e}")
            await interaction.response.send_message(
                "An error occurred while processing the ban.",
                ephemeral=True
            )

    @ban_user.error
    async def ban_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ) -> None:
        """Handle errors in the ban command"""
        try:
            if isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message(
                    "You need the `Ban Members` permission to use this command!",
                    ephemeral=True
                )
            elif isinstance(error, app_commands.TransformerError):
                await interaction.response.send_message(
                    "Invalid user format. Please use a user ID, mention, or username.",
                    ephemeral=True
                )
            else:
                logger.error(f"Unexpected error in ban command: {error}")
                await interaction.response.send_message(
                    "An unexpected error occurred.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error handling ban command error: {e}")

    @app_commands.command(
        name="tempban",
        description="⏳ Temporarily ban a user from the server"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(
        user="👤 The user to tempban (ID, mention, or username)",
        duration="⏱️ Duration (e.g. 1d, 2h, 30m)",
        reason="📝 Reason for the tempban"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def tempban_user(
        self,
        interaction: discord.Interaction,
        user: str,
        duration: str,
        reason: Optional[str] = None
    ) -> None:
        """Temporarily ban a user from the server"""
        try:
            # Resolve the user from the string input
            user_to_ban = await self._resolve_user(interaction, user)
            
            if not user_to_ban:
                await interaction.response.send_message(
                    f"Could not find user: {user}\nPlease use a user ID, mention, or username.",
                    ephemeral=True
                )
                return

            # Don't allow tempbanning bots or self
            if user_to_ban.bot:
                await interaction.response.send_message(
                    "Cannot tempban bots!",
                    ephemeral=True
                )
                return
                
            if user_to_ban == interaction.user:
                await interaction.response.send_message(
                    "You cannot tempban yourself!",
                    ephemeral=True
                )
                return

            # Check if user is already banned
            try:
                await interaction.guild.fetch_ban(user_to_ban)
                await interaction.response.send_message(
                    f"{user_to_ban.mention} is already banned!",
                    ephemeral=True
                )
                return
            except discord.NotFound:
                # User is not banned, proceed
                pass

            # Parse duration
            try:
                duration_seconds = self._parse_duration(duration)
                if duration_seconds <= 0:
                    raise ValueError("Duration must be positive")
            except ValueError as e:
                await interaction.response.send_message(
                    f"Invalid duration format: {e}\nUse format like: 1d, 2h, 30m",
                    ephemeral=True
                )
                return

            # Calculate unban time
            unban_time = discord.utils.utcnow() + datetime.timedelta(seconds=duration_seconds)

            # Create tempban embed
            tempban_embed = discord.Embed(
                title="⏳ User Tempbanned",
                description=(
                    f"**User:** {user_to_ban.mention}\n"
                    f"**Banned By:** {interaction.user.mention}\n"
                    f"**Duration:** {duration}\n"
                    f"**Unban Time:** <t:{int(unban_time.timestamp())}:R>\n"
                    f"**Reason:** {reason if reason else 'No reason provided'}"
                ),
                color=self.embed_color,
                timestamp=interaction.created_at
            )
            
            # Try to DM the user (only if they're a member)
            dm_status = "Could not DM user (not a member or DMs disabled)"
            if isinstance(user_to_ban, discord.Member):
                try:
                    await user_to_ban.send(embed=tempban_embed)
                    dm_status = "Tempban notification sent via DM"
                except discord.Forbidden:
                    dm_status = "Could not DM user (DMs disabled)"
                except Exception as e:
                    logger.error(f"Error sending tempban DM: {e}")
                    dm_status = "Error sending DM"

            # Ban the user
            await interaction.guild.ban(user_to_ban, reason=f"Tempbanned by {interaction.user} for {duration}. Reason: {reason or 'No reason provided'}")
            
            # Schedule unban
            self.bot.loop.create_task(self._schedule_unban(user_to_ban.id, unban_time))
            
            # Create confirmation embed
            confirm_embed = discord.Embed(
                title="⏳ User Tempbanned",
                description=(
                    f"**User:** {user_to_ban.mention}\n"
                    f"**Banned By:** {interaction.user.mention}\n"
                    f"**Duration:** {duration}\n"
                    f"**Unban Time:** <t:{int(unban_time.timestamp())}:R>\n"
                    f"**Reason:** {reason if reason else 'No reason provided'}\n"
                    f"**DM Status:** {dm_status}"
                ),
                color=self.embed_color,
                timestamp=interaction.created_at
            )
            
            # Send confirmation
            await interaction.response.send_message(
                embed=confirm_embed,
                ephemeral=True
            )
            
            # Send tempban log to configured channel
            log_embed = discord.Embed(
                title="⏳ User Tempbanned",
                description=(
                    f"**User:** {user_to_ban.mention} (`{user_to_ban.id}`)\n"
                    f"**Banned By:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                    f"**Duration:** {duration}\n"
                    f"**Unban Time:** <t:{int(unban_time.timestamp())}:R>\n"
                    f"**Reason:** {reason if reason else 'No reason provided'}\n"
                    f"**DM Status:** {dm_status}\n"
                    f"**Channel:** {interaction.channel.mention}"
                ),
                color=self.embed_color,
                timestamp=interaction.created_at
            )
            log_embed.set_footer(text=f"User ID: {user_to_ban.id} | Unban Time: {unban_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            await self._send_ban_log(log_embed, "tempban")
            
            # Log the tempban
            logger.info(f"{interaction.user} tempbanned {user_to_ban} for {duration}. Reason: {reason}")

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to ban users!",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                "User not found or not accessible.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in tempban command: {e}")
            await interaction.response.send_message(
                "An error occurred while processing the tempban.",
                ephemeral=True
            )

    @tempban_user.error
    async def tempban_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ) -> None:
        """Handle errors in the tempban command"""
        try:
            if isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message(
                    "You need the `Ban Members` permission to use this command!",
                    ephemeral=True
                )
            elif isinstance(error, app_commands.TransformerError):
                await interaction.response.send_message(
                    "Invalid user format. Please use a user ID, mention, or username.",
                    ephemeral=True
                )
            else:
                logger.error(f"Unexpected error in tempban command: {error}")
                await interaction.response.send_message(
                    "An unexpected error occurred.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error handling tempban command error: {e}")

    @app_commands.command(
        name="unban",
        description="🔓 Unban a user from the server"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(
        user="👤 The user to unban (ID or username#discriminator)",
        reason="📝 Reason for the unban"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban_user(
        self,
        interaction: discord.Interaction,
        user: str,
        reason: Optional[str] = None
    ) -> None:
        """Unban a user from the server"""
        try:
            # Get banned users
            banned_users = [entry async for entry in interaction.guild.bans()]
            
            # Try to find the user
            user_to_unban = None
            try:
                # Try to parse as user ID
                user_id = int(user)
                user_to_unban = discord.utils.get(banned_users, user__id=user_id)
            except ValueError:
                # Try to parse as username#discriminator
                for ban_entry in banned_users:
                    if str(ban_entry.user) == user:
                        user_to_unban = ban_entry
                        break
            
            if not user_to_unban:
                await interaction.response.send_message(
                    f"Could not find banned user: {user}",
                    ephemeral=True
                )
                return

            # Unban the user
            await interaction.guild.unban(
                user_to_unban.user,
                reason=f"Unbanned by {interaction.user}. Reason: {reason or 'No reason provided'}"
            )
            
            # Create unban embed
            unban_embed = discord.Embed(
                title="🔓 User Unbanned",
                description=(
                    f"**User:** {user_to_unban.user.mention}\n"
                    f"**Unbanned By:** {interaction.user.mention}\n"
                    f"**Reason:** {reason if reason else 'No reason provided'}"
                ),
                color=self.embed_color,
                timestamp=interaction.created_at
            )
            
            # Send confirmation
            await interaction.response.send_message(
                embed=unban_embed,
                ephemeral=True
            )
            
            # Send unban log to configured channel
            log_embed = discord.Embed(
                title="🔓 User Unbanned",
                description=(
                    f"**User:** {user_to_unban.user.mention} (`{user_to_unban.user.id}`)\n"
                    f"**Unbanned By:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                    f"**Reason:** {reason if reason else 'No reason provided'}\n"
                    f"**Channel:** {interaction.channel.mention}"
                ),
                color=self.embed_color,
                timestamp=interaction.created_at
            )
            log_embed.set_footer(text=f"User ID: {user_to_unban.user.id}")
            
            await self._send_ban_log(log_embed, "unban")
            
            # Log the unban
            logger.info(f"{interaction.user} unbanned {user_to_unban.user} for reason: {reason}")

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to unban users!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in unban command: {e}")
            await interaction.response.send_message(
                "An error occurred while processing the unban.",
                ephemeral=True
            )

    @unban_user.error
    async def unban_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ) -> None:
        """Handle errors in the unban command"""
        try:
            if isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message(
                    "You need the `Ban Members` permission to use this command!",
                    ephemeral=True
                )
            else:
                logger.error(f"Unexpected error in unban command: {error}")
                await interaction.response.send_message(
                    "An unexpected error occurred.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error handling unban command error: {e}")

    @app_commands.command(
        name="setbanlog",
        description="🔧 Set the ban log channel for moderation actions"
    )
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(
        channel="📝 The channel to send ban logs to (use 'none' to disable)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_ban_log_channel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ) -> None:
        """Set the ban log channel for moderation actions"""
        try:
            import json
            import os
            
            # Load current settings
            settings_file = 'data/bot_settings.json'
            with open(settings_file, 'r') as f:
                settings = json.load(f)
            
            # Update the ban log channel
            if channel:
                settings.setdefault("moderation", {})["ban_log_channel_id"] = channel.id
                message = f"✅ Ban log channel set to {channel.mention}"
                logger.info(f"Ban log channel set to {channel.name} ({channel.id}) by {interaction.user}")
            else:
                settings.setdefault("moderation", {})["ban_log_channel_id"] = None
                message = "✅ Ban log channel disabled"
                logger.info(f"Ban log channel disabled by {interaction.user}")
            
            # Save settings
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            
            # Reload settings in config
            from config import load_bot_settings
            import config
            config.BOT_SETTINGS = load_bot_settings()
            
            await interaction.response.send_message(message, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error setting ban log channel: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while setting the ban log channel.",
                ephemeral=True
            )

    @set_ban_log_channel.error
    async def set_ban_log_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ) -> None:
        """Handle errors in the set ban log channel command"""
        try:
            if isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message(
                    "You need the `Administrator` permission to use this command!",
                    ephemeral=True
                )
            else:
                logger.error(f"Unexpected error in set ban log command: {error}")
                await interaction.response.send_message(
                    "An unexpected error occurred.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error handling set ban log command error: {e}")

    async def _resolve_user(self, interaction: discord.Interaction, user_input: str) -> Optional[discord.User]:
        """Resolve a user from string input (ID, mention, or username)"""
        try:
            # Handle mentions: <@123456789> or <@!123456789>
            if user_input.startswith('<@') and user_input.endswith('>'):
                user_id = int(user_input[2:-1].replace('!', ''))
                return await self.bot.fetch_user(user_id)
            
            # Try to parse as user ID
            try:
                user_id = int(user_input)
                return await self.bot.fetch_user(user_id)
            except ValueError:
                pass
            
            # Try to parse as username
            username = user_input.strip('@')
            # Try to find by username in guild members
            member = discord.utils.get(interaction.guild.members, name=username)
            if member:
                return member
            
            # If not found in members, try to find by display name
            member = discord.utils.get(interaction.guild.members, display_name=username)
            if member:
                return member
            
            return None
            
        except Exception as e:
            logger.error(f"Error resolving user {user_input}: {e}")
            return None

    async def _send_ban_log(self, embed: discord.Embed, action_type: str) -> None:
        """Send ban log to the configured channel"""
        try:
            # Get ban log channel ID from settings
            ban_log_channel_id = BOT_SETTINGS.get("moderation", {}).get("ban_log_channel_id")
            
            if not ban_log_channel_id:
                logger.info("No ban log channel configured, skipping log message")
                return
            
            # Get the channel
            channel = self.bot.get_channel(ban_log_channel_id)
            if not channel:
                logger.warning(f"Ban log channel {ban_log_channel_id} not found")
                return
            
            # Send the log message
            await channel.send(embed=embed)
            logger.info(f"Sent {action_type} log to channel {channel.name}")
            
        except Exception as e:
            logger.error(f"Error sending ban log: {e}")

    def _parse_duration(self, duration: str) -> int:
        """Parse duration string into seconds"""
        duration = duration.lower()
        if duration.endswith('d'):
            return int(duration[:-1]) * 86400
        elif duration.endswith('h'):
            return int(duration[:-1]) * 3600
        elif duration.endswith('m'):
            return int(duration[:-1]) * 60
        else:
            raise ValueError("Invalid duration format. Use d, h, or m")

    async def _schedule_unban(self, user_id: int, unban_time: datetime.datetime) -> None:
        """Schedule an unban for a user"""
        try:
            # Wait until unban time
            await discord.utils.sleep_until(unban_time)
            
            # Get the guild
            guild = self.bot.get_guild(GUILD_ID)
            if not guild:
                logger.error(f"Could not find guild {GUILD_ID} for unban")
                return
            
            # Unban the user
            user = await self.bot.fetch_user(user_id)
            await guild.unban(user, reason="Temporary ban expired")
            
            # Send automatic unban log to configured channel
            log_embed = discord.Embed(
                title="🔓 User Auto-Unbanned",
                description=(
                    f"**User:** {user.mention} (`{user.id}`)\n"
                    f"**Action:** Automatic unban after tempban expired\n"
                    f"**Original Tempban End:** <t:{int(unban_time.timestamp())}:F>\n"
                    f"**Unbanned At:** <t:{int(datetime.datetime.now().timestamp())}:F>"
                ),
                color=self.embed_color,
                timestamp=datetime.datetime.now()
            )
            log_embed.set_footer(text=f"User ID: {user.id} | Auto-unban")
            
            await self._send_ban_log(log_embed, "auto-unban")
            
            logger.info(f"Automatically unbanned {user} after tempban expired")
            
        except Exception as e:
            logger.error(f"Error in scheduled unban: {e}")

async def setup(bot: commands.Bot) -> None:
    """Set up the Moderation cog"""
    try:
        await bot.add_cog(Moderation(bot))
    except Exception as e:
        logger.error(f"Error loading Moderation cog: {e}")
        raise