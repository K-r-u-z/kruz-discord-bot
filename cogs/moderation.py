import discord
from discord import app_commands
from discord.ext import commands
from config import GUILD_ID

GUILD = discord.Object(id=GUILD_ID)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="kruzwarn",
        description="Warn a user"
    )
    @app_commands.guilds(GUILD)
    @app_commands.describe(
        user="The user to warn",
        reason="The reason for the warning"
    )
    @app_commands.checks.has_permissions(kick_members=True)
    async def warn_user(self, interaction: discord.Interaction, user: discord.Member, rule: str, reason: str = None):
        warn_embed = discord.Embed(
            title="⚠️ Warning Issued",
            description=f"**User:** {user.mention}\n"
                       f"**Rule Broken:** {rule}\n"
                       f"**Warned By:** {interaction.user.mention}\n"
                       f"**Reason:** {reason if reason else 'No reason provided'}",
            color=0xbc69f0
        )
        
        try:
            await user.send(embed=warn_embed)
            await interaction.response.send_message(f"Warning sent to {user.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"Could not DM {user.mention}. They might have DMs disabled.",
                ephemeral=True
            )

    @warn_user.error
    async def warn_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You don't have permission to use this command!",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Moderation(bot))