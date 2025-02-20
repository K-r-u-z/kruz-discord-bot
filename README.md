# Kruz's Community Bot

A Discord bot for managing the Kruz's Community server.
Join https://discord.gg/9qaK8uaKXN to see the bot in action!

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
- `MEME_CHANNEL_ID`: Channel ID where memes will be posted
- `REDDIT_CLIENT_ID`: Your Reddit application client ID
- `REDDIT_CLIENT_SECRET`: Your Reddit application secret
- `REDDIT_USER_AGENT`: Your Reddit user agent string

## Bot Settings

All bot settings are stored in `bot_settings.json`. The bot will create this file with default settings if it doesn't exist:

```json
{
    "server_name": "Your Server Name",
    "status": {
        "type": "watching",
        "name": "over {server_name}",
        "status": "online"
    },
    "embed_color": "0xbc69f0"
}
```

## Features

### Automated Meme Posting
- Fetches and posts memes from Reddit (r/meme)
- Smart content filtering with extensive blocklist
- Configurable posting interval (minimum 1 minute)
- Memory-efficient storage:
  - Auto-cleanup of old posted memes
  - Maximum 500 stored meme IDs
  - Periodic data trimming
- Commands:
  - `/kruzmemes` - Control meme functionality:
    - enable/disable - Toggle meme posting
    - status - Check current status
    - interval <minutes> - Set posting interval
    - addblockedkeyword <word> - Add word to filter
    - removeblockedkeyword <word> - Remove word from filter
    - listblockedkeywords - View all blocked words

### Server Information Commands
- `/rules` - Displays comprehensive server rules in formatted embeds
- `/channelindex` - Shows detailed server channel structure and descriptions

### Moderation Tools
- `/kruzwarn` - Allows moderators to warn users for rule violations
  - DM notification to warned users
  - Requires kick_members permission
  - Includes rule reference and reason

### Game Information Commands
- `/lotterymessage` - Information about Dank Memer lottery
- `/gameeventmessage` - Details about game events
- `/minigamemessage` - Guide for various mini-games
- `/fishinggamemessage` - Information about the fishing game
- `/fightinggamemessage` - Details about the fighting game system
- `/farminggamemessage` - Guide for the farming game
- `/huntinggamemessage` - Information about the hunting game
- `/robbinggamemessage` - Details about robbing mechanics

### Administrative Commands
All administrative commands require administrator permissions.

- `/kruzbot` - Manage bot settings:
  - settings - View current configuration
  - setname <name> - Change server name
  - setstatus <type> <text> [status] - Update bot's status
  - setcolor <hex> - Change embed color

## Technical Features

### Error Handling & Logging
- Basic error handling and console output
- Graceful shutdown handling
- Connection recovery system
- Command error feedback

### Performance Optimizations
- Rate limiting protection
- Batched file I/O operations
- Memory-efficient data storage
- Periodic cleanup of stored data
- Command cooldowns

### Security Features
- Environment variable configuration
- Permission-based command access
- Content filtering system
- Extensive blocklist for inappropriate content
- Input validation

### Data Persistence
Settings are stored in JSON files with automatic validation:
- `bot_settings.json`: Bot-wide settings
  - Server name
  - Bot status configuration
  - Embed colors
- `meme_settings.json`: Meme-related settings
  - Blocked words list
  - Posted meme IDs
  - Posting interval
  - Last post timestamp

### Health Monitoring
- Periodic health checks
- Discord connection monitoring
- Reddit API status verification
- Automatic reconnection
- Error reporting system 