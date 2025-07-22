# bot.py - Fixed Main Bot Entry Point with Enhanced Features
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
    WAITING_MANAGER_NAME, WAITING_TEAM_NAME, WAITING_EDIT_INPUT,
    WAITING_ACCESS_NAME, WAITING_ADMIN_TEAM_NAME
) = range(11)

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
        self.application = None  # Store application reference
        
    async def post_init(self, application: Application) -> None:
        """Initialize after bot is built"""
        try:
            self.application = application  # Store application reference
            
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
            
            # Set cross-references
            self.user_handlers.admin_handlers = self.admin_handlers
            self.admin_handlers.auction_handlers = self.auction_handlers

            # Initialize callback handlers with all handler references
            self.callback_handlers = CallbackHandlers(
                self.db, 
                application.bot, 
                self.admin_handlers, 
                self.user_handlers,
                self.auction_handlers
            )

            # Set handler references in admin handlers
            self.admin_handlers.callback_handlers = self.callback_handlers
            
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
        
        # Send WITHOUT animation/GIF - this was causing the button issues
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
        """Handle manager input - Step 1: Get user ID"""
        if update.message.text.lower() == 'cancel':
            await update.message.reply_text(f"{EMOJI_ICONS['info']} Operation cancelled.")
            return ConversationHandler.END
        
        # Handle forwarded message
        if update.message.forward_from:
            user = update.message.forward_from
            user_id = user.id
            username = user.username
        else:
            # Handle text input
            text = update.message.text.strip()
            
            if text.startswith('@'):
                # Username
                try:
                    user = await context.bot.get_chat(text)
                    user_id = user.id
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
                f"Team: {existing.team_name or 'Not set'}\n"
                f"Balance: {self.formatter.format_currency(existing.balance)}"
            )
            return ConversationHandler.END
        
        # Store user info in context
        context.user_data['new_manager'] = {
            'user_id': user_id,
            'username': username
        }
        
        # Ask for display name
        await update.message.reply_text(
            f"{EMOJI_ICONS['user']} <b>Enter Display Name</b>\n\n"
            f"Enter the name to display for this manager:\n"
            f"(This helps identify users better than usernames)\n\n"
            f"Type 'skip' to use their Telegram name",
            parse_mode='HTML'
        )
        return WAITING_MANAGER_NAME

    async def add_manager_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle manager name input"""
        text = update.message.text.strip()
        
        if text.lower() == 'cancel':
            await update.message.reply_text(f"{EMOJI_ICONS['info']} Operation cancelled.")
            return ConversationHandler.END
        
        if text.lower() == 'skip':
            # Try to get name from Telegram
            try:
                user = await context.bot.get_chat(context.user_data['new_manager']['user_id'])
                name = user.full_name or user.title or "Unknown"
            except:
                name = "Unknown"
        else:
            name = text
        
        context.user_data['new_manager']['name'] = name
        
        # Ask for team name
        await update.message.reply_text(
            f"{EMOJI_ICONS['team']} <b>Enter Team Name</b>\n\n"
            f"Enter the team name for this manager:\n"
            f"(Optional - helps identify their team)\n\n"
            f"Type 'skip' to leave empty",
            parse_mode='HTML'
        )
        return WAITING_TEAM_NAME

    async def add_manager_team(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle team name input and create manager"""
        text = update.message.text.strip()
        
        if text.lower() == 'cancel':
            await update.message.reply_text(f"{EMOJI_ICONS['info']} Operation cancelled.")
            return ConversationHandler.END
        
        team_name = None if text.lower() == 'skip' else text
        
        # Create manager
        manager_data = context.user_data['new_manager']
        manager = Manager(
            user_id=manager_data['user_id'],
            name=manager_data['name'],
            username=manager_data['username'],
            team_name=team_name
        )
        
        success = await self.db.add_manager(manager)
        
        if success:
            await update.message.reply_text(
                f"{EMOJI_ICONS['success']} <b>Manager Added Successfully!</b>\n\n"
                f"{EMOJI_ICONS['user']} Name: {manager.name}\n"
                f"{EMOJI_ICONS['team']} Team: {team_name or 'Not set'}\n"
                f"{EMOJI_ICONS['id']} ID: <code>{manager.user_id}</code>\n"
                f"{EMOJI_ICONS['money']} Balance: {self.formatter.format_currency(DEFAULT_BALANCE)}\n\n"
                f"They can now use the bot!",
                parse_mode='HTML'
            )
            
            # Notify the new manager
            try:
                await context.bot.send_message(
                    manager.user_id,
                    f"{EMOJI_ICONS['celebration']} <b>Welcome to eFootball Auction!</b>\n\n"
                    f"You've been registered as a manager.\n"
                    f"Name: {manager.name}\n"
                    f"Team: {team_name or 'Not set'}\n"
                    f"Starting balance: {self.formatter.format_currency(DEFAULT_BALANCE)}\n\n"
                    f"Use /start to begin!",
                    parse_mode='HTML'
                )
            except:
                pass
        else:
            await update.message.reply_text(f"{EMOJI_ICONS['error']} Failed to add manager!")
        
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
    
    async def handle_edit_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle edit input from admin"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(f"{EMOJI_ICONS['error']} Admin access required!")
            return ConversationHandler.END
        
        editing_user_id = context.user_data.get('editing_user_id')
        edit_type = context.user_data.get('edit_type')
        
        if not editing_user_id or not edit_type:
            await update.message.reply_text(f"{EMOJI_ICONS['error']} Error: Lost context. Please try again.")
            return ConversationHandler.END
        
        text = update.message.text.strip()
        
        if edit_type == 'name':
            # Update name
            result = await self.db.managers.update_one(
                {"user_id": editing_user_id},
                {"$set": {"name": text}}
            )
            
            if result.modified_count > 0:
                await update.message.reply_text(
                    f"{EMOJI_ICONS['success']} Name updated successfully!\n"
                    f"New name: {text}"
                )
            else:
                await update.message.reply_text(f"{EMOJI_ICONS['error']} Failed to update name!")
                
        elif edit_type == 'team':
            # Update team
            team_name = None if text.lower() == 'none' else text
            result = await self.db.managers.update_one(
                {"user_id": editing_user_id},
                {"$set": {"team_name": team_name}}
            )
            
            if result.modified_count > 0:
                await update.message.reply_text(
                    f"{EMOJI_ICONS['success']} Team updated successfully!\n"
                    f"New team: {team_name or 'Not set'}"
                )
            else:
                await update.message.reply_text(f"{EMOJI_ICONS['error']} Failed to update team!")
                
        elif edit_type == 'balance':
            # Update balance
            try:
                # Parse balance
                if '.' in text:
                    balance = int(float(text) * 1_000_000)
                else:
                    balance = int(text) * 1_000_000
                
                if balance < 0:
                    await update.message.reply_text(f"{EMOJI_ICONS['error']} Balance cannot be negative!")
                    return ConversationHandler.END
                
                result = await self.db.managers.update_one(
                    {"user_id": editing_user_id},
                    {"$set": {"balance": balance}}
                )
                
                if result.modified_count > 0:
                    await update.message.reply_text(
                        f"{EMOJI_ICONS['success']} Balance updated successfully!\n"
                        f"New balance: {self.formatter.format_currency(balance)}"
                    )
                else:
                    await update.message.reply_text(f"{EMOJI_ICONS['error']} Failed to update balance!")
                    
            except ValueError:
                await update.message.reply_text(f"{EMOJI_ICONS['error']} Invalid balance format! Use numbers only.")
                return ConversationHandler.END
        
        # Clear context
        context.user_data.clear()
        return ConversationHandler.END
        
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel any ongoing operation"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            f"{EMOJI_ICONS['info']} Operation cancelled."
        )
        return ConversationHandler.END
    
    async def _start_edit_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start edit conversation from callback"""
        query = update.callback_query
        await self.callback_handlers.handle_callback(query, context)
        # Check if edit type was set
        if 'edit_type' in context.user_data:
            return WAITING_EDIT_INPUT
        return ConversationHandler.END
    
    async def handle_access_name_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle name input during access request"""
        if update.message.text and update.message.text.lower() == 'cancel':
            await update.message.reply_text(f"{EMOJI_ICONS['info']} Request cancelled.")
            return ConversationHandler.END
        
        name = update.message.text.strip()
        
        if not name or len(name) < 2:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} Please enter a valid name (at least 2 characters):"
            )
            return WAITING_ACCESS_NAME
        
        # Store name in context
        context.user_data['access_request_name'] = name
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        # Check if request already exists
        existing_request = await self.db.join_requests.find_one({
            'user_id': user_id,
            'status': 'pending'
        })
        
        if existing_request:
            await update.message.reply_text(
                f"{EMOJI_ICONS['warning']} You already have a pending request!"
            )
            return ConversationHandler.END
        
        # Add to join requests with provided name
        request_data = {
            'user_id': user_id,
            'user_name': name,  # Use provided name instead of Telegram name
            'username': username,
            'chat_id': update.message.chat.id,
            'status': 'pending',
            'created_at': datetime.now()
        }
        
        await self.db.join_requests.insert_one(request_data)
        
        await update.message.reply_text(
            f"{EMOJI_ICONS['success']} <b>REQUEST SUBMITTED!</b>\n\n"
            f"✅ Name: <b>{name}</b>\n"
            f"📋 Your access request has been sent to admins\n"
            f"⏳ You'll be notified once processed\n\n"
            f"Use /start to return to the main menu.",
            parse_mode='HTML'
        )
        
        # Notify all admins
        for admin_id in ADMIN_IDS:
            try:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve_request_{user_id}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"reject_request_{user_id}")
                    ]
                ]
                
                await context.bot.send_message(
                    admin_id,
                    f"{EMOJI_ICONS['bell']} <b>NEW ACCESS REQUEST</b>\n\n"
                    f"{EMOJI_ICONS['user']} Name: <b>{name}</b>\n"
                    f"{EMOJI_ICONS['id']} ID: <code>{user_id}</code>\n"
                    f"{EMOJI_ICONS['at']} Username: @{username or 'None'}\n"
                    f"{EMOJI_ICONS['clock']} Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"Click below to approve or reject:",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        
        return ConversationHandler.END

    async def handle_admin_team_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle team name input from admin during approval"""
        if update.message.text and update.message.text.lower() == 'cancel':
            await update.message.reply_text(f"{EMOJI_ICONS['info']} Approval cancelled.")
            return ConversationHandler.END
        
        team_name = update.message.text.strip()
        
        # Get stored user info
        user_id = context.user_data.get('approving_user_id')
        user_name = context.user_data.get('approving_user_name')
        username = context.user_data.get('approving_username')
        
        if not user_id:
            await update.message.reply_text(f"{EMOJI_ICONS['error']} Error: Lost context. Please try again.")
            return ConversationHandler.END
        
        # Process team name
        if team_name.lower() == 'skip':
            team_name = None
        
        # Create manager
        manager = Manager(
            user_id=user_id,
            name=user_name,
            username=username,
            team_name=team_name
        )
        
        success = await self.db.add_manager(manager)
        
        if success:
            # Update request status
            await self.db.join_requests.update_one(
                {'user_id': user_id, 'status': 'pending'},
                {'$set': {'status': 'approved', 'processed_by': update.effective_user.id}}
            )
            
            await update.message.reply_text(
                f"{EMOJI_ICONS['success']} <b>MANAGER APPROVED!</b>\n\n"
                f"{EMOJI_ICONS['user']} Name: <b>{user_name}</b>\n"
                f"{EMOJI_ICONS['team']} Team: <b>{team_name or 'Not set'}</b>\n"
                f"{EMOJI_ICONS['money']} Balance: {self.formatter.format_currency(DEFAULT_BALANCE)}\n\n"
                f"✅ User has been notified!",
                parse_mode='HTML'
            )
            
            # Notify the user
            try:
                welcome_keyboard = [[InlineKeyboardButton("🏠 Get Started", callback_data="start")]]
                
                await context.bot.send_message(
                    user_id,
                    f"{EMOJI_ICONS['celebration']} <b>ACCESS GRANTED!</b>\n\n"
                    f"🎉 Welcome to eFootball Auction!\n"
                    f"📝 Name: <b>{user_name}</b>\n"
                    f"🏆 Team: <b>{team_name or 'Not assigned yet'}</b>\n"
                    f"💰 Starting Balance: {self.formatter.format_currency(DEFAULT_BALANCE)}\n\n"
                    f"🚀 You're now ready to participate in auctions!\n"
                    f"Use the button below to start exploring.",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(welcome_keyboard)
                )
            except Exception as e:
                logger.warning(f"Failed to notify approved user {user_id}: {e}")
        else:
            await update.message.reply_text(f"{EMOJI_ICONS['error']} Failed to create manager!")
        
        # Clear context
        context.user_data.clear()
        return ConversationHandler.END
        
    def add_handlers(self, application):
        """Add all command and message handlers"""
        # Conversation handlers for admin operations
        add_manager_conv = ConversationHandler(
            entry_points=[CommandHandler("add_manager", self.add_manager_start)],
            states={
                WAITING_MANAGER_INPUT: [
                    MessageHandler(filters.TEXT | filters.StatusUpdate.USER_SHARED, self.add_manager_input)
                ],
                WAITING_MANAGER_NAME: [
                    MessageHandler(filters.TEXT, self.add_manager_name)
                ],
                WAITING_TEAM_NAME: [
                    MessageHandler(filters.TEXT, self.add_manager_team)
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

        edit_manager_conv = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    self._start_edit_conversation,
                    pattern="^(edit_name_|edit_team_|edit_balance_)"
                )
            ],
            states={
                WAITING_EDIT_INPUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_edit_input)
                ]
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel_operation)
            ],
            per_message=False,
            per_chat=False  # Track by user, not chat
        )

        access_request_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self._start_access_request_conversation,
                pattern="^request_access$"
            )],
            states={
                WAITING_ACCESS_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_access_name_input)
                ]
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel_operation),
                CommandHandler("start", self.start_command)
            ],
            per_message=False
        )
        
        admin_approval_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self._start_approval_conversation,
                pattern="^approve_request_"
            )],
            states={
                WAITING_ADMIN_TEAM_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_admin_team_input)
                ]
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel_operation)
            ],
            per_message=False
        )
        
        # Add conversation handlers
        application.add_handler(add_manager_conv)
        application.add_handler(broadcast_conv)
        application.add_handler(edit_manager_conv)
        application.add_handler(access_request_conv)
        application.add_handler(admin_approval_conv)
        
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
        application.add_handler(CommandHandler("managers_summary", self.handle_managers_summary))
        application.add_handler(CommandHandler("managers_detailed", self.handle_managers_detailed))
        application.add_handler(CommandHandler("next", self.handle_next_player))
        
        # User commands
        application.add_handler(CommandHandler("bid", self.handle_bid))
        application.add_handler(CommandHandler("balance", self.handle_balance))
        application.add_handler(CommandHandler("mystats", self.handle_mystats))
        application.add_handler(CommandHandler("leaderboard", self.handle_leaderboard))
        application.add_handler(CommandHandler("achievements", self.handle_achievements))
        
        # This handler specifically for auction group
        application.add_handler(MessageHandler(
            filters.Regex(r'^\d+(?:\.\d+)?$') & filters.Chat(AUCTION_GROUP_ID),
            self.handle_number_bid
        ))
        
        # Message handlers
        application.add_handler(MessageHandler(
            filters.ChatType.GROUPS & ~filters.COMMAND, 
            self.handle_group_messages
        ))

        # Callback query handler - MUST BE AFTER CONVERSATION HANDLERS
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

    async def handle_managers_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.admin_handlers:
            await self.admin_handlers.show_all_managers_summary(update, context)

    async def handle_managers_detailed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.admin_handlers:
            await self.admin_handlers.show_all_managers_detailed(update, context)
    
    async def handle_next_player(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.admin_handlers:
            await self.admin_handlers.next_player_command(update, context)
    
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
    
    async def handle_achievements(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.user_handlers:
            await self.user_handlers.show_achievements(update, context)

    async def handle_number_bid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle number-only bids in auction group"""
        if update.message.chat_id != AUCTION_GROUP_ID:
            return
        
        # Delete the message to keep chat clean
        try:
            await update.message.delete()
        except:
            pass
        
        # Set context args for bid processing
        context.args = [update.message.text]
        
        # Process as bid
        if self.user_handlers:
            await self.user_handlers.place_bid(update, context)
    
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

        try:
            await query.answer()
        except:
            pass

        if self.callback_handlers:
            await self.callback_handlers.handle_callback(query, context)

    async def _start_access_request_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start access request conversation"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Check if already registered
        manager = await self.db.get_manager(user_id)
        if manager:
            await query.edit_message_text(
                f"{EMOJI_ICONS['success']} <b>ALREADY REGISTERED</b>\n\n"
                f"You're already a registered manager!\n"
                f"Use /start to access your dashboard.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Dashboard", callback_data="start")
                ]])
            )
            return ConversationHandler.END
        
        # Check if request already exists
        existing_request = await self.db.join_requests.find_one({
            'user_id': user_id,
            'status': 'pending'
        })
        
        if existing_request:
            await query.edit_message_text(
                f"{EMOJI_ICONS['clock']} <b>REQUEST PENDING</b>\n\n"
                f"Your access request is already under review.\n"
                f"Please wait for admin approval.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="start")
                ]])
            )
            return ConversationHandler.END
        
        await query.edit_message_text(
            f"{EMOJI_ICONS['user']} <b>REQUEST ACCESS</b>\n\n"
            f"To join as a manager, please provide your name:\n"
            f"(This will be displayed in auctions and leaderboards)\n\n"
            f"💡 <i>Use your real name</i>",
            parse_mode='HTML'
        )
        
        return WAITING_ACCESS_NAME

    async def _start_approval_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start admin approval conversation"""
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("Admin access required!", show_alert=True)
            return ConversationHandler.END
        
        data = query.data
        user_id = int(data.replace("approve_request_", ""))
        
        # Get request details
        request = await self.db.join_requests.find_one({
            'user_id': user_id,
            'status': 'pending'
        })
        
        if not request:
            await query.edit_message_text(
                f"{EMOJI_ICONS['error']} Request not found or already processed!"
            )
            return ConversationHandler.END
        
        # Store user info in context
        context.user_data['approving_user_id'] = user_id
        context.user_data['approving_user_name'] = request['user_name']
        context.user_data['approving_username'] = request.get('username')
        
        await query.edit_message_text(
            f"{EMOJI_ICONS['team']} <b>SET TEAM NAME</b>\n\n"
            f"👤 Manager: <b>{request['user_name']}</b>\n"
            f"🆔 ID: <code>{user_id}</code>\n\n"
            f"Enter a team name for this manager:\n"
            f"(Optional - type 'skip' to leave empty)",
            parse_mode='HTML'
        )
        
        return WAITING_ADMIN_TEAM_NAME
    
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