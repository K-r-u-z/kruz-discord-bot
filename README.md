# Discord Community Bot

A Discord bot for managing the Kruz's Community server.
Join https://discord.gg/9qaK8uaKXN to see the bot in action!

## Features

### Welcome System
- Customizable welcome messages with embeds
- Auto-role assignment for new members
- Placeholder support for dynamic content
- Preview system for testing messages

### Automatic Memes
- Automated meme posting system
- Content filtering and word blocking (customizable)
- Customizable posting intervals

### Embed System
- Create and manage embedded messages
- Automatic embed updates when content changes (Tracks and updates existing embeds)
- Organize embeds by categories
- Multi-line footer support
- Posts to current channel by default
- Clean preview system for embed contents

### Free Games Announcements
- Automatic free game notifications
- Customizable filters (store, price, rating)
- Game details with thumbnails and links
- Configurable announcement channel

### Moderation
- Warning system with DM notifications
- Message purging commands
- More moderation features planned

## Commands

### Welcome Message Commands
- `/welcome` - Configure welcome message settings
  - `⚙️ Setup Channel` - Set welcome message channel
  - `🔄 Toggle` - Enable/Disable welcome messages
  - `👋 Test Welcome` - Send a test welcome message (also test the autorole feature if enabled)
  - `📝 Edit Message` - Open modal to edit welcome message
  - `📋 Show Format` - Show available placeholders and formatting options

### Auto-Role Commands
- `/autorole` - Configure automatic role assignment
  - `🔄 Toggle` - Enable/Disable autorole
  - `👀 Show Settings` - Display current autorole settings
  - `✨ Set Role` - Set role for new members

### Moderation Commands
- `/kruzwarn` - ⚠️ Issue a warning to a user
  - `👤 User` - The user to warn
  - `📜 Rule` - The rule that was broken
  - `📝 Reason` - Additional details about the warning

- `/purge` - 🗑️ Delete multiple messages (1-100)
- `/cls` - 🧹 Clear messages (defaults to 100)

### Settings Commands
- `/settings` - Configure bot settings
  - `📋 Show Settings` - Display current settings
  - `📝 Change Server Name` - Update server name
  - `🎨 Change Color` - Update embed color
  - `🎮 Change Activity` - Set bot's activity
  - `🔵 Change Status` - Set bot's online status

### Meme Commands
- `/kruzmemes` - Manage meme poster settings
  - `🔄 Toggle` - Enable/Disable meme posting
  - `⏱️ Set Interval` - Change posting frequency
  - `📌 Set Channel` - Set meme channel
  - `🚫 Block Words` - Manage word filters

### Embed Management
- `/kruzembeds` - Create and manage embedded messages
  - `📝 Create/Edit` - Create or edit an embed
    - Specify category and name
    - Set title (optional)
    - Add content
    - Add footer with support for multiple lines
  - `🗑️ Delete` - Delete an embed or category
  - `📋 List All` - Show all embeds or embeds in a category
  - `📤 Post` - Post embed(s) to the current channel
    - Post single embed or entire category
    - Auto-updates when changes are made
  - `🔄 Refresh All` - Refresh all tracked embeds (incase auto updates fail for some reason)

  # Tips:
- Categories help organize related embeds (rules, news, info, etc.)
- Embeds auto-update when edited
- Use descriptive names for easy management
- Preview before posting with list command

### Free Games Commands
- `/freegames` - Configure free games announcements
  - `📋 List Free Games` - Browse current free games
  - `📌 Setup Channel` - Set announcement channel
  - `🔄 Toggle` - Enable/Disable announcements
  - `⚙️ Settings` - Configure filters and notifications
  - `🧪 Test` - Send test announcement

## Setup

1. Clone repository
2. Copy .env.example to .env and fill credentials:
```env
DISCORD_TOKEN=your_discord_token
DISCORD_GUILD_ID=your_guild_id
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=your_reddit_user_agent
FREESTUFF_API_KEY=your_freestuff_api_key

```
3. Install requirements: `pip install -r requirements.txt`
4. Run: `python main.py`

## Available Placeholders

Embeds support these placeholders:
- `{user_mention}` - Mentions the new member
- `{user_name}` - Member's username
- `{display_name}` - Member's display name
- `{user_id}` - Member's ID
- `{server_name}` - Server name
- `{member_count}` - Current member count

## Text Formatting

Embeds support these formatting options in title and description:
- `**text**` - **Bold**
- `__text__` - __Underline__
- `*text*` - *Italic*
- `***text***` - ***Bold Italic***
- `__*text*__` - __*Underline Italic*__
- `**__text__**` - **__Bold Underline__**
- `***__text__***` - ***__Bold Italic Underline__***
- \`text\` - `Inline Code`

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
  - freegames.py
  - __init__.py
- data/
  - bot_settings.json
  - embed_contents.json
  - embedded_messages_ids.json
  - meme_settings.json
  - freegames_settings.json
  - welcome_settings.json

## Requirements
- Python 3.8+
- discord.py
- python-dotenv
- asyncpraw
- async-timeout
- aiohttp