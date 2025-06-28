# handlers/callback_handlers.py - Complete Callback Query Handling
import logging
from datetime import datetime, timedelta
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from bson import ObjectId
from config.settings import *
from database.models import Manager, Player
from utilities.formatters import MessageFormatter

logger = logging.getLogger(__name__)

class CallbackHandlers:
    def __init__(self, db, bot, admin_handlers, user_handlers):
        self.db = db
        self.bot = bot
        self.admin_handlers = admin_handlers
        self.user_handlers = user_handlers
        self.formatter = MessageFormatter()
        
    async def handle_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Main callback query router"""
        await query.answer()
        data = query.data
        user_id = query.from_user.id
        
        logger.info(f"Callback: {data} from user {user_id}")
        
        try:
            # Admin callbacks
            if data == "admin_settings":
                await self._handle_admin_settings(query, context)
            elif data == "admin_dashboard":
                await self._handle_admin_dashboard(query, context)
            elif data == "start_auction_menu":
                await self._handle_start_auction_menu(query, context)
            elif data.startswith("auction_from_"):
                await self._handle_auction_source(query, context, data)
            elif data == "admin_groups":
                await self._handle_admin_groups(query, context)
            elif data == "admin_broadcast":
                await self._handle_admin_broadcast_menu(query, context)
            elif data == "view_managers":
                await self._handle_view_managers(query, context)
            elif data == "view_analytics":
                await self._handle_view_analytics(query, context)
                
            # Settings callbacks
            elif data.startswith("settings_"):
                await self._handle_settings(query, context, data)
            elif data.startswith("timer_set_"):
                await self._handle_timer_setting(query, context, data)
            elif data.startswith("mode_set_"):
                await self._handle_mode_setting(query, context, data)
            elif data.startswith("budget_set_"):
                await self._handle_budget_setting(query, context, data)
            elif data == "analytics_toggle":
                await self._handle_analytics_toggle(query, context)
            elif data.startswith("notification_"):
                await self._handle_notification_setting(query, context, data)
            elif data.startswith("session_"):
                await self._handle_session_action(query, context, data)
                
            # Manager management
            elif data == "add_manager_menu":
                await self._handle_add_manager_menu(query, context)
            elif data == "reset_balances":
                await self._handle_reset_balances_confirm(query, context)
            elif data == "confirm_reset_balances":
                await self._handle_reset_balances(query, context)
            elif data == "ban_manager_menu":
                await self._handle_ban_manager_menu(query, context)
            elif data == "remove_all_managers":
                await self._handle_remove_all_managers_confirm(query, context)
            elif data == "confirm_remove_all":
                await self._handle_remove_all_managers(query, context)
            elif data.startswith("ban_manager_"):
                await self._handle_ban_specific_manager(query, context, data)
            elif data.startswith("unban_manager_"):
                await self._handle_unban_manager(query, context, data)
            elif data.startswith("remove_manager_"):
                await self._handle_remove_manager(query, context, data)
                
            # User callbacks
            elif data == "check_balance":
                await self._handle_check_balance(query, context)
            elif data == "my_team":
                await self._handle_my_team(query, context)
            elif data == "my_stats":
                await self._handle_my_stats(query, context)
            elif data == "achievements":
                await self._handle_achievements(query, context)
            elif data == "leaderboard":
                await self._handle_leaderboard(query, context)
            elif data == "active_auctions":
                await self._handle_active_auctions(query, context)
            elif data == "refresh_balance":
                await self._handle_check_balance(query, context)
                
            # Quick bid callbacks
            elif data.startswith("qbid_"):
                await self._handle_quick_bid(query, context, data)
            elif data.startswith("auction_stats_"):
                await self._handle_auction_stats(query, context, data)
            elif data.startswith("watch_auction_"):
                await self._handle_watch_auction(query, context, data)
                
            # Help callbacks
            elif data.endswith("_help"):
                await self._handle_help_section(query, context, data)
                
            # General callbacks
            elif data == "start":
                await self._handle_start(query, context)
            elif data == "cancel" or data == "cancel_operation":
                await query.edit_message_text(f"{EMOJI_ICONS['info']} Operation cancelled.")
            elif data == "request_access":
                await self._handle_request_access(query, context)
            elif data == "about_bot":
                await self._handle_about(query, context)
            elif data == "game_mode":
                await self._handle_game_mode(query, context)
                
            # Group management
            elif data.startswith("manage_group_"):
                await self._handle_manage_group(query, context, data)
            elif data.startswith("set_data_group_"):
                await self._handle_set_group_type(query, context, data, "data")
            elif data.startswith("set_unsold_group_"):
                await self._handle_set_group_type(query, context, data, "unsold")
                
        except Exception as e:
            logger.error(f"Error handling callback {data}: {e}")
            await query.answer(
                f"{EMOJI_ICONS['error']} An error occurred. Please try again.",
                show_alert=True
            )
            
    # Admin callback handlers
    async def _handle_admin_settings(self, query, context):
        """Handle admin settings callback"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
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
        
        await query.edit_message_text(
            settings_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_admin_dashboard(self, query, context):
        """Show admin dashboard"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        # Get current stats
        current_auction = await self.db.get_current_auction()
        managers = await self.db.get_all_managers()
        session = await self.db.get_current_session()
        groups = await self.db.get_all_groups()
        
        # Get analytics data
        analytics = await self.admin_handlers.analytics.get_auction_analytics(days=7)
        
        dashboard_msg = f"""
{EMOJI_ICONS['chart']} <b>ADMIN DASHBOARD</b>

{EMOJI_ICONS['info']} <b>System Status:</b>
- Bot Status: 🟢 Online
- Mode: {'AUTO' if AUTO_MODE else 'MANUAL'}
- Timer: {AUCTION_TIMER}s

{EMOJI_ICONS['team']} <b>Managers:</b> {len(managers)}
{EMOJI_ICONS['player']} <b>Current Auction:</b> {current_auction.player_name if current_auction else 'None'}
{EMOJI_ICONS['home']} <b>Connected Groups:</b> {len(groups)}

{EMOJI_ICONS['chart_up']} <b>Last 7 Days:</b>
- Total Auctions: {analytics.get('total_auctions', 0)}
- Revenue: {self.formatter.format_currency(analytics.get('total_revenue', 0))}
- Active Bidders: {analytics.get('unique_bidders', 0)}

{EMOJI_ICONS['clock']} <b>Uptime:</b> {self._get_uptime()}
        """.strip()
        
        keyboard = [
            [
                InlineKeyboardButton("🔨 Start Auction", callback_data="start_auction_menu"),
                InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")
            ],
            [
                InlineKeyboardButton("📊 Full Analytics", callback_data="view_analytics"),
                InlineKeyboardButton("👥 Managers", callback_data="view_managers")
            ],
            [
                InlineKeyboardButton("🏢 Groups", callback_data="admin_groups"),
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="start")]
        ]
        
        await query.edit_message_text(
            dashboard_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_start_auction_menu(self, query, context):
        """Handle start auction menu"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        # Check if auction is already running
        current_auction = await self.db.get_current_auction()
        if current_auction:
            await query.answer(
                f"An auction is already running for {current_auction.player_name}!",
                show_alert=True
            )
            return
            
        keyboard = [
            [InlineKeyboardButton("📋 From Data Group", callback_data="auction_from_data")],
            [InlineKeyboardButton("✍️ Manual Entry", callback_data="auction_from_manual")],
            [InlineKeyboardButton("📂 From Saved Players", callback_data="auction_from_saved")],
            [InlineKeyboardButton("❌ Cancel", callback_data="admin_dashboard")]
        ]
        
        msg = f"""
{EMOJI_ICONS['hammer']} <b>START NEW AUCTION</b>

Select auction source:

📋 <b>From Data Group</b> - Start from next player in queue
✍️ <b>Manual Entry</b> - Enter player details manually
📂 <b>From Saved</b> - Select from database

Current Mode: <b>{('AUTO' if AUTO_MODE else 'MANUAL')}</b>
Timer: <b>{AUCTION_TIMER}s</b>
        """.strip()
        
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
    async def _handle_auction_source(self, query, context, data):
        """Handle auction source selection"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        source = data.replace("auction_from_", "")
        
        if source == "data":
            # Get next player from data group
            players = await self.db.get_available_players()
            if not players:
                await query.answer("No players available in data group!", show_alert=True)
                return
                
            # Start auction with first player
            player = players[0]
            success = await self.admin_handlers._create_auction_from_player(query, context, player)
            
            if success:
                await query.answer("Auction started successfully!", show_alert=True)
            else:
                await query.answer("Failed to start auction!", show_alert=True)
                
        elif source == "manual":
            await query.edit_message_text(
                f"{EMOJI_ICONS['info']} Manual auction entry feature will be available soon!\n\n"
                f"For now, use the data group method or /start_auction command."
            )
            
        elif source == "saved":
            await query.edit_message_text(
                f"{EMOJI_ICONS['info']} Saved players feature will be available soon!\n\n"
                f"For now, use the data group method."
            )
            
    async def _handle_admin_groups(self, query, context):
        """Handle group management"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        groups = await self.db.get_all_groups()
        
        msg = f"""
{EMOJI_ICONS['home']} <b>GROUP MANAGEMENT</b>

Connected Groups: {len(groups)}

{EMOJI_ICONS['info']} <b>Current Groups:</b>
        """.strip()
        
        keyboard = []
        
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
                
        keyboard.extend([
            [InlineKeyboardButton("🔍 Find Group ID", callback_data="find_group_id")],
            [InlineKeyboardButton("📋 All Groups", callback_data="list_all_groups")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_dashboard")]
        ])
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_admin_broadcast_menu(self, query, context):
        """Handle broadcast menu"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        keyboard = [
            [InlineKeyboardButton("📢 Create Broadcast", callback_data="create_broadcast")],
            [InlineKeyboardButton("📋 Broadcast History", callback_data="broadcast_history")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_dashboard")]
        ]
        
        managers_count = len(await self.db.get_all_managers())
        
        msg = f"""
{EMOJI_ICONS['loudspeaker']} <b>BROADCAST CENTER</b>

Create and manage broadcasts to all managers.

{EMOJI_ICONS['team']} <b>Target Audience:</b> {managers_count} managers

{EMOJI_ICONS['info']} <b>Supported Content:</b>
• Text messages
• Images with captions
• Videos with captions
• Documents with captions
        """.strip()
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_view_managers(self, query, context):
        """View all managers"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        managers = await self.db.get_all_managers()
        
        if not managers:
            await query.edit_message_text(
                f"{EMOJI_ICONS['error']} No managers found!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="admin_dashboard")
                ]])
            )
            return
            
        # Show manager list with pagination
        managers_msg = self.formatter.format_managers_list(managers[:10])  # Show first 10
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back", callback_data="admin_dashboard")],
            [InlineKeyboardButton("⚙️ Manage", callback_data="settings_managers")]
        ]
        
        await query.edit_message_text(
            managers_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_view_analytics(self, query, context):
        """View analytics dashboard"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        # Get analytics data
        analytics = await self.admin_handlers.analytics.get_auction_analytics(days=7)
        
        analytics_msg = f"""
{EMOJI_ICONS['chart']} <b>ANALYTICS DASHBOARD</b>

{EMOJI_ICONS['calendar']} <b>Last 7 Days:</b>

📊 <b>Auction Performance:</b>
• Total Auctions: {analytics.get('total_auctions', 0)}
• Sold Players: {analytics.get('sold_count', 0)}
• Sell Rate: {analytics.get('sell_rate', 0):.1f}%

💰 <b>Financial:</b>
• Total Revenue: {self.formatter.format_currency(analytics.get('total_revenue', 0))}
• Avg Sale Price: {self.formatter.format_currency(analytics.get('avg_sale_price', 0))}

👥 <b>Engagement:</b>
• Total Bids: {analytics.get('total_bids', 0)}
• Unique Bidders: {analytics.get('unique_bidders', 0)}
• Avg Bids/Auction: {analytics.get('avg_bids_per_auction', 0):.1f}

⏰ <b>Peak Hours:</b>
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
            [InlineKeyboardButton("🔙 Back", callback_data="admin_dashboard")]
        ]
        
        await query.edit_message_text(
            analytics_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    # Settings callback handlers
    async def _handle_settings(self, query, context, data):
        """Handle settings callbacks"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        setting = data.replace("settings_", "")
        
        if setting == "managers":
            await self._show_manager_settings(query, context)
        elif setting == "timer":
            await self._show_timer_settings(query, context)
        elif setting == "mode":
            await self._show_mode_settings(query, context)
        elif setting == "budget":
            await self._show_budget_settings(query, context)
        elif setting == "analytics":
            await self._show_analytics_settings(query, context)
        elif setting == "notifications":
            await self._show_notification_settings(query, context)
        elif setting == "session":
            await self._show_session_settings(query, context)
        elif setting == "groups":
            await self._handle_admin_groups(query, context)
            
    async def _show_manager_settings(self, query, context):
        """Show manager management settings"""
        managers = await self.db.get_all_managers()
        banned_count = len([m for m in managers if m.is_banned])
        
        msg = f"""
{EMOJI_ICONS['team']} <b>MANAGER SETTINGS</b>

Total Managers: {len(managers)}
Banned: {banned_count}

{EMOJI_ICONS['info']} <b>Points System:</b>
Points are earned through:
• Placing bids: +1 point
• Winning auctions: +10 points
• Achievements: Variable points
• Daily participation: +5 points

Points determine manager levels and unlock achievements.

Select an action:
        """.strip()
        
        keyboard = [
            [InlineKeyboardButton("➕ Add Manager", callback_data="add_manager_menu")],
            [InlineKeyboardButton("📋 List Managers", callback_data="view_managers")],
            [InlineKeyboardButton("🔄 Reset Balances", callback_data="reset_balances")],
            [InlineKeyboardButton("🚫 Ban Manager", callback_data="ban_manager_menu")],
            [InlineKeyboardButton("🗑️ Remove All", callback_data="remove_all_managers")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_settings")]
        ]
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _show_timer_settings(self, query, context):
        """Show timer settings"""
        current_timer = await self.db.get_setting("auction_timer") or AUCTION_TIMER
        
        msg = f"""
{EMOJI_ICONS['clock']} <b>TIMER SETTINGS</b>

Current Timer: <b>{current_timer} seconds</b>

{EMOJI_ICONS['info']} Timer determines how long auctions run in AUTO mode.

Select a timer duration:
        """.strip()
        
        keyboard = [
            [
                InlineKeyboardButton("30s", callback_data="timer_set_30"),
                InlineKeyboardButton("45s", callback_data="timer_set_45"),
                InlineKeyboardButton("60s", callback_data="timer_set_60")
            ],
            [
                InlineKeyboardButton("90s", callback_data="timer_set_90"),
                InlineKeyboardButton("120s", callback_data="timer_set_120"),
                InlineKeyboardButton("180s", callback_data="timer_set_180")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_settings")]
        ]
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_timer_setting(self, query, context, data):
        """Handle timer setting change"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        timer_value = int(data.replace("timer_set_", ""))
        await self.db.set_setting("auction_timer", timer_value)
        
        # Update global setting
        global AUCTION_TIMER
        AUCTION_TIMER = timer_value
        
        await query.answer(f"✅ Timer set to {timer_value} seconds!", show_alert=True)
        await self._show_timer_settings(query, context)
        
    async def _show_mode_settings(self, query, context):
        """Show auction mode settings"""
        current_mode = await self.db.get_setting("auction_mode") or ("auto" if AUTO_MODE else "manual")
        
        msg = f"""
{EMOJI_ICONS['gear']} <b>AUCTION MODE SETTINGS</b>

Current Mode: <b>{current_mode.upper()}</b>

{EMOJI_ICONS['info']} <b>Mode Descriptions:</b>
- <b>AUTO:</b> Timer automatically ends auction
- <b>MANUAL:</b> Admin manually calls final bid

Select mode:
        """.strip()
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "🤖 Auto Mode" + (" ✅" if current_mode == "auto" else ""), 
                    callback_data="mode_set_auto"
                ),
                InlineKeyboardButton(
                    "👤 Manual Mode" + (" ✅" if current_mode == "manual" else ""), 
                    callback_data="mode_set_manual"
                )
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_settings")]
        ]
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_mode_setting(self, query, context, data):
        """Handle mode setting change"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        mode = data.replace("mode_set_", "")
        await self.db.set_setting("auction_mode", mode)
        
        # Update global setting
        global AUTO_MODE
        AUTO_MODE = (mode == "auto")
        
        await query.answer(f"✅ Mode set to {mode.upper()}!", show_alert=True)
        await self._show_mode_settings(query, context)
        
    async def _show_budget_settings(self, query, context):
        """Show budget settings"""
        current_budget = await self.db.get_setting("default_balance") or DEFAULT_BALANCE
        
        msg = f"""
{EMOJI_ICONS['money']} <b>BUDGET SETTINGS</b>

Current Default Balance: <b>{self.formatter.format_currency(current_budget)}</b>

{EMOJI_ICONS['info']} This is the starting balance for new managers.

Select default starting balance:
        """.strip()
        
        keyboard = [
            [
                InlineKeyboardButton("100M", callback_data="budget_set_100"),
                InlineKeyboardButton("150M", callback_data="budget_set_150"),
                InlineKeyboardButton("200M", callback_data="budget_set_200")
            ],
            [
                InlineKeyboardButton("250M", callback_data="budget_set_250"),
                InlineKeyboardButton("300M", callback_data="budget_set_300"),
                InlineKeyboardButton("500M", callback_data="budget_set_500")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_settings")]
        ]
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_budget_setting(self, query, context, data):
        """Handle budget setting change"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        budget_value = int(data.replace("budget_set_", "")) * 1_000_000
        await self.db.set_setting("default_balance", budget_value)
        
        # Update global setting
        global DEFAULT_BALANCE
        DEFAULT_BALANCE = budget_value
        
        await query.answer(f"✅ Default balance set to {budget_value // 1_000_000}M!", show_alert=True)
        await self._show_budget_settings(query, context)
        
    async def _show_analytics_settings(self, query, context):
        """Show analytics settings"""
        analytics_enabled = await self.db.get_setting("track_analytics")
        if analytics_enabled is None:
            analytics_enabled = TRACK_ANALYTICS
            
        msg = f"""
{EMOJI_ICONS['chart']} <b>ANALYTICS SETTINGS</b>

Analytics Tracking: <b>{'ENABLED' if analytics_enabled else 'DISABLED'}</b>

{EMOJI_ICONS['info']} <b>Analytics Purpose:</b>
Analytics help you understand:
• User behavior patterns and preferences
• Auction performance and engagement
• Peak activity times for scheduling
• Revenue trends and optimization opportunities

{EMOJI_ICONS['warning']} <b>Privacy:</b>
All data is anonymized and used only for improving the auction experience.
        """.strip()
        
        keyboard = [
            [InlineKeyboardButton(
                f"{'🔴 Disable' if analytics_enabled else '🟢 Enable'} Analytics", 
                callback_data="analytics_toggle"
            )],
            [InlineKeyboardButton("📊 View Analytics", callback_data="view_analytics")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_settings")]
        ]
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_analytics_toggle(self, query, context):
        """Toggle analytics on/off"""
        global TRACK_ANALYTICS

        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        current = await self.db.get_setting("track_analytics")
        if current is None:
            current = TRACK_ANALYTICS
            
        new_value = not current
        await self.db.set_setting("track_analytics", new_value)
        
        # Update global setting
        TRACK_ANALYTICS = new_value
        
        await query.answer(
            f"✅ Analytics {'enabled' if new_value else 'disabled'}!", 
            show_alert=True
        )
        await self._show_analytics_settings(query, context)
        
    async def _show_notification_settings(self, query, context):
        """Show notification settings"""
        settings = {
            'auction_start': await self.db.get_setting("notify_auction_start") or True,
            'auction_end': await self.db.get_setting("notify_auction_end") or True,
            'new_bid': await self.db.get_setting("notify_new_bid") or True,
            'achievements': await self.db.get_setting("notify_achievements") or True
        }
        
        msg = f"""
{EMOJI_ICONS['bell']} <b>NOTIFICATION SETTINGS</b>

{EMOJI_ICONS['info']} <b>Notification Purpose:</b>
Notifications keep managers engaged by alerting them about:
• New auctions starting
• When they're outbid
• Achievements they unlock
• Important auction events

{EMOJI_ICONS['gear']} Configure which notifications to send:
        """.strip()
        
        keyboard = []
        notifications_info = {
            'auction_start': 'Auction Start Alerts',
            'auction_end': 'Auction End Notifications', 
            'new_bid': 'Outbid Notifications',
            'achievements': 'Achievement Unlocks'
        }
        
        for key, label in notifications_info.items():
            enabled = settings[key]
            icon = "✅" if enabled else "❌"
            keyboard.append([InlineKeyboardButton(
                f"{icon} {label}", 
                callback_data=f"notification_toggle_{key}"
            )])
            
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_settings")])
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_notification_setting(self, query, context, data):
        """Handle notification toggle"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        if data.startswith("notification_toggle_"):
            key = data.replace("notification_toggle_", "")
            setting_key = f"notify_{key}"
            
            current = await self.db.get_setting(setting_key)
            if current is None:
                current = True
                
            new_value = not current
            await self.db.set_setting(setting_key, new_value)
            
            await query.answer(
                f"✅ {key.replace('_', ' ').title()} notifications {'enabled' if new_value else 'disabled'}!", 
                show_alert=True
            )
            await self._show_notification_settings(query, context)
            
    async def _show_session_settings(self, query, context):
        """Show session settings"""
        current_session = await self.db.get_current_session()
        
        msg = f"""
{EMOJI_ICONS['calendar']} <b>SESSION SETTINGS</b>

{EMOJI_ICONS['info']} <b>Session Purpose:</b>
Sessions help organize and track auction events:
• Group related auctions together
• Generate session-specific reports
• Track performance over time
• Maintain historical records

{EMOJI_ICONS['gear']} <b>Current Session:</b>
        """.strip()
        
        if current_session:
            msg += f"""
- ID: {current_session['session_id']}
- Name: {current_session['name']}
- Status: {current_session['status'].upper()}
- Started: {current_session['start_time'].strftime('%Y-%m-%d %H:%M')}
- Players: {current_session.get('total_players', 0)}
            """
        else:
            msg += "\nNo active session"
            
        keyboard = [
            [InlineKeyboardButton("🆕 New Session", callback_data="session_new")],
            [InlineKeyboardButton("📊 Session Report", callback_data="session_report")]
        ]
        
        if current_session and current_session['status'] == 'active':
            keyboard.append([InlineKeyboardButton("🏁 End Session", callback_data="session_end")])
            
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_settings")])
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_session_action(self, query, context, data):
        """Handle session actions"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        action = data.replace("session_", "")
        
        if action == "new":
            # Create new session
            session_name = f"Auction Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            session_id = await self.db.create_session(session_name)
            
            await query.answer(f"✅ New session created!", show_alert=True)
            await self._show_session_settings(query, context)
            
        elif action == "end":
            # End current session
            current = await self.db.get_current_session()
            if current:
                await self.db.close_session(current['session_id'])
                await query.answer("✅ Session ended!", show_alert=True)
            await self._show_session_settings(query, context)
            
        elif action == "report":
            # Generate session report
            current = await self.db.get_current_session()
            if not current:
                await query.answer("No active session to report on!", show_alert=True)
                return
                
            report = await self.admin_handlers.analytics.generate_session_report(current['session_id'])
            
            report_msg = f"""
{EMOJI_ICONS['chart']} <b>SESSION REPORT</b>

{EMOJI_ICONS['calendar']} Session: {report.get('session_name', 'Unknown')}
{EMOJI_ICONS['clock']} Duration: {report.get('duration', 'Unknown')}

📊 <b>Statistics:</b>
• Total Auctions: {report.get('total_auctions', 0)}
• Sold Players: {report.get('sold_players', 0)}
• Total Revenue: {self.formatter.format_currency(report.get('total_revenue', 0))}
• Active Managers: {report.get('participating_managers', 0)}

{EMOJI_ICONS['trophy']} <b>Top Spender:</b>
            """.strip()
            
            rankings = report.get('manager_rankings', [])
            if rankings:
                top = rankings[0]
                report_msg += f"\n{top['name']} - {self.formatter.format_currency(top['total_spent'])}"
            else:
                report_msg += "\nNo data available"
                
            await query.edit_message_text(
                report_msg,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="settings_session")
                ]])
            )
            
    # Manager management handlers
    async def _handle_add_manager_menu(self, query, context):
        """Handle add manager menu"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        await query.edit_message_text(
            f"{EMOJI_ICONS['info']} <b>ADD MANAGER</b>\n\n"
            f"Use the command /add_manager to add a new manager.\n\n"
            f"This will start an interactive process where you can:\n"
            f"• Enter a user ID\n"
            f"• Enter a @username\n"
            f"• Forward a message from the user\n\n"
            f"Try it now!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="settings_managers")
            ]])
        )
        
    async def _handle_reset_balances_confirm(self, query, context):
        """Show reset balances confirmation"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        managers_count = len(await self.db.get_all_managers())
        current_balance = await self.db.get_setting("default_balance") or DEFAULT_BALANCE
        
        msg = f"""
{EMOJI_ICONS['warning']} <b>RESET ALL BALANCES</b>

This will reset ALL manager balances to {self.formatter.format_currency(current_balance)}.

{EMOJI_ICONS['info']} <b>Affected:</b>
• {managers_count} managers
• All balances will be reset
• Player lists will be cleared
• Spending history will be reset

{EMOJI_ICONS['warning']} <b>This action cannot be undone!</b>

Are you sure?
        """.strip()
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Reset All", callback_data="confirm_reset_balances"),
                InlineKeyboardButton("❌ Cancel", callback_data="settings_managers")
            ]
        ]
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_reset_balances(self, query, context):
        """Reset all manager balances"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        current_balance = await self.db.get_setting("default_balance") or DEFAULT_BALANCE
        await self.db.reset_all_balances(current_balance, query.from_user.id)
        
        await query.answer("✅ All balances reset successfully!", show_alert=True)
        
        await query.edit_message_text(
            f"{EMOJI_ICONS['success']} <b>BALANCES RESET</b>\n\n"
            f"All manager balances have been reset to {self.formatter.format_currency(current_balance)}.\n\n"
            f"All players and spending history have been cleared.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="settings_managers")
            ]])
        )
        
    async def _handle_ban_manager_menu(self, query, context):
        """Show ban manager menu"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        managers = await self.db.get_all_managers()
        active_managers = [m for m in managers if not m.is_banned]
        banned_managers = [m for m in managers if m.is_banned]
        
        msg = f"""
{EMOJI_ICONS['warning']} <b>MANAGER MODERATION</b>

Active Managers: {len(active_managers)}
Banned Managers: {len(banned_managers)}

Select an action:
        """.strip()
        
        keyboard = []
        
        # Show active managers for banning
        if active_managers:
            for manager in active_managers[:5]:  # Show first 5
                keyboard.append([InlineKeyboardButton(
                    f"🚫 Ban {manager.name}",
                    callback_data=f"ban_manager_{manager.user_id}"
                )])
                
        # Show banned managers for unbanning
        if banned_managers:
            msg += f"\n\n{EMOJI_ICONS['info']} <b>Banned Managers:</b>"
            for manager in banned_managers[:3]:  # Show first 3
                msg += f"\n• {manager.name}"
                keyboard.append([InlineKeyboardButton(
                    f"✅ Unban {manager.name}",
                    callback_data=f"unban_manager_{manager.user_id}"
                )])
                
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_managers")])
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_ban_specific_manager(self, query, context, data):
        """Ban specific manager"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        user_id = int(data.replace("ban_manager_", ""))
        manager = await self.db.get_manager(user_id)
        
        if not manager:
            await query.answer("Manager not found!", show_alert=True)
            return
            
        # Ban the manager
        await self.db.ban_manager(user_id, query.from_user.id, "Banned by admin")
        
        await query.answer(f"✅ {manager.name} has been banned!", show_alert=True)
        
        # Notify the banned user
        try:
            await context.bot.send_message(
                user_id,
                f"{EMOJI_ICONS['warning']} <b>Account Suspended</b>\n\n"
                f"Your account has been suspended from participating in auctions.\n"
                f"Contact an admin if you believe this is an error.",
                parse_mode='HTML'
            )
        except:
            pass
            
        await self._handle_ban_manager_menu(query, context)
        
    async def _handle_unban_manager(self, query, context, data):
        """Unban specific manager"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        user_id = int(data.replace("unban_manager_", ""))
        manager = await self.db.get_manager(user_id)
        
        if not manager:
            await query.answer("Manager not found!", show_alert=True)
            return
            
        # Unban the manager
        await self.db.unban_manager(user_id)
        
        await query.answer(f"✅ {manager.name} has been unbanned!", show_alert=True)
        
        # Notify the unbanned user
        try:
            await context.bot.send_message(
                user_id,
                f"{EMOJI_ICONS['success']} <b>Account Restored</b>\n\n"
                f"Your account has been restored. You can now participate in auctions again!",
                parse_mode='HTML'
            )
        except:
            pass
            
        await self._handle_ban_manager_menu(query, context)
        
    async def _handle_remove_all_managers_confirm(self, query, context):
        """Show remove all managers confirmation"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        managers_count = len(await self.db.get_all_managers())
        
        msg = f"""
{EMOJI_ICONS['warning']} <b>REMOVE ALL MANAGERS</b>

{EMOJI_ICONS['error']} <b>DANGER ZONE</b>

This will permanently delete ALL manager accounts:
• {managers_count} managers will be removed
• All balances and data will be lost
• All auction history will remain but be unlinked

{EMOJI_ICONS['warning']} <b>This action CANNOT be undone!</b>

Are you absolutely sure?
        """.strip()
        
        keyboard = [
            [
                InlineKeyboardButton("💀 YES, DELETE ALL", callback_data="confirm_remove_all"),
                InlineKeyboardButton("❌ Cancel", callback_data="settings_managers")
            ]
        ]
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_remove_all_managers(self, query, context):
        """Remove all managers"""
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return
            
        # Remove all managers except admins
        result = await self.db.managers.delete_many({
            "user_id": {"$nin": ADMIN_IDS}
        })
        
        await query.answer(f"✅ Removed {result.deleted_count} managers!", show_alert=True)
        
        await query.edit_message_text(
            f"{EMOJI_ICONS['success']} <b>MANAGERS REMOVED</b>\n\n"
            f"All non-admin managers have been removed.\n"
            f"Deleted: {result.deleted_count} accounts",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="settings_managers")
            ]])
        )
        
    # User callback handlers
    async def _handle_check_balance(self, query, context):
        """Handle balance check callback"""
        manager = await self.db.get_manager(query.from_user.id)
        if not manager:
            await query.answer("You're not registered!", show_alert=True)
            return
            
        balance_msg = await self.user_handlers._create_balance_card(manager)
        
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
        
        await query.edit_message_text(
            balance_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_my_team(self, query, context):
        """Handle my team callback"""
        manager = await self.db.get_manager(query.from_user.id)
        if not manager:
            await query.answer("You're not registered!", show_alert=True)
            return
            
        await self.user_handlers.show_my_team(query, context, manager)
        
    async def _handle_my_stats(self, query, context):
        """Handle my stats callback"""
        manager = await self.db.get_manager(query.from_user.id)
        if not manager:
            await query.answer("You're not registered!", show_alert=True)
            return
            
        # Get analytics
        analytics = await self.db.get_user_analytics(query.from_user.id, days=7)
        
        stats_msg = f"""
{EMOJI_ICONS['chart']} <b>DETAILED STATISTICS</b>

{EMOJI_ICONS['user']} <b>Manager:</b> {manager.name}
{EMOJI_ICONS['calendar']} <b>Joined:</b> {manager.created_at.strftime('%d %b %Y')}

{EMOJI_ICONS['trophy']} <b>Auction Performance:</b>
• Total Bids: {manager.statistics.get('total_bids', 0)}
• Auctions Won: {manager.statistics.get('auctions_won', 0)}
• Win Rate: {manager.statistics.get('win_rate', 0):.1f}%
• Highest Bid: {self.formatter.format_currency(manager.statistics.get('highest_bid', 0))}

{EMOJI_ICONS['chart_up']} <b>Last 7 Days:</b>
• Bids Placed: {analytics.get('bid_placed', {}).get('count', 0)}
• Players Won: {analytics.get('auction_won', {}).get('count', 0)}

{EMOJI_ICONS['medal']} <b>Achievements:</b> {len(manager.achievements)}/{len(ACHIEVEMENTS)}
{EMOJI_ICONS['star']} <b>Total Points:</b> {manager.statistics.get('points', 0)}
{EMOJI_ICONS['gem']} <b>Level:</b> {manager.statistics.get('level', 1)}
        """.strip()
        
        keyboard = [
            [
                InlineKeyboardButton(f"{EMOJI_ICONS['trophy']} Achievements", callback_data="achievements"),
                InlineKeyboardButton(f"{EMOJI_ICONS['chart']} Leaderboard", callback_data="leaderboard")
            ],
            [InlineKeyboardButton(f"{EMOJI_ICONS['team']} My Team", callback_data="my_team")]
        ]
        
        await query.edit_message_text(
            stats_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_achievements(self, query, context):
        """Handle achievements callback"""
        manager = await self.db.get_manager(query.from_user.id)
        if not manager:
            await query.answer("You're not registered!", show_alert=True)
            return
            
        await self.user_handlers.show_achievements(query, context, manager)
        
    async def _handle_leaderboard(self, query, context):
        """Handle leaderboard callback"""
        # Get top managers
        leaderboard = await self.db.get_leaderboard(LEADERBOARD_SIZE)
        
        if not leaderboard:
            await query.edit_message_text(
                f"{EMOJI_ICONS['error']} No leaderboard data available!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="start")
                ]])
            )
            return
            
        # Get current user's rank
        user_id = query.from_user.id
        user_rank = None
        for i, manager in enumerate(leaderboard, 1):
            if manager.user_id == user_id:
                user_rank = i
                break
                
        leaderboard_msg = f"""
{EMOJI_ICONS['trophy']} <b>TOP MANAGERS LEADERBOARD</b>

{self.user_handlers._create_leaderboard_display(leaderboard)}
        """.strip()
        
        if user_rank:
            leaderboard_msg += f"\n\n{EMOJI_ICONS['star']} Your Rank: #{user_rank}"
        else:
            leaderboard_msg += f"\n\n{EMOJI_ICONS['info']} You're not in top {LEADERBOARD_SIZE}"
            
        keyboard = [
            [
                InlineKeyboardButton(f"{EMOJI_ICONS['chart']} My Stats", callback_data="my_stats"),
                InlineKeyboardButton(f"{EMOJI_ICONS['loading']} Refresh", callback_data="leaderboard")
            ]
        ]
        
        await query.edit_message_text(
            leaderboard_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_active_auctions(self, query, context):
        """Handle active auctions callback"""
        current_auction = await self.db.get_current_auction()
        
        if not current_auction:
            await query.edit_message_text(
                f"{EMOJI_ICONS['info']} <b>NO ACTIVE AUCTIONS</b>\n\n"
                f"There are currently no auctions running.\n"
                f"Check back soon for new player auctions!",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="start")
                ]])
            )
            return
            
        auction_msg = self.formatter.format_auction_status(current_auction)
        
        keyboard = [
            [InlineKeyboardButton(f"{EMOJI_ICONS['target']} Go to Auction", 
                                url=f"https://t.me/c/{str(AUCTION_GROUP_ID)[4:]}")],
            [InlineKeyboardButton(f"{EMOJI_ICONS['loading']} Refresh", callback_data="active_auctions")]
        ]
        
        await query.edit_message_text(
            auction_msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_quick_bid(self, query, context, data):
        """Handle quick bid callback"""
        # Parse callback data: qbid_auctionid_amount
        parts = data.split('_')
        if len(parts) != 3:
            await query.answer("Invalid bid data!", show_alert=True)
            return
            
        auction_id = parts[1]
        amount = int(parts[2])
        
        if self.user_handlers:
            await self.user_handlers.handle_quick_bid(query, context, auction_id, amount)
            
    async def _handle_request_access(self, query, context):
        """Handle access request"""
        user_id = query.from_user.id
        user_name = query.from_user.full_name
        username = query.from_user.username
        
        # Check if already registered
        manager = await self.db.get_manager(user_id)
        if manager:
            await query.answer("You're already registered!", show_alert=True)
            return
            
        # Add to join requests
        request_data = {
            'user_id': user_id,
            'user_name': user_name,
            'username': username,
            'chat_id': query.message.chat.id
        }
        
        await self.db.add_join_request(request_data)
        
        await query.edit_message_text(
            f"{EMOJI_ICONS['success']} <b>REQUEST SUBMITTED</b>\n\n"
            f"Your access request has been sent to the admins.\n"
            f"You'll be notified once it's processed.\n\n"
            f"{EMOJI_ICONS['clock']} Please wait for approval.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="start")
            ]])
        )
        
        # Notify admins
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"{EMOJI_ICONS['bell']} <b>NEW ACCESS REQUEST</b>\n\n"
                    f"{EMOJI_ICONS['user']} Name: {user_name}\n"
                    f"{EMOJI_ICONS['id']} ID: <code>{user_id}</code>\n"
                    f"{EMOJI_ICONS['at']} Username: @{username or 'None'}\n\n"
                    f"Use /settings → Managers to approve/reject.",
                    parse_mode='HTML'
                )
            except:
                pass
                
    async def _handle_about(self, query, context):
        """Handle about bot callback"""
        uptime = datetime.now() - query.message.date if hasattr(query.message, 'date') else timedelta(0)
        hours = int(uptime.total_seconds() // 3600)
        minutes = int((uptime.total_seconds() % 3600) // 60)
        
        about_msg = f"""
🤖 <b>EFOOTBALL AUCTION BOT v2.0</b>

<b>🎮 Features:</b>
- Real-time player auctions
- Visual countdown timers
- Advanced analytics
- Team management
- Achievements & rewards
- Live leaderboards

<b>⚡ Performance:</b>
- Response time: <50ms
- 99.9% reliability
- 24/7 availability

<b>👨‍💻 Developed by:</b> @YourUsername
<b>🌟 Version:</b> 2.0.0
<b>📅 Last Update:</b> {datetime.now().strftime('%Y-%m-%d')}

<i>Making auctions exciting since 2025!</i>
        """.strip()
        
        keyboard = [
            [InlineKeyboardButton("🌐 Website", url="https://yourwebsite.com")],
            [InlineKeyboardButton("💬 Support", url="https://t.me/yoursupport")],
            [InlineKeyboardButton("🔙 Back", callback_data="start")]
        ]
        
        await query.edit_message_text(
            about_msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
    async def _handle_game_mode(self, query, context):
        """Handle game mode display"""
        current_mode = await self.db.get_setting("auction_mode") or ("auto" if AUTO_MODE else "manual")
        current_timer = await self.db.get_setting("auction_timer") or AUCTION_TIMER
        current_budget = await self.db.get_setting("default_balance") or DEFAULT_BALANCE
        
        msg = f"""
{EMOJI_ICONS['gear']} <b>GAME MODE</b>

Welcome to eFootball Auction Bot!

<b>How it works:</b>
1. Managers get a starting budget
2. Players are auctioned one by one
3. Place bids to win players
4. Build your dream team!

<b>Current Settings:</b>
- Starting Balance: {self.formatter.format_currency(current_budget)}
- Auction Timer: {current_timer}s
- Mode: {current_mode.upper()}

Ready to play? Join the auction group!
        """.strip()
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="start")]]
        
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def _handle_start(self, query, context):
        """Handle start callback - redirect to main start function"""
        # Create a fake update for the start command
        from telegram import Message, Chat, User
        
        # Create the start command again
        user_id = query.from_user.id
        user_name = query.from_user.full_name
        
        # Check if user is admin
        if user_id in ADMIN_IDS:
            welcome_msg = self.formatter.format_admin_welcome(user_name)
            keyboard = [
                [
                    InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
                    InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard")
                ],
                [
                    InlineKeyboardButton("🔨 Start Auction", callback_data="start_auction_menu"),
                    InlineKeyboardButton("👥 Managers", callback_data="view_managers")
                ],
                [
                    InlineKeyboardButton("📈 Analytics", callback_data="view_analytics"),
                    InlineKeyboardButton("🏢 Groups", callback_data="admin_groups")
                ],
                [
                    InlineKeyboardButton("🎮 Game Mode", callback_data="game_mode"),
                    InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
                ]
            ]
        else:
            # Check if user is registered manager
            manager = await self.db.get_manager(user_id)
            if manager:
                welcome_msg = self.formatter.format_manager_welcome(manager)
                keyboard = [
                    [
                        InlineKeyboardButton("💰 My Balance", callback_data="check_balance"),
                        InlineKeyboardButton("🏆 My Team", callback_data="my_team")
                    ],
                    [
                        InlineKeyboardButton("📊 My Stats", callback_data="my_stats"),
                        InlineKeyboardButton("🎯 Active Auctions", callback_data="active_auctions")
                    ],
                    [
                        InlineKeyboardButton("🏅 Leaderboard", callback_data="leaderboard"),
                        InlineKeyboardButton("🎮 Achievements", callback_data="achievements")
                    ]
                ]
            else:
                welcome_msg = self.formatter.format_unregistered_welcome(user_name)
                keyboard = [
                    [InlineKeyboardButton("📝 Request Access", callback_data="request_access")],
                    [InlineKeyboardButton("ℹ️ About", callback_data="about_bot")]
                ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            welcome_msg,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
    # Helper methods
    def _get_uptime(self) -> str:
        """Get bot uptime"""
        try:
            uptime = datetime.now() - datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            return f"{hours}h {minutes}m"
        except:
            return "Unknown"