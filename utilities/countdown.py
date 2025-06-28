# utilities/countdown.py - Visual Countdown Timer Management
import asyncio
import logging
from typing import Dict, Callable, Optional
from datetime import datetime
from config.settings import COUNTDOWN_STAGES, WARNING_TIME

logger = logging.getLogger(__name__)

class CountdownManager:
    def __init__(self):
        self.active_countdowns: Dict[str, asyncio.Task] = {}
        
    def start_countdown(self, auction_id: str, duration: int, 
                       update_callback: Callable, context: any) -> None:
        """Start a countdown timer for an auction"""
        # Cancel existing countdown if any
        self.stop_countdown(auction_id)
        
        # Create new countdown task
        task = asyncio.create_task(
            self._countdown_worker(auction_id, duration, update_callback, context)
        )
        self.active_countdowns[auction_id] = task
        
    def stop_countdown(self, auction_id: str) -> None:
        """Stop a countdown timer"""
        if auction_id in self.active_countdowns:
            self.active_countdowns[auction_id].cancel()
            del self.active_countdowns[auction_id]
            
    def stop_all_countdowns(self) -> None:
        """Stop all active countdowns"""
        for auction_id in list(self.active_countdowns.keys()):
            self.stop_countdown(auction_id)
            
    async def _countdown_worker(self, auction_id: str, duration: int, 
                              update_callback: Callable, context: any) -> None:
        """Countdown worker task with smart update intervals"""
        try:
            start_time = datetime.now()
            end_time = start_time.timestamp() + duration
            last_update = 0
            
            while True:
                current_time = datetime.now().timestamp()
                time_left = int(end_time - current_time)
                
                if time_left <= 0:
                    # Countdown finished
                    await update_callback(auction_id, 0, context)
                    break
                    
                # Determine update interval based on time left
                update_interval = self._get_update_interval(time_left)
                
                # Update if interval passed or critical moments
                if time_left != last_update and (
                    time_left % update_interval == 0 or 
                    time_left in [60, 30, 20, 10, 5, 3, 2, 1] or
                    current_time - last_update >= update_interval
                ):
                    await update_callback(auction_id, time_left, context)
                    last_update = time_left
                    
                # Sleep for optimization
                await asyncio.sleep(0.5 if time_left <= 10 else 1)
                
        except asyncio.CancelledError:
            logger.info(f"Countdown cancelled for auction {auction_id}")
        except Exception as e:
            logger.error(f"Countdown error for auction {auction_id}: {e}")
            
    def _get_update_interval(self, time_left: int) -> int:
        """Get appropriate update interval based on time remaining"""
        if time_left <= 10:
            return 1  # Every second for final countdown
        elif time_left <= 30:
            return 5  # Every 5 seconds
        elif time_left <= 60:
            return 10  # Every 10 seconds
        else:
            return 30  # Every 30 seconds
            
    def get_urgency_level(self, time_left: int) -> str:
        """Determine urgency level based on time remaining"""
        for threshold, stage_data in sorted(COUNTDOWN_STAGES.items()):
            if time_left <= threshold:
                return stage_data['urgency']
        return 'low'
        
    def format_countdown_display(self, time_left: int) -> str:
        """Format countdown for display with visual indicators"""
        if time_left <= 0:
            return "⏰ TIME'S UP!"
            
        # Get appropriate emoji
        emoji = '⏰'
        for threshold, stage_data in sorted(COUNTDOWN_STAGES.items()):
            if time_left <= threshold:
                emoji = stage_data['emoji']
                break
                
        # Format time
        if time_left < 60:
            time_str = f"{time_left}s"
        else:
            minutes = time_left // 60
            seconds = time_left % 60
            time_str = f"{minutes}:{seconds:02d}"
            
        # Add urgency indicator
        if time_left <= 5:
            return f"🚨 {time_str} 🚨"
        elif time_left <= 10:
            return f"{emoji} {time_str} ⚠️"
        else:
            return f"{emoji} {time_str}"
            
    def create_countdown_animation(self, time_left: int, total_time: int) -> str:
        """Create animated countdown visualization"""
        if time_left <= 0:
            return "💥 ENDED 💥"
            
        # Calculate percentage
        percentage = ((total_time - time_left) / total_time) * 100
        
        # Create visual representation
        if time_left <= 5:
            # Critical - animated effect
            frames = ['🔴', '⭕', '🔴', '⭕']
            frame = frames[time_left % len(frames)]
            return f"{frame} {time_left} {frame}"
        elif time_left <= 10:
            # Warning - pulsing effect
            return f"⚠️ {time_left} ⚠️"
        else:
            # Normal - progress indicator
            filled = int((percentage / 100) * 10)
            bar = "█" * filled + "░" * (10 - filled)
            return f"[{bar}] {time_left}s"
            
    def should_announce_time(self, time_left: int) -> bool:
        """Check if time should be announced"""
        announcement_times = [60, 30, 20, 10, 5, 3, 2, 1]
        return time_left in announcement_times
        
    def get_countdown_message(self, time_left: int) -> Optional[str]:
        """Get special countdown announcement message"""
        messages = {
            60: "⏰ One minute remaining!",
            30: "⏱️ 30 seconds left!",
            20: "⚡ 20 seconds - Hurry up!",
            10: "🚨 FINAL 10 SECONDS!",
            5: "🔥 5... Going fast!",
            3: "💥 3... Almost there!",
            2: "💥 2... Last chance!",
            1: "💥 1... FINAL SECOND!",
            0: "🔨 SOLD!"
        }
        return messages.get(time_left)