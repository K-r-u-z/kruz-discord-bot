import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging
from config import GUILD_ID, BOT_SETTINGS

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

async def setup(bot: commands.Bot) -> None:
    """Set up the Moderation cog"""
    try:
        await bot.add_cog(Moderation(bot))
    except Exception as e:
        logger.error(f"Error loading Moderation cog: {e}")
        raise