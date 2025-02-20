import os
import json
from dotenv import load_dotenv

load_dotenv()

# Discord Bot Configuration
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))  # This will be used for both cases
MEME_CHANNEL_ID = int(os.getenv('MEME_CHANNEL_ID'))

# Reddit Configuration
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT')

def _get_default_settings():
    """Return default bot settings"""
    return {
        "server_name": "Kruz's Community",
        "status": {
            "type": "watching",
            "name": "over {server_name}",
            "status": "online"
        },
        "embed_color": "0xbc69f0"
    }

def _load_settings_file():
    """Load settings from file or create with defaults"""
    settings_file = 'bot_settings.json'
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            return json.load(f)
    else:
        default_settings = _get_default_settings()
        with open(settings_file, 'w') as f:
            json.dump(default_settings, f, indent=4)
        return default_settings

def load_bot_settings():
    """Load and validate bot settings"""
    required_fields = {'server_name', 'status', 'embed_color'}
    
    try:
        settings = _load_settings_file()
        missing = required_fields - set(settings.keys())
        if missing:
            print(f"Missing required settings: {missing}, using defaults")
            return _get_default_settings()
            
        # Validate status configuration
        if not all(k in settings['status'] for k in ['type', 'name', 'status']):
            print("Invalid status configuration, using defaults")
            return _get_default_settings()
            
        return settings
    except Exception as e:
        print(f"Settings load error: {e}")
        return _get_default_settings()

BOT_SETTINGS = load_bot_settings()