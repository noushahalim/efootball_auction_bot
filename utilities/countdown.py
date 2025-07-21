# utilities/countdown.py - Simple countdown manager for auction timers
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Callable
from telegram import Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from bson import ObjectId
from config.settings import EMOJI_ICONS

logger = logging.getLogger(__name__)

class CountdownManager:
    def __init__(self):
        self.active_countdowns: Dict[str, Dict] = {}
        self.countdown_tasks: Dict[str, asyncio.Task] = {}
        
    async def start_countdown(self, auction_id: str, duration: int, 
                            message: Message, context: ContextTypes.DEFAULT_TYPE,
                            update_callback: Optional[Callable] = None) -> None:
        """Start countdown for auction"""
        try:
            # Stop any existing countdown
            await self.stop_countdown(auction_id)
            
            # Store countdown info
            end_time = datetime.now().timestamp() + duration
            self.active_countdowns[auction_id] = {
                'message': message,
                'end_time': end_time,
                'duration': duration,
                'context': context,
                'update_callback': update_callback
            }
            
            # Start countdown task
            task = asyncio.create_task(self._countdown_worker(auction_id))
            self.countdown_tasks[auction_id] = task
            
            logger.info(f"Started countdown for auction {auction_id} with {duration}s")
            
        except Exception as e:
            logger.error(f"Error starting countdown: {e}")
            
    async def _countdown_worker(self, auction_id: str):
        """Worker to update countdown"""
        try:
            last_update = 0
            
            while auction_id in self.active_countdowns:
                info = self.active_countdowns[auction_id]
                current_time = datetime.now().timestamp()
                time_left = int(info['end_time'] - current_time)
                
                if time_left <= 0:
                    # Countdown finished
                    if info['update_callback']:
                        await info['update_callback'](auction_id, 0)
                    break
                
                # Update at intervals: every 1s for last 10s, every 5s for last minute, every 10s otherwise
                update_interval = 1 if time_left <= 10 else 5 if time_left <= 60 else 10
                
                if time_left != last_update and time_left % update_interval == 0:
                    if info['update_callback']:
                        await info['update_callback'](auction_id, time_left)
                    last_update = time_left
                
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info(f"Countdown cancelled for {auction_id}")
        except Exception as e:
            logger.error(f"Error in countdown worker: {e}")
            
    async def reset_countdown(self, auction_id: str, new_duration: int) -> bool:
        """Reset countdown with new duration"""
        try:
            if auction_id not in self.active_countdowns:
                return False
                
            # Cancel current task
            if auction_id in self.countdown_tasks:
                self.countdown_tasks[auction_id].cancel()
                await asyncio.sleep(0.1)
                
            # Update end time
            info = self.active_countdowns[auction_id]
            info['end_time'] = datetime.now().timestamp() + new_duration
            info['duration'] = new_duration
            
            # Start new countdown task
            task = asyncio.create_task(self._countdown_worker(auction_id))
            self.countdown_tasks[auction_id] = task
            
            logger.info(f"Reset countdown for {auction_id} to {new_duration}s")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting countdown: {e}")
            return False
            
    async def stop_countdown(self, auction_id: str) -> None:
        """Stop countdown"""
        try:
            # Cancel task
            if auction_id in self.countdown_tasks:
                self.countdown_tasks[auction_id].cancel()
                del self.countdown_tasks[auction_id]
                
            # Remove from active
            if auction_id in self.active_countdowns:
                del self.active_countdowns[auction_id]
                
            logger.info(f"Stopped countdown for {auction_id}")
            
        except Exception as e:
            logger.error(f"Error stopping countdown: {e}")
            
    def get_time_remaining(self, auction_id: str) -> int:
        """Get time remaining for auction"""
        if auction_id not in self.active_countdowns:
            return 0
            
        info = self.active_countdowns[auction_id]
        current_time = datetime.now().timestamp()
        time_left = int(info['end_time'] - current_time)
        
        return max(0, time_left)
        
    def is_countdown_active(self, auction_id: str) -> bool:
        """Check if countdown is active"""
        return auction_id in self.active_countdowns