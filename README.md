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
- Content filtering and word blocking
- Customizable posting settings
- Support for multiple subreddits

### Embed System
- Create and manage embedded messages
- Automatic embed updates when content changes (Tracks and updates existing embeds)
- Organize embeds by categories
- Multi-line footer support
- Posts to current channel by default
- Clean preview system for embed contents

### Moderation
- Warning system
- Message purging
- More moderation features coming soon

## Commands

### Welcome Message Commands
- `/welcome` - Configure welcome message settings
  - `👋 Test Welcome` - Send a test welcome message (also test the autorole feature if enabled)
  - `📝 Edit Message` - Open modal to edit welcome message
  - `⚙️ Setup Channel` - Set welcome message channel
  - `📋 Show Format` - Show available placeholders and formatting options
  - `🔄 Toggle System` - Enable/Disable welcome messages

### Auto-Role Commands
- `/autorole` - Configure automatic role assignment
  - `👀 Show Settings` - Display current autorole settings
  - `✨ Set Role` - Set role for new members
  - `✅ Enable` - Enable autorole
  - `❌ Disable` - Disable autorole

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
  - `🔄 Refresh All` - Refresh all tracked embeds


Example Usage:
```
# Create/Edit an embed
/kruzembeds edit rules welcome
/kruzembeds edit announcements event1

# Post embeds
/kruzembeds post rules welcome    # Post single embed
/kruzembeds post rules           # Post entire category

# Manage embeds
/kruzembeds list rules          # List embeds in category
/kruzembeds delete rules welcome # Delete specific embed
/kruzembeds refresh             # Update all tracked embeds
```

### Meme Commands
- `/kruzmemes` - Manage meme poster settings
  - `✅ Enable` - Enable meme posting
  - `❌ Disable` - Disable meme posting
  - `🚫 Block Words` - Add words to block list
  - `✨ Unblock Words` - Remove words from block list

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