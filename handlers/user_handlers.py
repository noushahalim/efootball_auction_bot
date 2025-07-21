# handlers/user_handlers.py - Fixed User Handlers with Timer Reset...
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest, Forbidden
from bson import ObjectId
from config.settings import *
from database.models import Manager, Bid, Achievement
from utilities.formatters import MessageFormatter
from utilities.helpers import ValidationHelper
from utilities.animations import AnimationManager

logger = logging.getLogger(__name__)

class UserHandlers:
    def __init__(self, db, bot):
        self.db = db
        self.bot = bot
        self.formatter = MessageFormatter()
        self.validator = ValidationHelper()
        self.animations = AnimationManager()
        self.bid_cooldowns = {}  # Track bid cooldowns
        self.admin_handlers = None  # Will be set by admin_handlers
        
    async def place_bid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /bid command with enhanced validation and visuals"""
        user_id = update.effective_user.id
        args = context.args
        
        # Check if in auction group
        if update.message.chat_id != AUCTION_GROUP_ID:
            await update.message.reply_text(
                f"{EMOJI_ICONS['warning']} Bidding is only allowed in the auction group!",
                reply_to_message_id=update.message.message_id
            )
            return
            
        # Delete the bid command message for cleaner chat
        try:
            await update.message.delete()
        except:
            pass
            
        # Check cooldown
        if await self._check_bid_cooldown(user_id):
            try:
                await context.bot.send_message(
                    user_id,
                    f"{EMOJI_ICONS['warning']} Please wait before bidding again! (Anti-spam protection)"
                )
            except:
                pass
            return
            
        # Check if user is registered
        manager = await self.db.get_manager(user_id)
        if not manager:
            error_msg = self.formatter.format_bid_error('not_registered')
            try:
                await context.bot.send_message(user_id, error_msg)
            except:
                await context.bot.send_message(
                    AUCTION_GROUP_ID,
                    f"{EMOJI_ICONS['error']} {update.effective_user.mention_html()}, you're not registered!",
                    parse_mode='HTML'
                )
            return
            
        # Check if banned
        if manager.is_banned:
            try:
                await context.bot.send_message(
                    user_id,
                    f"{EMOJI_ICONS['error']} You are banned from bidding.\nReason: {manager.ban_reason or 'Not specified'}"
                )
            except:
                pass
            return
            
        # Check active auction
        current_auction = await self.db.get_current_auction()
        if not current_auction:
            try:
                await context.bot.send_message(
                    user_id,
                    self.formatter.format_bid_error('no_auction')
                )
            except:
                pass
            return
            
        if current_auction.status != 'active':
            try:
                await context.bot.send_message(
                    user_id,
                    self.formatter.format_bid_error('auction_ended')
                )
            except:
                pass
            return
            
        # Validate bid amount
        if not args:
            help_msg = f"""
{EMOJI_ICONS['info']} <b>HOW TO BID</b>

Current bid: {self.formatter.format_currency(current_auction.current_bid)}
Your balance: {self.formatter.format_currency(manager.balance)}

<b>Examples:</b>
• /bid 15 (for ₹15M)
• /bid 25.5 (for ₹25.5M)
• /bid 25000000 (for ₹25M)

<b>Quick options:</b>
• /bid +1 (current + 1M)
• /bid +5 (current + 5M)
• /bid max (your max possible)
            """.strip()
            
            try:
                await context.bot.send_message(
                    user_id,
                    help_msg,
                    parse_mode='HTML'
                )
            except:
                pass
            return
            
        # Process bid amount
        bid_amount = await self._process_bid_amount(
            args[0], 
            current_auction.current_bid,
            manager.balance
        )
        
        if not bid_amount:
            try:
                await context.bot.send_message(
                    user_id,
                    f"{EMOJI_ICONS['error']} Invalid bid amount!\n\n{self._get_bid_help()}"
                )
            except:
                pass
            return
            
        # Validate bid
        is_valid, error_msg, validated_amount = self.validator.validate_bid_amount(
            str(bid_amount),
            current_auction.current_bid,
            manager.balance,
            current_auction.base_price
        )
        
        if not is_valid:
            try:
                await context.bot.send_message(
                    user_id,
                    self.formatter.format_bid_error('invalid_amount', error_msg),
                    parse_mode='HTML'
                )
            except:
                pass
            return
            
        # Process the bid
        await self._process_bid(update, context, current_auction, manager, validated_amount)
        
    async def _process_bid_amount(self, amount_str: str, current_bid: int, balance: int) -> Optional[int]:
        """Process bid amount string with special options"""
        amount_str = amount_str.lower().strip()
        
        # Handle special cases
        if amount_str.startswith('+'):
            # Increment bid
            try:
                increment = float(amount_str[1:]) * 1_000_000
                return int(current_bid + increment)
            except:
                return None
                
        elif amount_str == 'max':
            # Maximum possible bid
            return min(balance, current_bid + MAX_STRAIGHT_BID)
            
        else:
            # Regular amount
            try:
                # Handle decimal millions
                if '.' in amount_str:
                    return int(float(amount_str) * 1_000_000)
                else:
                    amount = int(amount_str)
                    # Auto-detect if in millions
                    if amount <= 999:
                        return amount * 1_000_000
                    return amount
            except:
                return None
                
    async def _check_bid_cooldown(self, user_id: int) -> bool:
        """Check if user is in bid cooldown"""
        if not FLOOD_CONTROL_ENABLED:
            return False
            
        now = datetime.now()
        if user_id in self.bid_cooldowns:
            last_bid = self.bid_cooldowns[user_id]
            if (now - last_bid).seconds < MESSAGE_COOLDOWN:
                return True
                
        self.bid_cooldowns[user_id] = now
        return False
        
    async def _process_bid(self, update, context, auction, manager, bid_amount):
        """Process a valid bid with timer reset"""
        try:
            # Create bid object
            bid = Bid(
                auction_id=auction._id,
                user_id=manager.user_id,
                amount=bid_amount,
                bid_type='manual'
            )
            
            # Update auction in database
            await self.db.update_auction_bid(auction._id, bid)
            
            # Update manager name if needed
            user_name = update.effective_user.full_name or update.effective_user.first_name
            if manager.name != user_name:
                await self.db.managers.update_one(
                    {"user_id": manager.user_id},
                    {"$set": {"name": user_name}}
                )
                manager.name = user_name
            
            # Notify admin handlers to reset timer AND update display
            if self.admin_handlers:
                await self.admin_handlers.handle_new_bid(auction._id, manager.user_id, bid_amount, context)
            
            # Create bid announcement
            bid_msg = f"""
{EMOJI_ICONS['chart_up']} <b>NEW BID!</b>

{EMOJI_ICONS['user']} {manager.name} bid {self.formatter.format_currency(bid_amount)}!
            """.strip()
            
            # Send brief bid notification
            try:
                notification = await context.bot.send_message(
                    AUCTION_GROUP_ID,
                    bid_msg,
                    parse_mode='HTML'
                )
                # Delete after 3 seconds
                asyncio.create_task(self._delete_message_after(notification, 3))
            except:
                pass
            
            # Send private confirmation
            new_balance = manager.balance - bid_amount
            confirmation = f"""
{EMOJI_ICONS['success']} <b>BID PLACED!</b>

{EMOJI_ICONS['player']} <b>Player:</b> {auction.player_name}
{EMOJI_ICONS['bid']} <b>Your Bid:</b> {self.formatter.format_currency(bid_amount)}
{EMOJI_ICONS['money']} <b>If Won:</b> {self.formatter.format_currency(new_balance)} balance

{EMOJI_ICONS['fire']} You're the highest bidder!
            """.strip()
            
            try:
                await context.bot.send_message(
                    manager.user_id,
                    confirmation,
                    parse_mode='HTML'
                )
            except:
                pass
            
            # Notify previous bidder
            await self._notify_outbid_user(context, auction, manager, bid_amount)
            
        except Exception as e:
            logger.error(f"Error processing bid: {e}")
            try:
                await context.bot.send_message(
                    manager.user_id,
                    f"{EMOJI_ICONS['error']} Error placing bid. Please try again."
                )
            except:
                pass

    async def _delete_message_after(self, message, seconds):
        """Delete message after delay"""
        await asyncio.sleep(seconds)
        try:
            await message.delete()
        except:
            pass
                
    def _create_quick_bid_buttons(self, current_bid: int, auction_id: ObjectId) -> List[List[InlineKeyboardButton]]:
        """Create enhanced quick bid buttons with proper increment rules"""
        buttons = []
        
        if current_bid == 0:
            # Base price button handled by auction message
            return buttons
        elif current_bid < 20_000_000:
            # Only show +1M button
            new_amount = current_bid + 1_000_000
            button_text = f"{EMOJI_ICONS['bid']} Bid {new_amount // 1_000_000}M"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"qbid_{auction_id}_{new_amount}")])
        else:
            # Dynamic increments based on current bid
            if current_bid < 50_000_000:
                increments = [1_000_000, 2_000_000, 5_000_000]
            elif current_bid < 100_000_000:
                increments = [2_000_000, 5_000_000, 10_000_000]
            else:
                increments = [5_000_000, 10_000_000, 20_000_000]
            
            for increment in increments:
                new_amount = current_bid + increment
                button_text = f"{EMOJI_ICONS['bid']} +{increment // 1_000_000}M ({new_amount // 1_000_000}M)"
                buttons.append([InlineKeyboardButton(button_text, callback_data=f"qbid_{auction_id}_{new_amount}")])
        
        return buttons
        
    async def _notify_outbid_user(self, context, auction, new_leader, new_bid):
        """Notify outbid user with enhanced message"""
        if not auction.bids or len(auction.bids) < 2:
            return
            
        previous_bid = auction.bids[-2]
        if previous_bid.user_id == new_leader.user_id:
            return
            
        previous_manager = await self.db.get_manager(previous_bid.user_id)
        if not previous_manager:
            return
            
        # Create notification
        await self.db.create_notification(
            previous_bid.user_id,
            'outbid',
            f"{EMOJI_ICONS['warning']} Outbid Alert!",
            f"You've been outbid on {auction.player_name}",
            {
                'player': auction.player_name,
                'new_bid': new_bid,
                'bidder': new_leader.name
            }
        )
        
        # Send DM if enabled
        if ENABLE_DM_NOTIFICATIONS and NOTIFICATION_TYPES['outbid']:
            outbid_msg = f"""
{EMOJI_ICONS['warning']} <b>YOU'VE BEEN OUTBID!</b>

{EMOJI_ICONS['player']} <b>Player:</b> {auction.player_name}
{EMOJI_ICONS['chart_up']} <b>New Bid:</b> {self.formatter.format_currency(new_bid)}
{EMOJI_ICONS['user']} <b>By:</b> {new_leader.name}

{EMOJI_ICONS['target']} <b>Your Options:</b>
• Place a higher bid to reclaim
• Let this one go and save funds
• Check your balance: /balance

{EMOJI_ICONS['lightning']} <i>Act fast before time runs out!</i>
            """.strip()
            
            keyboard = [[
                InlineKeyboardButton(
                    f"{EMOJI_ICONS['rocket']} Go to Auction",
                    url=f"https://t.me/c/{str(AUCTION_GROUP_ID)[4:] if AUCTION_GROUP_ID else 'unknown'}"
                )
            ]]
            
            try:
                await context.bot.send_message(
                    previous_bid.user_id,
                    outbid_msg,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except:
                pass
                
    async def check_balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command with visual enhancements"""
        user_id = update.effective_user.id
        manager = await self.db.get_manager(user_id)
        
        if not manager:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} You are not registered as a manager!\n\n"
                f"Contact an admin to get registered."
            )
            return
            
        # Create visual balance card
        balance_msg = await self._create_balance_card(manager)
        
        # Action buttons
        keyboard = [
            [
                InlineKeyboardButton(f"{EMOJI_ICONS['team']} My Team", callback_data="my_team"),
                InlineKeyboardButton(f"{EMOJI_ICONS['chart']} My Stats", callback_data="my_stats")
            ],
            [
                InlineKeyboardButton(f"{EMOJI_ICONS['trophy']} Achievements", callback_data="achievements"),
                InlineKeyboardButton(f"{EMOJI_ICONS['target']} Active Auction", callback_data="active_auctions")
            ],
            [InlineKeyboardButton(f"{EMOJI_ICONS['loading']} Refresh", callback_data="refresh_balance")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            balance_msg,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
    async def _create_balance_card(self, manager: Manager) -> str:
        """Create visual balance card"""
        # Calculate spending rate
        if manager.statistics.get('auctions_participated', 0) > 0:
            avg_spend = manager.total_spent // manager.statistics['auctions_participated']
        else:
            avg_spend = 0
            
        # Get current balance setting
        current_default = await self.db.get_setting("default_balance") or DEFAULT_BALANCE
            
        # Create balance bar
        balance_percentage = (manager.balance / current_default) * 100
        balance_bar = self.formatter.create_progress_bar(balance_percentage, 10)
        
        # Calculate level and progress
        level, points_in_level, points_for_next = self.validator.calculate_manager_level(
            manager.statistics.get('points', 0)
        )
        
        card = f"""
{EMOJI_ICONS['money']} <b>BALANCE OVERVIEW</b>

{EMOJI_ICONS['user']} <b>Manager:</b> {manager.name}
{EMOJI_ICONS['gem']} <b>Level:</b> {level}
{EMOJI_ICONS['star']} <b>Points:</b> {manager.statistics.get('points', 0)}

{EMOJI_ICONS['money']} <b>Current Balance:</b>
{self.formatter.format_currency(manager.balance)}
{balance_bar} {balance_percentage:.0f}%

{EMOJI_ICONS['chart_up']} <b>Spending Stats:</b>
• Total Spent: {self.formatter.format_currency(manager.total_spent)}
• Players Bought: {len(manager.players)}
• Avg per Player: {self.formatter.format_currency(avg_spend)}

{EMOJI_ICONS['lightning']} <b>Quick Stats:</b>
• Win Rate: {self._calculate_win_rate(manager):.1f}%
• Total Bids: {manager.statistics.get('total_bids', 0)}
• Highest Bid: {self.formatter.format_currency(manager.statistics.get('highest_bid', 0))}
        """.strip()
        
        return card
        
    def _calculate_win_rate(self, manager: Manager) -> float:
        """Calculate manager's win rate"""
        total_bids = manager.statistics.get('total_bids', 0)
        auctions_won = manager.statistics.get('auctions_won', 0)
        
        if total_bids == 0:
            return 0.0
        return (auctions_won / total_bids) * 100
        
    async def show_my_team(self, query, context, manager: Optional[Manager] = None):
        """Show user's team - fixed version"""
        user_id = query.from_user.id
        
        if not manager:
            manager = await self.db.get_manager(user_id)
        
        if not manager:
            await query.answer("You are not registered!", show_alert=True)
            return
        
        # Create team display
        if not manager.players:
            team_msg = f"""
    {EMOJI_ICONS['team']} <b>MY TEAM</b>

    {EMOJI_ICONS['info']} You haven't bought any players yet!

    Start bidding in auctions to build your dream team.

    {EMOJI_ICONS['target']} <b>Tips:</b>
    - Focus on key positions first
    - Balance your spending
    - Watch for bargain deals
            """.strip()
        else:
            # Get team rating
            team_rating = self._calculate_team_rating(manager)
            
            team_msg = f"""
    {EMOJI_ICONS['team']} <b>MY TEAM</b>

    {EMOJI_ICONS['user']} <b>Manager:</b> {manager.name}
    {EMOJI_ICONS['player']} <b>Squad Size:</b> {len(manager.players)}
    {EMOJI_ICONS['star']} <b>Team Rating:</b> {team_rating}★

    {EMOJI_ICONS['trophy']} <b>Players:</b>
            """.strip()
            
            # Show all players with proper formatting
            for i, player in enumerate(manager.players, 1):
                if isinstance(player, dict):
                    # If player is stored as dict with details
                    player_name = player.get('name', 'Unknown')
                    player_price = player.get('price', 0)
                    team_msg += f"\n{i}. {player_name} - {self.formatter.format_currency(player_price)}"
                else:
                    # If player is stored as string
                    team_msg += f"\n{i}. {player}"
        
        keyboard = [
            [
                InlineKeyboardButton(f"{EMOJI_ICONS['money']} Balance", callback_data="check_balance"),
                InlineKeyboardButton(f"{EMOJI_ICONS['chart']} Stats", callback_data="my_stats")
            ],
            [InlineKeyboardButton(f"{EMOJI_ICONS['loading']} Refresh", callback_data="my_team")]
        ]
        
        try:
            await query.edit_message_text(
                team_msg,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing team: {e}")
            await query.answer("Error displaying team. Please try again.", show_alert=True)
            
    def _calculate_team_rating(self, manager: Manager) -> float:
        """Calculate team rating based on spending and player count"""
        if not manager.players:
            return 0.0
            
        avg_price = manager.total_spent / len(manager.players)
        base_rating = 3.0
        
        # Rating based on average player price
        if avg_price > 50_000_000:
            price_rating = 5.0
        elif avg_price > 30_000_000:
            price_rating = 4.5
        elif avg_price > 20_000_000:
            price_rating = 4.0
        elif avg_price > 10_000_000:
            price_rating = 3.5
        else:
            price_rating = 3.0
            
        # No bonus for team completion anymore
        return min(5.0, price_rating)
            
    async def show_detailed_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed user statistics"""
        user_id = update.effective_user.id
        manager = await self.db.get_manager(user_id)
        
        if not manager:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} You are not registered!"
            )
            return
            
        # Get analytics
        analytics = await self.db.get_user_analytics(user_id, days=7)
        
        # Calculate additional stats
        level, points_in_level, points_for_next = self.validator.calculate_manager_level(
            manager.statistics.get('points', 0)
        )
        
        win_rate = self._calculate_win_rate(manager)
        
        stats_msg = f"""
{EMOJI_ICONS['chart']} <b>DETAILED STATISTICS</b>

{EMOJI_ICONS['user']} <b>Manager:</b> {manager.name}
{EMOJI_ICONS['calendar']} <b>Joined:</b> {manager.created_at.strftime('%d %b %Y')}
{EMOJI_ICONS['gem']} <b>Level:</b> {level} ({points_in_level}/{points_for_next} to next)

{EMOJI_ICONS['trophy']} <b>Auction Performance:</b>
• Total Bids: {manager.statistics.get('total_bids', 0)}
• Auctions Won: {manager.statistics.get('auctions_won', 0)}
• Win Rate: {win_rate:.1f}%
• Highest Bid: {self.formatter.format_currency(manager.statistics.get('highest_bid', 0))}

{EMOJI_ICONS['money']} <b>Financial Summary:</b>
• Current Balance: {self.formatter.format_currency(manager.balance)}
• Total Spent: {self.formatter.format_currency(manager.total_spent)}
• Average per Player: {self.formatter.format_currency(manager.total_spent // len(manager.players) if manager.players else 0)}

{EMOJI_ICONS['chart_up']} <b>Last 7 Days:</b>
• Bids Placed: {analytics.get('bid_placed', {}).get('count', 0)}
• Players Won: {analytics.get('auction_won', {}).get('count', 0)}

{EMOJI_ICONS['medal']} <b>Progress:</b>
• Achievements: {len(manager.achievements)}/{len(ACHIEVEMENTS)}
• Total Points: {manager.statistics.get('points', 0)}
• Current Rank: {await self._get_user_rank(user_id)}
        """.strip()
        
        keyboard = [
            [
                InlineKeyboardButton(f"{EMOJI_ICONS['trophy']} Achievements", callback_data="achievements"),
                InlineKeyboardButton(f"{EMOJI_ICONS['chart']} Leaderboard", callback_data="leaderboard")
            ],
            [InlineKeyboardButton(f"{EMOJI_ICONS['team']} My Team", callback_data="my_team")]
        ]
        
        await update.message.reply_text(
            stats_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _get_user_rank(self, user_id: int) -> str:
        """Get user's current rank"""
        try:
            leaderboard = await self.db.get_leaderboard(100)  # Get top 100
            for i, manager in enumerate(leaderboard, 1):
                if manager.user_id == user_id:
                    return f"#{i}"
            return "Unranked"
        except:
            return "Unknown"
        
    async def show_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show leaderboard with visual rankings"""
        # Get top managers
        leaderboard = await self.db.get_leaderboard(LEADERBOARD_SIZE)
        
        if not leaderboard:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} No leaderboard data available!"
            )
            return
            
        # Get current user's rank
        user_id = update.effective_user.id
        user_rank = None
        for i, manager in enumerate(leaderboard, 1):
            if manager.user_id == user_id:
                user_rank = i
                break
                
        leaderboard_msg = f"""
{EMOJI_ICONS['trophy']} <b>TOP MANAGERS LEADERBOARD</b>

{self._create_leaderboard_display(leaderboard)}

{EMOJI_ICONS['info']} <i>Rankings based on total points earned</i>
        """.strip()
        
        if user_rank:
            leaderboard_msg += f"\n\n{EMOJI_ICONS['star']} Your Rank: #{user_rank}"
        elif user_id:
            leaderboard_msg += f"\n\n{EMOJI_ICONS['info']} You're not in top {LEADERBOARD_SIZE}"
            
        keyboard = [
            [
                InlineKeyboardButton(f"{EMOJI_ICONS['chart']} My Stats", callback_data="my_stats"),
                InlineKeyboardButton(f"{EMOJI_ICONS['loading']} Refresh", callback_data="leaderboard")
            ]
        ]
        
        await update.message.reply_text(
            leaderboard_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    def _create_leaderboard_display(self, managers: List[Manager]) -> str:
        """Create visual leaderboard display"""
        display = ""
        
        for i, manager in enumerate(managers, 1):
            # Get rank emoji
            if i <= len(LEADERBOARD_EMOJIS):
                rank_emoji = LEADERBOARD_EMOJIS[i-1]
            else:
                rank_emoji = f"{i}."
                
            # Format entry
            points = manager.statistics.get('points', 0)
            wins = manager.statistics.get('auctions_won', 0)
            balance = self.formatter.format_currency(manager.balance)
            
            display += f"\n{rank_emoji} <b>{manager.name}</b>"
            display += f"\n    {EMOJI_ICONS['star']} {points} pts | {EMOJI_ICONS['trophy']} {wins} wins | {EMOJI_ICONS['money']} {balance}"
            
            # Add special badge for top 3
            if i == 1:
                display += f" {EMOJI_ICONS['crown']}"
            elif i <= 3:
                display += f" {EMOJI_ICONS['sparkles']}"
                
        return display
        
    async def show_achievements(self, update, context, manager: Optional[Manager] = None):
        """Show user achievements with progress"""
        query = update.callback_query if hasattr(update, 'callback_query') else None
        user_id = query.from_user.id if query else update.effective_user.id
        
        if not manager:
            manager = await self.db.get_manager(user_id)
            
        if not manager:
            text = f"{EMOJI_ICONS['error']} You are not registered!"
            if query:
                await query.answer(text, show_alert=True)
            else:
                await update.message.reply_text(text)
            return
            
        # Calculate completion percentage
        total_achievements = len(ACHIEVEMENTS)
        unlocked_count = len(manager.achievements)
        completion_percentage = (unlocked_count / total_achievements) * 100
        
        # Get achievement progress
        achievements_msg = f"""
{EMOJI_ICONS['medal']} <b>ACHIEVEMENTS</b>

{EMOJI_ICONS['star']} Progress: {unlocked_count}/{total_achievements} ({completion_percentage:.0f}%)
{self.formatter.create_progress_bar(completion_percentage, 10)}

{EMOJI_ICONS['chart']} <b>Total Points Earned:</b> {sum(ACHIEVEMENTS[ach]['points'] for ach in manager.achievements)}
        """.strip()
        
        # Show achievements by category
        unlocked_achievements = []
        locked_achievements = []
        
        for ach_id, ach_data in ACHIEVEMENTS.items():
            if ach_id in manager.achievements:
                unlocked_achievements.append((ach_id, ach_data))
            else:
                locked_achievements.append((ach_id, ach_data))
        
        # Show unlocked achievements first
        if unlocked_achievements:
            achievements_msg += f"\n\n{EMOJI_ICONS['trophy']} <b>UNLOCKED:</b>"
            for ach_id, ach_data in unlocked_achievements:
                achievements_msg += f"\n{ach_data['emoji']} <b>{ach_data['name']}</b> (+{ach_data['points']} pts)"
        
        # Show locked achievements
        if locked_achievements:
            achievements_msg += f"\n\n{EMOJI_ICONS['lock']} <b>LOCKED:</b>"
            for ach_id, ach_data in locked_achievements[:3]:  # Show first 3 locked
                achievements_msg += f"\n🔒 <b>{ach_data['name']}</b>"
                achievements_msg += f"\n<i>{self._get_achievement_hint(ach_id, manager)}</i>"
                
        keyboard = [[
            InlineKeyboardButton(f"{EMOJI_ICONS['chart']} Stats", callback_data="my_stats"),
            InlineKeyboardButton(f"{EMOJI_ICONS['trophy']} Leaderboard", callback_data="leaderboard")
        ]]
        
        if query:
            await query.edit_message_text(
                achievements_msg,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                achievements_msg,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    def _get_achievement_hint(self, achievement_id: str, manager: Manager) -> str:
        """Get hint for locked achievement with progress"""
        hints = {
            'first_bid': "Place your first bid in any auction",
            'win_auction': "Win your first auction",
            'bid_warrior': f"Win 10 auctions (Current: {manager.statistics.get('auctions_won', 0)}/10)",
            'big_spender': f"Spend over 100M total (Current: {self.formatter.format_currency(manager.total_spent)})",
            'perfect_team': f"Build a team with many players (Current: {len(manager.players)})",
            'auction_master': f"Win 50 auctions (Current: {manager.statistics.get('auctions_won', 0)}/50)",
            'speed_bidder': "Place 5 bids within 1 minute",
            'bargain_hunter': "Win 5 players at their base price",
            'millionaire': f"Maintain 100M+ balance (Current: {self.formatter.format_currency(manager.balance)})",
            'comeback_king': "Win after being outbid 10 times in a row"
        }
        return hints.get(achievement_id, "Keep playing to unlock!")
        
    async def handle_quick_bid(self, query, context, auction_id: str, amount: int):
        """Handle quick bid button press"""
        user_id = query.from_user.id
        
        # Anti-spam check
        if await self._check_bid_cooldown(user_id):
            await query.answer(
                f"{EMOJI_ICONS['warning']} Please wait before bidding again!",
                show_alert=True
            )
            return
            
        # Get manager
        manager = await self.db.get_manager(user_id)
        if not manager:
            await query.answer(
                f"{EMOJI_ICONS['error']} You're not registered!",
                show_alert=True
            )
            return
            
        # Check if banned
        if manager.is_banned:
            await query.answer(
                f"{EMOJI_ICONS['error']} You are banned from bidding!",
                show_alert=True
            )
            return
            
        # Get current auction
        current_auction = await self.db.get_current_auction()
        if not current_auction or str(current_auction._id) != auction_id:
            await query.answer(
                f"{EMOJI_ICONS['error']} This auction has ended!",
                show_alert=True
            )
            return
            
        # Validate amount is still valid
        if amount <= current_auction.current_bid:
            await query.answer(
                f"{EMOJI_ICONS['warning']} Someone already bid higher!",
                show_alert=True
            )
            return
            
        # Validate balance
        if amount > manager.balance:
            await query.answer(
                f"{EMOJI_ICONS['error']} Insufficient balance! You have {manager.balance // 1_000_000}M",
                show_alert=True
            )
            return
            
        # Process quick bid
        try:
            bid = Bid(
                auction_id=current_auction._id,
                user_id=user_id,
                amount=amount,
                bid_type='quick'
            )
            
            await self.db.update_auction_bid(current_auction._id, bid)
            
            # Notify admin handlers to reset timer
            if self.admin_handlers:
                await self.admin_handlers.handle_new_bid(current_auction._id, user_id, amount, context)
            
            # Answer callback
            await query.answer(
                f"{EMOJI_ICONS['success']} Bid placed: {self.formatter.format_currency(amount)}!"
            )
            
            # Send quick confirmation animation/sticker
            try:
                await context.bot.send_sticker(
                    AUCTION_GROUP_ID,
                    sticker="CAACAgIAAxkBAAEBPQRhXoX5AAF5kgABQKN5AAH5yQ8AAgMAA8A2TxP5al-2ZdafVyEE"  # Success sticker
                )
            except:
                pass
                
            # Send confirmation to bidder
            if ENABLE_DM_NOTIFICATIONS:
                try:
                    await context.bot.send_message(
                        user_id,
                        f"{EMOJI_ICONS['rocket']} Quick bid successful!\n"
                        f"Amount: {self.formatter.format_currency(amount)}",
                        parse_mode='HTML'
                    )
                except:
                    pass
                    
            # Notify outbid user
            await self._notify_outbid_user(context, current_auction, manager, amount)
            
        except Exception as e:
            logger.error(f"Error in quick bid: {e}")
            await query.answer(
                f"{EMOJI_ICONS['error']} Error placing bid!",
                show_alert=True
            )
            
    def _get_bid_help(self) -> str:
        """Get bid help message"""
        return f"""
{EMOJI_ICONS['info']} <b>Valid formats:</b>
• Numbers: 15, 25, 50
• Decimals: 15.5, 22.3
• Increments: +1, +5, +10
• Maximum: max

{EMOJI_ICONS['tip']} <b>Tips:</b>
• All amounts are in millions (M)
• Minimum increment: 1M
• Check your balance first
        """.strip()