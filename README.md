# Discord Community Bot

A Discord bot for managing the Kruz's Community server.
Join https://discord.gg/9qaK8uaKXN to see the bot in action!

## Features

### Welcome System
- Customizable welcome messages with embeds
- Auto-role assignment for new members
- Placeholder support for dynamic content
- Preview system for testing messages

### Moderation
- Warning system
- Message purging
- More moderation features coming soon

## Commands

### Welcome Message Commands
- `/welcome setup` - Set welcome message channel
- `/welcome formatting` - Show available placeholders and formatting options
- `/welcome edit` - Open modal to edit welcome message
- `/welcome test` - Send a test welcome message
- `/welcome toggle` - Enable/Disable welcome messages

### Auto-Role Commands
- `/autorole show` - Display current autorole settings
- `/autorole set @role` - Set and enable role for new members
- `/autorole enable` - Enable autorole
- `/autorole disable` - Disable autorole

### Moderation Commands
- `/warn @user reason` - Warn a user
- `/purge amount [#channel]` - Delete multiple messages (1-100)
- `/cls amount [#channel]` - Alias for purge command

## Available Placeholders

Welcome messages support these placeholders:
- `{user_mention}` - Mentions the new member
- `{user_name}` - Member's username
- `{display_name}` - Member's display name
- `{user_id}` - Member's ID
- `{server_name}` - Server name
- `{member_count}` - Current member count

## Text Formatting

Welcome messages support these formatting options in title and description:
- `**text**` - Bold
- `__text__` - Underline
- `*text*` - Italic
- `***text***` - Bold Italic
- `__*text*__` - Underline Italic
- `**__text__**` - Bold Underline
- `***__text__***` - Bold Italic Underline
- \`text\` - Inline Code

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
- main.py
- config.py
- cogs/
  - embeds.py
  - moderation.py
  - memes.py
  - settings.py
  - welcome.py
  - __init__.py
- data/
  - bot_settings.json
  - embed_contents.json
  - embedded_messages_ids.json
  - meme_settings.json

## Requirements
- Python 3.8+
- discord.py
- python-dotenv
- asyncpraw
- async-timeout