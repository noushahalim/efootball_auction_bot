# utilities/gif_countdown.py - Fixed GIF countdown system...
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
from telegram import Message, InputMediaAnimation, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from bson import ObjectId
from config.settings import COUNTDOWN_GIFS

logger = logging.getLogger(__name__)

class GifCountdownManager:
    def __init__(self, db):
        self.db = db
        self.active_auctions: Dict[str, Dict] = {}
        self.countdown_tasks: Dict[str, asyncio.Task] = {}
        
        # Updated GIF mapping without start GIF
        self.gif_intervals = {
            180: COUNTDOWN_GIFS.get('180_120', 'https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif'),
            120: COUNTDOWN_GIFS.get('120_90', 'https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif'),
            90: COUNTDOWN_GIFS.get('90_60', 'https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif'),
            60: COUNTDOWN_GIFS.get('60_45', 'https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif'),
            45: COUNTDOWN_GIFS.get('45_30', 'https://media.giphy.com/media/3o7aCWJavAgtBzLWrS/giphy.gif'),
            30: COUNTDOWN_GIFS.get('30_20', 'https://media.giphy.com/media/26BRuo6sLetdllPAQ/giphy.gif'),
            0: COUNTDOWN_GIFS.get('ended', 'https://media.giphy.com/media/3o7aCWJavAgtBzLWrS/giphy.gif')
        }
        
    def _get_gif_for_time(self, time_left: int) -> Tuple[int, str]:
        """Get appropriate GIF based on time remaining"""
        if time_left <= 0:
            return 0, self.gif_intervals[0]
        
        # Find the appropriate interval
        intervals = sorted([180, 120, 90, 60, 45, 30], reverse=True)
        for interval in intervals:
            if time_left >= interval:
                return interval, self.gif_intervals[interval]
        
        # Less than 30 seconds, use 30s GIF
        return 30, self.gif_intervals[30]
        
    async def start_auction_display(self, auction_id: str, auction_data: dict, 
                                duration: int, context: ContextTypes.DEFAULT_TYPE, 
                                chat_id: int) -> Optional[Message]:
        """Start auction with timer-based GIF and player image"""
        try:
            # Clean up any existing auction
            await self.stop_auction_display(auction_id, context)
            
            # Get initial GIF based on duration
            interval, gif_url = self._get_gif_for_time(duration)
            
            # Get current bidder name
            bidder_name = await self._get_bidder_name(auction_data.get('current_bidder'), context)
            
            # Format initial message
            caption = self._format_auction_message(auction_data, duration, duration, bidder_name)
            
            # Check if we have a player image
            player_image = auction_data.get('player_data', {}).get('image_url')
            
            if player_image:
                # Send player image with GIF in caption area
                try:
                    message = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=player_image,
                        caption=caption + f"\n\n🎬 <a href='{gif_url}'>View Timer</a>",
                        parse_mode='HTML',
                        reply_markup=self._create_bid_buttons(auction_data, auction_id)
                    )
                except:
                    # Fallback to GIF if image fails
                    message = await context.bot.send_animation(
                        chat_id=chat_id,
                        animation=gif_url,
                        caption=caption,
                        parse_mode='HTML',
                        reply_markup=self._create_bid_buttons(auction_data, auction_id)
                    )
            else:
                # No player image, use GIF
                message = await context.bot.send_animation(
                    chat_id=chat_id,
                    animation=gif_url,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=self._create_bid_buttons(auction_data, auction_id)
                )
            
            # Store auction info with proper end time
            end_time = datetime.now().timestamp() + duration
            self.active_auctions[auction_id] = {
                'message': message,
                'chat_id': chat_id,
                'auction_data': auction_data,
                'duration': duration,
                'end_time': end_time,
                'current_gif_interval': interval,
                'last_update': datetime.now().timestamp(),
                'has_image': bool(player_image)
            }
            
            # Start countdown task
            task = asyncio.create_task(self._countdown_worker(auction_id, context))
            self.countdown_tasks[auction_id] = task
            
            logger.info(f"Started auction {auction_id} with {duration}s timer, GIF interval: {interval}")
            return message
            
        except Exception as e:
            logger.error(f"Error starting auction display: {e}")
            return None
            
    async def _countdown_worker(self, auction_id: str, context: ContextTypes.DEFAULT_TYPE):
        """Worker to update countdown display"""
        try:
            while auction_id in self.active_auctions:
                auction_info = self.active_auctions[auction_id]
                
                # Calculate time remaining
                current_time = datetime.now().timestamp()
                time_left = int(auction_info['end_time'] - current_time)
                
                if time_left <= 0:
                    # Auction ended
                    await self._end_auction(auction_id, context)
                    break
                
                # Check if we need to change GIF
                new_interval, new_gif = self._get_gif_for_time(time_left)
                
                # Update if interval changed or every 5 seconds
                time_since_update = current_time - auction_info['last_update']
                should_update = (new_interval != auction_info['current_gif_interval'] or 
                               time_since_update >= 5)
                
                if should_update:
                    await self._update_auction_display(
                        auction_id, time_left, new_interval, new_gif, context
                    )
                    auction_info['last_update'] = current_time
                
                # Sleep for 1 second
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info(f"Countdown worker cancelled for auction {auction_id}")
        except Exception as e:
            logger.error(f"Error in countdown worker: {e}")
            
    async def _update_auction_display(self, auction_id: str, time_left: int, 
                                     new_interval: int, new_gif: str, context):
        """Update auction message with new GIF if needed"""
        try:
            auction_info = self.active_auctions.get(auction_id)
            if not auction_info:
                return
                
            # Get latest auction data from database
            auction = await self.db.auctions.find_one({"_id": ObjectId(auction_id)})
            if auction:
                auction_info['auction_data']['current_bid'] = auction.get('current_bid', 0)
                auction_info['auction_data']['current_bidder'] = auction.get('current_bidder')
            
            # Get bidder name
            bidder_name = await self._get_bidder_name(
                auction_info['auction_data'].get('current_bidder'), context
            )
            
            # Format message
            caption = self._format_auction_message(
                auction_info['auction_data'], 
                time_left, 
                auction_info['duration'],
                bidder_name
            )
            
            message = auction_info['message']
            
            # Update GIF if interval changed
            if new_interval != auction_info['current_gif_interval']:
                await context.bot.edit_message_media(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    media=InputMediaAnimation(
                        media=new_gif,
                        caption=caption,
                        parse_mode='HTML'
                    ),
                    reply_markup=self._create_bid_buttons(auction_info['auction_data'], auction_id)
                )
                auction_info['current_gif_interval'] = new_interval
                logger.info(f"Changed GIF to interval {new_interval} for auction {auction_id}")
            else:
                # Just update caption
                await context.bot.edit_message_caption(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=self._create_bid_buttons(auction_info['auction_data'], auction_id)
                )
                    
        except BadRequest as e:
            if "MESSAGE_NOT_MODIFIED" not in str(e):
                logger.error(f"Error updating auction display: {e}")
        except Exception as e:
            logger.error(f"Error updating auction display: {e}")

    def _create_bid_buttons(self, auction_data: dict, auction_id: str):
        """Create bid buttons"""
        from config.settings import EMOJI_ICONS
        
        keyboard = []
        current_bid = auction_data.get('current_bid', 0)
        base_price = auction_data.get('base_price', 0)
        
        if current_bid == 0:
            button_text = f"{EMOJI_ICONS['bid']} Bid {base_price // 1_000_000}M"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"qbid_{auction_id}_{base_price}")])
        elif current_bid >= base_price and current_bid < 20_000_000:
            new_bid = current_bid + 1_000_000
            button_text = f"{EMOJI_ICONS['bid']} Bid {new_bid // 1_000_000}M (+1M)"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"qbid_{auction_id}_{new_bid}")])
        else:
            increments = [1_000_000, 2_000_000, 5_000_000, 10_000_000]
            for i, amount in enumerate(increments):
                if i % 2 == 0:
                    row = []
                new_bid = current_bid + amount
                button_text = f"+{amount // 1_000_000}M ({new_bid // 1_000_000}M)"
                row.append(InlineKeyboardButton(button_text, callback_data=f"qbid_{auction_id}_{new_bid}"))
                if i % 2 == 1 or i == len(increments) - 1:
                    keyboard.append(row)
                    
        return InlineKeyboardMarkup(keyboard) if keyboard else None
            
    async def reset_timer(self, auction_id: str, new_duration: int, context: ContextTypes.DEFAULT_TYPE):
        """Reset timer when new bid is placed"""
        try:
            auction_info = self.active_auctions.get(auction_id)
            if not auction_info:
                logger.warning(f"No auction found for {auction_id}")
                return False
                
            # Cancel current countdown task
            if auction_id in self.countdown_tasks:
                self.countdown_tasks[auction_id].cancel()
                await asyncio.sleep(0.1)
            
            # Update end time
            new_end_time = datetime.now().timestamp() + new_duration
            auction_info['end_time'] = new_end_time
            auction_info['duration'] = new_duration
            
            # Get appropriate GIF for new duration
            new_interval, new_gif = self._get_gif_for_time(new_duration)
            
            # Update display immediately with new GIF
            await self._update_auction_display(
                auction_id, new_duration, new_interval, new_gif, context
            )
            
            # Start new countdown task
            task = asyncio.create_task(self._countdown_worker(auction_id, context))
            self.countdown_tasks[auction_id] = task
            
            logger.info(f"Reset timer for auction {auction_id} to {new_duration}s")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting timer: {e}")
            return False
            
    async def _get_bidder_name(self, user_id: Optional[int], context) -> str:
        """Get bidder name from user ID"""
        if not user_id:
            return ""
            
        try:
            # First try to get from database
            manager = await self.db.get_manager(user_id)
            if manager and manager.name:
                return manager.name
                
            # Try to fetch from Telegram
            try:
                user = await context.bot.get_chat(user_id)
                name = user.full_name or user.first_name or f"User {user_id}"
                
                # Update manager name in database
                if manager:
                    await self.db.managers.update_one(
                        {"user_id": user_id},
                        {"$set": {"name": name}}
                    )
                    
                return name
            except:
                return f"User {user_id}"
                
        except Exception as e:
            logger.error(f"Error getting bidder name: {e}")
            return f"User {user_id}"
            
    def _format_auction_message(self, auction_data: dict, time_left: int, duration: int, bidder_name: str) -> str:
        """Format auction message with proper bidder name"""
        from utilities.formatters import MessageFormatter
        from config.settings import EMOJI_ICONS
        formatter = MessageFormatter()
        
        # Time display
        if time_left <= 10:
            time_display = f"🔴 <b>{time_left}s</b> 🔴"
        elif time_left <= 30:
            time_display = f"🟡 <b>{time_left}s</b> 🟡"
        else:
            mins = time_left // 60
            secs = time_left % 60
            time_display = f"🟢 <b>{mins}:{secs:02d}</b>"
        
        # Bidder info with name instead of number
        bidder_info = ""
        if auction_data.get('current_bidder') and bidder_name:
            bidder_info = f"\n{EMOJI_ICONS['winner']} <b>Leading:</b> {bidder_name}"
        
        # Get player details for better display
        player_data = auction_data.get('player_data', {})
        position_info = f"\n📍 <b>Position:</b> {player_data.get('position')}" if player_data.get('position') else ""
        rating_info = f"\n⭐ <b>Rating:</b> {player_data.get('rating')}" if player_data.get('rating') else ""
        
        return f"""
🔥 <b>LIVE AUCTION</b> 🔥

⚽ <b>Player:</b> {auction_data.get('player_name', 'Unknown')}{position_info}{rating_info}
💰 <b>Base Price:</b> {formatter.format_currency(auction_data.get('base_price', 0))}

📈 <b>Current Bid:</b> {formatter.format_currency(auction_data.get('current_bid', 0))}{bidder_info}

⏱️ <b>Time Left:</b> {time_display}
        """.strip()
        
    async def _end_auction(self, auction_id: str, context):
        """End auction and show final GIF"""
        try:
            auction_info = self.active_auctions.get(auction_id)
            if not auction_info:
                return
                
            # Show end GIF
            end_gif = self.gif_intervals[0]
            message = auction_info['message']
            
            await context.bot.edit_message_media(
                chat_id=message.chat.id,
                message_id=message.message_id,
                media=InputMediaAnimation(
                    media=end_gif,
                    caption="🔨 <b>AUCTION ENDED!</b> 🔨\n\nFinal results coming up...",
                    parse_mode='HTML'
                )
            )
            
            # Clean up
            if auction_id in self.countdown_tasks:
                self.countdown_tasks[auction_id].cancel()
                del self.countdown_tasks[auction_id]
            
            if auction_id in self.active_auctions:
                del self.active_auctions[auction_id]
                
        except Exception as e:
            logger.error(f"Error ending auction: {e}")
            
    async def stop_auction_display(self, auction_id: str, context):
        """Stop auction display"""
        try:
            # Cancel countdown task
            if auction_id in self.countdown_tasks:
                self.countdown_tasks[auction_id].cancel()
                del self.countdown_tasks[auction_id]
                
            # Remove from active auctions
            if auction_id in self.active_auctions:
                del self.active_auctions[auction_id]
                
        except Exception as e:
            logger.error(f"Error stopping auction: {e}")