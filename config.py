import os
import json
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
if not load_dotenv():
    raise RuntimeError("Failed to load .env file")

def get_env_var(name: str, required: bool = True) -> str:
    """Get environment variable with validation"""
    value = os.getenv(name)
    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value

# Discord Bot Configuration with validation
TOKEN = get_env_var('DISCORD_TOKEN')
GUILD_ID = int(get_env_var('DISCORD_GUILD_ID'))
MEME_CHANNEL_ID = int(get_env_var('MEME_CHANNEL_ID'))

# Reddit Configuration
REDDIT_CLIENT_ID = get_env_var('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = get_env_var('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = get_env_var('REDDIT_USER_AGENT')

def _get_default_settings() -> Dict[str, Any]:
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

def _load_settings_file() -> Dict[str, Any]:
    """Load settings from file or create with defaults"""
    settings_file = 'data/bot_settings.json'
    try:
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                return json.load(f)
        default_settings = _get_default_settings()
        with open(settings_file, 'w') as f:
            json.dump(default_settings, f, indent=4)
        return default_settings
    except Exception as e:
        print(f"Error loading settings file: {e}")
        return _get_default_settings()

def load_bot_settings() -> Dict[str, Any]:
    """Load and validate bot settings"""
    required_fields = {'server_name', 'status', 'embed_color'}
    required_status_fields = {'type', 'name', 'status'}
    
    try:
        settings = _load_settings_file()
        
        # Validate required fields
        missing = required_fields - set(settings.keys())
        if missing:
            print(f"Warning: Missing required settings: {missing}")
            return _get_default_settings()
        
        # Validate status configuration
        if not isinstance(settings['status'], dict) or \
           not all(k in settings['status'] for k in required_status_fields):
            print("Warning: Invalid status configuration")
            return _get_default_settings()
        
        return settings
        
    except Exception as e:
        print(f"Error loading settings: {e}")
        return _get_default_settings()

# Load settings
BOT_SETTINGS = load_bot_settings()

def validate_env_vars():
    required_vars = {
        'DISCORD_TOKEN': TOKEN,
        'DISCORD_GUILD_ID': GUILD_ID,
        'MEME_CHANNEL_ID': MEME_CHANNEL_ID,
        'REDDIT_CLIENT_ID': REDDIT_CLIENT_ID,
        'REDDIT_CLIENT_SECRET': REDDIT_CLIENT_SECRET,
        'REDDIT_USER_AGENT': REDDIT_USER_AGENT
    }
    
    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

validate_env_vars()