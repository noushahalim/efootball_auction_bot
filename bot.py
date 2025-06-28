# bot.py - Fixed Bot Entry Point with proper handler connections
import asyncio
import logging
import os
import sys
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, 
    CallbackQueryHandler, ConversationHandler
)
from telegram.error import BadRequest, TelegramError, Forbidden

# Import our modules
from config.settings import *
from database.db import Database
from database.models import Manager, Auction, Player
from handlers.admin_handlers import AdminHandlers
from handlers.user_handlers import UserHandlers
from handlers.error_handlers import ErrorHandlers
from handlers.callback_handlers import CallbackHandlers
from handlers.auction_handlers import AuctionHandlers
from utilities.formatters import MessageFormatter
from utilities.helpers import ValidationHelper
from utilities.countdown import CountdownManager
from utilities.analytics import AnalyticsManager

# Configure logging with colors
class ColoredFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    green = "\x1b[32;20m"
    reset = "\x1b[0m"
    
    FORMATS = {
        logging.DEBUG: grey + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset,
        logging.INFO: green + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset,
        logging.WARNING: yellow + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset,
        logging.ERROR: red + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset,
        logging.CRITICAL: bold_red + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Configure logging
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(ColoredFormatter())
logging.basicConfig(level=logging.INFO, handlers=[ch])
logger = logging.getLogger(__name__)

# Conversation states
(
    WAITING_MANAGER_INPUT, WAITING_BROADCAST_INPUT, WAITING_MANUAL_PLAYER_NAME,
    WAITING_MANUAL_PLAYER_PRICE, WAITING_BAN_REASON, WAITING_SESSION_NAME,
    WAITING_ADD_ADMIN, WAITING_PLAYER_POSITION, WAITING_PLAYER_RATING
) = range(9)

class EFootballAuctionBot:
    def __init__(self):
        self.db = Database()
        self.formatter = MessageFormatter()
        self.validator = ValidationHelper()
        self.countdown = CountdownManager()
        self.analytics = AnalyticsManager(self.db)
        
        # Initialize handlers
        self.admin_handlers = None
        self.user_handlers = None
        self.error_handlers = ErrorHandlers()
        self.callback_handlers = None
        self.auction_handlers = None
        
        # Bot state
        self.startup_time = datetime.now()
        self.active_countdowns = {}
        self.auction_queue = []  # Queue for multiple players
        self.session_break_timer = 30  # Default 30 seconds between auctions
        
    async def post_init(self, application: Application) -> None:
        """Initialize after bot is built"""
        try:
            # Test database connection
            logger.info("🔄 Connecting to MongoDB...")
            await self.db.client.admin.command('ping')
            logger.info("✅ MongoDB connected successfully!")
            
            # Initialize database
            await self.db.create_indexes()
            
            # Initialize handlers with application context
            self.admin_handlers = AdminHandlers(self.db, application.bot)
            self.user_handlers = UserHandlers(self.db, application.bot)
            self.auction_handlers = AuctionHandlers(self.db, application.bot, self.countdown, self.analytics)
            self.callback_handlers = CallbackHandlers(self.db, application.bot, self.admin_handlers, self.user_handlers)
            
            # Set auction handlers reference in admin handlers
            self.admin_handlers.auction_handlers = self.auction_handlers
            
            # Update admin list from database
            await self.db.update_admin_list()
            
            # Set bot commands
            await self.set_bot_commands(application)
            
            # Check bot connectivity to groups
            await self.verify_groups(application.bot)
            
            # Start background tasks
            asyncio.create_task(self.background_tasks())
            
            logger.info("🚀 Bot initialized successfully!")
            
        except Exception as e:
            logger.critical(f"❌ Failed to initialize bot: {e}")
            logger.critical("Please ensure MongoDB is running and accessible")
            raise
        
    async def set_bot_commands(self, application):
        """Set bot commands in Telegram"""
        commands = [
            BotCommand("start", "🏠 Start the bot"),
            BotCommand("help", "❓ Get help"),
            BotCommand("balance", "💰 Check your balance"),
            BotCommand("bid", "🎯 Place a bid"),
            BotCommand("mystats", "📊 View your statistics"),
            BotCommand("leaderboard", "🏆 View leaderboard"),
            BotCommand("myteam", "👥 View my team"),
        ]
        
        admin_commands = commands + [
            BotCommand("start_auction", "🔨 Start new auction"),
            BotCommand("stop_auction", "⏸️ Pause auction"),
            BotCommand("skip_bid", "⏭️ Skip to unsold"),
            BotCommand("final_call", "🔔 Final call (manual)"),
            BotCommand("auction_result", "📋 View results"),
            BotCommand("settings", "⚙️ Bot settings"),
            BotCommand("broadcast", "📢 Send announcement"),
            BotCommand("groups", "🏢 Manage groups"),
            BotCommand("analytics", "📈 View analytics"),
            BotCommand("add_manager", "➕ Add new manager"),
            BotCommand("add_admin", "👮 Add new admin"),
            BotCommand("clear_all", "🗑️ Clear all data"),
        ]
        
        await application.bot.set_my_commands(commands)
        
        # Set admin commands for specific users
        for admin_id in ADMIN_IDS:
            try:
                await application.bot.set_my_commands(admin_commands, scope={"type": "chat", "chat_id": admin_id})
            except:
                pass
                
    async def verify_groups(self, bot):
        """Verify bot has access to configured groups"""
        global DATA_GROUP_ID, UNSOLD_GROUP_ID
        
        groups = {
            "Auction Group": AUCTION_GROUP_ID,
            "Data Group": DATA_GROUP_ID,
            "Unsold Group": UNSOLD_GROUP_ID
        }
        
        for name, group_id in groups.items():
            if group_id:
                try:
                    chat = await bot.get_chat(group_id)
                    member = await bot.get_chat_member(group_id, bot.id)
                    
                    if member.status in ['administrator', 'member']:
                        logger.info(f"✅ Connected to {name}: {chat.title}")
                        await self.db.add_group(group_id, chat.title, name.lower().replace(' ', '_'))
                    else:
                        logger.warning(f"⚠️ Bot not active in {name}")
                        await self.db.update_group_status(group_id, 'inactive')
                        
                except BadRequest as e:
                    if "chat not found" in str(e).lower():
                        logger.error(f"❌ {name} not found ({group_id})")
                        logger.info(f"💡 Use /groups command to manage group connections")
                    else:
                        logger.error(f"❌ Cannot access {name} ({group_id}): {e}")
                except Exception as e:
                    logger.error(f"❌ Error checking {name} ({group_id}): {e}")
                    
    async def background_tasks(self):
        """Run background tasks"""
        while True:
            try:
                # Clean up old data
                await self.db.cleanup_old_auctions()
                
                # Update analytics
                await self.analytics.update_hourly_stats()
                
                # Check for stuck auctions
                await self.auction_handlers.check_stuck_auctions()
                
            except Exception as e:
                logger.error(f"Background task error: {e}")
                
            await asyncio.sleep(3600)  # Run every hour
            
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced /start command with visual welcome"""
        user_id = update.effective_user.id
        user_name = update.effective_user.full_name
        
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
        
        # Send with animation
        try:
            await update.message.reply_animation(
                animation=WELCOME_GIF,
                caption=welcome_msg,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except:
            # Fallback to text message
            await update.message.reply_text(
                welcome_msg,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Interactive help command"""
        help_sections = {
            "basic_help": "📚 Basic Commands",
            "bidding_help": "🎯 Bidding Guide",
            "strategy_help": "🧠 Strategy Tips",
            "rules_help": "📜 Auction Rules",
            "faq_help": "❓ FAQ"
        }
        
        keyboard = [[InlineKeyboardButton(text, callback_data=data)] 
                   for data, text in help_sections.items()]
        
        help_msg = """
🆘 <b>EFOOTBALL AUCTION HELP CENTER</b>

Welcome to the ultimate auction experience! Select a topic below to learn more:

🎮 <b>Quick Tips:</b>
• React fast - auctions move quickly!
• Watch your balance - plan your bids
• Build a balanced team
• Use quick bid buttons for speed

Select a help topic below:
        """.strip()
        
        await update.message.reply_text(
            help_msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
    # Conversation handlers for admin operations
    async def add_manager_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start add manager conversation"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(f"{EMOJI_ICONS['error']} Admin access required!")
            return ConversationHandler.END
            
        await update.message.reply_text(
            f"{EMOJI_ICONS['user']} <b>ADD NEW MANAGER</b>\n\n"
            f"Please provide:\n"
            f"• User ID (e.g., 123456789)\n"
            f"• Username (e.g., @username)\n"
            f"• Or forward a message from the user\n\n"
            f"Type 'cancel' to abort.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")
            ]])
        )
        return WAITING_MANAGER_INPUT
        
    async def add_manager_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle manager input"""
        if update.message.text and update.message.text.lower() == 'cancel':
            await update.message.reply_text(f"{EMOJI_ICONS['info']} Operation cancelled.")
            return ConversationHandler.END
            
        # Handle forwarded message
        if update.message.forward_from:
            user = update.message.forward_from
            user_id = user.id
            name = user.full_name
            username = user.username
        else:
            # Handle text input
            text = update.message.text.strip()
            
            if text.startswith('@'):
                # Username
                try:
                    user = await context.bot.get_chat(text)
                    user_id = user.id
                    name = user.full_name or user.title
                    username = user.username
                except:
                    await update.message.reply_text(
                        f"{EMOJI_ICONS['error']} User not found! Try forwarding a message from them."
                    )
                    return WAITING_MANAGER_INPUT
            elif text.isdigit():
                # User ID
                try:
                    user_id = int(text)
                    user = await context.bot.get_chat(user_id)
                    name = user.full_name or user.title
                    username = user.username
                except:
                    await update.message.reply_text(
                        f"{EMOJI_ICONS['error']} Invalid user ID! Try forwarding a message from them."
                    )
                    return WAITING_MANAGER_INPUT
            else:
                await update.message.reply_text(
                    f"{EMOJI_ICONS['error']} Invalid format! Use @username, user ID, or forward a message."
                )
                return WAITING_MANAGER_INPUT
                
        # Check if already exists
        existing = await self.db.get_manager(user_id)
        if existing:
            await update.message.reply_text(
                f"{EMOJI_ICONS['warning']} Manager already exists!\n"
                f"Name: {existing.name}\n"
                f"Balance: {self.formatter.format_currency(existing.balance)}"
            )
            return ConversationHandler.END
            
        # Add manager
        manager = Manager(
            user_id=user_id,
            name=name,
            username=username
        )
        
        success = await self.db.add_manager(manager)
        
        if success:
            await update.message.reply_text(
                f"{EMOJI_ICONS['success']} <b>Manager Added Successfully!</b>\n\n"
                f"{EMOJI_ICONS['user']} Name: {name}\n"
                f"{EMOJI_ICONS['id']} ID: <code>{user_id}</code>\n"
                f"{EMOJI_ICONS['money']} Balance: {self.formatter.format_currency(DEFAULT_BALANCE)}\n\n"
                f"They can now use the bot!",
                parse_mode='HTML'
            )
            
            # Notify the new manager
            try:
                await context.bot.send_message(
                    user_id,
                    f"{EMOJI_ICONS['celebration']} <b>Welcome to eFootball Auction!</b>\n\n"
                    f"You've been registered as a manager.\n"
                    f"Starting balance: {self.formatter.format_currency(DEFAULT_BALANCE)}\n\n"
                    f"Use /start to begin!",
                    parse_mode='HTML'
                )
            except:
                pass
        else:
            await update.message.reply_text(f"{EMOJI_ICONS['error']} Failed to add manager!")
            
        return ConversationHandler.END
        
    async def add_admin_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start add admin conversation"""
        user_id = update.effective_user.id
        
        if user_id != SUPER_ADMIN_ID:
            await update.message.reply_text(f"{EMOJI_ICONS['error']} Only super admin can add admins!")
            return ConversationHandler.END
            
        await update.message.reply_text(
            f"{EMOJI_ICONS['shield']} <b>ADD NEW ADMIN</b>\n\n"
            f"Please provide:\n"
            f"• User ID (e.g., 123456789)\n"
            f"• Username (e.g., @username)\n"
            f"• Or forward a message from the user\n\n"
            f"Type 'cancel' to abort.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")
            ]])
        )
        return WAITING_ADD_ADMIN
        
    async def add_admin_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin input"""
        if update.message.text and update.message.text.lower() == 'cancel':
            await update.message.reply_text(f"{EMOJI_ICONS['info']} Operation cancelled.")
            return ConversationHandler.END
            
        # Similar logic to add_manager_input but for admins
        # ... (similar parsing logic)
        
        # For brevity, assuming we have user_id, name, username
        text = update.message.text.strip()
        if text.isdigit():
            user_id = int(text)
            try:
                user = await context.bot.get_chat(user_id)
                name = user.full_name or user.title
                username = user.username
            except:
                await update.message.reply_text(f"{EMOJI_ICONS['error']} User not found!")
                return WAITING_ADD_ADMIN
        else:
            await update.message.reply_text(f"{EMOJI_ICONS['error']} Please provide a valid user ID!")
            return WAITING_ADD_ADMIN
            
        # Add as admin
        await self.db.make_admin(user_id)
        
        await update.message.reply_text(
            f"{EMOJI_ICONS['success']} <b>Admin Added Successfully!</b>\n\n"
            f"{EMOJI_ICONS['shield']} Name: {name}\n"
            f"{EMOJI_ICONS['id']} ID: <code>{user_id}</code>\n\n"
            f"They now have admin privileges!",
            parse_mode='HTML'
        )
        
        # Notify the new admin
        try:
            await context.bot.send_message(
                user_id,
                f"{EMOJI_ICONS['shield']} <b>Admin Access Granted!</b>\n\n"
                f"You now have admin privileges in eFootball Auction Bot.\n"
                f"Use /start to see admin options.",
                parse_mode='HTML'
            )
        except:
            pass
            
        return ConversationHandler.END
        
    async def broadcast_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start broadcast conversation"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(f"{EMOJI_ICONS['error']} Admin access required!")
            return ConversationHandler.END
            
        await update.message.reply_text(
            f"{EMOJI_ICONS['loudspeaker']} <b>CREATE BROADCAST</b>\n\n"
            f"Send the message you want to broadcast to all managers.\n\n"
            f"Supports: Text, images, videos, documents\n"
            f"Type 'cancel' to abort.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")
            ]])
        )
        return WAITING_BROADCAST_INPUT
        
    async def broadcast_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle broadcast input"""
        if update.message.text and update.message.text.lower() == 'cancel':
            await update.message.reply_text(f"{EMOJI_ICONS['info']} Broadcast cancelled.")
            return ConversationHandler.END
            
        # Get all managers
        managers = await self.db.get_all_managers()
        
        if not managers:
            await update.message.reply_text(f"{EMOJI_ICONS['error']} No managers found!")
            return ConversationHandler.END
            
        # Create broadcast message
        broadcast_msg = f"""
{EMOJI_ICONS['loudspeaker']} <b>ADMIN ANNOUNCEMENT</b>

{update.message.text or "📎 Media message"}

<i>- Auction Administration</i>
        """.strip()
        
        sent = 0
        failed = 0
        
        status_msg = await update.message.reply_text(
            f"{EMOJI_ICONS['loading']} Broadcasting to {len(managers)} managers..."
        )
        
        for manager in managers:
            try:
                if update.message.photo:
                    await context.bot.send_photo(
                        manager.user_id,
                        photo=update.message.photo[-1].file_id,
                        caption=broadcast_msg,
                        parse_mode='HTML'
                    )
                elif update.message.video:
                    await context.bot.send_video(
                        manager.user_id,
                        video=update.message.video.file_id,
                        caption=broadcast_msg,
                        parse_mode='HTML'
                    )
                elif update.message.document:
                    await context.bot.send_document(
                        manager.user_id,
                        document=update.message.document.file_id,
                        caption=broadcast_msg,
                        parse_mode='HTML'
                    )
                else:
                    await context.bot.send_message(
                        manager.user_id,
                        broadcast_msg,
                        parse_mode='HTML'
                    )
                sent += 1
            except:
                failed += 1
                
            # Update progress every 10 users
            if (sent + failed) % 10 == 0:
                try:
                    await status_msg.edit_text(
                        f"{EMOJI_ICONS['loading']} Progress: {sent + failed}/{len(managers)}"
                    )
                except:
                    pass
                    
        await status_msg.edit_text(
            f"{EMOJI_ICONS['success']} <b>Broadcast Complete!</b>\n\n"
            f"✅ Sent: {sent}\n"
            f"❌ Failed: {failed}",
            parse_mode='HTML'
        )
        
        return ConversationHandler.END
        
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel any ongoing operation"""
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text(f"{EMOJI_ICONS['info']} Operation cancelled.")
        else:
            await update.message.reply_text(f"{EMOJI_ICONS['info']} Operation cancelled.")
        return ConversationHandler.END
        
    async def clear_all_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear all data from database"""
        user_id = update.effective_user.id
        
        if user_id != SUPER_ADMIN_ID:
            await update.message.reply_text(f"{EMOJI_ICONS['error']} Only super admin can clear all data!")
            return
            
        # Confirmation keyboard
        keyboard = [
            [
                InlineKeyboardButton("⚠️ YES, DELETE ALL", callback_data="confirm_clear_all"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_clear_all")
            ]
        ]
        
        await update.message.reply_text(
            f"{EMOJI_ICONS['warning']} <b>⚠️ DANGER ZONE ⚠️</b>\n\n"
            f"This will permanently delete:\n"
            f"• All managers (except admins)\n"
            f"• All auction history\n"
            f"• All player data\n"
            f"• All analytics\n"
            f"• All settings\n\n"
            f"<b>This action CANNOT be undone!</b>\n\n"
            f"Are you absolutely sure?",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    def add_handlers(self, application):
        """Add all command and message handlers"""
        # Conversation handlers for admin operations
        add_manager_conv = ConversationHandler(
            entry_points=[CommandHandler("add_manager", self.add_manager_start)],
            states={
                WAITING_MANAGER_INPUT: [
                    MessageHandler(filters.TEXT | filters.StatusUpdate.USER_SHARED, self.add_manager_input)
                ]
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel_operation, pattern="^cancel_operation$"),
                CommandHandler("cancel", self.cancel_operation)
            ]
        )
        
        add_admin_conv = ConversationHandler(
            entry_points=[CommandHandler("add_admin", self.add_admin_start)],
            states={
                WAITING_ADD_ADMIN: [
                    MessageHandler(filters.TEXT, self.add_admin_input)
                ]
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel_operation, pattern="^cancel_operation$"),
                CommandHandler("cancel", self.cancel_operation)
            ]
        )
        
        broadcast_conv = ConversationHandler(
            entry_points=[CommandHandler("broadcast", self.broadcast_start)],
            states={
                WAITING_BROADCAST_INPUT: [
                    MessageHandler(
                        filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                        self.broadcast_input
                    )
                ]
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel_operation, pattern="^cancel_operation$"),
                CommandHandler("cancel", self.cancel_operation)
            ]
        )
        
        # Add conversation handlers
        application.add_handler(add_manager_conv)
        application.add_handler(add_admin_conv)
        application.add_handler(broadcast_conv)
        
        # Basic commands
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        
        # Admin commands
        application.add_handler(CommandHandler("start_auction", self.handle_start_auction))
        application.add_handler(CommandHandler("stop_auction", self.handle_stop_auction))
        application.add_handler(CommandHandler("skip_bid", self.handle_skip_bid))
        application.add_handler(CommandHandler("final_call", self.handle_final_call))
        application.add_handler(CommandHandler("auction_result", self.handle_auction_result))
        application.add_handler(CommandHandler("settings", self.handle_settings))
        application.add_handler(CommandHandler("undo_bid", self.handle_undo_bid))
        application.add_handler(CommandHandler("continue_auction", self.handle_continue_auction))
        application.add_handler(CommandHandler("groups", self.handle_groups))
        application.add_handler(CommandHandler("analytics", self.handle_analytics))
        application.add_handler(CommandHandler("clear_all", self.clear_all_data))
        
        # User commands
        application.add_handler(CommandHandler("bid", self.handle_bid))
        application.add_handler(CommandHandler("balance", self.handle_balance))
        application.add_handler(CommandHandler("mystats", self.handle_mystats))
        application.add_handler(CommandHandler("leaderboard", self.handle_leaderboard))
        application.add_handler(CommandHandler("myteam", self.handle_myteam))
        
        # Message handlers
        application.add_handler(MessageHandler(
            filters.ChatType.GROUPS & ~filters.COMMAND, 
            self.handle_group_messages
        ))
        
        # Callback query handler - MUST BE LAST
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Error handler
        application.add_error_handler(self.error_handlers.error_handler)
    
    # Wrapper methods for admin handlers
    async def handle_start_auction(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.admin_handlers:
            await self.admin_handlers.start_auction_command(update, context)
    
    async def handle_stop_auction(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.admin_handlers:
            await self.admin_handlers.stop_auction(update, context)
    
    async def handle_skip_bid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.admin_handlers:
            await self.admin_handlers.skip_bid(update, context)
    
    async def handle_final_call(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.admin_handlers:
            await self.admin_handlers.final_call(update, context)
    
    async def handle_auction_result(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.admin_handlers:
            await self.admin_handlers.auction_result(update, context)
    
    async def handle_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.admin_handlers:
            await self.admin_handlers.settings_command(update, context)
    
    async def handle_undo_bid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.admin_handlers:
            await self.admin_handlers.undo_bid(update, context)
    
    async def handle_continue_auction(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.admin_handlers:
            await self.admin_handlers.continue_auction(update, context)
            
    async def handle_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.admin_handlers:
            await self.admin_handlers.manage_groups_command(update, context)
            
    async def handle_analytics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.admin_handlers:
            await self.admin_handlers.analytics_command(update, context)
    
    # Wrapper methods for user handlers
    async def handle_bid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.user_handlers:
            await self.user_handlers.place_bid(update, context)
    
    async def handle_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.user_handlers:
            await self.user_handlers.check_balance_command(update, context)
            
    async def handle_mystats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.user_handlers:
            await self.user_handlers.show_detailed_stats(update, context)
            
    async def handle_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.user_handlers:
            await self.user_handlers.show_leaderboard(update, context)
            
    async def handle_myteam(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.user_handlers:
            await self.user_handlers.show_my_team_command(update, context)
    
    async def handle_group_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages in groups"""
        if update.message.chat_id == DATA_GROUP_ID:
            # Process player data messages
            await self.admin_handlers.handle_data_message(update, context)
        elif update.message.chat_id == AUCTION_GROUP_ID:
            # Handle auction group messages if needed
            pass
            
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route all callback queries"""
        query = update.callback_query
        if self.callback_handlers:
            await self.callback_handlers.handle_callback(query, context)
    
    def run(self):
        """Start the bot with enhanced error handling"""
        try:
            # Create application
            application = Application.builder().token(BOT_TOKEN).post_init(self.post_init).build()
            
            # Add handlers after build
            self.add_handlers(application)
            
            # Start bot
            logger.info("🚀 Starting eFootball Auction Bot...")
            logger.info(f"🤖 Bot username: @{BOT_USERNAME}")
            logger.info("⚡ All systems operational!")
            
            application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            logger.critical(f"Failed to start bot: {e}")
            sys.exit(1)

if __name__ == "__main__":
    bot = EFootballAuctionBot()
    bot.run()