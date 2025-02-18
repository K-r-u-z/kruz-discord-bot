# Kruz's Community Bot

A Discord bot for managing the Kruz's Community server.

## Setup

1. Clone this repository
2. Copy `.env.example` to `.env`
3. Fill in your credentials in `.env`:
   - Get Discord credentials from [Discord Developer Portal](https://discord.com/developers/applications)
   - Get Reddit credentials from [Reddit Apps](https://www.reddit.com/prefs/apps)
4. Install requirements: `pip install -r requirements.txt`
5. Run the bot: `python main.py`

## Environment Variables

- `DISCORD_TOKEN`: Your Discord bot token
- `DISCORD_GUILD_ID`: Your Discord server ID
- `REDDIT_CLIENT_ID`: Your Reddit application client ID
- `REDDIT_CLIENT_SECRET`: Your Reddit application secret
- `REDDIT_USER_AGENT`: Your Reddit user agent string

## Features

### Automated Meme Posting
- Fetches and posts memes from Reddit (r/wholesomememes, r/memes, r/dankmemes)
- Content filtering for NSFW and inappropriate content
- Configurable posting interval
- Tracks posted memes to avoid duplicates

### Server Information Commands
- `/rules` - Displays comprehensive server rules in formatted embeds
- `/channelindex` - Shows detailed server channel structure and descriptions

### Moderation Tools
- `/warn` - Allows moderators to warn users for rule violations
- Includes DM notification to warned users
- Requires kick_members permission

### Game Information Commands
- `/lotterymessage` - Information about Dank Memer lottery
- `/gameeventmessage` - Details about game events
- `/minigamemessage` - Guide for various mini-games (Trivia, Connect4, etc.)
- `/fishinggamemessage` - Information about the fishing game
- `/fightinggamemessage` - Details about the fighting game system
- `/farminggamemessage` - Guide for the farming game
- `/huntinggamemessage` - Information about the hunting game
- `/robbinggamemessage` - Details about robbing mechanics

### Administrative Commands
- `/memeposter` - Enable/disable automatic meme posting
- `/memeinterval` - Adjust the interval between meme posts
- Requires administrator permissions

### Error Handling
- Comprehensive error handling for all commands
- User-friendly error messages
- Connection recovery system with exponential backoff

### Security Features
- Content filtering system for inappropriate content (memes)
- Rate limiting protection
- Permission-based command access 