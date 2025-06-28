# database/models.py - Fixed Data Models with MongoDB Integration
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId
from enum import Enum
from config.settings import DEFAULT_BALANCE

class AuctionStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ManagerRole(Enum):
    USER = "user"
    VIP = "vip"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

@dataclass
class Manager:
    user_id: int
    name: str
    username: Optional[str] = None
    balance: int = DEFAULT_BALANCE
    players: List[str] = field(default_factory=list)
    total_spent: int = 0
    role: str = ManagerRole.USER.value
    achievements: List[str] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    is_banned: bool = False
    ban_reason: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    _id: Optional[ObjectId] = None  # Add this to handle MongoDB _id
    
    def __post_init__(self):
        if not self.statistics:
            self.statistics = {
                'total_bids': 0,
                'auctions_won': 0,
                'auctions_participated': 0,
                'highest_bid': 0,
                'favorite_position': None,
                'win_rate': 0.0,
                'points': 0,
                'level': 1,
                'streak_days': 0,
                'last_bid_date': None
            }
        # Handle MongoDB document conversion
        if self._id is not None and not isinstance(self._id, ObjectId):
            self._id = ObjectId(self._id)
            
    def to_dict(self):
        data = {
            'user_id': self.user_id,
            'name': self.name,
            'username': self.username,
            'balance': self.balance,
            'players': self.players,
            'total_spent': self.total_spent,
            'role': self.role,
            'achievements': self.achievements,
            'statistics': self.statistics,
            'created_at': self.created_at,
            'last_active': self.last_active,
            'is_banned': self.is_banned,
            'ban_reason': self.ban_reason,
            'preferences': self.preferences
        }
        if self._id:
            data['_id'] = self._id
        return data
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create Manager instance from MongoDB document"""
        # Don't pass _id to constructor, handle it separately
        manager_data = {k: v for k, v in data.items() if k != '_id'}
        manager = cls(**manager_data)
        manager._id = data.get('_id')
        return manager

@dataclass
class Player:
    name: str
    base_price: int
    message_id: int
    position: Optional[str] = None
    rating: Optional[int] = None
    team: Optional[str] = None
    nationality: Optional[str] = None
    image_url: Optional[str] = None
    status: str = 'available'
    sold_to: Optional[int] = None
    final_price: Optional[int] = None
    bid_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    auction_duration: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    _id: Optional[ObjectId] = None
    
    def to_dict(self):
        data = {
            'name': self.name,
            'base_price': self.base_price,
            'message_id': self.message_id,
            'position': self.position,
            'rating': self.rating,
            'team': self.team,
            'nationality': self.nationality,
            'image_url': self.image_url,
            'status': self.status,
            'sold_to': self.sold_to,
            'final_price': self.final_price,
            'bid_count': self.bid_count,
            'created_at': self.created_at,
            'auction_duration': self.auction_duration,
            'tags': self.tags
        }
        if self._id:
            data['_id'] = self._id
        return data
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create Player instance from MongoDB document"""
        player_data = {k: v for k, v in data.items() if k != '_id'}
        player = cls(**player_data)
        player._id = data.get('_id')
        return player

@dataclass
class Bid:
    auction_id: ObjectId
    user_id: int
    amount: int
    timestamp: datetime = field(default_factory=datetime.now)
    is_auto_bid: bool = False
    bid_type: str = 'manual'  # manual, quick, auto
    
    def to_dict(self):
        return {
            'auction_id': self.auction_id,
            'user_id': self.user_id,
            'amount': self.amount,
            'timestamp': self.timestamp,
            'is_auto_bid': self.is_auto_bid,
            'bid_type': self.bid_type
        }

@dataclass
class Auction:
    player_name: str
    base_price: int
    current_bid: int
    player_data: Optional[Dict[str, Any]] = None
    current_bidder: Optional[int] = None
    bids: List[Bid] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: str = AuctionStatus.ACTIVE.value
    message_id: Optional[int] = None
    mode: str = 'auto'
    timer_duration: int = 60
    extension_count: int = 0
    watchers: List[int] = field(default_factory=list)
    quick_stats: Dict[str, Any] = field(default_factory=dict)
    _id: Optional[ObjectId] = None
    
    def __post_init__(self):
        if not self.quick_stats:
            self.quick_stats = {
                'total_bidders': 0,
                'bid_frequency': 0,
                'highest_increment': 0,
                'competition_level': 'low'
            }
        if self._id is not None and not isinstance(self._id, ObjectId):
            self._id = ObjectId(self._id)
    
    def to_dict(self):
        data = {
            'player_name': self.player_name,
            'base_price': self.base_price,
            'current_bid': self.current_bid,
            'player_data': self.player_data,
            'current_bidder': self.current_bidder,
            'bids': [bid.to_dict() for bid in self.bids],
            'start_time': self.start_time,
            'end_time': self.end_time,
            'status': self.status,
            'message_id': self.message_id,
            'mode': self.mode,
            'timer_duration': self.timer_duration,
            'extension_count': self.extension_count,
            'watchers': self.watchers,
            'quick_stats': self.quick_stats
        }
        if self._id:
            data['_id'] = self._id
        return data
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create Auction instance from MongoDB document"""
        auction_data = {k: v for k, v in data.items() if k not in ['_id', 'bids']}
        # Convert bid dicts to Bid objects
        bids = [Bid(**bid) for bid in data.get('bids', [])]
        auction = cls(**auction_data, bids=bids)
        auction._id = data.get('_id')
        return auction

@dataclass
class Achievement:
    user_id: int
    achievement_id: str
    unlocked_at: datetime = field(default_factory=datetime.now)
    progress: int = 0
    target: int = 1
    is_completed: bool = False
    _id: Optional[ObjectId] = None
    
    def to_dict(self):
        data = {
            'user_id': self.user_id,
            'achievement_id': self.achievement_id,
            'unlocked_at': self.unlocked_at,
            'progress': self.progress,
            'target': self.target,
            'is_completed': self.is_completed
        }
        if self._id:
            data['_id'] = self._id
        return data

@dataclass
class Analytics:
    event_type: str
    user_id: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None
    _id: Optional[ObjectId] = None
    
    def to_dict(self):
        data = {
            'event_type': self.event_type,
            'user_id': self.user_id,
            'data': self.data,
            'timestamp': self.timestamp,
            'session_id': self.session_id
        }
        if self._id:
            data['_id'] = self._id
        return data

@dataclass
class Notification:
    user_id: int
    type: str
    title: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    is_read: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    _id: Optional[ObjectId] = None
    
    def to_dict(self):
        data = {
            'user_id': self.user_id,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'data': self.data,
            'is_read': self.is_read,
            'created_at': self.created_at,
            'expires_at': self.expires_at
        }
        if self._id:
            data['_id'] = self._id
        return data

@dataclass
class Team:
    manager_id: int
    name: str
    formation: str = '4-3-3'
    players: Dict[str, List[str]] = field(default_factory=dict)
    captain: Optional[str] = None
    rating: float = 0.0
    chemistry: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    _id: Optional[ObjectId] = None
    
    def to_dict(self):
        data = {
            'manager_id': self.manager_id,
            'name': self.name,
            'formation': self.formation,
            'players': self.players,
            'captain': self.captain,
            'rating': self.rating,
            'chemistry': self.chemistry,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        if self._id:
            data['_id'] = self._id
        return data

@dataclass
class AuctionSession:
    session_id: str
    name: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_players: int = 0
    sold_players: int = 0
    unsold_players: int = 0
    total_money_spent: int = 0
    participating_managers: List[int] = field(default_factory=list)
    status: str = 'active'
    settings: Dict[str, Any] = field(default_factory=dict)
    _id: Optional[ObjectId] = None
    
    def to_dict(self):
        data = {
            'session_id': self.session_id,
            'name': self.name,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_players': self.total_players,
            'sold_players': self.sold_players,
            'unsold_players': self.unsold_players,
            'total_money_spent': self.total_money_spent,
            'participating_managers': self.participating_managers,
            'status': self.status,
            'settings': self.settings
        }
        if self._id:
            data['_id'] = self._id
        return data