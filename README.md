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
- Customizable posting intervals

### Embed System
- Create and manage embedded messages
- Organize embeds by categories
- Multi-line footer support
- Posts to current channel by default
- Clean preview system for embed contents

### Free Games Announcements
- Automatic free game notifications
- Customizable filters (store, price, rating)
- Game details with thumbnails and links
- Configurable announcement channel
- (Uses https://freestuffbot.xyz API)

### Moderation
- Warning system with DM notifications
- Message purging commands

### AutoMod System
- Spam Protection
- Advertising Protection
- Text Filter
- Caps Filter
- Emoji Spam Protection
- Warning System

### Leveling System
- Experience Points
  - Message-based XP gain
  - Configurable XP rates
  - Cooldown system
  - Role rewards
- Level Progression
  - Automatic level-up notifications
  - Role rewards at specific levels
  - Leaderboard system
  - Streak system

### Clans System
- Create and customize clans
- Invite members to clans
- Leave clans
- Delete clans
- Transfer clan leadership
- View clan information
- List all clans
- Change clan color
- Change clan name

### Custom Private Voice Channels
- Create private voice channels
- Delete private voice channels
- Level-based access (requires level 10)
- Automatic category management

### RSS Feed System
- Multiple RSS feed support
- Customizable feed colors per channel
- Role mention notifications
- Duplicate post prevention
- Configurable check intervals
- Feed management interface
- Title history tracking

### Earthquake Feed
- Real-time earthquake alerts
- Customizable alert colors
- Role mention notifications
- Magnitude-based filtering
- Location-based filtering
- Detailed earthquake information
- Automatic feed updates

## Commands

### Welcome Message Commands
- `/welcome` - Configure welcome message settings
  - `📌 Setup Channel` - Set welcome message channel
  - `🔄 Toggle` - Enable/Disable welcome messages
  - `👋 Test Welcome` - Send a test welcome message
  - `📝 Edit Message` - Open modal to edit welcome message
  - `📋 Show Format` - Show available placeholders

### Auto-Role Commands
- `/autorole` - Configure automatic role assignment
  - `🔄 Toggle` - Enable/Disable autorole
  - `👀 Show Settings` - Display current autorole settings
  - `✨ Set Role` - Set role for new members

### Moderation Commands
- `/kruzwarn` - Issue a warning to a user
- `/purge` - Delete multiple messages (1-100)
- `/cls` - Clear messages (defaults to 100)
- `/ban` - Ban a user from the server
  - Requires ban_members permission
  - Optional reason parameter
  - Sends DM notification to banned user
- `/tempban` - Temporarily ban a user
  - Requires ban_members permission
  - Duration format: 1d (days), 2h (hours), 30m (minutes)
  - Optional reason parameter
  - Automatically unbans after duration
  - Sends DM notification to tempbanned user
- `/unban` - Unban a user from the server
  - Requires ban_members permission
  - Accepts user ID or username#discriminator
  - Optional reason parameter

### Settings Commands
- `/settings` - Configure bot settings
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
  - `🗑️ Delete` - Delete an embed or category
  - `📋 List All` - Show all embeds or embeds in a category
  - `📤 Post` - Post embed(s) to the current channel
  - `🔄 Refresh All` - Refresh all tracked embeds

### Free Games Commands
- `/freegames` - Configure free games announcements
  - `📋 List Free Games` - Browse current free games
  - `📌 Setup Channel` - Set announcement channel
  - `🔄 Toggle` - Enable/Disable announcements
  - `⚙️ Settings` - Configure filters and notifications
  - `🧪 Test` - Send test announcement

### AutoMod Commands
- `/automod` - Open AutoMod settings menu
- `/warningreset` - Reset warnings for a user
- `/warnings` - Check warnings for a user

### Leveling Commands
- `/level` - Check your current level and XP
- `/leaderboard` - View server level rankings
- `/levelsettings` - Configure leveling system
- `/streak` - Check your current streak

### Clan Commands
- `/clan` - Manage clans
  - `🏰 Create` - Create a new clan
  - `👥 Invite` - Invite members to your clan
  - `🚪 Leave` - Leave your current clan
  - `🗑️ Delete` - Delete your clan
  - `👑 Transfer` - Transfer clan leadership
  - `ℹ️ Info` - View clan information
  - `📋 List` - List all clans
  - `🎨 Color` - Change clan color
  - `📝 Name` - Change clan name

### Voice Channel Commands
- `/voice` - Manage private voice channels
- `/voicesetup` - Set up the category for private voice channels

### RSS Feed Commands
- `/rss` - Manage RSS feed settings
  - `➕ Add Feed` - Add a new RSS feed
  - `📋 List Feeds` - View all configured feeds
  - `✏️ Edit Feed` - Modify existing feed settings
  - `🎨 Set Channel Color` - Customize feed colors
  - `📢 Set Role Mentions` - Configure role notifications
  - `⏱️ Set Check Interval` - Adjust update frequency
  - `🔄 Toggle RSS System` - Enable/Disable feed system
  - `🧹 Manage Duplicates` - Configure duplicate prevention
  - `📢 Post Latest` - Manually post latest feed items

### Earthquake Commands
- `/earthquake` - Manage earthquake feed settings
  - `📌 Setup Channel` - Set alert channel
  - `🔄 Toggle Feed` - Enable/Disable alerts
  - `📊 Status` - View feed status
  - `🎨 Color Settings` - Customize alert colors
  - `👥 Manage Roles` - Configure role notifications

## Setup

1. Clone repository
2. Copy .env.example to .env and fill credentials:
```env
DISCORD_TOKEN=
DISCORD_GUILD_ID=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=
FREESTUFF_REST_API_KEY=
FREESTUFF_PUBLIC_KEY=
YOUR_WEBHOOK_URL=

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
- Content filtering
- Input validation
- Rate limit protection

### 💾 Data Storage
- JSON-based configuration files
- Organized data directory structure
- Memory-efficient data management

### 🔄 Error Handling
- Error catching
- Graceful shutdown handling
- Connection recovery system
- Command error feedback

### 🚀 Performance
- Efficient memory usage
- Command cooldowns
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
  - leveling.py
  - clans.py
  - voice_channels.py
  - automod.py
  - rss_feed.py
  - earthquakes.py
  - __init__.py
- data/
  - bot_settings.json
  - embed_contents.json
  - embedded_messages_ids.json
  - meme_settings.json
  - freegames_settings.json
  - earthquake_settings.json
  - leveling_settings.json
  - rss_settings.json
  - voice_settings.json
  - automod_settings.json
  - welcome_settings.json
  - clans.json

## Requirements

- Python 3.8 or higher
- discord.py>=2.3.0
- python-dotenv>=1.0.0
- asyncpraw>=7.7.1
- async-timeout>=4.0.3
- aiohttp>=3.8.1
- PyNaCl>=1.4.0
- requests>=2.31.0
- python-dateutil>=2.8.2
- feedparser>=6.0.10

## Installation
1. Clone the repository
2. Install Python dependencies: `pip install -r requirements.txt`
3. Create a `.env` file based on `.env.example`
4. Run the bot: `python main.py`