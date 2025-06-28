# utilities/analytics.py - Advanced Analytics and Reporting
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
import json
from config.settings import TRACK_ANALYTICS, ACHIEVEMENTS
from database.models import Analytics

logger = logging.getLogger(__name__)

class AnalyticsManager:
    def __init__(self, db):
        self.db = db
        
    async def track_event(self, event_type: str, user_id: Optional[int] = None, 
                         data: Dict[str, Any] = None) -> None:
        """Track analytics event"""
        if not TRACK_ANALYTICS:
            return
            
        await self.db.track_event(event_type, user_id, data or {})
        
    async def get_auction_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive auction analytics"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get all auctions in period
        auctions = await self.db.auctions.find({
            "start_time": {"$gte": start_date, "$lte": end_date}
        }).to_list(None)
        
        if not auctions:
            return self._empty_analytics()
            
        # Calculate metrics
        total_auctions = len(auctions)
        completed_auctions = [a for a in auctions if a['status'] == 'completed']
        sold_auctions = [a for a in completed_auctions if a.get('current_bidder')]
        
        total_revenue = sum(a['current_bid'] for a in sold_auctions)
        avg_sale_price = total_revenue // len(sold_auctions) if sold_auctions else 0
        
        # Bidding patterns
        all_bids = []
        for auction in auctions:
            all_bids.extend(auction.get('bids', []))
            
        # Time analysis
        peak_hours = self._analyze_peak_hours(auctions)
        
        # Player analysis
        top_players = self._analyze_top_players(sold_auctions)
        
        # Manager analysis
        top_spenders = await self._analyze_top_spenders(sold_auctions)
        
        return {
            'period_days': days,
            'total_auctions': total_auctions,
            'completed_auctions': len(completed_auctions),
            'sold_count': len(sold_auctions),
            'unsold_count': len(completed_auctions) - len(sold_auctions),
            'sell_rate': (len(sold_auctions) / len(completed_auctions) * 100) if completed_auctions else 0,
            'total_revenue': total_revenue,
            'avg_sale_price': avg_sale_price,
            'total_bids': len(all_bids),
            'unique_bidders': len(set(bid.get('user_id') for bid in all_bids)),
            'avg_bids_per_auction': len(all_bids) / total_auctions if total_auctions else 0,
            'peak_hours': peak_hours,
            'top_players': top_players[:5],
            'top_spenders': top_spenders[:5]
        }
        
    async def get_manager_analytics(self, user_id: int) -> Dict[str, Any]:
        """Get detailed manager analytics"""
        manager = await self.db.get_manager(user_id)
        if not manager:
            return {}
            
        # Get user's auction history
        user_auctions = await self.db.auctions.find({
            "bids.user_id": user_id,
            "status": "completed"
        }).to_list(None)
        
        # Calculate metrics
        total_auctions_participated = len(user_auctions)
        won_auctions = [a for a in user_auctions if a.get('current_bidder') == user_id]
        
        # Bidding behavior
        all_user_bids = []
        for auction in user_auctions:
            user_bids = [b for b in auction.get('bids', []) if b.get('user_id') == user_id]
            all_user_bids.extend(user_bids)
            
        # Position preferences
        position_stats = self._analyze_position_preferences(won_auctions)
        
        # Time patterns
        bid_time_patterns = self._analyze_bid_timing(all_user_bids)
        
        # Financial analysis
        spending_trend = self._analyze_spending_trend(won_auctions)
        
        return {
            'user_id': user_id,
            'name': manager.name,
            'total_auctions': total_auctions_participated,
            'won_auctions': len(won_auctions),
            'win_rate': (len(won_auctions) / total_auctions_participated * 100) if total_auctions_participated else 0,
            'total_bids': len(all_user_bids),
            'avg_bids_per_auction': len(all_user_bids) / total_auctions_participated if total_auctions_participated else 0,
            'total_spent': manager.total_spent,
            'current_balance': manager.balance,
            'squad_size': len(manager.players),
            'position_preferences': position_stats,
            'bid_timing': bid_time_patterns,
            'spending_trend': spending_trend,
            'achievements_unlocked': len(manager.achievements),
            'current_level': manager.statistics.get('level', 1),
            'total_points': manager.statistics.get('points', 0)
        }
        
    async def generate_session_report(self, session_id: str) -> Dict[str, Any]:
        """Generate comprehensive session report"""
        session = await self.db.sessions.find_one({"session_id": session_id})
        if not session:
            return {}
            
        # Get all auctions in session
        session_auctions = await self.db.auctions.find({
            "start_time": {
                "$gte": session['start_time'],
                "$lte": session.get('end_time', datetime.now())
            }
        }).to_list(None)
        
        # Manager performance
        manager_stats = defaultdict(lambda: {
            'auctions_won': 0,
            'total_spent': 0,
            'players': []
        })
        
        for auction in session_auctions:
            if auction.get('current_bidder'):
                winner_id = auction['current_bidder']
                manager_stats[winner_id]['auctions_won'] += 1
                manager_stats[winner_id]['total_spent'] += auction['current_bid']
                manager_stats[winner_id]['players'].append(auction['player_name'])
                
        # Convert manager stats
        manager_rankings = []
        for user_id, stats in manager_stats.items():
            manager = await self.db.get_manager(user_id)
            if manager:
                manager_rankings.append({
                    'name': manager.name,
                    'auctions_won': stats['auctions_won'],
                    'total_spent': stats['total_spent'],
                    'avg_per_player': stats['total_spent'] // stats['auctions_won'] if stats['auctions_won'] else 0,
                    'players': stats['players']
                })
                
        # Sort by total spent
        manager_rankings.sort(key=lambda x: x['total_spent'], reverse=True)
        
        return {
            'session_id': session_id,
            'session_name': session['name'],
            'duration': self._calculate_session_duration(session),
            'total_auctions': len(session_auctions),
            'sold_players': session.get('sold_players', 0),
            'unsold_players': session.get('unsold_players', 0),
            'total_revenue': session.get('total_money_spent', 0),
            'participating_managers': len(session.get('participating_managers', [])),
            'manager_rankings': manager_rankings,
            'avg_auction_duration': self._calculate_avg_auction_duration(session_auctions),
            'highest_sale': self._find_highest_sale(session_auctions),
            'best_value': self._find_best_value(session_auctions)
        }
        
    async def update_hourly_stats(self) -> None:
        """Update hourly statistics (for background task)"""
        try:
            current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
            
            # Get hourly metrics
            hourly_auctions = await self.db.auctions.count_documents({
                "start_time": {
                    "$gte": current_hour,
                    "$lt": current_hour + timedelta(hours=1)
                }
            })
            
            # Store hourly stats
            await self.db.analytics.insert_one({
                'type': 'hourly_stats',
                'hour': current_hour,
                'auction_count': hourly_auctions,
                'timestamp': datetime.now()
            })
            
        except Exception as e:
            logger.error(f"Error updating hourly stats: {e}")
            
    def _empty_analytics(self) -> Dict[str, Any]:
        """Return empty analytics structure"""
        return {
            'period_days': 0,
            'total_auctions': 0,
            'completed_auctions': 0,
            'sold_count': 0,
            'unsold_count': 0,
            'sell_rate': 0,
            'total_revenue': 0,
            'avg_sale_price': 0,
            'total_bids': 0,
            'unique_bidders': 0,
            'avg_bids_per_auction': 0,
            'peak_hours': {},
            'top_players': [],
            'top_spenders': []
        }
        
    def _analyze_peak_hours(self, auctions: List[dict]) -> Dict[int, int]:
        """Analyze peak auction hours"""
        hour_counts = defaultdict(int)
        
        for auction in auctions:
            hour = auction['start_time'].hour
            hour_counts[hour] += 1
            
        # Return top 5 hours
        sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_hours[:5])
        
    def _analyze_top_players(self, sold_auctions: List[dict]) -> List[Dict[str, Any]]:
        """Analyze top selling players"""
        players = []
        
        for auction in sold_auctions:
            players.append({
                'name': auction['player_name'],
                'price': auction['current_bid'],
                'base_price': auction['base_price'],
                'profit': auction['current_bid'] - auction['base_price'],
                'bid_count': len(auction.get('bids', []))
            })
            
        # Sort by price
        players.sort(key=lambda x: x['price'], reverse=True)
        return players
        
    async def _analyze_top_spenders(self, sold_auctions: List[dict]) -> List[Dict[str, Any]]:
        """Analyze top spending managers"""
        spender_stats = defaultdict(lambda: {'total': 0, 'count': 0})
        
        for auction in sold_auctions:
            if auction.get('current_bidder'):
                spender_stats[auction['current_bidder']]['total'] += auction['current_bid']
                spender_stats[auction['current_bidder']]['count'] += 1
                
        # Get manager names
        top_spenders = []
        for user_id, stats in spender_stats.items():
            manager = await self.db.get_manager(user_id)
            if manager:
                top_spenders.append({
                    'name': manager.name,
                    'total_spent': stats['total'],
                    'players_bought': stats['count'],
                    'avg_per_player': stats['total'] // stats['count']
                })
                
        # Sort by total spent
        top_spenders.sort(key=lambda x: x['total_spent'], reverse=True)
        return top_spenders
        
    def _analyze_position_preferences(self, won_auctions: List[dict]) -> Dict[str, int]:
        """Analyze position preferences of a manager"""
        position_counts = defaultdict(int)
        
        for auction in won_auctions:
            player_data = auction.get('player_data', {})
            position = player_data.get('position', 'Unknown')
            position_counts[position] += 1
            
        return dict(position_counts)
        
    def _analyze_bid_timing(self, bids: List[dict]) -> Dict[str, Any]:
        """Analyze when user typically places bids"""
        time_slots = defaultdict(int)
        
        for bid in bids:
            timestamp = bid.get('timestamp', datetime.now())
            hour = timestamp.hour
            
            if 6 <= hour < 12:
                time_slots['morning'] += 1
            elif 12 <= hour < 17:
                time_slots['afternoon'] += 1
            elif 17 <= hour < 21:
                time_slots['evening'] += 1
            else:
                time_slots['night'] += 1
                
        return dict(time_slots)
        
    def _analyze_spending_trend(self, won_auctions: List[dict]) -> List[Dict[str, Any]]:
        """Analyze spending trend over time"""
        # Group by date
        daily_spending = defaultdict(lambda: {'total': 0, 'count': 0})
        
        for auction in won_auctions:
            date = auction['end_time'].date() if auction.get('end_time') else auction['start_time'].date()
            daily_spending[date]['total'] += auction['current_bid']
            daily_spending[date]['count'] += 1
            
        # Convert to list
        trend = []
        for date, stats in sorted(daily_spending.items()):
            trend.append({
                'date': date.isoformat(),
                'total_spent': stats['total'],
                'players_bought': stats['count'],
                'avg_price': stats['total'] // stats['count'] if stats['count'] else 0
            })
            
        return trend[-7:]  # Last 7 days
        
    def _calculate_session_duration(self, session: dict) -> str:
        """Calculate session duration"""
        if session.get('end_time'):
            duration = session['end_time'] - session['start_time']
        else:
            duration = datetime.now() - session['start_time']
            
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        
        return f"{hours}h {minutes}m"
        
    def _calculate_avg_auction_duration(self, auctions: List[dict]) -> int:
        """Calculate average auction duration in seconds"""
        if not auctions:
            return 0
            
        total_duration = 0
        count = 0
        
        for auction in auctions:
            if auction.get('end_time'):
                duration = (auction['end_time'] - auction['start_time']).seconds
                total_duration += duration
                count += 1
                
        return total_duration // count if count else 0
        
    def _find_highest_sale(self, auctions: List[dict]) -> Optional[Dict[str, Any]]:
        """Find highest sale in auctions"""
        sold_auctions = [a for a in auctions if a.get('current_bidder')]
        if not sold_auctions:
            return None
            
        highest = max(sold_auctions, key=lambda x: x['current_bid'])
        return {
            'player': highest['player_name'],
            'price': highest['current_bid'],
            'winner_id': highest['current_bidder']
        }
        
    def _find_best_value(self, auctions: List[dict]) -> Optional[Dict[str, Any]]:
        """Find best value purchase (lowest price relative to base)"""
        sold_auctions = [a for a in auctions if a.get('current_bidder')]
        if not sold_auctions:
            return None
            
        # Calculate price to base ratio
        for auction in sold_auctions:
            auction['value_ratio'] = auction['current_bid'] / auction['base_price']
            
        best_value = min(sold_auctions, key=lambda x: x['value_ratio'])
        return {
            'player': best_value['player_name'],
            'price': best_value['current_bid'],
            'base_price': best_value['base_price'],
            'discount': int((1 - best_value['value_ratio']) * 100)
        }
    
    async def generate_csv_report(self, report_data: dict) -> bytes:
        """Generate CSV report"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['Auction Report'])
        writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])
        
        # Session summary
        if 'session_info' in report_data:
            session = report_data['session_info']
            writer.writerow(['Session Summary'])
            writer.writerow(['Session ID', session.get('session_id', 'N/A')])
            writer.writerow(['Duration', session.get('duration', 'N/A')])
            writer.writerow(['Total Auctions', session.get('total_auctions', 0)])
            writer.writerow(['Sold Players', session.get('sold_players', 0)])
            writer.writerow(['Total Revenue', session.get('total_revenue', 0)])
            writer.writerow([])
        
        # Manager rankings
        if 'manager_rankings' in report_data:
            writer.writerow(['Manager Rankings'])
            writer.writerow(['Rank', 'Name', 'Players Won', 'Total Spent', 'Points'])
            
            for i, manager in enumerate(report_data['manager_rankings'], 1):
                writer.writerow([
                    i,
                    manager['name'],
                    manager.get('auctions_won', 0),
                    manager.get('total_spent', 0),
                    manager.get('points', 0)
                ])
            writer.writerow([])
        
        # Auction details
        if 'auctions' in report_data:
            writer.writerow(['Auction Details'])
            writer.writerow(['Player', 'Base Price', 'Final Price', 'Winner', 'Bids', 'Duration'])
            
            for auction in report_data['auctions']:
                writer.writerow([
                    auction.get('player_name', 'Unknown'),
                    auction.get('base_price', 0),
                    auction.get('final_price', 0),
                    auction.get('winner_name', 'Unsold'),
                    auction.get('bid_count', 0),
                    f"{auction.get('duration', 0)}s"
                ])
        
        # Convert to bytes
        output.seek(0)
        return output.getvalue().encode('utf-8')

    async def generate_pdf_report(self, report_data: dict) -> bytes:
        """Generate PDF report (placeholder - requires additional library)"""
        # This would require a PDF library like reportlab
        # For now, return a simple text representation
        text_report = f"""
    EFOOTBALL AUCTION REPORT
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    {'='*50}

    SESSION SUMMARY
    Session ID: {report_data.get('session_id', 'N/A')}
    Duration: {report_data.get('duration', 'N/A')}
    Total Auctions: {report_data.get('total_auctions', 0)}
    Sold Players: {report_data.get('sold_players', 0)}
    Total Revenue: {report_data.get('total_revenue', 0)}

    {'='*50}

    TOP MANAGERS
    {"Rank":<6} {"Name":<20} {"Spent":<15} {"Players":<10}
    {'-'*50}
        """
        
        for i, manager in enumerate(report_data.get('manager_rankings', [])[:10], 1):
            text_report += f"{i:<6} {manager['name']:<20} {manager['total_spent']:<15} {manager['auctions_won']:<10}\n"
        
        return text_report.encode('utf-8')