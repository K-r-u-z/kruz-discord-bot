import discord
from discord.ext import commands
import asyncio
import signal # Might use this later
from config import TOKEN, GUILD_ID

# Constants
GUILD_ID = discord.Object(id=GUILD_ID)

# Client Setup
class Client(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        self.initial_extensions = [
            'cogs.commands',
            'cogs.games',
            'cogs.moderation',
            'cogs.memes'
        ]
    
    async def setup_hook(self):
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                print(f"Loaded extension {extension}")
            except Exception as e:
                print(f"Failed to load extension {extension}: {e}")

        try:
            synced = await self.tree.sync(guild=GUILD_ID)
            print(f"Synced {len(synced)} commands")
        except Exception as e:
            print(f"Error syncing commands: {e}")

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="over Kruz's Community"
            )
        )

async def main():
    bot = Client()
    try:
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()
            print("Bot has been shut down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot has been shut down by keyboard interrupt.")
    except Exception as e:
        print(f"Fatal error: {e}")
