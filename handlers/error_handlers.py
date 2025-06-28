# handlers/error_handlers.py - Comprehensive Error Handling
import logging
import traceback
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import (
    TelegramError, 
    Forbidden, 
    BadRequest, 
    TimedOut, 
    NetworkError,
    ChatMigrated,
    RetryAfter
)
from config.settings import EMOJI_ICONS, ADMIN_IDS

logger = logging.getLogger(__name__)

class ErrorHandlers:
    def __init__(self):
        self.error_count = 0
        self.error_history = []
        self.max_error_logs = 100
        
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Main error handler for all bot errors"""
        self.error_count += 1
        
        # Log the error with full traceback
        logger.error(
            f"Exception while handling update {update}:",
            exc_info=context.error
        )
        
        # Store error in history
        self.error_history.append({
            'timestamp': datetime.now(),
            'error': str(context.error),
            'type': type(context.error).__name__
        })
        
        # Keep only recent errors
        if len(self.error_history) > self.max_error_logs:
            self.error_history = self.error_history[-self.max_error_logs:]
        
        # Get error details
        error = context.error
        error_type = type(error).__name__
        error_message = str(error)
        
        # Handle specific error types
        try:
            if isinstance(error, Forbidden):
                await self._handle_forbidden_error(update, context, error_message)
            elif isinstance(error, BadRequest):
                await self._handle_bad_request_error(update, context, error_message)
            elif isinstance(error, TimedOut):
                await self._handle_timeout_error(update, context)
            elif isinstance(error, NetworkError):
                await self._handle_network_error(update, context)
            elif isinstance(error, ChatMigrated):
                await self._handle_chat_migrated_error(update, context, error)
            elif isinstance(error, RetryAfter):
                await self._handle_retry_after_error(update, context, error)
            else:
                await self._handle_generic_error(update, context, error_type, error_message)
                
            # Notify admins of critical errors
            if self.error_count % 10 == 0:  # Every 10 errors
                await self._notify_admins_of_errors(context)
                
        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            
    async def _handle_forbidden_error(self, update, context, error_message):
        """Handle Forbidden errors (bot blocked, no permissions, etc.)"""
        logger.warning(f"Forbidden error: {error_message}")
        
        if "bot was blocked by the user" in error_message:
            # User blocked the bot
            if update and hasattr(update, 'effective_user'):
                user_id = update.effective_user.id
                logger.info(f"User {user_id} blocked the bot")
                # Could mark user as inactive in database
                
        elif "bot can't initiate conversation" in error_message:
            # Bot can't start conversation
            if update and hasattr(update, 'effective_chat'):
                if update.effective_chat.type in ['group', 'supergroup']:
                    try:
                        await context.bot.send_message(
                            update.effective_chat.id,
                            f"{EMOJI_ICONS['warning']} I can't send you a private message. Please start a chat with me first!"
                        )
                    except:
                        pass
                        
        elif "not enough rights" in error_message:
            # Bot lacks permissions in group
            logger.error(f"Bot lacks permissions: {error_message}")
            # Notify admins
            
    async def _handle_bad_request_error(self, update, context, error_message):
        """Handle BadRequest errors"""
        logger.warning(f"Bad request error: {error_message}")
        
        error_responses = {
            "message to edit not found": f"{EMOJI_ICONS['warning']} The message no longer exists.",
            "message is not modified": None,  # Silently ignore
            "query is too old": f"{EMOJI_ICONS['warning']} This button has expired. Please try again.",
            "message can't be deleted": f"{EMOJI_ICONS['warning']} Unable to delete message.",
            "message to delete not found": None,  # Already deleted
            "chat not found": f"{EMOJI_ICONS['error']} Group or chat not found.",
            "user not found": f"{EMOJI_ICONS['error']} User not found.",
            "message text is empty": f"{EMOJI_ICONS['error']} Cannot send empty message.",
            "reply message not found": f"{EMOJI_ICONS['error']} Original message not found.",
            "message too long": f"{EMOJI_ICONS['error']} Message is too long. Please shorten it.",
        }
        
        # Find matching error
        response = None
        for error_key, error_response in error_responses.items():
            if error_key.lower() in error_message.lower():
                response = error_response
                break
                
        if response and update and hasattr(update, 'effective_chat'):
            try:
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.answer(response, show_alert=True)
                else:
                    await context.bot.send_message(
                        update.effective_chat.id,
                        response
                    )
            except:
                pass
                
    async def _handle_timeout_error(self, update, context):
        """Handle timeout errors"""
        logger.warning("Timeout error occurred")
        
        if update and hasattr(update, 'effective_chat'):
            try:
                await context.bot.send_message(
                    update.effective_chat.id,
                    f"{EMOJI_ICONS['clock']} Request timed out. Please try again."
                )
            except:
                pass
                
    async def _handle_network_error(self, update, context):
        """Handle network errors"""
        logger.warning("Network error occurred")
        
        # Don't spam user with network errors
        # Just log and continue
        
    async def _handle_chat_migrated_error(self, update, context, error):
        """Handle chat migration (group to supergroup)"""
        logger.info(f"Chat migrated: {error}")
        
        # Update chat ID in database if needed
        if hasattr(error, 'new_chat_id'):
            new_id = error.new_chat_id
            logger.info(f"New chat ID: {new_id}")
            # Update configuration
            
    async def _handle_retry_after_error(self, update, context, error):
        """Handle rate limit errors"""
        retry_after = error.retry_after
        logger.warning(f"Rate limited. Retry after {retry_after} seconds")
        
        if update and hasattr(update, 'effective_chat'):
            try:
                await context.bot.send_message(
                    update.effective_chat.id,
                    f"{EMOJI_ICONS['warning']} Too many requests. Please wait {retry_after} seconds."
                )
            except:
                pass
                
    async def _handle_generic_error(self, update, context, error_type, error_message):
        """Handle all other errors"""
        logger.error(f"Unhandled error - Type: {error_type}, Message: {error_message}")
        
        # Full traceback for debugging
        if self.error_count <= self.max_error_logs:
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            
        # User-friendly error message
        if update and hasattr(update, 'effective_chat'):
            # Don't send error messages for every error to avoid spam
            # Only for important user-facing errors
            if "AttributeError" not in error_type and "KeyError" not in error_type:
                try:
                    error_text = f"""
{EMOJI_ICONS['error']} <b>Oops! Something went wrong</b>

Don't worry, our team has been notified.

{EMOJI_ICONS['refresh']} <i>Please try again in a moment.</i>
                    """.strip()
                    
                    if hasattr(update, 'callback_query') and update.callback_query:
                        await update.callback_query.answer(
                            "❌ An error occurred. Please try again.",
                            show_alert=True
                        )
                    else:
                        await context.bot.send_message(
                            update.effective_chat.id,
                            error_text,
                            parse_mode='HTML'
                        )
                except:
                    pass
                    
    async def _notify_admins_of_errors(self, context):
        """Notify admins when errors accumulate"""
        if not ADMIN_IDS:
            return
            
        # Get error summary
        recent_errors = self.error_history[-5:]  # Last 5 errors
        error_types = {}
        for error in self.error_history:
            error_type = error['type']
            error_types[error_type] = error_types.get(error_type, 0) + 1
            
        # Create summary message
        summary = f"""
{EMOJI_ICONS['warning']} <b>ERROR REPORT</b>

Total Errors: {self.error_count}

<b>Recent Errors:</b>
        """.strip()
        
        for error in recent_errors:
            time_str = error['timestamp'].strftime('%H:%M:%S')
            summary += f"\n• {time_str} - {error['type']}"
            
        summary += "\n\n<b>Error Types:</b>"
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5]:
            summary += f"\n• {error_type}: {count}"
            
        # Send to first admin
        try:
            await context.bot.send_message(
                ADMIN_IDS[0],
                summary,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
            
    async def handle_command_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                 command: str, error: Exception):
        """Handle specific command errors"""
        logger.error(f"Error in command {command}: {error}")
        
        user_id = update.effective_user.id if update.effective_user else None
        
        # Log command error
        await self._log_command_error(user_id, command, error)
        
        # Send user-friendly error message
        error_messages = {
            'start': "Failed to start. Please try again.",
            'bid': "Failed to place bid. Please check your syntax and try again.",
            'balance': "Failed to check balance. Please try again.",
            'help': "Failed to load help. Please try again.",
        }
        
        message = error_messages.get(command, f"Failed to execute {command}. Please try again.")
        
        try:
            await update.message.reply_text(
                f"{EMOJI_ICONS['error']} {message}"
            )
        except:
            pass
            
    async def _log_command_error(self, user_id: int, command: str, error: Exception):
        """Log command-specific errors"""
        logger.error(f"Command error - User: {user_id}, Command: {command}, Error: {error}")
        
    def get_error_stats(self) -> dict:
        """Get error statistics for monitoring"""
        if not self.error_history:
            return {
                'total_errors': 0,
                'error_rate': 0,
                'common_errors': [],
                'health_status': 'healthy'
            }
            
        # Calculate error rate (errors per hour)
        if self.error_history:
            time_span = (datetime.now() - self.error_history[0]['timestamp']).total_seconds() / 3600
            error_rate = len(self.error_history) / max(time_span, 1)
        else:
            error_rate = 0
            
        # Get common errors
        error_types = {}
        for error in self.error_history:
            error_type = error['type']
            error_types[error_type] = error_types.get(error_type, 0) + 1
            
        common_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Determine health status
        if error_rate < 5:
            health_status = 'healthy'
        elif error_rate < 20:
            health_status = 'degraded'
        else:
            health_status = 'critical'
            
        return {
            'total_errors': self.error_count,
            'error_rate': error_rate,
            'common_errors': common_errors,
            'health_status': health_status,
            'recent_errors': self.error_history[-10:]
        }
        
    async def log_auction_error(self, context: ContextTypes.DEFAULT_TYPE, 
                              error_type: str, details: dict):
        """Log auction-specific errors"""
        logger.error(f"Auction error - Type: {error_type}, Details: {details}")
        
        # Track auction errors separately
        auction_error = {
            'timestamp': datetime.now(),
            'type': error_type,
            'details': details
        }
        
        # Could store in database for analysis
        
    def clear_error_history(self):
        """Clear error history (for maintenance)"""
        self.error_history = []
        self.error_count = 0
        logger.info("Error history cleared")

    def require_context(context_type: str):
        """Decorator to enforce command context requirements"""
        def decorator(func):
            async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
                chat_type = update.effective_chat.type
                user_id = update.effective_user.id
                
                error_messages = {
                    'private_only': f"{EMOJI_ICONS['error']} This command only works in private chat!\nPlease DM me and try again.",
                    'group_only': f"{EMOJI_ICONS['error']} This command only works in groups!",
                    'auction_group_only': f"{EMOJI_ICONS['error']} This command only works in the auction group!",
                    'admin_only': f"{EMOJI_ICONS['error']} This command requires admin privileges!",
                    'dm_settings': f"{EMOJI_ICONS['warning']} Settings commands only work in private chat!\nPlease DM me and use the command again."
                }
                
                # Check context requirements
                if context_type == 'private_only' and chat_type != 'private':
                    await update.message.reply_text(error_messages.get('dm_settings' if 'settings' in update.message.text else 'private_only'))
                    return
                elif context_type == 'group_only' and chat_type not in ['group', 'supergroup']:
                    await update.message.reply_text(error_messages['group_only'])
                    return
                elif context_type == 'auction_group_only' and update.effective_chat.id != AUCTION_GROUP_ID:
                    await update.message.reply_text(error_messages['auction_group_only'])
                    return
                elif context_type == 'admin_only' and user_id not in ADMIN_IDS:
                    await update.message.reply_text(error_messages['admin_only'])
                    return
                    
                return await func(self, update, context)
            return wrapper
        return decorator