import discord
from discord import app_commands
from discord.ext import commands
from config import GUILD_ID, BOT_SETTINGS
import asyncio
import time

# Convert hex color string to int
EMBED_COLOR = int(BOT_SETTINGS["embed_color"], 16)

GUILD = discord.Object(id=GUILD_ID)

class ServerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._command_cooldowns = {}
        self._cooldown_duration = 5  # seconds

    async def _check_cooldown(self, user_id: int) -> bool:
        if user_id in self._command_cooldowns:
            last_use = self._command_cooldowns[user_id]
            if time.time() - last_use < self._cooldown_duration:
                return False
        self._command_cooldowns[user_id] = time.time()
        return True

    @app_commands.command(name="rules", description="Sends the rules embed.")
    @app_commands.guilds(GUILD)
    async def getRules(self, interaction: discord.Interaction):
        if not await self._check_cooldown(interaction.user.id):
            await interaction.response.send_message(
                "Please wait a few seconds before using this command again.",
                ephemeral=True
            )
            return
        # Server rules overview
        embed1 = discord.Embed(
            title=f"{BOT_SETTINGS['server_name']} Rules", 
            description=f"The **{BOT_SETTINGS['server_name']}** Discord server is a Public Community Server, and as such the server is held to a higher standard by Discord than a none public server. We expect all members of the server including staff to conduct themselves in an appropriate manner at all times.\n\n Please note that staff in the server reserve the right to issues actions against members at their discretion, if you feel that an action taken against you is wrong, you are welcome to submit a complaint via the https://discord.com/channels/1210120154562953216/1339588584881131582", 
            color=EMBED_COLOR
        )
        
        # Rules 1-5
        embed2 = discord.Embed(
            description="1 - **Civility and respect**\nPlease keep all messages civil and respectful, treat each other with respect, even if you disagree. If you cannot do that them block them. An example of uncivil/disrespectful comments may be \"don't be so stupid\" \"don't make comments on a topic you know nothing about.\"\n\n"
                              "2 - **Trolling**\nTrolling is not allowed in this server, do not make posts or comments in this server to deliberately upset/wind up others. An example of trolling comments may be \"Kruz is stupid\" or \"This political party sucks\".\n\n"
                              f"3 - **Inappropriate Content**\nThe {BOT_SETTINGS['server_name']} server is an 18+ server, and we have a NSFW channel. Please post any content that is not safe for work in the server's dedicated #｜nsfw channel. This includes drugs, graphic or vulgar content, offensive memes, gore and images of dead bodies. Avoid posting pornographic content as that is not what our server is about. Please note that violation of this rule could lead to a permanent ban. This includes GIFs and Memes.\n\n"
                              "4 - **Sensitive messages**\nOur server includes a lot of news so naturally there may be content posted that falls within discords ToS but could be upsetting, we ask that you mark potentially upsetting content with the spoiler tag. An example of this could be if you post news about Sexual Assault, Abuse, Racism etc.\n\n"
                              "5 - **Fake news/Conspiracy theories/Disinformation**\nPosting disinformation is against Discord ToS. Please only post articles from a reliable source with a reputation, please do not post misinformation in the server - all links are subject to removal by the server staff. For example, please do not post articles from \"The Onion\" as pass it off as news.", 
                              color=EMBED_COLOR
        )
        
        # Rules 6-10
        embed3 = discord.Embed(
            description="6 - **No Hate Speech**\nEveryone is welcome in this server regardless of race, ethnicity, political views, sex, gender identity/expression, sexuality or any other identity they may hold. Discrimination/hate against someone for one or more of their identities is prohibited. For example, using a racial slur. Please note that breaking this rule can result in an instant ban. **_(EX. If you call somebody a \"xyz\" make sure its in a joking manner and you are not insulting someone.)_**\n\n"
                              "7 - **Dog Piling**\nPlease do not dog pile on people (dog pilling is a group of people ganging up on one person)\n\n"
                              "8 - **Self Promotion**\nSelf-promotion is strictly prohibited unless permission has been given. Please create a ticket for more information.\n\n"
                              "9 - **Channel Usage**\nPlease use all channels for their intended purpose, if a member of staff asks you to move to another channel, please do so on the first request. For example, we like to keep news out of General Chat. Gifs & Memes should go in the appropriate channel.\n\n"
                              "10 - **Drama**\nPlease do not engage in drama within the server, do not create, encourage or bring drama from other places. For example, do not reference blocked chatters or drama that is external.", 
                              color=EMBED_COLOR
        )
        
        # Rules 11-15
        embed4 = discord.Embed(
            description="11 - **Unsolicited Messages**\nPlease do not send unsolicited DMs to people in the server this includes random server invites, links and general unsolicited chatter. It is encouraged that all server members turn direct messages off for people not on their friends list.\n\n"
                              "12 - **English Only**\nPlease keep all messages in the server in English so the server staff can understand your messages, content written in none English will be deleted. If you post an embed in a language other than English, please provide the translation.\n\n"
                              "13 - **Names/Profile**\nPlease keep your discord name/profile appropriate when in the server. You can right click your name and change is for this server only if you wish. Mods reserve the right to change chatter's names without their consent. Your profile picture and bio should also be appropriate.\n\n"
                              f"14 - **Extremism**\nAny form of extremism is prohibited in the {BOT_SETTINGS['server_name']} server. If you show an extremist view, you may be banned without warning. For example, sympathising with organisations prescribed as terrorist by the US Government or saying comments such as \"kill all XYZ\"\n\n"
                              "15 - **Political parties and politicians names**\nPlease refer to political parties and politicians by their correct names. Breaking this rule means you are breaking the civility rule and will incur infractions.", 
                              color=EMBED_COLOR
        )
        embed4.set_footer(text=f"Thank you for following our server rules,\n{BOT_SETTINGS['server_name']}")
        
        await interaction.response.defer(ephemeral=True)
        await interaction.delete_original_response()
        await interaction.channel.send(embeds=[embed1, embed2, embed3, embed4])

    @app_commands.command(name="channelindex", description="Shows the server channel index.")
    @app_commands.guilds(GUILD)
    async def getChannelIndex(self, interaction: discord.Interaction):
        # Server channels
        embed1 = discord.Embed(
            description="**__Make sure \"Show All Channels\" is selected to keep up with newly added channels or changes!__**\n\n"
            "## **Server Channel Index:**\n\n"
            "https://discord.com/channels/1210120154562953216/1339596616780222525 - Server wide announcements will be made in this channel such as server updates.\n\n"
            "https://discord.com/channels/1210120154562953216/1339588561879564400 - Changes made to the server are logged in this channel such as the addition of a focus channel or a focus channel being made read only.\n\n"
            "https://discord.com/channels/1210120154562953216/1339588584881131582 - This channel can be used to report other members of the server or raise complaints/give feedback.\n\n"
            "https://discord.com/channels/1210120154562953216/1339596982305558578 - Server rules.\n\n",
            color=EMBED_COLOR
        )
        
        # Chat channels
        embed2 = discord.Embed(
            description="## **Chat Channels:**\n\n"
            "https://discord.com/channels/1210120154562953216/1339588095443599449 - This channel is where members can generally talk about anything they like with the community.\n\n"
            "https://discord.com/channels/1210120154562953216/1339588141044203551 - This channel can be used to post gifs and memes, please note that gifs and memes should always be SFW unless posted in NSFW channel and abide by the server https://discord.com/channels/1210120154562953216/1339596982305558578\n\n",
            color=EMBED_COLOR
        )
        
        # News channels
        embed3 = discord.Embed(
            description="## **News Channels:**\n\n"
            "https://discord.com/channels/1210120154562953216/1339589096556986482 - News discussion channel\n\n"
            "https://discord.com/channels/1210120154562953216/1339589117465333811 - Weather discussion and live updates channel.\n\n"
            "https://discord.com/channels/1210120154562953216/1339589184066818060 - Live Earthquakes & Tsunami reports + discussion.\n\n"
            "https://discord.com/channels/1210120154562953216/1339589235065356470 - Twitter/X post from trusted sources.\n\n"
            "https://discord.com/channels/1210120154562953216/1339712763395706951 - YT channels that go live covering top news & weather.\n\n",
            color=EMBED_COLOR
        )
        
        # Conflict channels
        embed4 = discord.Embed(
            description="## **Conflict Channels:**\n\n"
            "https://discord.com/channels/1210120154562953216/1339715328074322071 - Discuss and view Ukraine/Russia war news.\n\n"
            "https://discord.com/channels/1210120154562953216/1339715534253457429 - Discuss and view the Middle-East conflicts.\n\n",
            color=EMBED_COLOR
        )
        
        # Off-topic forums
        embed5 = discord.Embed(
            description="## **Off-Topic Forums:**\n\n"
            "https://discord.com/channels/1210120154562953216/1339702431918854247 - Create threads about anything.\n\n",
            color=EMBED_COLOR
        )
        
        # Server games
        embed_games = discord.Embed(
            description="## **Server Games:**\n\n"
            "https://discord.com/channels/1210120154562953216/1340944247309729803 - Participate in the server's [dank memer](https://discord.gg/memers) lottery by using: /lottery buy or /lottery auto\n\n"
            "https://discord.com/channels/1210120154562953216/1340935958815703060 - The Game Events will be held here.\n\n"
            "https://discord.com/channels/1210120154562953216/1340931099643220044 - Play Trivia, Connect4, Rock Paper Scissors, Tic-Tac-Toe, and more! Complete your work shifts here also!\n\n"
            "https://discord.com/channels/1210120154562953216/1340931167871959120 - The fishing game! Get started with /fish guide or /fish catch\n\n"
            "https://discord.com/channels/1210120154562953216/1340933322267820063 - Fight your friends! Get started with /fight quick\n\n"
            "https://discord.com/channels/1210120154562953216/1340932133841277061 - Get started on your farm with /farm view\n\n"
            "https://discord.com/channels/1210120154562953216/1340933473183072266 - Make sure you own a rifle! Start hunting with /hunt\n\n"
            "https://discord.com/channels/1210120154562953216/1340932556656214086 - Rob your friends using /rob or /bankrob\n\n",
            color=EMBED_COLOR
        )
        
        # Gaming channels
        embed6 = discord.Embed(
            description="## **Gaming Channels:**\n\n"
            "https://discord.com/channels/1210120154562953216/1339586887563870279 - Latest news in the gaming industry.\n\n"
            "https://discord.com/channels/1210120154562953216/1339587274035167333 - This channel is where members can generally talk about videogames and related news.\n\n",
            color=EMBED_COLOR
        )
        
        await interaction.response.defer(ephemeral=True)
        await interaction.delete_original_response()
        await interaction.channel.send(embeds=[embed1, embed2, embed3, embed4, embed5, embed_games, embed6])

async def setup(bot):
    await bot.add_cog(ServerCommands(bot)) 