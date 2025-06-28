# utilities/formatters.py - Enhanced Message Formatting with Visual Elements
from datetime import datetime
from typing import List, Optional
from config.settings import *
from database.models import Manager, Auction, Player

class MessageFormatter:
    def __init__(self):
        self.icons = EMOJI_ICONS
        self.bars = PROGRESS_BARS
        
    def format_admin_welcome(self, name: str) -> str:
        """Format admin welcome message with visual flair"""
        return f"""
{self.icons['sparkles']} <b>WELCOME ADMIN</b> {self.icons['sparkles']}

{self.icons['admin']} <b>Admin:</b> {name}
{self.icons['crown']} <b>Access Level:</b> Full Control

{self.icons['rocket']} <b>Quick Actions:</b>
• Start auctions instantly
• Manage all managers
• View detailed analytics
• Configure bot settings

{self.icons['fire']} <i>Let's make this auction legendary!</i>
        """.strip()
        
    def format_manager_welcome(self, manager: Manager) -> str:
        """Format manager welcome with stats"""
        level_bar = self._get_level_progress(manager.statistics.get('points', 0))
        
        return f"""
{self.icons['trophy']} <b>WELCOME BACK!</b> {self.icons['trophy']}

{self.icons['user']} <b>{manager.name}</b>
{self.icons['gem']} Level {manager.statistics.get('level', 1)} {level_bar}

{self.icons['money']} <b>Balance:</b> {self.format_currency(manager.balance)}
{self.icons['team']} <b>Squad:</b> {len(manager.players)}/11 players
{self.icons['star']} <b>Points:</b> {manager.statistics.get('points', 0)}

{self.icons['target']} <i>Ready to dominate the auction?</i>
        """.strip()
        
    def format_unregistered_welcome(self, name: str) -> str:
        """Format unregistered user welcome"""
        return f"""
{self.icons['wave']} <b>HELLO {name.upper()}!</b>

{self.icons['info']} You're not registered yet.

To participate in auctions, you need to be added as a manager by an admin.

{self.icons['sparkles']} <b>What's this bot?</b>
• Live player auctions
• Build your dream team
• Compete with others
• Win achievements

{self.icons['bell']} <i>Request access to join the fun!</i>
        """.strip()
        
    def format_auction_start(self, player_name: str, base_price: int) -> str:
        """Format auction start announcement"""
        return f"""
{self.icons['hammer']} <b>NEW AUCTION STARTED!</b> {self.icons['hammer']}

{self.icons['fire']} {self.icons['fire']} {self.icons['fire']} {self.icons['fire']} {self.icons['fire']}

{self.icons['player']} <b>PLAYER:</b> {player_name.upper()}
{self.icons['moneybag']} <b>BASE PRICE:</b> {self.format_currency(base_price)}

{self.icons['bell']} <b>BIDDING IS NOW OPEN!</b>

{self.icons['lightning']} <i>Place your bids before time runs out!</i>
        """.strip()
        
    def format_new_bid(self, player_name: str, bidder_name: str, amount: int, time_left: Optional[int] = None) -> str:
        """Format new bid announcement with urgency"""
        urgency = ""
        if time_left and time_left <= 10:
            urgency = f"\n\n{self.icons['warning']} <b>FINAL SECONDS!</b> {self.icons['warning']}"
        elif time_left and time_left <= 30:
            urgency = f"\n\n{self.icons['timer']} Time is running out!"
            
        return f"""
{self.icons['chart_up']} <b>NEW BID!</b> {self.icons['chart_up']}

{self.icons['player']} <b>Player:</b> {player_name}
{self.icons['moneybag']} <b>Amount:</b> {self.format_currency(amount)}
{self.icons['crown']} <b>Leader:</b> {bidder_name}
{urgency}

{self.icons['target']} <i>Can you beat this?</i>
        """.strip()
        
    def format_auction_won(self, player_name: str, winner_name: str, final_price: int) -> str:
        """Format auction won message with celebration"""
        profit_margin = self._calculate_profit_margin(final_price)
        
        return f"""
{self.icons['trophy']} {self.icons['trophy']} <b>SOLD!</b> {self.icons['trophy']} {self.icons['trophy']}

{self.icons['celebration']} {self.icons['sparkles']} {self.icons['star']} {self.icons['sparkles']} {self.icons['celebration']}

{self.icons['player']} <b>{player_name.upper()}</b>
{self.icons['winner']} <b>WINNER:</b> {winner_name}
{self.icons['moneybag']} <b>PRICE:</b> {self.format_currency(final_price)}

{profit_margin}

{self.icons['fire']} <i>Congratulations on the signing!</i>
        """.strip()
        
    def format_auction_unsold(self, player_name: str) -> str:
        """Format unsold player message"""
        return f"""
{self.icons['warning']} <b>UNSOLD</b> {self.icons['warning']}

{self.icons['player']} <b>Player:</b> {player_name}
{self.icons['info']} No bids received

{self.icons['arrow_right']} Moving to unsold pool

{self.icons['lightbulb']} <i>Maybe next time!</i>
        """.strip()
        
    def format_balance_check(self, manager: Manager) -> str:
        """Format balance check with visual bars"""
        balance_percentage = (manager.balance / DEFAULT_BALANCE) * 100
        balance_bar = self.create_progress_bar(balance_percentage, 10)
        
        return f"""
{self.icons['money']} <b>YOUR BALANCE</b>

{self.icons['user']} <b>Manager:</b> {manager.name}
{self.icons['gem']} <b>Level:</b> {manager.statistics.get('level', 1)}

{self.icons['moneybag']} <b>Available:</b>
{self.format_currency(manager.balance)}
{balance_bar} {balance_percentage:.0f}%

{self.icons['chart']} <b>Statistics:</b>
• Spent: {self.format_currency(manager.total_spent)}
• Players: {len(manager.players)}
• Win Rate: {manager.statistics.get('win_rate', 0):.1f}%

{self.icons['clock']} <i>Updated: {datetime.now().strftime('%H:%M:%S')}</i>
        """.strip()
        
    def format_managers_list(self, managers: List[Manager]) -> str:
        """Format managers list with rankings"""
        msg = f"{self.icons['trophy']} <b>MANAGER RANKINGS</b>\n\n"
        
        # Sort by points
        managers.sort(key=lambda x: x.statistics.get('points', 0), reverse=True)
        
        for i, manager in enumerate(managers[:10], 1):
            # Rank emoji
            if i <= len(LEADERBOARD_EMOJIS):
                rank = LEADERBOARD_EMOJIS[i-1]
            else:
                rank = f"{i}."
                
            points = manager.statistics.get('points', 0)
            balance_display = self.format_currency(manager.balance)
            
            msg += f"{rank} <b>{manager.name}</b>\n"
            msg += f"   {self.icons['star']} {points} pts | "
            msg += f"{self.icons['money']} {balance_display} | "
            msg += f"{self.icons['team']} {len(manager.players)} players\n\n"
            
        return msg.strip()
        
    def format_auction_status(self, auction: Auction) -> str:
        """Format current auction status"""
        bidder_count = len(set(bid.user_id for bid in auction.bids))
        competition_level = self._get_competition_level(bidder_count)
        
        msg = f"""
{self.icons['fire']} <b>AUCTION STATUS</b>

{self.icons['player']} <b>Player:</b> {auction.player_name}
{self.icons['money']} <b>Base:</b> {self.format_currency(auction.base_price)}
{self.icons['chart_up']} <b>Current:</b> {self.format_currency(auction.current_bid)}

{self.icons['team']} <b>Bidders:</b> {bidder_count} {competition_level}
{self.icons['timer']} <b>Status:</b> {auction.status.upper()}
{self.icons['gear']} <b>Mode:</b> {auction.mode.upper()}
        """
        
        if auction.current_bidder:
            msg += f"\n{self.icons['crown']} <b>Leader:</b> Check auction group"
            
        return msg.strip()
        
    def format_bid_error(self, error_type: str, details: str = "") -> str:
        """Format bid error messages with helpful context"""
        base_errors = {
            'invalid_amount': f"{self.icons['error']} <b>Invalid Amount!</b>\n{details}",
            'insufficient_balance': f"{self.icons['error']} <b>Insufficient Balance!</b>\n{details}",
            'same_amount': f"{self.icons['warning']} <b>Same Bid!</b>\nBid must be higher than current.",
            'too_low': f"{self.icons['warning']} <b>Too Low!</b>\n{details}",
            'not_registered': f"{self.icons['error']} <b>Not Registered!</b>\nContact admin to register.",
            'no_auction': f"{self.icons['info']} <b>No Active Auction!</b>\nWait for next auction.",
            'auction_ended': f"{self.icons['error']} <b>Auction Ended!</b>\nToo late to bid."
        }
        
        error_msg = base_errors.get(error_type, f"{self.icons['error']} Unknown error!")
        
        # Add helpful tips
        if error_type == 'invalid_amount':
            error_msg += f"\n\n{self.icons['tip']} Try: /bid 15 (for 15M)"
        elif error_type == 'insufficient_balance':
            error_msg += f"\n\n{self.icons['tip']} Check: /balance"
            
        return error_msg
        
    def format_currency(self, amount: int) -> str:
        """Format currency with proper notation"""
        if amount >= 1_000_000_000:  # Billion
            return f"₹{amount / 1_000_000_000:.1f}B"
        elif amount >= 1_000_000:  # Million
            return f"₹{amount / 1_000_000:.1f}M"
        elif amount >= 1_000:  # Thousand
            return f"₹{amount / 1_000:.1f}K"
        else:
            return f"₹{amount}"
            
    def format_final_results(self, managers: List[Manager]) -> str:
        """Format final auction results with summary"""
        total_spent = sum(m.total_spent for m in managers)
        total_players = sum(len(m.players) for m in managers)
        active_managers = len([m for m in managers if m.players])
        
        msg = f"""
{self.icons['trophy']} <b>FINAL RESULTS</b> {self.icons['trophy']}

{self.icons['chart']} <b>AUCTION SUMMARY</b>
• Total Managers: {len(managers)}
• Active Bidders: {active_managers}
• Players Sold: {total_players}
• Total Revenue: {self.format_currency(total_spent)}

{self.icons['medal']} <b>TOP SPENDERS</b>
        """.strip()
        
        # Top 3 spenders
        top_spenders = sorted(managers, key=lambda m: m.total_spent, reverse=True)[:3]
        medals = ['🥇', '🥈', '🥉']
        
        for i, manager in enumerate(top_spenders):
            if manager.total_spent > 0:
                msg += f"\n{medals[i]} {manager.name} - {self.format_currency(manager.total_spent)}"
                
        # Best value team
        value_teams = [(m, m.total_spent/len(m.players)) for m in managers if m.players]
        if value_teams:
            best_value = min(value_teams, key=lambda x: x[1])
            msg += f"\n\n{self.icons['star']} <b>BEST VALUE</b>"
            msg += f"\n{best_value[0].name} - {self.format_currency(int(best_value[1]))}/player"
            
        return msg
        
    def create_progress_bar(self, percentage: float, length: int = 10) -> str:
        """Create visual progress bar"""
        filled = int((percentage / 100) * length)
        empty = length - filled
        
        bar = self.bars['filled'] * filled + self.bars['empty'] * empty
        
        # Add color based on percentage
        if percentage >= 75:
            return f"🟢 {bar}"
        elif percentage >= 50:
            return f"🟡 {bar}"
        elif percentage >= 25:
            return f"🟠 {bar}"
        else:
            return f"🔴 {bar}"
            
    def _get_level_progress(self, points: int) -> str:
        """Get level progress visualization"""
        level_thresholds = [0, 50, 150, 300, 500, 1000, 2000, 5000]
        current_level = 1
        
        for i, threshold in enumerate(level_thresholds[1:], 1):
            if points >= threshold:
                current_level = i + 1
            else:
                # Calculate progress to next level
                prev_threshold = level_thresholds[i-1]
                progress = ((points - prev_threshold) / (threshold - prev_threshold)) * 100
                return self.create_progress_bar(progress, 5)
                
        return self.create_progress_bar(100, 5)
        
    def _calculate_profit_margin(self, price: int) -> str:
        """Calculate profit margin indicator"""
        if price < 10_000_000:
            return f"{self.icons['gem']} <b>BARGAIN BUY!</b>"
        elif price < 30_000_000:
            return f"{self.icons['star']} <b>GOOD DEAL!</b>"
        elif price < 50_000_000:
            return f"{self.icons['money']} <b>MARKET VALUE!</b>"
        else:
            return f"{self.icons['fire']} <b>PREMIUM SIGNING!</b>"
            
    def _get_competition_level(self, bidder_count: int) -> str:
        """Get competition level indicator"""
        if bidder_count <= 2:
            return "🟢 Low"
        elif bidder_count <= 5:
            return "🟡 Medium"
        elif bidder_count <= 8:
            return "🟠 High"
        else:
            return "🔴 Intense!"
            
    def format_achievement_unlock(self, achievement_id: str) -> str:
        """Format achievement unlock notification"""
        ach_data = ACHIEVEMENTS.get(achievement_id, {})
        
        return f"""
{self.icons['celebration']} <b>ACHIEVEMENT UNLOCKED!</b> {self.icons['celebration']}

{ach_data.get('emoji', '🏆')} <b>{ach_data.get('name', 'Unknown')}</b>

+{ach_data.get('points', 0)} points

{self.icons['sparkles']} <i>Keep up the great work!</i>
        """.strip()