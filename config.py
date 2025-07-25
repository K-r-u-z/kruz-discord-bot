import os
import json
from typing import Dict, Any
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Add debug logging for env file loading
env_path = os.path.join(os.path.dirname(__file__), '.env')
logger.info(f"Attempting to load .env file from: {env_path}")
logger.info(f"Current working directory: {os.getcwd()}")

# Clear existing environment variables we're about to set
if 'DISCORD_TOKEN' in os.environ:
    logger.info("Clearing existing DISCORD_TOKEN from environment")
    del os.environ['DISCORD_TOKEN']

# Load environment variables with override
if not load_dotenv(env_path, override=True):
    logger.error(f"Failed to load .env file from {env_path}")
    raise RuntimeError(f"Failed to load .env file from {env_path}")
else:
    logger.info("Successfully loaded .env file")

def get_env_var(name: str, required: bool = True) -> str:
    """Get environment variable with validation"""
    value = os.getenv(name)
    if required and not value:
        logger.error(f"Missing required environment variable: {name}")
        raise ValueError(f"Missing required environment variable: {name}")
    logger.info(f"Loaded environment variable: {name}")
    return value

# Discord Bot Configuration with validation
TOKEN = get_env_var('DISCORD_TOKEN')
GUILD_ID = int(get_env_var('DISCORD_GUILD_ID'))

# Reddit Configuration
REDDIT_CLIENT_ID = get_env_var('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = get_env_var('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = get_env_var('REDDIT_USER_AGENT')

# FreeStuff API Configuration
FREESTUFF_REST_API_KEY = get_env_var('FREESTUFF_REST_API_KEY')
FREESTUFF_PUBLIC_KEY = get_env_var('FREESTUFF_PUBLIC_KEY')
YOUR_WEBHOOK_URL = get_env_var('YOUR_WEBHOOK_URL')

def _get_default_settings() -> Dict[str, Any]:
    """Return default bot settings"""
    return {
        "server_name": "Your Server Name",
        "presence": {
            "status": "online",
            "activity": "watching over {server_name}"
        },
        "embed_color": "0xbc69f0",
        "moderation": {
            "ban_log_channel_id": None
        }
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
    required_fields = {'server_name', 'presence', 'embed_color'}
    required_presence_fields = {'status', 'activity'}
    
    try:
        settings = _load_settings_file()
        
        # Validate required fields
        missing = required_fields - set(settings.keys())
        if missing:
            print(f"Warning: Missing required settings: {missing}")
            return _get_default_settings()
        
        # Validate presence configuration
        presence = settings.get('presence', {})
        if not isinstance(presence, dict) or \
           not all(k in presence for k in required_presence_fields):
            print("Warning: Invalid presence configuration")
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
        'REDDIT_CLIENT_ID': REDDIT_CLIENT_ID,
        'REDDIT_CLIENT_SECRET': REDDIT_CLIENT_SECRET,
        'REDDIT_USER_AGENT': REDDIT_USER_AGENT,
        'FREESTUFF_REST_API_KEY': FREESTUFF_REST_API_KEY,
        'FREESTUFF_PUBLIC_KEY': FREESTUFF_PUBLIC_KEY,
        'YOUR_WEBHOOK_URL': YOUR_WEBHOOK_URL
    }
    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

validate_env_vars()