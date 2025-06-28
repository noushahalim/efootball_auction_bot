# handlers/admin_handlers.py - Complete Admin Handlers Implementation
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from telegram.error import BadRequest, TelegramError, Forbidden
from bson import ObjectId
from config.settings import *
from database.models import Manager, Player, Auction, Bid, AuctionSession, ManagerRole
from utilities.formatters import MessageFormatter
from utilities.helpers import ValidationHelper
from utilities.countdown import CountdownManager
from utilities.analytics import AnalyticsManager

logger = logging.getLogger(__name__)

class AdminHandlers:
    def __init__(self, db, bot):
        self.db = db
        self.bot = bot
        self.formatter = MessageFormatter()
        self.validator = ValidationHelper()
        self.countdown = CountdownManager()
        self.analytics = AnalyticsManager(db)
        self.auction_tasks = {}
        self.current_session = None
        
    async def start_auction_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start_auction command with improved parsing"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} You don't have permission to use this command!"
            )
            return

        # Check if auction is already running
        current_auction = await self.db.get_current_auction()
        if current_auction:
            await update.message.reply_text(
                f"{EMOJI_ICONS['warning']} An auction is already running!\n"
                f"Player: {current_auction.player_name}\n\n"
                f"Stop it first with /stop_auction"
            )
            return

        args = context.args
        
        if args:
            # Parse message link or ID
            message_id = None
            if args[0].startswith('https://t.me/'):
                # Extract message ID from link
                match = re.search(r'/(\d+)$', args[0])
                if match:
                    message_id = int(match.group(1))
                else:
                    await update.message.reply_text(
                        f"{EMOJI_ICONS['error']} Invalid message link format!"
                    )
                    return
            else:
                try:
                    message_id = int(args[0])
                except ValueError:
                    await update.message.reply_text(
                        f"{EMOJI_ICONS['error']} Invalid message ID format!"
                    )
                    return
            
            # Start auction from specific message
            success = await self._start_auction_from_message(update, context, message_id)
        else:
            # Start from next available player
            success = await self._start_next_auction(update, context)
            
    async def _start_next_auction(self, update, context):
        """Start auction from next available player"""
        players = await self.db.get_available_players()
        
        if not players:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} No players available for auction!\n\n"
                f"Add players to the data group first."
            )
            return False
            
        # Get first available player
        player = players[0]
        return await self._create_auction_from_player(update, context, player)
        
    async def _start_auction_from_message(self, update, context, message_id: int) -> bool:
        """Start auction from specific message ID"""
        try:
            # Try to get message from data group
            try:
                message = await context.bot.forward_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=DATA_GROUP_ID,
                    message_id=message_id
                )
                # Delete the forwarded message
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=message.message_id
                )
            except Exception as e:
                await update.message.reply_text(
                    f"{EMOJI_ICONS['error']} Cannot access message!\n"
                    f"Make sure the message exists in the data group."
                )
                return False
                
            player_data = await self._parse_player_message(message)
            
            if not player_data:
                await update.message.reply_text(
                    f"{EMOJI_ICONS['error']} Could not parse player data from message!\n\n"
                    f"Expected format:\n"
                    f"'Player Name' price\n"
                    f"\"Player Name\" price"
                )
                return False
                
            # Create and start auction
            return await self._create_auction(update, context, player_data)
            
        except Exception as e:
            logger.error(f"Error starting auction from message {message_id}: {e}")
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} Error: {str(e)}"
            )
            return False
            
    async def _create_auction_from_player(self, update, context, player: Player) -> bool:
        """Create auction from existing player object"""
        player_data = {
            'name': player.name,
            'base_price': player.base_price,
            'message_id': player.message_id,
            'image_url': player.image_url,
            'position': player.position,
            'rating': player.rating
        }
        
        return await self._create_auction(update, context, player_data)
        
    async def _parse_player_message(self, message) -> Optional[Dict[str, Any]]:
        """Parse player data from message with improved regex"""
        text = message.text or message.caption or ""
        
        if not text:
            return None
            
        # Try multiple patterns
        patterns = [
            r"['\"]([^'\"]+)['\"][\s]*(\d+)",  # 'Name' price or "Name" price
            r"(['\"][^'\"]+['\"])[\s]*(\d+)",   # With quotes included
            r"([A-Za-z\s]+)[\s]*(\d+)$",        # Name price (simple)
            r"^([^0-9]+)(\d+)$",                # Any non-digit followed by digits
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.strip())
            if match:
                name = match.group(1).strip().strip("'\"")
                try:
                    price = int(match.group(2)) * 1_000_000  # Convert to actual amount
                    
                    player_data = {
                        'name': name,
                        'base_price': price,
                        'message_id': message.message_id,
                        'image_url': None
                    }
                    
                    # Get image if present
                    if message.photo:
                        player_data['image_url'] = message.photo[-1].file_id
                        
                    # Try to extract additional info
                    extra_info = self._extract_player_info(text)
                    player_data.update(extra_info)
                    
                    return player_data
                    
                except ValueError:
                    continue
                    
        return None
        
    def _extract_player_info(self, text: str) -> Dict[str, Any]:
        """Extract additional player information from text"""
        info = {}
        
        # Extract position
        positions = ['GK', 'CB', 'LB', 'RB', 'CDM', 'CM', 'CAM', 'LM', 'RM', 'LW', 'RW', 'CF', 'ST']
        for pos in positions:
            if pos in text.upper():
                info['position'] = pos
                break
                
        # Extract rating if present (e.g., "87 rated")
        rating_match = re.search(r'(\d{2})\s*rated', text, re.IGNORECASE)
        if rating_match:
            info['rating'] = int(rating_match.group(1))
            
        return info
        
    async def _create_auction(self, update, context, player_data: Dict[str, Any]) -> bool:
        """Create and start auction with player data"""
        try:
            # Create player record if not exists
            existing_player = await self.db.get_player_by_message_id(player_data['message_id'])
            if not existing_player:
                player = Player(
                    name=player_data['name'],
                    base_price=player_data['base_price'],
                    message_id=player_data['message_id'],
                    image_url=player_data.get('image_url'),
                    position=player_data.get('position'),
                    rating=player_data.get('rating')
                )
                await self.db.add_player(player)
            
            # Create auction
            current_mode = await self.db.get_setting("auction_mode") or ("auto" if AUTO_MODE else "manual")
            current_timer = await self.db.get_setting("auction_timer") or AUCTION_TIMER
            
            auction = Auction(
                player_name=player_data['name'],
                base_price=player_data['base_price'],
                current_bid=player_data['base_price'],
                player_data=player_data,
                mode=current_mode,
                timer_duration=current_timer
            )
            
            auction_id = await self.db.create_auction(auction)
            
            # Send auction message with visual countdown
            await self._send_auction_message(context, auction, auction_id)
            
            # Start timer if auto mode
            if current_mode == 'auto':
                await self._start_auction_timer(auction_id, context)
                
            # Notify in admin chat
            await update.message.reply_text(
                f"{EMOJI_ICONS['success']} Auction started successfully!\n\n"
                f"{EMOJI_ICONS['player']} Player: {player_data['name']}\n"
                f"{EMOJI_ICONS['money']} Base: {self.formatter.format_currency(player_data['base_price'])}\n"
                f"{EMOJI_ICONS['gear']} Mode: {current_mode.upper()}\n"
                f"{EMOJI_ICONS['timer']} Timer: {current_timer}s"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating auction: {e}")
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} Failed to create auction: {str(e)}"
            )
            return False
            
    async def _send_auction_message(self, context, auction: Auction, auction_id: ObjectId):
        """Send auction message with enhanced visuals"""
        # Create visual auction message
        countdown_bar = self.formatter.create_progress_bar(100, 10)
        
        auction_msg = f"""
{EMOJI_ICONS['fire']} <b>LIVE AUCTION</b> {EMOJI_ICONS['fire']}

{EMOJI_ICONS['player']} <b>Player:</b> {auction.player_name}
{EMOJI_ICONS['money']} <b>Base Price:</b> {self.formatter.format_currency(auction.base_price)}

{EMOJI_ICONS['chart_up']} <b>Current Bid:</b> {self.formatter.format_currency(auction.current_bid)}
{EMOJI_ICONS['timer']} <b>Time:</b> {auction.timer_duration}s

{countdown_bar}

{EMOJI_ICONS['target']} <b>Quick Bid Options:</b>
        """.strip()
        
        # Create quick bid buttons
        keyboard = []
        for amount in QUICK_BID_AMOUNTS:
            new_bid = auction.current_bid + amount
            button_text = f"{EMOJI_ICONS['bid']} +{amount // 1_000_000}M ({new_bid // 1_000_000}M)"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"qbid_{auction_id}_{new_bid}")])
            
        keyboard.append([
            InlineKeyboardButton(f"{EMOJI_ICONS['stats']} Stats", callback_data=f"auction_stats_{auction_id}"),
            InlineKeyboardButton(f"{EMOJI_ICONS['bell']} Watch", callback_data=f"watch_auction_{auction_id}")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send with image if available
        try:
            if auction.player_data and auction.player_data.get('image_url'):
                sent_message = await context.bot.send_photo(
                    AUCTION_GROUP_ID,
                    photo=auction.player_data['image_url'],
                    caption=auction_msg,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            else:
                # Send with animation
                sent_message = await context.bot.send_animation(
                    AUCTION_GROUP_ID,
                    animation=AUCTION_START_GIF,
                    caption=auction_msg,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
        except:
            # Fallback to text message
            sent_message = await context.bot.send_message(
                AUCTION_GROUP_ID,
                auction_msg,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
        # Update auction with message ID
        await self.db.auctions.update_one(
            {"_id": auction_id},
            {"$set": {"message_id": sent_message.message_id}}
        )
        
        # Start countdown updates
        self.countdown.start_countdown(
            str(auction_id), 
            auction.timer_duration, 
            self._update_auction_message,
            context
        )
        
    async def _update_auction_message(self, auction_id: str, time_left: int, context):
        """Update auction message with countdown"""
        try:
            auction = await self.db.auctions.find_one({"_id": ObjectId(auction_id)})
            if not auction or auction['status'] != 'active':
                return
                
            # Determine urgency level
            urgency = self.countdown.get_urgency_level(time_left)
            emoji = COUNTDOWN_STAGES[min(k for k in COUNTDOWN_STAGES.keys() if k >= time_left)]['emoji']
            
            # Update progress bar
            progress = ((auction['timer_duration'] - time_left) / auction['timer_duration']) * 100
            countdown_bar = self.formatter.create_progress_bar(progress, 10)
            
            # Format current bidder info
            bidder_info = ""
            if auction['current_bidder']:
                bidder = await self.db.get_manager(auction['current_bidder'])
                if bidder:
                    bidder_info = f"\n{EMOJI_ICONS['winner']} <b>Leading:</b> {bidder.name}"
            
            auction_msg = f"""
{EMOJI_ICONS['fire']} <b>LIVE AUCTION</b> {EMOJI_ICONS['fire']}

{EMOJI_ICONS['player']} <b>Player:</b> {auction['player_name']}
{EMOJI_ICONS['money']} <b>Base Price:</b> {self.formatter.format_currency(auction['base_price'])}

{EMOJI_ICONS['chart_up']} <b>Current Bid:</b> {self.formatter.format_currency(auction['current_bid'])}{bidder_info}
{emoji} <b>Time:</b> {time_left}s

{countdown_bar}

{self._get_urgency_message(urgency)}
            """.strip()
            
            # Update quick bid buttons
            keyboard = []
            for amount in QUICK_BID_AMOUNTS:
                new_bid = auction['current_bid'] + amount
                button_text = f"{EMOJI_ICONS['bid']} +{amount // 1_000_000}M ({new_bid // 1_000_000}M)"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"qbid_{auction_id}_{new_bid}")])
                
            keyboard.append([
                InlineKeyboardButton(f"{EMOJI_ICONS['stats']} Stats", callback_data=f"auction_stats_{auction_id}"),
                InlineKeyboardButton(f"{EMOJI_ICONS['bell']} Watch", callback_data=f"watch_auction_{auction_id}")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Update message
            if auction.get('message_id'):
                try:
                    await context.bot.edit_message_caption(
                        chat_id=AUCTION_GROUP_ID,
                        message_id=auction['message_id'],
                        caption=auction_msg,
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                except BadRequest as e:
                    if "message is not modified" not in str(e):
                        logger.error(f"Error updating auction message: {e}")
            
        except Exception as e:
            logger.error(f"Error in countdown update: {e}")
            
    def _get_urgency_message(self, urgency: str) -> str:
        """Get urgency message based on time left"""
        messages = {
            'low': f"{EMOJI_ICONS['info']} Place your bids now!",
            'medium': f"{EMOJI_ICONS['warning']} Hurry up! Time is running out!",
            'high': f"{EMOJI_ICONS['fire']} FINAL MOMENTS! Last chance to bid!",
            'critical': f"{EMOJI_ICONS['bell']} GOING ONCE... GOING TWICE..."
        }
        return messages.get(urgency, "")
        
    async def _start_auction_timer(self, auction_id: ObjectId, context):
        """Start auction timer for auto mode"""
        async def timer_callback():
            auction = await self.db.auctions.find_one({"_id": auction_id})
            if auction:
                await asyncio.sleep(auction['timer_duration'])
                await self._end_auction_automatically(auction_id, context)
            
        task = asyncio.create_task(timer_callback())
        self.auction_tasks[auction_id] = task
        
    async def _end_auction_automatically(self, auction_id: ObjectId, context):
        """End auction when timer expires"""
        auction = await self.db.auctions.find_one({"_id": auction_id})
        if not auction or auction.get('status') != 'active':
            return
            
        # Stop countdown
        self.countdown.stop_countdown(str(auction_id))
        
        # Determine outcome
        if auction.get('current_bidder'):
            await self._finalize_auction_win(auction, context)
        else:
            await self._finalize_auction_unsold(auction, context)
            
    async def _finalize_auction_win(self, auction: dict, context):
        """Finalize auction with a winner"""
        try:
            # Get winner details
            winner = await self.db.get_manager(auction['current_bidder'])
            if not winner:
                logger.error(f"Winner {auction['current_bidder']} not found!")
                return
                
            # Update manager
            new_balance = winner.balance - auction['current_bid']
            await self.db.update_manager_balance(
                auction['current_bidder'],
                new_balance,
                auction['current_bid']
            )
            
            await self.db.add_player_to_manager(
                auction['current_bidder'],
                auction['player_name'],
                auction['current_bid']
            )
            
            # Update player status
            if 'message_id' in auction.get('player_data', {}):
                await self.db.update_player_status(
                    auction['player_data']['message_id'],
                    'sold',
                    auction['current_bidder'],
                    auction['current_bid']
                )
                
            # Complete auction
            await self.db.complete_auction(auction['_id'])
            
            # Send winning message with celebration
            win_msg = f"""
{EMOJI_ICONS['trophy']} <b>SOLD!</b> {EMOJI_ICONS['trophy']}

{EMOJI_ICONS['celebration']} Congratulations!

{EMOJI_ICONS['player']} <b>Player:</b> {auction['player_name']}
{EMOJI_ICONS['winner']} <b>Winner:</b> {winner.name}
{EMOJI_ICONS['moneybag']} <b>Final Price:</b> {self.formatter.format_currency(auction['current_bid'])}

{EMOJI_ICONS['sparkles']} <i>Great addition to the team!</i>
            """.strip()
            
            keyboard = [[
                InlineKeyboardButton(
                    f"{EMOJI_ICONS['chart']} View Stats", 
                    callback_data=f"auction_summary_{auction['_id']}"
                )
            ]]
            
            await context.bot.send_message(
                AUCTION_GROUP_ID,
                win_msg,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # Send victory sticker
            try:
                await context.bot.send_sticker(AUCTION_GROUP_ID, WIN_STICKER)
            except:
                pass
                
            # Notify winner privately
            try:
                winner_msg = f"""
{EMOJI_ICONS['trophy']} <b>YOU WON!</b> {EMOJI_ICONS['trophy']}

{EMOJI_ICONS['player']} <b>Player:</b> {auction['player_name']}
{EMOJI_ICONS['moneybag']} <b>Price:</b> {self.formatter.format_currency(auction['current_bid'])}
{EMOJI_ICONS['money']} <b>Balance:</b> {self.formatter.format_currency(new_balance)}

{EMOJI_ICONS['sparkles']} Well played!
                """.strip()
                
                await context.bot.send_message(
                    winner.user_id,
                    winner_msg,
                    parse_mode='HTML'
                )
            except:
                pass
                
        except Exception as e:
            logger.error(f"Error finalizing auction win: {e}")
            
    async def _finalize_auction_unsold(self, auction: dict, context):
        """Finalize auction as unsold"""
        try:
            # Update player status
            if 'message_id' in auction.get('player_data', {}):
                await self.db.update_player_status(
                    auction['player_data']['message_id'],
                    'unsold'
                )
                
            # Complete auction
            await self.db.complete_auction(auction['_id'])
            
            # Send unsold message
            unsold_msg = f"""
{EMOJI_ICONS['warning']} <b>UNSOLD</b> {EMOJI_ICONS['warning']}

{EMOJI_ICONS['player']} <b>Player:</b> {auction['player_name']}
{EMOJI_ICONS['money']} <b>Base Price:</b> {self.formatter.format_currency(auction['base_price'])}

{EMOJI_ICONS['info']} <i>No bids received - Moving to unsold pool</i>
            """.strip()
            
            await context.bot.send_message(
                AUCTION_GROUP_ID,
                unsold_msg,
                parse_mode='HTML'
            )
            
            # Forward to unsold group
            if UNSOLD_GROUP_ID:
                try:
                    unsold_detail = f"""
🔴 <b>UNSOLD PLAYER</b>

{EMOJI_ICONS['player']} {auction['player_name']}
{EMOJI_ICONS['money']} Base: {self.formatter.format_currency(auction['base_price'])}
{EMOJI_ICONS['timer']} Time: {datetime.now().strftime('%H:%M:%S')}
                    """.strip()
                    
                    await context.bot.send_message(
                        UNSOLD_GROUP_ID,
                        unsold_detail,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Error sending to unsold group: {e}")
                
        except Exception as e:
            logger.error(f"Error finalizing unsold auction: {e}")
            
    async def stop_auction(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop/pause current auction"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} You don't have permission!"
            )
            return
            
        current_auction = await self.db.get_current_auction()
        if not current_auction:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} No active auction to stop!"
            )
            return
            
        # Stop countdown
        self.countdown.stop_countdown(str(current_auction._id))
        
        # Cancel timer
        if current_auction._id in self.auction_tasks:
            self.auction_tasks[current_auction._id].cancel()
            del self.auction_tasks[current_auction._id]
            
        # Pause auction
        await self.db.auctions.update_one(
            {"_id": current_auction._id},
            {"$set": {"status": "paused"}}
        )
        
        # Save state
        await self.db.set_setting("paused_auction_id", str(current_auction._id))
        
        await update.message.reply_text(
            f"{EMOJI_ICONS['stop']} Auction paused!\n\n"
            f"Player: {current_auction.player_name}\n"
            f"Current Bid: {self.formatter.format_currency(current_auction.current_bid)}\n\n"
            f"Use /continue_auction to resume"
        )
        
        # Notify in auction group
        await context.bot.send_message(
            AUCTION_GROUP_ID,
            f"{EMOJI_ICONS['stop']} <b>AUCTION PAUSED</b>\n\n"
            f"The auction has been temporarily paused by admin.",
            parse_mode='HTML'
        )
        
    async def continue_auction(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Continue paused auction"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} You don't have permission!"
            )
            return
            
        # Get paused auction ID
        paused_id = await self.db.get_setting("paused_auction_id")
        if not paused_id:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} No paused auction found!"
            )
            return
            
        # Resume auction
        await self.db.auctions.update_one(
            {"_id": ObjectId(paused_id)},
            {"$set": {"status": "active"}}
        )
        
        # Clear saved state
        await self.db.set_setting("paused_auction_id", None)
        
        # Get auction details
        auction = await self.db.get_current_auction()
        if auction and auction.mode == 'auto':
            # Restart timer with remaining time
            current_timer = await self.db.get_setting("auction_timer") or AUCTION_TIMER
            await self._start_auction_timer(auction._id, context)
            self.countdown.start_countdown(
                str(auction._id),
                current_timer,
                self._update_auction_message,
                context
            )
            
        await update.message.reply_text(
            f"{EMOJI_ICONS['success']} Auction resumed!"
        )
        
        # Notify auction group
        await context.bot.send_message(
            AUCTION_GROUP_ID,
            f"{EMOJI_ICONS['rocket']} <b>AUCTION RESUMED!</b>\n\n"
            f"The auction is now active again. Continue bidding!",
            parse_mode='HTML'
        )
        
    async def skip_bid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Skip current player to unsold"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} You don't have permission!"
            )
            return
            
        current_auction = await self.db.get_current_auction()
        if not current_auction:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} No active auction to skip!"
            )
            return
            
        # Stop countdown
        self.countdown.stop_countdown(str(current_auction._id))
        
        # Cancel timer
        if current_auction._id in self.auction_tasks:
            self.auction_tasks[current_auction._id].cancel()
            del self.auction_tasks[current_auction._id]
            
        # Mark as unsold
        await self._finalize_auction_unsold(
            await self.db.auctions.find_one({"_id": current_auction._id}),
            context
        )
        
        await update.message.reply_text(
            f"{EMOJI_ICONS['skip']} Player marked as unsold!"
        )
        
    async def final_call(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Final call for manual mode"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} You don't have permission!"
            )
            return
            
        current_auction = await self.db.get_current_auction()
        if not current_auction:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} No active auction!"
            )
            return
            
        current_mode = await self.db.get_setting("auction_mode") or ("auto" if AUTO_MODE else "manual")
        if current_mode == 'auto':
            await update.message.reply_text(
                f"{EMOJI_ICONS['warning']} Cannot use final call in auto mode!"
            )
            return
            
        # Send final call message
        final_msg = f"""
{EMOJI_ICONS['bell']} <b>FINAL CALL!</b> {EMOJI_ICONS['bell']}

{EMOJI_ICONS['player']} <b>Player:</b> {current_auction.player_name}
{EMOJI_ICONS['money']} <b>Current Bid:</b> {self.formatter.format_currency(current_auction.current_bid)}

{EMOJI_ICONS['hammer']} <b>Going Once... Going Twice...</b>

Last chance to bid!
        """.strip()
        
        await context.bot.send_message(
            AUCTION_GROUP_ID,
            final_msg,
            parse_mode='HTML'
        )
        
        # Wait a moment then finalize
        await asyncio.sleep(5)
        
        # Check if any new bids came in
        updated_auction = await self.db.get_current_auction()
        if updated_auction and updated_auction.current_bid > current_auction.current_bid:
            await update.message.reply_text(
                f"{EMOJI_ICONS['info']} New bid received! Continue auction."
            )
        else:
            # Finalize
            if current_auction.current_bidder:
                await self._finalize_auction_win(
                    await self.db.auctions.find_one({"_id": current_auction._id}),
                    context
                )
            else:
                await self._finalize_auction_unsold(
                    await self.db.auctions.find_one({"_id": current_auction._id}),
                    context
                )
                
            await update.message.reply_text(
                f"{EMOJI_ICONS['success']} Auction completed!"
            )
            
    async def undo_bid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Undo last bid"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} You don't have permission!"
            )
            return
            
        current_auction = await self.db.get_current_auction()
        if not current_auction:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} No active auction!"
            )
            return
            
        if not current_auction.bids:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} No bids to undo!"
            )
            return
            
        # Remove last bid
        last_bid = current_auction.bids[-1]
        current_auction.bids.pop()
        
        # Determine new current bid
        if current_auction.bids:
            prev_bid = current_auction.bids[-1]
            new_current_bid = prev_bid.amount
            new_current_bidder = prev_bid.user_id
        else:
            new_current_bid = current_auction.base_price
            new_current_bidder = None
            
        # Update database
        await self.db.auctions.update_one(
            {"_id": current_auction._id},
            {
                "$set": {
                    "bids": [bid.to_dict() for bid in current_auction.bids],
                    "current_bid": new_current_bid,
                    "current_bidder": new_current_bidder
                }
            }
        )
        
        # Notify
        undo_msg = f"""
{EMOJI_ICONS['undo']} <b>BID UNDONE</b>

Last bid of {self.formatter.format_currency(last_bid.amount)} has been removed.

Current bid: {self.formatter.format_currency(new_current_bid)}
        """.strip()
        
        await context.bot.send_message(
            AUCTION_GROUP_ID,
            undo_msg,
            parse_mode='HTML'
        )
        
        await update.message.reply_text(
            f"{EMOJI_ICONS['success']} Last bid undone!"
        )
        
    async def auction_result(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show auction results"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} You don't have permission!"
            )
            return
            
        managers = await self.db.get_all_managers()
        
        if not managers:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} No managers found!"
            )
            return
            
        # Send loading message
        loading_msg = await update.message.reply_text(
            f"{EMOJI_ICONS['loading']} Generating auction results..."
        )
        
        # Generate detailed results
        session = await self.db.get_current_session()
        
        # Send individual manager cards
        for manager in managers:
            if manager.players:  # Only show managers who bought players
                card = self._create_manager_result_card(manager)
                await update.message.reply_text(card, parse_mode='HTML')
                await asyncio.sleep(0.5)  # Prevent flooding
                
        # Send summary
        summary = await self._create_auction_summary(managers, session)
        
        keyboard = [
            [InlineKeyboardButton(
                f"{EMOJI_ICONS['chart']} Download Report",
                callback_data="download_report"
            )],
            [InlineKeyboardButton(
                f"{EMOJI_ICONS['trophy']} View Leaderboard",
                callback_data="leaderboard"
            )]
        ]
        
        await loading_msg.edit_text(
            summary,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    def _create_manager_result_card(self, manager: Manager) -> str:
        """Create detailed manager result card"""
        # Calculate stats
        avg_price = manager.total_spent // len(manager.players) if manager.players else 0
        
        card = f"""
{EMOJI_ICONS['trophy']} <b>MANAGER REPORT</b>

{EMOJI_ICONS['admin']} <b>Name:</b> {manager.name}
{EMOJI_ICONS['money']} <b>Balance:</b> {self.formatter.format_currency(manager.balance)}
{EMOJI_ICONS['chart_up']} <b>Spent:</b> {self.formatter.format_currency(manager.total_spent)}
{EMOJI_ICONS['team']} <b>Squad Size:</b> {len(manager.players)}

{EMOJI_ICONS['star']} <b>Average/Player:</b> {self.formatter.format_currency(avg_price)}

{EMOJI_ICONS['player']} <b>Players:</b>
        """.strip()
        
        for i, player in enumerate(manager.players, 1):
            card += f"\n{i}. {player}"
            
        # Add achievements if any
        if manager.achievements:
            card += f"\n\n{EMOJI_ICONS['medal']} <b>Achievements:</b> {len(manager.achievements)}"
            
        return card
        
    async def _create_auction_summary(self, managers: List[Manager], session: Optional[dict]) -> str:
        """Create auction summary"""
        total_spent = sum(m.total_spent for m in managers)
        total_players = sum(len(m.players) for m in managers)
        active_bidders = len([m for m in managers if m.players])
        
        summary = f"""
{EMOJI_ICONS['chart']} <b>AUCTION SUMMARY</b>

{EMOJI_ICONS['team']} <b>Total Managers:</b> {len(managers)}
{EMOJI_ICONS['target']} <b>Active Bidders:</b> {active_bidders}
{EMOJI_ICONS['player']} <b>Players Sold:</b> {total_players}
{EMOJI_ICONS['moneybag']} <b>Total Spent:</b> {self.formatter.format_currency(total_spent)}

{EMOJI_ICONS['star']} <b>Top Spenders:</b>
        """.strip()
        
        # Add top 3 spenders
        top_spenders = sorted(managers, key=lambda m: m.total_spent, reverse=True)[:3]
        medals = ['🥇', '🥈', '🥉']
        
        for i, manager in enumerate(top_spenders):
            if manager.total_spent > 0:
                summary += f"\n{medals[i]} {manager.name} - {self.formatter.format_currency(manager.total_spent)}"
                
        return summary
        
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show settings menu"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} Admin access required!"
            )
            return
            
        if update.message.chat.type != 'private':
            await update.message.reply_text(
                f"{EMOJI_ICONS['warning']} Settings only work in private chat!\n"
                f"Please DM me and use /settings"
            )
            return
            
        # Get current settings
        current_mode = await self.db.get_setting("auction_mode") or ("auto" if AUTO_MODE else "manual")
        current_timer = await self.db.get_setting("auction_timer") or AUCTION_TIMER
        current_budget = await self.db.get_setting("default_balance") or DEFAULT_BALANCE
        analytics_enabled = await self.db.get_setting("track_analytics")
        if analytics_enabled is None:
            analytics_enabled = TRACK_ANALYTICS
            
        keyboard = [
            [
                InlineKeyboardButton("👥 Managers", callback_data="settings_managers"),
                InlineKeyboardButton("⏰ Timer", callback_data="settings_timer")
            ],
            [
                InlineKeyboardButton("🎮 Mode", callback_data="settings_mode"),
                InlineKeyboardButton("💰 Budget", callback_data="settings_budget")
            ],
            [
                InlineKeyboardButton("📊 Analytics", callback_data="settings_analytics"),
                InlineKeyboardButton("🔔 Notifications", callback_data="settings_notifications")
            ],
            [
                InlineKeyboardButton("🎯 Session", callback_data="settings_session"),
                InlineKeyboardButton("🏢 Groups", callback_data="settings_groups")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="start")]
        ]
        
        settings_msg = f"""
{EMOJI_ICONS['settings']} <b>ADMIN SETTINGS</b>

{EMOJI_ICONS['info']} <b>Current Configuration:</b>

🎮 Mode: <b>{current_mode.upper()}</b>
⏰ Timer: <b>{current_timer}s</b>
💰 Default Balance: <b>{self.formatter.format_currency(current_budget)}</b>
📊 Analytics: <b>{'ON' if analytics_enabled else 'OFF'}</b>

Select a category to configure:
        """.strip()
        
        await update.message.reply_text(
            settings_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def manage_groups_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /groups command"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} Admin access required!"
            )
            return
            
        groups = await self.db.get_all_groups()
        
        msg = f"""
{EMOJI_ICONS['home']} <b>GROUP MANAGEMENT</b>

Connected Groups: {len(groups)}

{EMOJI_ICONS['info']} <b>Configured Groups:</b>
        """.strip()
        
        # Show configured groups
        group_info = {
            AUCTION_GROUP_ID: ("Auction Group", "🏟️"),
            DATA_GROUP_ID: ("Data Group", "📋"),
            UNSOLD_GROUP_ID: ("Unsold Group", "📦")
        }
        
        for group_id, (name, icon) in group_info.items():
            if group_id:
                status = "🟢" if any(g['chat_id'] == group_id and g['status'] == 'active' for g in groups) else "🔴"
                msg += f"\n{icon} {name}: {status} <code>{group_id}</code>"
            else:
                msg += f"\n{icon} {name}: ❌ Not configured"
                
        # Show connected groups
        if groups:
            msg += f"\n\n{EMOJI_ICONS['team']} <b>All Connected Groups:</b>"
            for group in groups[:5]:  # Show first 5
                status = "🟢" if group['status'] == 'active' else "🔴"
                msg += f"\n{status} {group['title']} (<code>{group['chat_id']}</code>)"
                
        keyboard = [
            [InlineKeyboardButton("🔍 Find Group ID", callback_data="find_group_help")],
            [InlineKeyboardButton("📋 All Groups", callback_data="list_all_groups")],
            [InlineKeyboardButton("🔧 Group Tools", callback_data="group_tools")]
        ]
        
        await update.message.reply_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def analytics_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analytics command"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} Admin access required!"
            )
            return
            
        # Get analytics data
        analytics = await self.analytics.get_auction_analytics(days=7)
        
        analytics_msg = f"""
{EMOJI_ICONS['chart']} <b>ANALYTICS DASHBOARD</b>

{EMOJI_ICONS['calendar']} <b>Last 7 Days Overview:</b>

📊 <b>Auction Performance:</b>
• Total Auctions: {analytics.get('total_auctions', 0)}
• Sold Players: {analytics.get('sold_count', 0)}
• Unsold Players: {analytics.get('unsold_count', 0)}
• Sell Rate: {analytics.get('sell_rate', 0):.1f}%

💰 <b>Financial Summary:</b>
• Total Revenue: {self.formatter.format_currency(analytics.get('total_revenue', 0))}
• Average Sale: {self.formatter.format_currency(analytics.get('avg_sale_price', 0))}

👥 <b>User Engagement:</b>
• Total Bids: {analytics.get('total_bids', 0)}
• Unique Bidders: {analytics.get('unique_bidders', 0)}
• Avg Bids/Auction: {analytics.get('avg_bids_per_auction', 0):.1f}

⏰ <b>Top Activity Hours:</b>
        """.strip()
        
        # Add peak hours
        peak_hours = analytics.get('peak_hours', {})
        for hour, count in list(peak_hours.items())[:3]:
            analytics_msg += f"\n• {hour}:00 - {count} auctions"
            
        keyboard = [
            [
                InlineKeyboardButton("📈 Detailed Report", callback_data="detailed_analytics"),
                InlineKeyboardButton("📊 Export Data", callback_data="export_analytics")
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="settings_analytics"),
                InlineKeyboardButton("🔄 Refresh", callback_data="view_analytics")
            ]
        ]
        
        await update.message.reply_text(
            analytics_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def handle_data_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages in data group"""
        try:
            # Parse player data
            player_data = await self._parse_player_message(update.message)
            
            if player_data:
                # Save to database
                player = Player(
                    name=player_data['name'],
                    base_price=player_data['base_price'],
                    message_id=update.message.message_id,
                    image_url=player_data.get('image_url'),
                    position=player_data.get('position'),
                    rating=player_data.get('rating')
                )
                
                success = await self.db.add_player(player)
                
                if success:
                    # React to message to indicate it was processed
                    try:
                        await update.message.set_reaction("✅")
                    except:
                        pass
                        
                    logger.info(f"Added player: {player.name} ({self.formatter.format_currency(player.base_price)})")
                else:
                    logger.warning(f"Player already exists: {player.name}")
                    
        except Exception as e:
            logger.error(f"Error processing data message: {e}")