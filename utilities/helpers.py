# utilities/helpers.py - Complete Validation and Helper Functions
import re
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any, List
from telegram.error import BadRequest, Forbidden
from config.settings import *

logger = logging.getLogger(__name__)

class ValidationHelper:
    @staticmethod
    def parse_player_message(text: str) -> Tuple[Optional[str], Optional[int]]:
        """Parse player message with multiple format support"""
        if not text:
            return None, None
            
        # Clean text
        text = text.strip()
        
        # Try different patterns
        patterns = [
            # 'Player Name' price or "Player Name" price
            r"['\"]([^'\"]+)['\"][\s]*(\d+(?:\.\d+)?)",
            # Player Name - price
            r"([A-Za-z\s\.\-]+)\s*[-–]\s*(\d+(?:\.\d+)?)",
            # Player Name price (at end)
            r"([A-Za-z\s\.\-]+?)\s+(\d+(?:\.\d+)?)$",
            # Just name and number
            r"^([^0-9]+?)\s*(\d+(?:\.\d+)?)$"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip().strip("'\"")
                try:
                    # Handle decimal prices (e.g., 15.5 for 15.5M)
                    price_str = match.group(2)
                    if '.' in price_str:
                        price = int(float(price_str) * 1_000_000)
                    else:
                        price = int(price_str) * 1_000_000
                        
                    # Validate reasonable price range
                    if 1_000_000 <= price <= 1_000_000_000:  # 1M to 1B
                        logger.info(f"Parsed player: {name} - {price}")
                        return name, price
                except ValueError:
                    continue
                    
        logger.warning(f"Could not parse player from: {text}")
        return None, None
        
    @staticmethod
    def validate_bid_amount(amount_str: str, current_bid: int, user_balance: int, 
                          base_price: int) -> Tuple[bool, str, int]:
        """Comprehensive bid validation"""
        try:
            # Clean amount string
            amount_str = str(amount_str).strip().replace(',', '').replace('₹', '')
            
            # Parse amount
            if '.' in amount_str:
                # Decimal millions
                amount = int(float(amount_str) * 1_000_000)
            else:
                amount = int(amount_str)
                # Auto-detect millions
                if amount <= 999:
                    amount = amount * 1_000_000
                    
        except (ValueError, TypeError):
            return False, "Invalid amount! Use numbers only (e.g., 15 for 15M)", 0
            
        # Validate amount range
        if amount <= 0:
            return False, "Amount must be positive!", 0
            
        if amount > 10_000_000_000:  # 10B max
            return False, "Amount too high! Maximum 10B", 0
            
        # Check against current bid
        if amount <= current_bid:
            diff_needed = current_bid - amount + BID_INCREMENT
            return False, f"Bid must exceed current bid! Need {diff_needed // 1_000_000}M more", 0
            
        # Check increment rules
        if current_bid >= base_price + MAX_STRAIGHT_BID:
            # Must follow increment rules
            min_increment = BID_INCREMENT
            if (amount - current_bid) < min_increment:
                return False, f"Minimum increment is {min_increment // 1_000_000}M!", 0
                
        # Check user balance
        if amount > user_balance:
            shortage = amount - user_balance
            return False, f"Insufficient balance! Need {shortage // 1_000_000}M more", 0
            
        return True, "Valid bid", amount
        
    @staticmethod
    def is_valid_message_id(message_id_str: str) -> Tuple[bool, int]:
        """Validate Telegram message ID"""
        try:
            message_id = int(message_id_str)
            # Telegram message IDs are positive integers
            if message_id > 0:
                return True, message_id
        except (ValueError, TypeError):
            pass
        return False, 0
        
    @staticmethod
    def format_time_remaining(seconds: int) -> str:
        """Format time in human-readable format"""
        if seconds <= 0:
            return "Time's up!"
        elif seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
            
    @staticmethod
    def parse_duration(duration_str: str) -> Optional[int]:
        """Parse duration string to seconds"""
        duration_str = duration_str.lower().strip()
        
        # Match patterns like "30s", "5m", "1h30m"
        pattern = r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?'
        match = re.match(pattern, duration_str)
        
        if not match or not any(match.groups()):
            return None
            
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        total_seconds = hours * 3600 + minutes * 60 + seconds
        
        # Validate reasonable range (5 seconds to 24 hours)
        if 5 <= total_seconds <= 86400:
            return total_seconds
            
        return None
        
    @staticmethod
    def extract_player_details(text: str) -> Dict[str, Any]:
        """Extract additional player details from text"""
        details = {
            'position': None,
            'rating': None,
            'team': None,
            'nationality': None,
            'special': []
        }
        
        # Position detection
        positions = [
            'GK', 'CB', 'LB', 'RB', 'LWB', 'RWB', 'CDM', 'CM', 'CAM', 
            'LM', 'RM', 'LW', 'RW', 'CF', 'ST', 'SS'
        ]
        
        text_upper = text.upper()
        for pos in positions:
            if f' {pos} ' in f' {text_upper} ' or text_upper.endswith(f' {pos}'):
                details['position'] = pos
                break
                
        # Rating detection (e.g., "87 rated", "87 OVR")
        rating_patterns = [
            r'(\d{2})\s*(?:rated|ovr|overall)',
            r'(?:rated|ovr|overall)\s*(\d{2})'
        ]
        
        for pattern in rating_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                rating = int(match.group(1))
                if 40 <= rating <= 99:  # Valid rating range
                    details['rating'] = rating
                    break
                    
        # Special card detection
        special_types = [
            'POTM', 'TOTW', 'Featured', 'Legend', 'Iconic', 'IM', 
            'TOTY', 'TOTS', 'Special', 'Premium'
        ]
        
        for special in special_types:
            if special.lower() in text.lower():
                details['special'].append(special)
                
        return details
        
    @staticmethod
    def calculate_bid_statistics(bids: List[Any]) -> Dict[str, Any]:
        """Calculate statistics from bid history"""
        if not bids:
            return {
                'total_bids': 0,
                'unique_bidders': 0,
                'avg_increment': 0,
                'max_increment': 0,
                'bid_frequency': 0,
                'competition_score': 0
            }
            
        # Calculate increments
        increments = []
        for i in range(1, len(bids)):
            increment = bids[i].amount - bids[i-1].amount
            increments.append(increment)
            
        # Calculate time intervals
        intervals = []
        for i in range(1, len(bids)):
            interval = (bids[i].timestamp - bids[i-1].timestamp).seconds
            intervals.append(interval)
            
        # Unique bidders
        unique_bidders = len(set(bid.user_id for bid in bids))
        
        # Competition score (0-100)
        competition_score = min(100, (unique_bidders * 20) + (len(bids) * 2))
        
        return {
            'total_bids': len(bids),
            'unique_bidders': unique_bidders,
            'avg_increment': sum(increments) // len(increments) if increments else 0,
            'max_increment': max(increments) if increments else 0,
            'bid_frequency': sum(intervals) / len(intervals) if intervals else 0,
            'competition_score': competition_score
        }
        
    @staticmethod
    def generate_session_id() -> str:
        """Generate unique session ID"""
        return f"AUC_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
    @staticmethod
    def validate_username(username: str) -> bool:
        """Validate Telegram username"""
        if not username:
            return False
            
        # Remove @ if present
        username = username.lstrip('@')
        
        # Telegram username rules: 5-32 chars, alphanumeric and underscores
        pattern = r'^[a-zA-Z0-9_]{5,32}$'
        return bool(re.match(pattern, username))
        
    @staticmethod
    def sanitize_input(text: str, max_length: int = 100) -> str:
        """Sanitize user input"""
        if not text:
            return ""
            
        # Remove control characters
        text = ''.join(char for char in text if char.isprintable() or char.isspace())
        
        # Limit length
        text = text[:max_length]
        
        # Strip extra whitespace
        text = ' '.join(text.split())
        
        return text.strip()
        
    @staticmethod
    def format_relative_time(timestamp: datetime) -> str:
        """Format timestamp as relative time"""
        now = datetime.now()
        diff = now - timestamp
        
        if diff.days > 7:
            return timestamp.strftime('%d %b %Y')
        elif diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "just now"
            
    @staticmethod
    def get_time_slot() -> str:
        """Get current time slot for analytics"""
        hour = datetime.now().hour
        
        if 6 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"
            
    @staticmethod
    def calculate_manager_level(points: int) -> Tuple[int, int, int]:
        """Calculate manager level from points"""
        level_thresholds = [
            0,      # Level 1
            50,     # Level 2
            150,    # Level 3
            300,    # Level 4
            500,    # Level 5
            1000,   # Level 6
            2000,   # Level 7
            5000,   # Level 8
            10000,  # Level 9
            20000   # Level 10
        ]
        
        level = 1
        for i, threshold in enumerate(level_thresholds[1:], 1):
            if points >= threshold:
                level = i + 1
            else:
                # Current level, points to next level, total for next level
                prev_threshold = level_thresholds[i-1]
                points_in_level = points - prev_threshold
                points_for_next = threshold - prev_threshold
                return level, points_in_level, points_for_next
                
        # Max level
        return len(level_thresholds), 0, 0
        
    @staticmethod
    def check_spam_pattern(user_id: int, action_history: List[datetime], 
                         window_seconds: int = 60, max_actions: int = 10) -> bool:
        """Check if user actions match spam pattern"""
        if not action_history:
            return False
            
        now = datetime.now()
        recent_actions = [
            action for action in action_history 
            if (now - action).seconds <= window_seconds
        ]
        
        return len(recent_actions) >= max_actions
    

class GroupIDFinder:
    """Helper class to find and validate group IDs"""
    
    @staticmethod
    async def find_group_id(bot, identifier: str) -> Optional[int]:
        """Find group ID from username or invite link"""
        try:
            # Handle @username
            if identifier.startswith('@'):
                chat = await bot.get_chat(identifier)
                return chat.id
                
            # Handle t.me/username
            elif 't.me/' in identifier:
                username = identifier.split('t.me/')[-1]
                if not username.startswith('@'):
                    username = '@' + username
                chat = await bot.get_chat(username)
                return chat.id
                
            # Handle direct chat ID
            elif identifier.lstrip('-').isdigit():
                chat_id = int(identifier)
                chat = await bot.get_chat(chat_id)
                return chat.id
                
        except Exception as e:
            logger.error(f"Error finding group ID for {identifier}: {e}")
            return None
            
    @staticmethod
    async def validate_bot_access(bot, chat_id: int) -> bool:
        """Check if bot has access to the chat"""
        try:
            member = await bot.get_chat_member(chat_id, bot.id)
            return member.status in ['administrator', 'member']
        except:
            return False


class NotificationManager:
    """Manage user notifications"""
    
    def __init__(self, db):
        self.db = db
        
    async def send_notification(self, user_id: int, notification_type: str, 
                              title: str, message: str, data: Dict = None):
        """Send notification to user"""
        try:
            # Check user notification preferences
            settings = await self.db.get_user_settings(user_id)
            if not settings.get('notifications', {}).get(notification_type, True):
                return False
                
            # Create notification in database
            await self.db.create_notification(user_id, notification_type, title, message, data or {})
            return True
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False
            
    async def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification statistics"""
        try:
            # Get stats from last 7 days
            start_date = datetime.now() - timedelta(days=7)
            
            pipeline = [
                {"$match": {"created_at": {"$gte": start_date}}},
                {"$group": {
                    "_id": "$type",
                    "total": {"$sum": 1},
                    "read": {"$sum": {"$cond": ["$is_read", 1, 0]}}
                }}
            ]
            
            cursor = self.db.notifications.aggregate(pipeline)
            stats = {}
            async for doc in cursor:
                stats[doc['_id']] = {
                    'total': doc['total'],
                    'read': doc['read'],
                    'read_rate': (doc['read'] / doc['total']) * 100 if doc['total'] > 0 else 0
                }
                
            return stats
            
        except Exception as e:
            logger.error(f"Error getting notification stats: {e}")
            return {}


class SecurityManager:
    """Handle security-related operations"""
    
    def __init__(self, db):
        self.db = db
        self.failed_attempts = {}
        self.banned_ips = set()
        
    async def check_user_permissions(self, user_id: int, required_role: str) -> bool:
        """Check if user has required permissions"""
        try:
            manager = await self.db.get_manager(user_id)
            if not manager:
                return False
                
            if manager.is_banned:
                return False
                
            # Check role hierarchy
            role_hierarchy = {
                'user': 0,
                'vip': 1,
                'moderator': 2,
                'admin': 3,
                'super_admin': 4
            }
            
            user_level = role_hierarchy.get(manager.role, 0)
            required_level = role_hierarchy.get(required_role, 0)
            
            return user_level >= required_level
            
        except Exception as e:
            logger.error(f"Error checking permissions: {e}")
            return False
            
    async def log_security_event(self, event_type: str, user_id: int, details: Dict):
        """Log security events"""
        try:
            await self.db.track_event(f'security_{event_type}', user_id, details)
        except Exception as e:
            logger.error(f"Error logging security event: {e}")
            
    async def check_rate_limit(self, user_id: int, action: str, 
                             window_minutes: int = 1, max_attempts: int = 10) -> bool:
        """Check if user is rate limited"""
        try:
            key = f"{user_id}_{action}"
            now = datetime.now()
            
            if key not in self.failed_attempts:
                self.failed_attempts[key] = []
                
            # Clean old attempts
            self.failed_attempts[key] = [
                attempt for attempt in self.failed_attempts[key]
                if (now - attempt).seconds < (window_minutes * 60)
            ]
            
            # Check limit
            if len(self.failed_attempts[key]) >= max_attempts:
                await self.log_security_event('rate_limit', user_id, {
                    'action': action,
                    'attempts': len(self.failed_attempts[key])
                })
                return True
                
            # Add current attempt
            self.failed_attempts[key].append(now)
            return False
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False


class DataExporter:
    """Export data in various formats"""
    
    def __init__(self, db):
        self.db = db
        
    async def export_auction_data(self, format_type: str = 'csv') -> bytes:
        """Export auction data"""
        try:
            auctions = await self.db.get_auction_results()
            
            if format_type == 'csv':
                return await self._export_as_csv(auctions)
            elif format_type == 'json':
                return await self._export_as_json(auctions)
            else:
                raise ValueError(f"Unsupported format: {format_type}")
                
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return b""
            
    async def _export_as_csv(self, data: List[Dict]) -> bytes:
        """Export data as CSV"""
        import csv
        import io
        
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            
        return output.getvalue().encode('utf-8')
        
    async def _export_as_json(self, data: List[Dict]) -> bytes:
        """Export data as JSON"""
        import json
        return json.dumps(data, indent=2, default=str).encode('utf-8')
        
    async def generate_manager_report(self, user_id: int) -> Dict[str, Any]:
        """Generate detailed manager report"""
        try:
            manager = await self.db.get_manager(user_id)
            if not manager:
                return {}
                
            # Get analytics
            analytics = await self.db.get_user_analytics(user_id, days=30)
            
            # Get auction history
            auctions = await self.db.auctions.find({
                "bids.user_id": user_id,
                "status": "completed"
            }).to_list(None)
            
            return {
                'manager': manager.to_dict(),
                'analytics': analytics,
                'auction_history': auctions,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating manager report: {e}")
            return {}


class ConfigManager:
    """Manage dynamic configuration"""
    
    def __init__(self, db):
        self.db = db
        self.cache = {}
        self.cache_expiry = {}
        
    async def get_config(self, key: str, default=None):
        """Get configuration value with caching"""
        try:
            # Check cache first
            if key in self.cache and key in self.cache_expiry:
                if datetime.now() < self.cache_expiry[key]:
                    return self.cache[key]
                    
            # Get from database
            value = await self.db.get_setting(key)
            if value is None:
                value = default
                
            # Cache for 5 minutes
            self.cache[key] = value
            self.cache_expiry[key] = datetime.now() + timedelta(minutes=5)
            
            return value
            
        except Exception as e:
            logger.error(f"Error getting config {key}: {e}")
            return default
            
    async def set_config(self, key: str, value: Any):
        """Set configuration value"""
        try:
            await self.db.set_setting(key, value)
            
            # Update cache
            self.cache[key] = value
            self.cache_expiry[key] = datetime.now() + timedelta(minutes=5)
            
        except Exception as e:
            logger.error(f"Error setting config {key}: {e}")
            
    def clear_cache(self):
        """Clear configuration cache"""
        self.cache.clear()
        self.cache_expiry.clear()