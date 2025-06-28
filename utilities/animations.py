# utilities/animations.py - Visual Animations and Effects
import random
from typing import List, Tuple
from config.settings import EMOJI_ICONS

class AnimationManager:
    def __init__(self):
        self.celebration_emojis = ['🎉', '🎊', '🎈', '🎆', '🎇', '✨', '💫', '⭐']
        self.money_emojis = ['💵', '💴', '💶', '💷', '💸', '💰', '💳']
        self.fire_emojis = ['🔥', '💥', '⚡', '💫', '✨']
        
    def get_countdown_animation(self, seconds: int) -> str:
        """Get animated countdown based on remaining time"""
        if seconds <= 0:
            return self.get_explosion_animation()
        elif seconds <= 3:
            return self.get_critical_countdown(seconds)
        elif seconds <= 10:
            return self.get_warning_countdown(seconds)
        else:
            return self.get_normal_countdown(seconds)
            
    def get_explosion_animation(self) -> str:
        """Final explosion animation"""
        frames = [
            "💥 BOOM! 💥",
            "🔥 SOLD! 🔥",
            "🎯 DONE! 🎯",
            "⚡ END! ⚡"
        ]
        return random.choice(frames)
        
    def get_critical_countdown(self, seconds: int) -> str:
        """Critical countdown animation (3, 2, 1)"""
        animations = {
            3: "🔴🔴🔴 THREE 🔴🔴🔴",
            2: "🟠🟠 TWO 🟠🟠",
            1: "🔴 ONE 🔴"
        }
        return animations.get(seconds, f"⏰ {seconds} ⏰")
        
    def get_warning_countdown(self, seconds: int) -> str:
        """Warning countdown animation (10-4 seconds)"""
        bar_length = min(seconds, 10)
        filled = "🟥" * bar_length
        empty = "⬜" * (10 - bar_length)
        return f"{filled}{empty} {seconds}s"
        
    def get_normal_countdown(self, seconds: int) -> str:
        """Normal countdown display"""
        minutes = seconds // 60
        secs = seconds % 60
        
        if minutes > 0:
            return f"⏱️ {minutes}:{secs:02d}"
        else:
            return f"⏰ {seconds}s"
            
    def get_bid_animation(self, bid_amount: int) -> str:
        """Get animation for new bid"""
        # More money emojis for higher bids
        if bid_amount >= 100_000_000:  # 100M+
            return "💎💎💎 MEGA BID! 💎💎💎"
        elif bid_amount >= 50_000_000:  # 50M+
            return "💰💰 BIG BID! 💰💰"
        elif bid_amount >= 25_000_000:  # 25M+
            return "💸 Strong Bid! 💸"
        else:
            return "💵 New Bid! 💵"
            
    def get_achievement_animation(self, achievement_type: str) -> List[str]:
        """Get achievement unlock animation frames"""
        animations = {
            'first_bid': [
                "🎯 Achievement Unlocking...",
                "🎯✨ Achievement Unlocking...",
                "🎯✨🏆 FIRST BID UNLOCKED!"
            ],
            'win_auction': [
                "🏆 Achievement Unlocking...",
                "🏆⭐ Achievement Unlocking...",
                "🏆⭐🎉 WINNER UNLOCKED!"
            ],
            'big_spender': [
                "💎 Achievement Unlocking...",
                "💎💰 Achievement Unlocking...",
                "💎💰👑 BIG SPENDER UNLOCKED!"
            ]
        }
        
        return animations.get(achievement_type, [
            "🏆 Achievement Unlocking...",
            "🏆✨ Achievement Unlocking...",
            "🏆✨🎉 ACHIEVEMENT UNLOCKED!"
        ])
        
    def get_loading_animation(self) -> List[str]:
        """Get loading animation frames"""
        return [
            "⚪ Loading...",
            "⚪⚪ Loading...",
            "⚪⚪⚪ Loading...",
            "⚪⚪⚪⚪ Loading..."
        ]
        
    def get_progress_animation(self, percentage: float) -> str:
        """Get progress bar animation"""
        filled = int(percentage / 10)
        
        if percentage >= 90:
            bar = "🟩" * filled + "⬜" * (10 - filled)
        elif percentage >= 70:
            bar = "🟨" * filled + "⬜" * (10 - filled)
        elif percentage >= 50:
            bar = "🟧" * filled + "⬜" * (10 - filled)
        else:
            bar = "🟥" * filled + "⬜" * (10 - filled)
            
        return f"[{bar}] {percentage:.0f}%"
        
    def get_celebration_sequence(self) -> str:
        """Get random celebration sequence"""
        sequences = [
            "🎉🎊🎈 CONGRATULATIONS! 🎈🎊🎉",
            "🏆⭐💫 WELL DONE! 💫⭐🏆",
            "🔥🎯💪 AMAZING! 💪🎯🔥",
            "👑💎✨ BRILLIANT! ✨💎👑"
        ]
        return random.choice(sequences)
        
    def get_money_rain(self) -> str:
        """Get money rain effect"""
        return "💸💰💵💴💶💷💰💸"
        
    def create_sparkle_text(self, text: str) -> str:
        """Add sparkles around text"""
        sparkles = random.choice(['✨', '💫', '⭐', '🌟'])
        return f"{sparkles} {text} {sparkles}"
        
    def get_rank_badge(self, rank: int) -> str:
        """Get rank badge based on position"""
        badges = {
            1: "🥇",
            2: "🥈", 
            3: "🥉",
            4: "🏅",
            5: "🏅"
        }
        return badges.get(rank, "🎖️")
        
    def get_status_indicator(self, status: str) -> str:
        """Get status indicator emoji"""
        indicators = {
            'online': "🟢",
            'idle': "🟡",
            'busy': "🟠",
            'offline': "🔴",
            'active': "⚡",
            'waiting': "⏳",
            'ready': "✅",
            'error': "❌"
        }
        return indicators.get(status.lower(), "⚪")
        
    def get_trend_indicator(self, value: float, previous: float) -> str:
        """Get trend indicator based on values"""
        if value > previous * 1.1:  # 10% increase
            return "📈🔥"
        elif value > previous:
            return "📈"
        elif value < previous * 0.9:  # 10% decrease
            return "📉❄️"
        elif value < previous:
            return "📉"
        else:
            return "➡️"
            
    def create_bid_battle_animation(self, bidder1: str, bidder2: str) -> List[str]:
        """Create bid battle animation between two bidders"""
        return [
            f"⚔️ {bidder1} vs {bidder2} ⚔️",
            f"💥 {bidder1} 🆚 {bidder2} 💥",
            f"🔥 BIDDING WAR! 🔥",
            f"⚡ {bidder1} ⚔️ {bidder2} ⚡"
        ]
        
    def get_urgency_pulse(self, urgency_level: str) -> str:
        """Get pulsing effect based on urgency"""
        pulses = {
            'low': "⚪⚪⚪",
            'medium': "🟡🟡🟡",
            'high': "🟠🟠🟠",
            'critical': "🔴⚪🔴"
        }
        return pulses.get(urgency_level, "⚪⚪⚪")