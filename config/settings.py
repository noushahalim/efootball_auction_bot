# config/settings.py - Enhanced Configuration with Dynamic Updates and Break Timer
import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
BOT_USERNAME = os.getenv('BOT_USERNAME', 'YourBotUsername')
SUPER_ADMIN_ID = int(os.getenv('SUPER_ADMIN_ID'))

# Dynamic admin list - will be updated from database
ADMIN_IDS = [SUPER_ADMIN_ID]

# Group IDs
AUCTION_GROUP_ID = int(os.getenv('AUCTION_GROUP_ID', 0))
DATA_GROUP_ID = int(os.getenv('DATA_GROUP_ID', 0))
UNSOLD_GROUP_ID = int(os.getenv('UNSOLD_GROUP_ID', 0))

# Database Configuration
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'efootball_auction')

# Auction Settings - These can be overridden by database settings
DEFAULT_BALANCE = 200_000_000  # 200M
BID_INCREMENT = 1_000_000      # 1M
MAX_STRAIGHT_BID = 20_000_000  # 20M
AUCTION_TIMER = 60              # seconds
AUTO_MODE = True                # True for auto, False for manual
WARNING_TIME = 10               # Final warning seconds
QUICK_BID_AMOUNTS = [1_000_000, 2_000_000, 5_000_000]  # 1M, 2M, 5M
AUCTION_BREAK = 30              # Default break between auctions (seconds)

# Visual Elements
WELCOME_GIF = "https://media.giphy.com/media/l0HlNaQ6gWfllcjDO/giphy.gif"
AUCTION_START_GIF = "https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif"
WIN_STICKER = "CAACAgIAAxkBAAEBPQRhXoX5AAF5kgABQKN5AAH5yQ8AAgMAA8A2TxP5al-2ZdafVyEE"

COUNTDOWN_GIFS = {
    'start': 'https://media.giphy.com/media/l0HlNaQ6gWfllcjDO/giphy.gif',
    '180_120': 'YOUR_180_120_GIF_URL',
    '120_90': 'YOUR_120_90_GIF_URL',
    '90_60': 'YOUR_90_60_GIF_URL',
    '60_45': 'https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif',
    '45_30': 'https://media.giphy.com/media/3o7aCWJavAgtBzLWrS/giphy.gif',
    '30_20': 'https://media.giphy.com/media/26BRuo6sLetdllPAQ/giphy.gif',
    '20_10': 'https://media.giphy.com/media/3ohzdYJK1wAdPWVk88/giphy.gif',
    '10_3': 'https://media.giphy.com/media/l0HlNaQ6gWfllcjDO/giphy.gif',
    '3_0': 'https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif',
    'ended': 'https://media.giphy.com/media/3o7aCWJavAgtBzLWrS/giphy.gif'
}

# Enhanced Emoji System
EMOJI_ICONS = {
    # Status indicators
    'fire': '🔥',
    'money': '💰',
    'trophy': '🏆',
    'player': '⚽',
    'timer': '⏰',
    'bid': '💸',
    'winner': '👑',
    'admin': '👨‍💼',
    'warning': '⚠️',
    'success': '✅',
    'error': '❌',
    'info': 'ℹ️',
    
    # Actions
    'start': '🚀',
    'stop': '⏸️',
    'skip': '⏭️',
    'undo': '↩️',
    'settings': '⚙️',
    'stats': '📊',
    'help': '🆘',
    'hammer': '🔨',
    'bell': '🔔',
    'loudspeaker': '📢',
    'rocket': '🚀',
    
    # Visual elements
    'sparkles': '✨',
    'star': '⭐',
    'medal': '🥇',
    'chart': '📈',
    'team': '👥',
    'celebration': '🎉',
    'target': '🎯',
    'lightning': '⚡',
    'gem': '💎',
    'crown': '👑',
    'wave': '👋',
    'home': '🏠',
    
    # Progress indicators
    'loading': '🔄',
    'progress': '📊',
    'complete': '✅',
    'pending': '⏳',
    'refresh': '🔄',
    'clock': '⏰',
    
    # User interface
    'user': '👤',
    'at': '@',
    'id': '🆔',
    'tip': '💡',
    'brain': '🧠',
    'scroll': '📜',
    'question': '❓',
    'lightbulb': '💡',
    'arrow_right': '➡️',
    'calendar': '📅',
    'gear': '⚙️',
    'lock': '🔒',
    
    # Data and analytics
    'chart_up': '📈',
    'chart_down': '📉',
    'moneybag': '💰',
    'coin': '🪙',
    
    # Additional icons
    'group': '👥',
    'channel': '📢',
    'bot': '🤖',
    'link': '🔗',
    'key': '🔑',
    'shield': '🛡️',
    'unlock': '🔓'
}

# Visual Progress Bars
PROGRESS_BARS = {
    'empty': '░',
    'filled': '█',
    'partial': '▓'
}

# Countdown Visual Stages
COUNTDOWN_STAGES = {
    60: {'emoji': '⏰', 'color': 'green', 'urgency': 'low'},
    30: {'emoji': '⏱️', 'color': 'yellow', 'urgency': 'medium'},
    10: {'emoji': '⏳', 'color': 'orange', 'urgency': 'high'},
    5: {'emoji': '🚨', 'color': 'red', 'urgency': 'critical'}
}

# Achievement System
ACHIEVEMENTS = {
    'first_bid': {'name': 'First Blood', 'emoji': '🎯', 'points': 10, 'description': 'Place your first bid'},
    'win_auction': {'name': 'Winner Winner', 'emoji': '🏆', 'points': 20, 'description': 'Win your first auction'},
    'bid_warrior': {'name': 'Bid Warrior', 'emoji': '⚔️', 'points': 50, 'description': 'Win 10 auctions'},
    'big_spender': {'name': 'Big Spender', 'emoji': '💎', 'points': 100, 'description': 'Spend over 100M total'},
    'auction_master': {'name': 'Auction Master', 'emoji': '👑', 'points': 500, 'description': 'Win 50 auctions'},
    'speed_bidder': {'name': 'Speed Demon', 'emoji': '⚡', 'points': 30, 'description': 'Place 5 bids in 1 minute'},
    'bargain_hunter': {'name': 'Bargain Hunter', 'emoji': '🏷️', 'points': 75, 'description': 'Win 5 players at base price'},
    'millionaire': {'name': 'Millionaire Club', 'emoji': '💰', 'points': 150, 'description': 'Maintain 100M+ balance'},
    'comeback_king': {'name': 'Comeback King', 'emoji': '🔄', 'points': 60, 'description': 'Win after being outbid 10 times'}
}

# Leaderboard Settings
LEADERBOARD_SIZE = 10
LEADERBOARD_EMOJIS = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

# Analytics Settings
TRACK_ANALYTICS = True
ANALYTICS_RETENTION_DAYS = 30

# Message Templates Configuration
MESSAGE_COOLDOWN = 1  # seconds between messages
EDIT_MESSAGE_LIMIT = 10  # max edits per message
CALLBACK_TIMEOUT = 5  # seconds for callback response

# Team Formation Templates (Removed limit)
FORMATIONS = {
    '4-3-3': {'defenders': 4, 'midfielders': 3, 'forwards': 3},
    '4-4-2': {'defenders': 4, 'midfielders': 4, 'forwards': 2},
    '3-5-2': {'defenders': 3, 'midfielders': 5, 'forwards': 2},
    '5-3-2': {'defenders': 5, 'midfielders': 3, 'forwards': 2},
    '4-2-3-1': {'defenders': 4, 'midfielders': 5, 'forwards': 1},
    '3-4-3': {'defenders': 3, 'midfielders': 4, 'forwards': 3}
}

# Player Positions
POSITIONS = {
    'GK': 'Goalkeeper',
    'CB': 'Center Back',
    'LB': 'Left Back', 
    'RB': 'Right Back',
    'LWB': 'Left Wing Back',
    'RWB': 'Right Wing Back',
    'CDM': 'Defensive Midfielder',
    'CM': 'Central Midfielder',
    'CAM': 'Attacking Midfielder',
    'LM': 'Left Midfielder',
    'RM': 'Right Midfielder',
    'LW': 'Left Winger',
    'RW': 'Right Winger',
    'CF': 'Center Forward',
    'ST': 'Striker',
    'SS': 'Second Striker'
}

# Notification Settings
ENABLE_DM_NOTIFICATIONS = True
NOTIFICATION_TYPES = {
    'outbid': True,
    'auction_won': True,
    'auction_ending': True,
    'achievement': True,
    'auction_start': True,
    'auction_end': True,
    'new_bid': True
}

# Anti-Spam Settings
MAX_BIDS_PER_MINUTE = 10
SPAM_BAN_DURATION = 300  # 5 minutes
FLOOD_CONTROL_ENABLED = True

# Cache Settings
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
CACHE_TTL = 300  # 5 minutes
USE_CACHE = True

# Webhook Settings (optional)
USE_WEBHOOK = os.getenv('USE_WEBHOOK', 'False').lower() == 'true'
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', 8443))

# Development Settings
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Sentry for error tracking (optional)
SENTRY_DSN = os.getenv('SENTRY_DSN')

# Timezone
TIMEZONE = os.getenv('TIMEZONE', 'UTC')

# API Rate Limits
TELEGRAM_RATE_LIMIT = {
    'messages_per_second': 30,
    'messages_per_minute': 20,
    'bulk_limit': 30
}

# File Upload Limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_FILE_TYPES = ['jpg', 'jpeg', 'png', 'gif', 'mp4', 'pdf', 'doc', 'docx']

# Session Management
SESSION_TIMEOUT = 3600  # 1 hour
MAX_SESSIONS = 10  # Maximum concurrent sessions

# Security Settings
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # 5 minutes
PASSWORD_MIN_LENGTH = 8

# Backup Settings
AUTO_BACKUP = True
BACKUP_INTERVAL = 24  # hours
BACKUP_RETENTION = 30  # days

# Performance Settings
CONNECTION_POOL_SIZE = 10
QUERY_TIMEOUT = 30  # seconds
MAX_CONCURRENT_AUCTIONS = 1

# Feature Flags
FEATURES = {
    'achievements': True,
    'analytics': True,
    'notifications': True,
    'auto_backup': True,
    'team_management': True,
    'advanced_stats': True,
    'multi_language': False,
    'voice_commands': False,
    'ai_recommendations': False
}

# Language Settings
DEFAULT_LANGUAGE = 'en'
SUPPORTED_LANGUAGES = ['en', 'es', 'fr', 'de', 'it', 'pt']

# Currency Settings
DEFAULT_CURRENCY = 'INR'
CURRENCY_SYMBOL = '₹'
CURRENCY_FORMAT = '{symbol}{amount:,.0f}'

# Time Zones for Global Support
SUPPORTED_TIMEZONES = [
    'UTC', 'US/Eastern', 'US/Central', 'US/Mountain', 'US/Pacific',
    'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Rome',
    'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Kolkata', 'Asia/Dubai'
]

# Help Documentation - Fixed Keys
HELP_SECTIONS = {
    'basic': {
        'title': '📚 Basic Commands',
        'description': 'Learn the essential commands to get started',
        'commands': [
            '/start - Open the main menu',
            '/help - Get help and tutorials', 
            '/balance - Check your current balance',
            '/mystats - View your detailed statistics',
            '/leaderboard - See top managers'
        ]
    },
    'bidding': {
        'title': '🎯 Bidding Guide',
        'description': 'Master the art of bidding',
        'content': [
            'Use /bid [amount] to place bids',
            'Examples: /bid 15 (for 15M), /bid +5 (current + 5M)',
            'Quick bid buttons appear during auctions',
            'Watch your balance - plan your strategy',
            'React quickly - auctions move fast!'
        ]
    },
    'strategy': {
        'title': '🧠 Strategy Tips',
        'description': 'Pro tips for auction success',
        'tips': [
            'Set position priorities before auctions start',
            'Don\'t overspend early - save for key players',
            'Watch other managers\' spending patterns',
            'Use quick bid buttons for speed',
            'Build a balanced team across all positions'
        ]
    },
    'rules': {
        'title': '📜 Auction Rules',
        'description': 'Important auction rules and guidelines',
        'rules': [
            'Minimum bid increment: 1M after 20M',
            'Starting balance: 200M for new managers',
            'No maximum team size - buy unlimited players',
            'Auction timer: 60 seconds (configurable)',
            'Timer resets on every new bid',
            'No bid cancellation once placed',
            'Fair play and respect for all participants'
        ]
    },
    'faq': {
        'title': '❓ Frequently Asked Questions',
        'description': 'Common questions and answers',
        'items': [
            {
                'question': 'How do I register?',
                'answer': 'Click "Request Access" and wait for admin approval'
            },
            {
                'question': 'Can I change my bid?',
                'answer': 'No, bids are final once placed'
            },
            {
                'question': 'What if I run out of money?',
                'answer': 'You cannot bid more than your balance'
            },
            {
                'question': 'How are achievements earned?',
                'answer': 'Through various activities like bidding, winning, and participation'
            },
            {
                'question': 'Is there a limit on players I can buy?',
                'answer': 'No! You can buy as many players as your budget allows'
            }
        ]
    }
}

# Default Settings that can be overridden by database
DEFAULT_SETTINGS = {
    'auction_mode': 'auto',
    'auction_timer': 60,
    'auction_break': 30,
    'default_balance': 200_000_000,
    'track_analytics': True,
    'notify_auction_start': True,
    'notify_auction_end': True,
    'notify_new_bid': True,
    'notify_achievements': True,
    'require_verification': False,
    'allow_new_members': True,
    'anti_spam_enabled': True,
    'ban_threshold': 5
}

# Function to update global settings from database
async def update_settings_from_db(db):
    """Update global settings from database values"""
    global AUTO_MODE, AUCTION_TIMER, DEFAULT_BALANCE, TRACK_ANALYTICS, AUCTION_BREAK
    
    try:
        # Update auction mode
        mode = await db.get_setting("auction_mode")
        if mode:
            AUTO_MODE = (mode == "auto")
            
        # Update timer
        timer = await db.get_setting("auction_timer")
        if timer:
            AUCTION_TIMER = timer
            
        # Update break timer
        break_timer = await db.get_setting("auction_break")
        if break_timer:
            AUCTION_BREAK = break_timer
            
        # Update default balance
        balance = await db.get_setting("default_balance")
        if balance:
            DEFAULT_BALANCE = balance
            
        # Update analytics
        analytics = await db.get_setting("track_analytics")
        if analytics is not None:
            TRACK_ANALYTICS = analytics
            
    except Exception as e:
        print(f"Error updating settings from database: {e}")

# Validation functions
def validate_group_id(group_id):
    """Validate group ID format"""
    if not isinstance(group_id, int):
        return False
    # Telegram group IDs are negative for groups/supergroups
    return group_id < 0

def validate_user_id(user_id):
    """Validate user ID format"""
    if not isinstance(user_id, int):
        return False
    # Telegram user IDs are positive
    return user_id > 0

def validate_currency_amount(amount):
    """Validate currency amount"""
    if not isinstance(amount, (int, float)):
        return False
    return 0 <= amount <= 10_000_000_000  # Max 10B

def validate_timer_duration(duration):
    """Validate timer duration"""
    if not isinstance(duration, int):
        return False
    return 10 <= duration <= 600  # 10 seconds to 10 minutes

# Environment validation
def validate_environment():
    """Validate required environment variables"""
    required_vars = ['BOT_TOKEN', 'SUPER_ADMIN_ID']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    # Validate bot token format
    if not BOT_TOKEN or len(BOT_TOKEN) < 40:
        raise ValueError("Invalid BOT_TOKEN format")
    
    # Validate admin ID
    try:
        int(SUPER_ADMIN_ID)
    except (ValueError, TypeError):
        raise ValueError("SUPER_ADMIN_ID must be a valid integer")

# Initialize validation on import
try:
    validate_environment()
except ValueError as e:
    print(f"Configuration Error: {e}")
    print("Please check your .env file and fix the configuration.")