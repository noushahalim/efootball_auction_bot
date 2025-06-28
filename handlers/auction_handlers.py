# handlers/auction_handlers.py - Specialized Auction Handling
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List  # Added List import
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