# Discord Community Bot

A Discord bot for managing the Kruz's Community server.
Join https://discord.gg/9qaK8uaKXN to see the bot in action!

## Features

### 🤖 Core Features
- **Server Management**: Customizable server name, bot status, and embed colors
- **Embed Management**: Comprehensive system for creating and managing embeds
- **Automated Meme Posting**: Smart content filtering with extensive blocklist
- **Moderation Tools**: Warning system with DM notifications (More features coming soon)

### 📝 Embed Management Commands
- `/kruzembeds list` - Show all embed categories and their contents
- `/kruzembeds create` - Create a new embed
- `/kruzembeds edit` - Edit existing embeds
- `/kruzembeds post` - Post single embed or all embeds from a category
- `/kruzembeds delete` - Delete embeds or categories

### 🛡️ Moderation Commands
- `/kruzwarn` - Issue warnings to users (requires kick_members permission)
- `/rules` - Display server rules
- `/channels` - Show server channel structure

### ⚙️ Administrative Commands
- `/kruzbot settings` - View current configuration
- `/kruzbot setname` - Change server name
- `/kruzbot setstatus` - Update bot's status
- `/kruzbot setcolor` - Change embed color

### 🎨 Meme Management
- `/kruzmemes enable/disable` - Toggle meme posting
- `/kruzmemes block` - Add filtered words
- `/kruzmemes unblock` - Remove filtered words
- `/kruzmemes` - Set posting interval

## Setup

1. Clone this repository
2. Copy .env.example to .env
3. Fill in your credentials in .env:
   ```env
   DISCORD_TOKEN=your_discord_token_here
   DISCORD_GUILD_ID=your_guild_id_here
   MEME_CHANNEL_ID=your_meme_channel_id_here
   REDDIT_CLIENT_ID=your_reddit_client_id_here
   REDDIT_CLIENT_SECRET=your_reddit_client_secret_here
   REDDIT_USER_AGENT=your_reddit_user_agent_here
   ```
4. Install requirements: `pip install -r requirements.txt`
5. Run the bot: `python main.py`

## Technical Details

### 🔒 Security Features
- Environment variable configuration
- Permission-based command access
- Extensive content filtering
- Input validation
- Rate limiting protection

### 💾 Data Storage
- JSON-based configuration files
- Organized data directory structure
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
- Asynchronous operations

### 📁 File Structure

## Requirements
- Python 3.8+
- discord.py
- python-dotenv
- asyncpraw
- async-timeout