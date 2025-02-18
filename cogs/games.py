import discord
from discord import app_commands
from discord.ext import commands
from config import GUILD_ID

GUILD = discord.Object(id=GUILD_ID)

class GameCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_game_message(self, interaction: discord.Interaction, embed_or_embeds):
        await interaction.response.defer(ephemeral=True)
        await interaction.delete_original_response()
        if isinstance(embed_or_embeds, list):
            await interaction.channel.send(embeds=embed_or_embeds)
        else:
            await interaction.channel.send(embed=embed_or_embeds)

    @app_commands.command(name="lotterymessage", description="Shows lottery information")
    @app_commands.guilds(GUILD)
    async def getLotteryMessage(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎰 Participate in the Dank Memer Lottery",
            description="Participate by using:\n\n `/lottery buy` or `/lottery auto`\n\n **Note:** You need to join the [Dank Memer server](https://discord.gg/memers) to see who wins.",
            color=0xbc69f0
        )
        await self.send_game_message(interaction, embed)

    @app_commands.command(name="gameeventmessage", description="Shows game event information")
    @app_commands.guilds(GUILD)
    async def getGameEventMessage(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎮 Game Events",
            description="Game events will be hosted here",
            color=0xbc69f0
        )
        await self.send_game_message(interaction, embed)

    @app_commands.command(name="minigamemessage", description="Shows minigame information")
    @app_commands.guilds(GUILD)
    async def getMinigameMessage(self, interaction: discord.Interaction):
        embed1 = discord.Embed(
            title="🎲 Welcome to the Mini Games!",
            description="Play Trivia, Connect4, Rock Paper Scissors, Tic-Tac-Toe, and more!\nComplete your work shifts here also!",
            color=0xbc69f0
        )
        
        embed2 = discord.Embed(
            description="**To get started type one of these:**\n\n"
                       "`/trivia`\n"
                       "`/game Connect4`\n"
                       "`/game rps`\n"
                       "`/game tictactoe`\n\n"
                       "**To start your work:**\n"
                       "`/work shift`",
            color=0xbc69f0
        )
        
        await self.send_game_message(interaction, [embed1, embed2])

    @app_commands.command(name="fishinggamemessage", description="Shows fishing game information")
    @app_commands.guilds(GUILD)
    async def getFishingGameMessage(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎣 Welcome to the Fishing Game!",
            description="Get started with:\n\n `/fish guide` or `/fish catch`",
            color=0xbc69f0
        )
        await self.send_game_message(interaction, embed)

    @app_commands.command(name="fightinggamemessage", description="Shows fighting game information")
    @app_commands.guilds(GUILD)
    async def getFightingGameMessage(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚔️ Welcome to the Fighting Game!",
            description="Fight your friends! Get started with:\n\n `/fight quick` or `/fight create`",
            color=0xbc69f0
        )
        await self.send_game_message(interaction, embed)

    @app_commands.command(name="farminggamemessage", description="Shows farming game information")
    @app_commands.guilds(GUILD)
    async def getFarmingGameMessage(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌾 Welcome to the Farming Game!",
            description="Get started on your farm with:\n\n `/farm view`",
            color=0xbc69f0
        )
        await self.send_game_message(interaction, embed)

    @app_commands.command(name="huntinggamemessage", description="Shows hunting game information")
    @app_commands.guilds(GUILD)
    async def getHuntingGameMessage(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎯 Welcome to the Hunting Game!",
            description="Make sure you own a rifle! Start hunting with:\n\n `/hunt`",
            color=0xbc69f0
        )
        await self.send_game_message(interaction, embed)

    @app_commands.command(name="robbinggamemessage", description="Shows robbing game information")
    @app_commands.guilds(GUILD)
    async def getRobbingGameMessage(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💰 Ready to start stealing?",
            description="Rob your friends using:\n\n `/rob` or `/bankrob`",
            color=0xbc69f0
        )
        await self.send_game_message(interaction, embed)

async def setup(bot):
    await bot.add_cog(GameCommands(bot)) 