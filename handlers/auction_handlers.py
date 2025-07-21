# handlers/auction_handlers.py - Specialized Auction Handling with Queue System
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bson import ObjectId
from config.settings import *
from database.models import Auction, Player, Bid
from utilities.formatters import MessageFormatter

logger = logging.getLogger(__name__)

class AuctionHandlers:
    def __init__(self, db, bot, countdown, analytics):
        self.db = db
        self.bot = bot
        self.countdown = countdown
        self.analytics = analytics
        self.formatter = MessageFormatter()
        self.active_extensions = {}  # Track auction extensions
        self.auction_queue = []  # Queue of players to auction
        self.current_session = None
        self.break_timer_task = None
        self.is_in_break = False
        self.admin_handlers = None  # Will be set by admin_handlers
        
    async def handle_auction_extension(self, auction_id: ObjectId, context: ContextTypes.DEFAULT_TYPE):
        """Handle auction time extension on last-second bids"""
        if auction_id in self.active_extensions:
            return  # Already extended
            
        # Add 10 seconds for last-second bid
        extension_time = 10
        self.active_extensions[auction_id] = True
        
        # Notify about extension
        extension_msg = f"""
{EMOJI_ICONS['warning']} <b>TIME EXTENDED!</b>

Last-second bid detected!
+{extension_time} seconds added

{EMOJI_ICONS['fire']} <i>The battle continues!</i>
        """.strip()
        
        try:
            await context.bot.send_message(
                AUCTION_GROUP_ID,
                extension_msg,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error sending extension message: {e}")
            
        # Clean up after delay
        await asyncio.sleep(extension_time + 5)
        if auction_id in self.active_extensions:
            del self.active_extensions[auction_id]
            
    async def handle_auto_bid(self, user_id: int, auction_id: ObjectId, 
                            max_amount: int, increment: int):
        """Handle automatic bidding up to max amount"""
        # Implementation for auto-bid feature
        # This would monitor the auction and automatically place bids
        pass
        
    async def handle_watch_auction(self, user_id: int, auction_id: str):
        """Add user to auction watchers for notifications"""
        try:
            await self.db.auctions.update_one(
                {"_id": ObjectId(auction_id)},
                {"$addToSet": {"watchers": user_id}}
            )
            
            # Create notification preference
            await self.db.create_notification(
                user_id,
                'watch_added',
                "👁️ Watching Auction",
                "You'll be notified about this auction's progress",
                {'auction_id': auction_id}
            )
            
            return True
        except Exception as e:
            logger.error(f"Error adding watcher: {e}")
            return False
            
    async def notify_watchers(self, auction: dict, event_type: str, context: ContextTypes.DEFAULT_TYPE):
        """Notify users watching an auction"""
        if not auction.get('watchers'):
            return
            
        for watcher_id in auction['watchers']:
            if watcher_id == auction.get('current_bidder'):
                continue  # Don't notify current leader
                
            try:
                if event_type == 'new_bid':
                    msg = f"""
{EMOJI_ICONS['bell']} <b>AUCTION UPDATE</b>

{EMOJI_ICONS['player']} {auction['player_name']}
{EMOJI_ICONS['chart_up']} New bid: {self.formatter.format_currency(auction['current_bid'])}

Check the auction now!
                    """.strip()
                elif event_type == 'ending_soon':
                    msg = f"""
{EMOJI_ICONS['warning']} <b>AUCTION ENDING SOON!</b>

{EMOJI_ICONS['player']} {auction['player_name']}
{EMOJI_ICONS['timer']} Less than 30 seconds left!

Last chance to bid!
                    """.strip()
                else:
                    continue
                    
                await context.bot.send_message(
                    watcher_id,
                    msg,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Error notifying watcher {watcher_id}: {e}")
                
    async def show_auction_statistics(self, auction_id: str, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Generate and return auction statistics"""
        try:
            auction = await self.db.auctions.find_one({"_id": ObjectId(auction_id)})
            if not auction:
                return "Auction not found!"
                
            # Calculate statistics
            total_bids = len(auction.get('bids', []))
            unique_bidders = len(set(bid['user_id'] for bid in auction.get('bids', [])))
            
            if total_bids > 0:
                bid_amounts = [bid['amount'] for bid in auction['bids']]
                avg_increment = sum(bid_amounts[i] - bid_amounts[i-1] 
                                  for i in range(1, len(bid_amounts))) // (len(bid_amounts) - 1)
            else:
                avg_increment = 0
                
            # Competition level
            if unique_bidders <= 2:
                competition = "🟢 Low"
            elif unique_bidders <= 5:
                competition = "🟡 Medium"
            else:
                competition = "🔴 High"
                
            stats_msg = f"""
{EMOJI_ICONS['chart']} <b>AUCTION STATISTICS</b>

{EMOJI_ICONS['player']} <b>Player:</b> {auction['player_name']}

{EMOJI_ICONS['stats']} <b>Bidding Activity:</b>
• Total Bids: {total_bids}
• Unique Bidders: {unique_bidders}
• Competition: {competition}
• Avg Increment: {self.formatter.format_currency(avg_increment)}

{EMOJI_ICONS['chart_up']} <b>Price Movement:</b>
• Base: {self.formatter.format_currency(auction['base_price'])}
• Current: {self.formatter.format_currency(auction['current_bid'])}
• Increase: {((auction['current_bid'] - auction['base_price']) / auction['base_price'] * 100):.1f}%
            """.strip()
            
            return stats_msg
            
        except Exception as e:
            logger.error(f"Error getting auction stats: {e}")
            return "Error loading statistics"
            
    async def check_stuck_auctions(self):
        """Check for auctions that might be stuck"""
        try:
            # Find auctions that have been active for too long
            stuck_time = datetime.now() - timedelta(minutes=10)
            
            stuck_auctions = await self.db.auctions.find({
                "status": "active",
                "start_time": {"$lt": stuck_time}
            }).to_list(None)
            
            for auction in stuck_auctions:
                logger.warning(f"Found stuck auction: {auction['_id']} - {auction['player_name']}")
                
                # Auto-complete stuck auctions
                await self.db.complete_auction(auction['_id'])
                
                # Notify admins
                for admin_id in ADMIN_IDS:
                    try:
                        await self.bot.send_message(
                            admin_id,
                            f"⚠️ Auto-completed stuck auction:\n"
                            f"Player: {auction['player_name']}\n"
                            f"Started: {auction['start_time'].strftime('%H:%M:%S')}"
                        )
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Error checking stuck auctions: {e}")
            
    async def generate_auction_summary(self, auction: dict) -> Dict[str, Any]:
        """Generate comprehensive auction summary"""
        # Get all bidders info
        bidder_stats = {}
        for bid in auction.get('bids', []):
            user_id = bid['user_id']
            if user_id not in bidder_stats:
                manager = await self.db.get_manager(user_id)
                if manager:
                    bidder_stats[user_id] = {
                        'name': manager.name,
                        'bid_count': 0,
                        'highest_bid': 0
                    }
            
            if user_id in bidder_stats:
                bidder_stats[user_id]['bid_count'] += 1
                bidder_stats[user_id]['highest_bid'] = max(
                    bidder_stats[user_id]['highest_bid'],
                    bid['amount']
                )
                
        # Winner info
        winner_info = None
        if auction.get('current_bidder'):
            winner = await self.db.get_manager(auction['current_bidder'])
            if winner:
                winner_info = {
                    'name': winner.name,
                    'final_balance': winner.balance - auction['current_bid'],
                    'total_players': len(winner.players) + 1
                }
                
        return {
            'auction_id': str(auction['_id']),
            'player': auction['player_name'],
            'base_price': auction['base_price'],
            'final_price': auction['current_bid'],
            'total_bids': len(auction.get('bids', [])),
            'unique_bidders': len(bidder_stats),
            'duration': (auction.get('end_time', datetime.now()) - auction['start_time']).seconds,
            'winner': winner_info,
            'bidder_stats': list(bidder_stats.values()),
            'price_increase_percent': ((auction['current_bid'] - auction['base_price']) / auction['base_price'] * 100)
        }
        
    async def handle_bulk_auction_start(self, player_list: List[Player], context: ContextTypes.DEFAULT_TYPE):
        """Handle starting multiple auctions in sequence"""
        results = {
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for player in player_list:
            try:
                # Create auction
                auction = Auction(
                    player_name=player.name,
                    base_price=player.base_price,
                    current_bid=player.base_price,
                    player_data={
                        'message_id': player.message_id,
                        'position': player.position,
                        'rating': player.rating
                    }
                )
                
                await self.db.create_auction(auction)
                results['success'] += 1
                
                # Wait between auctions
                await asyncio.sleep(2)
                
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"{player.name}: {str(e)}")
                logger.error(f"Error in bulk auction for {player.name}: {e}")
                
        return results
        
    async def get_recommended_bid(self, auction: Auction, user_balance: int) -> Optional[int]:
        """Get AI-recommended bid amount based on patterns"""
        # Simple recommendation logic (can be enhanced with ML)
        current_bid = auction.current_bid
        base_price = auction.base_price
        
        # Analyze bidding velocity
        if len(auction.bids) > 5:
            recent_increments = []
            for i in range(-5, -1):
                increment = auction.bids[i+1].amount - auction.bids[i].amount
                recent_increments.append(increment)
                
            avg_increment = sum(recent_increments) / len(recent_increments)
            recommended = current_bid + int(avg_increment * 1.2)  # Slightly above average
        else:
            # Early auction - use standard increment
            if current_bid < base_price + MAX_STRAIGHT_BID:
                recommended = min(current_bid + 5_000_000, base_price + MAX_STRAIGHT_BID)
            else:
                recommended = current_bid + BID_INCREMENT
                
        # Check against user balance
        if recommended > user_balance:
            return None
            
        return recommended
        
    async def load_auction_queue(self) -> int:
        """Load all available players into auction queue"""
        try:
            # Get all available players
            players = await self.db.get_available_players()
            
            if not players:
                logger.warning("No available players found for auction")
                return 0
                
            # Clear existing queue
            self.auction_queue = []
            
            # Load players into queue
            for player in players:
                self.auction_queue.append(player)
                
            logger.info(f"Loaded {len(self.auction_queue)} players into auction queue")
            return len(self.auction_queue)
            
        except Exception as e:
            logger.error(f"Error loading auction queue: {e}")
            return 0
            
    async def get_next_player(self) -> Optional[Player]:
        """Get next player from queue"""
        if not self.auction_queue:
            return None
            
        return self.auction_queue.pop(0)
        
    async def start_break_timer(self, context: ContextTypes.DEFAULT_TYPE, duration: int = None):
        """Start break timer between auctions"""
        try:
            # Get break duration from settings or use default
            if duration is None:
                duration = await self.db.get_setting("auction_break") or AUCTION_BREAK
                
            self.is_in_break = True
            logger.info(f"Starting break timer for {duration} seconds")
            
            # Send break message
            break_msg = f"""
{EMOJI_ICONS['clock']} <b>AUCTION BREAK</b>

Next auction starts in {duration} seconds...

{EMOJI_ICONS['info']} <i>Take a moment to plan your strategy!</i>
            """.strip()
            
            # Get current mode
            current_mode = await self.db.get_setting("auction_mode") or ("auto" if AUTO_MODE else "manual")
            
            keyboard = []
            if current_mode == 'auto':
                keyboard.append([
                    InlineKeyboardButton(
                        f"{EMOJI_ICONS['rocket']} Skip Break", 
                        callback_data="skip_break"
                    )
                ])
                
            # Add undo button if there was a previous auction
            last_auction = await self.db.auctions.find_one(
                {"status": "completed"},
                sort=[("end_time", -1)]
            )
            if last_auction and last_auction.get('current_bidder'):
                keyboard.append([
                    InlineKeyboardButton(
                        f"{EMOJI_ICONS['undo']} Undo Last", 
                        callback_data=f"undo_last_{last_auction['_id']}"
                    )
                ])
                
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            break_message = await context.bot.send_message(
                AUCTION_GROUP_ID,
                break_msg,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
            # Start countdown
            async def break_countdown():
                try:
                    for i in range(duration, 0, -5):
                        await asyncio.sleep(5)
                        
                        # Update break message
                        try:
                            break_msg_update = f"""
{EMOJI_ICONS['clock']} <b>AUCTION BREAK</b>

Next auction starts in {i-5} seconds...

{EMOJI_ICONS['info']} <i>Take a moment to plan your strategy!</i>
                            """.strip()
                            
                            await context.bot.edit_message_text(
                                chat_id=AUCTION_GROUP_ID,
                                message_id=break_message.message_id,
                                text=break_msg_update,
                                parse_mode='HTML',
                                reply_markup=reply_markup
                            )
                        except:
                            pass
                            
                    # Break finished
                    self.is_in_break = False
                    
                    # Delete break message
                    try:
                        await context.bot.delete_message(
                            chat_id=AUCTION_GROUP_ID,
                            message_id=break_message.message_id
                        )
                    except:
                        pass
                        
                    # Check mode and continue
                    if current_mode == 'auto' and self.auction_queue:
                        # Auto mode - continue to next player
                        if self.admin_handlers:
                            await self.admin_handlers._process_next_in_queue(context)
                    else:
                        # Manual mode or no more players
                        if not self.auction_queue:
                            if self.admin_handlers:
                                await self.admin_handlers._finish_auction_session(context)
                        else:
                            await context.bot.send_message(
                                AUCTION_GROUP_ID,
                                f"{EMOJI_ICONS['info']} Break finished. Admin can start next auction with /final_call",
                                parse_mode='HTML'
                            )
                            
                except asyncio.CancelledError:
                    logger.info("Break timer cancelled")
                    self.is_in_break = False
                    
            self.break_timer_task = asyncio.create_task(break_countdown())
            
        except Exception as e:
            logger.error(f"Error starting break timer: {e}")
            self.is_in_break = False
            
    async def skip_break(self):
        """Skip the break timer"""
        if self.break_timer_task:
            self.break_timer_task.cancel()
            self.is_in_break = False
            logger.info("Break timer skipped")
            
    async def reset_auction_timer(self, auction_id: ObjectId, context: ContextTypes.DEFAULT_TYPE):
        """Reset the auction timer (called on each new bid)"""
        try:
            # Get auction
            auction = await self.db.auctions.find_one({"_id": auction_id})
            if not auction or auction['status'] != 'active':
                return
                
            # This is now handled by admin_handlers.handle_new_bid
            # which calls gif_countdown.reset_timer
            logger.info(f"Timer reset requested for auction {auction_id}")
            
        except Exception as e:
            logger.error(f"Error resetting auction timer: {e}")
            
    def is_auction_in_break(self) -> bool:
        """Check if auction system is in break"""
        return self.is_in_break
        
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            'players_remaining': len(self.auction_queue),
            'in_break': self.is_in_break,
            'current_session': self.current_session
        }