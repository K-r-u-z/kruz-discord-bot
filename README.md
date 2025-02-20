# Discord Community Bot

A Discord bot for managing the Kruz's Community server.
Join https://discord.gg/9qaK8uaKXN to see the bot in action!

## Features

### 🤖 Core Features
- **Server Management**: Customizable server name, bot status, and embed colors
- **Automated Meme Posting**: Smart content filtering with extensive blocklist
- **Moderation Tools**: Warning system with DM notifications
- **Game Information**: Comprehensive game guides and information commands in the form of embeds.

### 🎮 Game Commands
- `/lotterymessage` - Dank Memer lottery information
- `/gameeventmessage` - Game event details
- `/minigamemessage` - Mini-games guide
- `/fishinggamemessage` - Fishing game guide
- `/fightinggamemessage` - Fighting system guide
- `/farminggamemessage` - Farming game guide
- `/huntinggamemessage` - Hunting game guide
- `/robbinggamemessage` - Robbing mechanics guide

### 🛡️ Moderation Commands
- `/kruzwarn` - Issue warnings to users (requires kick_members permission)
- `/rules` - Display server rules
- `/channelindex` - Show server channel structure

### ⚙️ Administrative Commands
- `/kruzbot settings` - View current configuration
- `/kruzbot setname` - Change server name
- `/kruzbot setstatus` - Update bot's status
- `/kruzbot setcolor` - Change embed color

### 🎨 Meme Management
- `/kruzmemes enable/disable` - Toggle meme posting
- `/kruzmemes status` - Check meme posting status
- `/kruzmemes interval` - Set posting interval
- `/kruzmemes addblockedkeyword` - Add filtered words
- `/kruzmemes removeblockedkeyword` - Remove filtered words
- `/kruzmemes listblockedkeywords` - View filtered words

## Setup

1. Clone this repository
2. Copy .env.example to .env
3. Fill in your credentials in .env:
   - Get Discord credentials from Discord Developer Portal
   - Get Reddit credentials from Reddit Apps
4. Install requirements: pip install -r requirements.txt
5. Run the bot: python main.py

## Technical Details

### 🔒 Security Features
- Environment variable configuration
- Permission-based command access
- Extensive content filtering
- Input validation
- Rate limiting protection

### 💾 Data Storage
- JSON-based configuration files
- Memory-efficient data management
- Automatic data cleanup
- Periodic storage optimization

### 🔄 Error Handling
- Comprehensive error catching
- Graceful shutdown handling
- Connection recovery system
- Command error feedback
- Rate limit protection

### 🚀 Performance
- Efficient memory usage
- Batched file operations
- Command cooldowns
- Optimized data structures

## Requirements
- Python 3.8+
- discord.py
- python-dotenv
- asyncpraw
- async-timeout