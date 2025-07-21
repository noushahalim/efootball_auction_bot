# database/db.py - Enhanced Database Operations with MongoDB...
import motor.motor_asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from bson import ObjectId
import logging
from config.settings import *
from database.models import *

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        self.db = self.client[DATABASE_NAME]
        
        # Collections
        self.managers = self.db.managers
        self.players = self.db.players
        self.auctions = self.db.auctions
        self.achievements = self.db.achievements
        self.analytics = self.db.analytics
        self.notifications = self.db.notifications
        self.teams = self.db.teams
        self.sessions = self.db.sessions
        self.settings = self.db.settings
        self.groups = self.db.groups
        self.broadcasts = self.db.broadcasts
        self.join_requests = self.db.join_requests

    async def create_indexes(self):
        """Create database indexes for performance"""
        try:
            # Manager indexes
            await self.managers.create_index("user_id", unique=True)
            await self.managers.create_index("username")
            await self.managers.create_index([("statistics.points", -1)])
            await self.managers.create_index("is_banned")
            await self.managers.create_index("role")
            
            # Player indexes
            await self.players.create_index("message_id", unique=True)
            await self.players.create_index("status")
            await self.players.create_index("name")
            await self.players.create_index("position")
            await self.players.create_index("created_at")
            
            # Auction indexes
            await self.auctions.create_index("status")
            await self.auctions.create_index([("start_time", -1)])
            await self.auctions.create_index("current_bidder")
            await self.auctions.create_index("player_name")
            
            # Analytics indexes
            await self.analytics.create_index([("timestamp", -1)])
            await self.analytics.create_index("event_type")
            await self.analytics.create_index("user_id")
            
            # Notification indexes
            await self.notifications.create_index("user_id")
            await self.notifications.create_index([("created_at", -1)])
            await self.notifications.create_index("is_read")
            
            # Groups indexes
            await self.groups.create_index("chat_id", unique=True)
            await self.groups.create_index("status")
            
            # Settings indexes
            await self.settings.create_index("key", unique=True)
            await self.settings.create_index("user_id")
            
            # Join requests indexes
            await self.join_requests.create_index([("user_id", 1), ("status", 1)])
            await self.join_requests.create_index("created_at")
            
            logger.info("✅ Database indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")

    # Manager operations
    async def add_manager(self, manager: Manager) -> bool:
        """Add a new manager with duplicate check"""
        try:
            # Check if already exists
            existing = await self.managers.find_one({"user_id": manager.user_id})
            if existing:
                return False
                
            await self.managers.insert_one(manager.to_dict())
            
            # Track analytics
            await self.track_event('manager_registered', manager.user_id, {
                'name': manager.name,
                'initial_balance': manager.balance
            })
            
            return True
        except Exception as e:
            logger.error(f"Error adding manager: {e}")
            return False

    async def get_manager(self, user_id: int) -> Optional[Manager]:
        """Get manager by user ID with caching"""
        try:
            doc = await self.managers.find_one({"user_id": user_id})
            if doc:
                # Update last active
                await self.managers.update_one(
                    {"user_id": user_id},
                    {"$set": {"last_active": datetime.now()}}
                )
                return Manager.from_dict(doc)
            return None
        except Exception as e:
            logger.error(f"Error getting manager {user_id}: {e}")
            return None

    async def update_manager_balance(self, user_id: int, new_balance: int, spent: int = 0):
        """Update manager balance with transaction logging"""
        try:
            result = await self.managers.update_one(
                {"user_id": user_id},
                {
                    "$set": {"balance": new_balance},
                    "$inc": {"total_spent": spent}
                }
            )
            
            # Track spending
            if spent > 0:
                await self.track_event('balance_spent', user_id, {
                    'amount': spent,
                    'new_balance': new_balance
                })
                
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating balance for {user_id}: {e}")
            return False

    async def add_player_to_manager(self, user_id: int, player_name: str, price: int):
        """Add player to manager's collection with stats update"""
        try:
            # Create player record
            player_data = {
                'name': player_name,
                'price': price,
                'bought_at': datetime.now()
            }
            
            result = await self.managers.update_one(
                {"user_id": user_id},
                {
                    "$push": {"players": player_data},
                    "$inc": {
                        "statistics.auctions_won": 1,
                        "statistics.points": 10
                    },
                    "$set": {"last_active": datetime.now()}
                }
            )
            
            # Check for achievements
            await self.check_achievements(user_id, 'auction_won')
            
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error adding player to manager {user_id}: {e}")
            return False

    async def get_all_managers(self, include_banned: bool = False) -> List[Manager]:
        """Get all managers with optional filtering"""
        try:
            query = {} if include_banned else {"is_banned": {"$ne": True}}
            cursor = self.managers.find(query).sort("statistics.points", -1)
            managers = []
            async for doc in cursor:
                managers.append(Manager.from_dict(doc))
            return managers
        except Exception as e:
            logger.error(f"Error getting all managers: {e}")
            return []

    async def get_leaderboard(self, limit: int = 10) -> List[Manager]:
        """Get top managers by points"""
        try:
            cursor = self.managers.find({"is_banned": {"$ne": True}}).sort(
                "statistics.points", -1
            ).limit(limit)
            
            leaderboard = []
            async for doc in cursor:
                leaderboard.append(Manager.from_dict(doc))
            return leaderboard
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []

    async def ban_manager(self, user_id: int, banned_by: int, reason: str):
        """Ban a manager"""
        try:
            await self.managers.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_banned": True,
                        "ban_reason": reason,
                        "banned_by": banned_by,
                        "banned_at": datetime.now()
                    }
                }
            )
            
            # Track ban event
            await self.track_event('manager_banned', user_id, {
                'banned_by': banned_by,
                'reason': reason
            })
            
        except Exception as e:
            logger.error(f"Error banning manager {user_id}: {e}")

    async def unban_manager(self, user_id: int):
        """Unban a manager"""
        try:
            await self.managers.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_banned": False,
                        "ban_reason": None,
                        "banned_by": None,
                        "banned_at": None
                    }
                }
            )
            
            # Track unban event
            await self.track_event('manager_unbanned', user_id, {})
            
        except Exception as e:
            logger.error(f"Error unbanning manager {user_id}: {e}")

    async def reset_all_balances(self, new_balance: int, reset_by: int):
        """Reset all manager balances"""
        try:
            await self.managers.update_many(
                {"user_id": {"$nin": ADMIN_IDS}},  # Don't reset admin balances
                {
                    "$set": {
                        "balance": new_balance,
                        "total_spent": 0,
                        "players": [],
                        "last_balance_reset": datetime.now(),
                        "reset_by": reset_by
                    }
                }
            )
            
            # Track reset event
            await self.track_event('balances_reset', reset_by, {
                'new_balance': new_balance
            })
            
        except Exception as e:
            logger.error(f"Error resetting balances: {e}")

    async def remove_all_managers(self, removed_by: int) -> int:
        """Remove all non-admin managers"""
        try:
            result = await self.managers.delete_many({
                "user_id": {"$nin": ADMIN_IDS}
            })
            
            # Track removal event
            await self.track_event('managers_removed', removed_by, {
                'count': result.deleted_count
            })
            
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error removing all managers: {e}")
            return 0

    # Player operations
    async def add_player(self, player: Player) -> bool:
        """Add a new player to database"""
        try:
            # Check if message_id already exists
            existing = await self.players.find_one({"message_id": player.message_id})
            if existing:
                logger.warning(f"Player with message_id {player.message_id} already exists")
                return False
                
            await self.players.insert_one(player.to_dict())
            return True
        except Exception as e:
            logger.error(f"Error adding player: {e}")
            return False

    async def get_player_by_message_id(self, message_id: int) -> Optional[Player]:
        """Get player by message ID"""
        try:
            doc = await self.players.find_one({"message_id": message_id})
            if doc:
                return Player.from_dict(doc)
            return None
        except Exception as e:
            logger.error(f"Error getting player by message ID {message_id}: {e}")
            return None

    async def get_available_players(self) -> List[Player]:
        """Get all available players for auction"""
        try:
            cursor = self.players.find({"status": "available"}).sort("created_at", 1)
            players = []
            async for doc in cursor:
                players.append(Player.from_dict(doc))
            return players
        except Exception as e:
            logger.error(f"Error getting available players: {e}")
            return []

    async def update_player_status(self, message_id: int, status: str, 
                                 sold_to: int = None, final_price: int = None):
        """Update player status after auction"""
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.now()
            }
            if sold_to:
                update_data["sold_to"] = sold_to
            if final_price:
                update_data["final_price"] = final_price
                
            await self.players.update_one(
                {"message_id": message_id},
                {"$set": update_data}
            )
        except Exception as e:
            logger.error(f"Error updating player status: {e}")

    # Auction operations
    async def create_auction(self, auction: Auction) -> ObjectId:
        """Create a new auction with session tracking"""
        try:
            # Get or create current session
            session = await self.get_current_session()
            if session:
                await self.sessions.update_one(
                    {"session_id": session['session_id']},
                    {"$inc": {"total_players": 1}}
                )
            
            result = await self.auctions.insert_one(auction.to_dict())
            
            # Track auction start
            await self.track_event('auction_started', None, {
                'player': auction.player_name,
                'base_price': auction.base_price,
                'auction_id': str(result.inserted_id)
            })
            
            return result.inserted_id
        except Exception as e:
            logger.error(f"Error creating auction: {e}")
            raise

    async def get_current_auction(self) -> Optional[Auction]:
        """Get current active auction with bid objects"""
        try:
            doc = await self.auctions.find_one({"status": AuctionStatus.ACTIVE.value})
            if doc:
                return Auction.from_dict(doc)
            return None
        except Exception as e:
            logger.error(f"Error getting current auction: {e}")
            return None

    async def update_auction_bid(self, auction_id: ObjectId, bid: Bid):
        """Add a bid to auction with statistics update"""
        try:
            # Update auction
            await self.auctions.update_one(
                {"_id": auction_id},
                {
                    "$push": {"bids": bid.to_dict()},
                    "$set": {
                        "current_bid": bid.amount,
                        "current_bidder": bid.user_id
                    },
                    "$inc": {"quick_stats.total_bidders": 1}
                }
            )
            
            # Update user statistics
            await self.managers.update_one(
                {"user_id": bid.user_id},
                {
                    "$inc": {
                        "statistics.total_bids": 1,
                        "statistics.points": 1
                    },
                    "$max": {"statistics.highest_bid": bid.amount}
                }
            )
            
            # Check for first bid achievement
            manager = await self.get_manager(bid.user_id)
            if manager and manager.statistics.get('total_bids', 0) == 1:
                await self.check_achievements(bid.user_id, 'first_bid')
            
            # Track bid
            await self.track_event('bid_placed', bid.user_id, {
                'amount': bid.amount,
                'auction_id': str(auction_id),
                'bid_type': bid.bid_type
            })
            
        except Exception as e:
            logger.error(f"Error updating auction bid: {e}")
            raise

    async def complete_auction(self, auction_id: ObjectId):
        """Complete an auction with final statistics"""
        try:
            auction = await self.auctions.find_one({"_id": auction_id})
            if not auction:
                return
                
            end_time = datetime.now()
            duration = (end_time - auction['start_time']).seconds
            
            await self.auctions.update_one(
                {"_id": auction_id},
                {
                    "$set": {
                        "status": AuctionStatus.COMPLETED.value,
                        "end_time": end_time,
                        "quick_stats.duration": duration
                    }
                }
            )
            
            # Update session stats
            session = await self.get_current_session()
            if session:
                if auction.get('current_bidder'):
                    await self.sessions.update_one(
                        {"session_id": session['session_id']},
                        {
                            "$inc": {
                                "sold_players": 1,
                                "total_money_spent": auction['current_bid']
                            }
                        }
                    )
                else:
                    await self.sessions.update_one(
                        {"session_id": session['session_id']},
                        {"$inc": {"unsold_players": 1}}
                    )
                    
            # Track completion
            await self.track_event('auction_completed', auction.get('current_bidder'), {
                'player': auction['player_name'],
                'final_price': auction['current_bid'],
                'duration': duration,
                'total_bids': len(auction.get('bids', []))
            })
                
        except Exception as e:
            logger.error(f"Error completing auction: {e}")

    async def get_auction_results(self, session_id: Optional[str] = None) -> List[dict]:
        """Get completed auction results"""
        try:
            query = {"status": AuctionStatus.COMPLETED.value}
            if session_id:
                # Filter by session if provided
                session = await self.sessions.find_one({"session_id": session_id})
                if session:
                    query["start_time"] = {
                        "$gte": session['start_time'],
                        "$lte": session.get('end_time', datetime.now())
                    }
                
            cursor = self.auctions.find(query).sort("end_time", -1)
            results = []
            async for doc in cursor:
                results.append(doc)
            return results
        except Exception as e:
            logger.error(f"Error getting auction results: {e}")
            return []

    # Analytics operations
    async def track_event(self, event_type: str, user_id: Optional[int], data: Dict[str, Any]):
        """Track analytics event"""
        if not TRACK_ANALYTICS:
            return
            
        try:
            analytics = Analytics(
                event_type=event_type,
                user_id=user_id,
                data=data
            )
            await self.analytics.insert_one(analytics.to_dict())
        except Exception as e:
            logger.error(f"Error tracking event: {e}")

    async def get_user_analytics(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """Get user analytics for specified period"""
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            pipeline = [
                {
                    "$match": {
                        "user_id": user_id,
                        "timestamp": {"$gte": start_date}
                    }
                },
                {
                    "$group": {
                        "_id": "$event_type",
                        "count": {"$sum": 1},
                        "data": {"$push": "$data"}
                    }
                }
            ]
            
            cursor = self.analytics.aggregate(pipeline)
            analytics = {}
            async for doc in cursor:
                analytics[doc['_id']] = {
                    'count': doc['count'],
                    'data': doc['data']
                }
            return analytics
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {}

    # Achievement operations
    async def check_achievements(self, user_id: int, trigger: str):
        """Check and award achievements"""
        try:
            manager = await self.get_manager(user_id)
            if not manager:
                return
                
            # Check various achievement conditions
            achievements_to_check = []
            
            if trigger == 'first_bid' and manager.statistics.get('total_bids', 0) == 1:
                achievements_to_check.append('first_bid')
                
            if trigger == 'auction_won':
                wins = manager.statistics.get('auctions_won', 0)
                if wins == 1:
                    achievements_to_check.append('win_auction')
                elif wins == 10:
                    achievements_to_check.append('bid_warrior')
                elif wins == 50:
                    achievements_to_check.append('auction_master')
                    
            if trigger == 'team_complete' and len(manager.players) == 11:
                achievements_to_check.append('perfect_team')
                
            if manager.total_spent > 100_000_000:
                achievements_to_check.append('big_spender')
                
            # Award achievements
            for achievement_id in achievements_to_check:
                await self.award_achievement(user_id, achievement_id)
        except Exception as e:
            logger.error(f"Error checking achievements: {e}")

    async def award_achievement(self, user_id: int, achievement_id: str):
        """Award achievement to user"""
        try:
            # Check if already awarded
            existing = await self.achievements.find_one({
                "user_id": user_id,
                "achievement_id": achievement_id
            })
            
            if existing:
                return
                
            # Award achievement
            achievement = Achievement(
                user_id=user_id,
                achievement_id=achievement_id,
                is_completed=True
            )
            
            await self.achievements.insert_one(achievement.to_dict())
            
            # Update manager
            points = ACHIEVEMENTS.get(achievement_id, {}).get('points', 0)
            await self.managers.update_one(
                {"user_id": user_id},
                {
                    "$push": {"achievements": achievement_id},
                    "$inc": {"statistics.points": points}
                }
            )
            
            # Create notification
            await self.create_notification(
                user_id,
                'achievement',
                f"🎉 Achievement Unlocked!",
                f"You've earned: {ACHIEVEMENTS[achievement_id]['name']}",
                {'achievement_id': achievement_id}
            )
            
            # Track achievement
            await self.track_event('achievement_unlocked', user_id, {
                'achievement_id': achievement_id,
                'points': points
            })
            
        except Exception as e:
            logger.error(f"Error awarding achievement: {e}")

    # Notification operations
    async def create_notification(self, user_id: int, type: str, title: str, 
                                message: str, data: Dict[str, Any] = None):
        """Create notification for user"""
        try:
            notification = Notification(
                user_id=user_id,
                type=type,
                title=title,
                message=message,
                data=data or {}
            )
            
            await self.notifications.insert_one(notification.to_dict())
        except Exception as e:
            logger.error(f"Error creating notification: {e}")

    async def get_unread_notifications(self, user_id: int) -> List[Notification]:
        """Get unread notifications for user"""
        try:
            cursor = self.notifications.find({
                "user_id": user_id,
                "is_read": False
            }).sort("created_at", -1).limit(10)
            
            notifications = []
            async for doc in cursor:
                notifications.append(Notification(**doc))
            return notifications
        except Exception as e:
            logger.error(f"Error getting notifications: {e}")
            return []

    async def mark_notifications_read(self, user_id: int):
        """Mark all notifications as read for user"""
        try:
            await self.notifications.update_many(
                {"user_id": user_id, "is_read": False},
                {"$set": {"is_read": True}}
            )
        except Exception as e:
            logger.error(f"Error marking notifications read: {e}")

    # Settings operations
    async def get_setting(self, key: str) -> Any:
        """Get a setting value"""
        try:
            doc = await self.settings.find_one({"key": key})
            return doc["value"] if doc else None
        except Exception as e:
            logger.error(f"Error getting setting {key}: {e}")
            return None

    async def set_setting(self, key: str, value: Any):
        """Set a setting value"""
        try:
            await self.settings.update_one(
                {"key": key},
                {"$set": {"key": key, "value": value, "updated_at": datetime.now()}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error setting {key}: {e}")

    async def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """Get user-specific settings"""
        try:
            doc = await self.settings.find_one({"user_id": user_id})
            if not doc:
                # Return default settings
                return {
                    'notifications': {
                        'auction_start': True,
                        'auction_end': True,
                        'outbid': True,
                        'achievements': True
                    },
                    'display': {
                        'show_balance': True,
                        'show_stats': True,
                        'compact_mode': False
                    },
                    'bidding': {
                        'confirm_bids': False,
                        'auto_increment': 1_000_000,
                        'quick_bid_amounts': [1_000_000, 2_000_000, 5_000_000]
                    }
                }
            return doc.get('settings', {})
        except Exception as e:
            logger.error(f"Error getting user settings: {e}")
            return {}

    async def update_user_settings(self, user_id: int, settings: Dict[str, Any]):
        """Update user settings"""
        try:
            await self.settings.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "settings": settings,
                        "updated_at": datetime.now()
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating user settings: {e}")

    # Session operations
    async def create_session(self, name: str) -> str:
        """Create new auction session"""
        try:
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            session = AuctionSession(
                session_id=session_id,
                name=name
            )
            
            # End any existing active session
            await self.sessions.update_many(
                {"status": "active"},
                {"$set": {"status": "completed", "end_time": datetime.now()}}
            )
            
            await self.sessions.insert_one(session.to_dict())
            
            # Track session creation
            await self.track_event('session_created', None, {
                'session_id': session_id,
                'name': name
            })
            
            return session_id
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return ""

    async def get_current_session(self) -> Optional[dict]:
        """Get current active session"""
        try:
            return await self.sessions.find_one({"status": "active"})
        except Exception as e:
            logger.error(f"Error getting current session: {e}")
            return None

    async def close_session(self, session_id: str):
        """Close an auction session"""
        try:
            await self.sessions.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "status": "completed",
                        "end_time": datetime.now()
                    }
                }
            )
            
            # Track session closure
            await self.track_event('session_closed', None, {
                'session_id': session_id
            })
            
        except Exception as e:
            logger.error(f"Error closing session: {e}")

    # Group management operations
    async def add_group(self, chat_id: int, title: str, group_type: str):
        """Add a group to bot management"""
        try:
            group_data = {
                'chat_id': chat_id,
                'title': title,
                'type': group_type,
                'status': 'active',
                'added_at': datetime.now(),
                'settings': {
                    'allow_bidding': True,
                    'min_bid_increment': 1_000_000,
                    'auction_duration': 60
                }
            }
            
            await self.groups.update_one(
                {'chat_id': chat_id},
                {'$set': group_data},
                upsert=True
            )
            
            # Track group addition
            await self.track_event('group_added', None, {
                'chat_id': chat_id,
                'title': title,
                'type': group_type
            })
            
        except Exception as e:
            logger.error(f"Error adding group: {e}")

    async def get_group(self, chat_id: int) -> Optional[dict]:
        """Get group information"""
        try:
            return await self.groups.find_one({'chat_id': chat_id})
        except Exception as e:
            logger.error(f"Error getting group: {e}")
            return None

    async def get_all_groups(self) -> List[dict]:
        """Get all managed groups"""
        try:
            cursor = self.groups.find({'status': 'active'})
            groups = []
            async for doc in cursor:
                groups.append(doc)
            return groups
        except Exception as e:
            logger.error(f"Error getting all groups: {e}")
            return []

    async def update_group_status(self, chat_id: int, status: str):
        """Update group status"""
        try:
            await self.groups.update_one(
                {'chat_id': chat_id},
                {'$set': {'status': status, 'updated_at': datetime.now()}}
            )
        except Exception as e:
            logger.error(f"Error updating group status: {e}")

    async def remove_group(self, chat_id: int):
        """Remove a group from management"""
        try:
            await self.groups.update_one(
                {'chat_id': chat_id},
                {'$set': {'status': 'removed', 'removed_at': datetime.now()}}
            )
        except Exception as e:
            logger.error(f"Error removing group: {e}")

    # Join request operations
    async def add_join_request(self, request_data: dict):
        """Add a join request"""
        try:
            request_data['created_at'] = datetime.now()
            request_data['status'] = 'pending'
            
            await self.join_requests.insert_one(request_data)
            
            # Track join request
            await self.track_event('join_request_created', request_data['user_id'], {
                'user_name': request_data.get('user_name'),
                'username': request_data.get('username')
            })
            
        except Exception as e:
            logger.error(f"Error adding join request: {e}")

    async def get_pending_requests(self) -> List[dict]:
        """Get all pending join requests"""
        try:
            cursor = self.join_requests.find({'status': 'pending'}).sort('created_at', -1)
            requests = []
            async for doc in cursor:
                requests.append(doc)
            return requests
        except Exception as e:
            logger.error(f"Error getting pending requests: {e}")
            return []

    async def process_join_request(self, user_id: int, chat_id: int, approved: bool, processed_by: int):
        """Process a join request"""
        try:
            status = 'approved' if approved else 'rejected'
            
            await self.join_requests.update_one(
                {'user_id': user_id, 'chat_id': chat_id, 'status': 'pending'},
                {
                    '$set': {
                        'status': status,
                        'processed_by': processed_by,
                        'processed_at': datetime.now()
                    }
                }
            )
            
            # Track processing
            await self.track_event('join_request_processed', user_id, {
                'approved': approved,
                'processed_by': processed_by
            })
            
        except Exception as e:
            logger.error(f"Error processing join request: {e}")

    # Admin operations
    async def update_admin_list(self):
        """Update admin list from database"""
        try:
            admins = await self.managers.find({
                "role": {"$in": [ManagerRole.ADMIN.value, ManagerRole.SUPER_ADMIN.value]}
            }).to_list(None)
            
            admin_ids = [admin['user_id'] for admin in admins]
            ADMIN_IDS.clear()
            ADMIN_IDS.extend(admin_ids)
            ADMIN_IDS.append(SUPER_ADMIN_ID)  # Always include super admin
            
            logger.info(f"Updated admin list: {len(ADMIN_IDS)} admins")
        except Exception as e:
            logger.error(f"Error updating admin list: {e}")

    async def make_admin(self, user_id: int, role: str = ManagerRole.ADMIN.value):
        """Make a user admin"""
        try:
            await self.managers.update_one(
                {"user_id": user_id},
                {"$set": {"role": role}}
            )
            
            # Update admin list
            await self.update_admin_list()
            
            # Track admin creation
            await self.track_event('admin_created', user_id, {
                'role': role
            })
            
        except Exception as e:
            logger.error(f"Error making admin: {e}")

    async def remove_admin(self, user_id: int):
        """Remove admin privileges"""
        try:
            await self.managers.update_one(
                {"user_id": user_id},
                {"$set": {"role": ManagerRole.USER.value}}
            )
            
            # Update admin list
            await self.update_admin_list()
            
            # Track admin removal
            await self.track_event('admin_removed', user_id, {})
            
        except Exception as e:
            logger.error(f"Error removing admin: {e}")

    # Cleanup operations
    async def cleanup_old_auctions(self, days: int = 30):
        """Clean up old auction data"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Archive old completed auctions
            old_auctions = await self.auctions.count_documents({
                "status": "completed",
                "end_time": {"$lt": cutoff_date}
            })
            
            if old_auctions > 0:
                logger.info(f"Found {old_auctions} old auctions to archive")
                # Move to archive collection instead of deleting
                # This preserves historical data
                
            # Clean up old analytics data
            await self.analytics.delete_many({
                "timestamp": {"$lt": cutoff_date}
            })
            
            # Clean up old notifications
            await self.notifications.delete_many({
                "created_at": {"$lt": cutoff_date},
                "is_read": True
            })
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")

    # Broadcast operations
    async def create_broadcast(self, broadcast_data: dict) -> ObjectId:
        """Create a broadcast message"""
        try:
            broadcast_data['created_at'] = datetime.now()
            broadcast_data['status'] = 'pending'
            broadcast_data['sent_count'] = 0
            broadcast_data['failed_count'] = 0
            
            result = await self.broadcasts.insert_one(broadcast_data)
            
            # Track broadcast creation
            await self.track_event('broadcast_created', broadcast_data.get('created_by'), {
                'broadcast_id': str(result.inserted_id),
                'target_count': len(broadcast_data.get('target_users', []))
            })
            
            return result.inserted_id
        except Exception as e:
            logger.error(f"Error creating broadcast: {e}")
            return None

    async def get_broadcast(self, broadcast_id: ObjectId) -> Optional[dict]:
        """Get broadcast by ID"""
        try:
            return await self.broadcasts.find_one({'_id': broadcast_id})
        except Exception as e:
            logger.error(f"Error getting broadcast: {e}")
            return None

    async def update_broadcast_status(self, broadcast_id: ObjectId, status: str):
        """Update broadcast status"""
        try:
            await self.broadcasts.update_one(
                {'_id': broadcast_id},
                {'$set': {'status': status, 'updated_at': datetime.now()}}
            )
        except Exception as e:
            logger.error(f"Error updating broadcast status: {e}")

    async def increment_broadcast_count(self, broadcast_id: ObjectId, sent: bool):
        """Increment broadcast sent/failed count"""
        try:
            field = 'sent_count' if sent else 'failed_count'
            await self.broadcasts.update_one(
                {'_id': broadcast_id},
                {'$inc': {field: 1}}
            )
        except Exception as e:
            logger.error(f"Error incrementing broadcast count: {e}")

    # Health check operations
    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check"""
        try:
            # Check connection
            await self.client.admin.command('ping')
            
            # Get collection stats
            stats = {
                'connection': 'healthy',
                'managers': await self.managers.count_documents({}),
                'players': await self.players.count_documents({}),
                'auctions': await self.auctions.count_documents({}),
                'analytics': await self.analytics.count_documents({}),
                'active_session': bool(await self.get_current_session()),
                'timestamp': datetime.now()
            }
            
            return stats
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'connection': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now()
            }
        
    async def get_manager_name(self, user_id: int) -> str:
        """Get manager name with fallback"""
        try:
            manager = await self.managers.find_one({"user_id": user_id})
            if manager and manager.get('name'):
                return manager['name']
            return f"User {user_id}"
        except Exception as e:
            logger.error(f"Error getting manager name: {e}")
            return f"User {user_id}"