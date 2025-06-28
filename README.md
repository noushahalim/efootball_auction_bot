# 🏆 eFootball Auction Bot v2.0

A sophisticated Telegram bot for managing live player auctions in eFootball leagues, featuring real-time bidding, visual countdowns, achievements, and comprehensive analytics.

![Python](https://img.shields.io/badge/python-v3.9+-blue.svg)
![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-v20.7-blue.svg)
![MongoDB](https://img.shields.io/badge/MongoDB-v4.4+-green.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🌟 Features

### Core Features
- **🔥 Real-time Auctions**: Live player auctions with visual countdown timers
- **💰 Smart Bidding**: Quick bid buttons, auto-increment, and bid validation
- **👥 Manager System**: Balance tracking, team building, and player portfolios
- **🎯 Achievements**: Unlock rewards and track progress
- **📊 Analytics**: Comprehensive statistics and insights
- **🏅 Leaderboards**: Competitive rankings and seasonal competitions

### Visual Enhancements
- **⏰ Dynamic Countdowns**: Visual progress bars and urgency indicators
- **🎨 Rich Messages**: Formatted messages with emojis and visual elements
- **📈 Live Updates**: Real-time bid updates without spam
- **🎉 Celebrations**: Animated victory messages and achievements

### Admin Features
- **🔨 Auction Control**: Start, pause, resume, and manage auctions
- **👤 Manager Management**: Add/remove managers, adjust balances
- **📊 Reports**: Generate detailed session and auction reports
- **⚙️ Settings**: Configure timers, modes, and auction parameters
- **📢 Broadcasts**: Send announcements to all managers

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- MongoDB 4.4+
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Redis (optional, for caching)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/efootball-auction-bot.git
cd efootball-auction-bot
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Set up MongoDB**
```bash
# Start MongoDB (if not running)
mongod --dbpath /path/to/data

# The bot will create indexes automatically
```

6. **Run the bot**
```bash
python bot.py
```

## 📋 Configuration

### Environment Variables
Edit `.env` file with your settings:

```env
# Required
BOT_TOKEN=your_bot_token_here
SUPER_ADMIN_ID=your_telegram_id
AUCTION_GROUP_ID=-100xxxxxxxxxx
DATA_GROUP_ID=-100xxxxxxxxxx

# Optional
MONGODB_URI=mongodb://localhost:27017/
DATABASE_NAME=efootball_auction
```

### Getting Group IDs
1. Add [@userinfobot](https://t.me/userinfobot) to your group
2. The bot will show the group ID
3. For supergroups, the format is `-100xxxxxxxxxx`

## 📱 Usage Guide

### For Admins

#### Starting an Auction
1. **From Data Group**: Forward player message to data group with format:
   ```
   'Player Name' price
   Example: 'Messi' 50
   ```

2. **Quick Start**: Use `/start_auction` command

3. **From Message**: `/start_auction message_id`

#### Managing Auctions
- `/stop_auction` - Pause current auction
- `/continue_auction` - Resume paused auction
- `/skip_bid` - Mark player as unsold
- `/final_call` - Final call (manual mode)
- `/undo_bid` - Undo last bid

#### Admin Commands
- `/settings` - Open settings menu (DM only)
- `/managers` - View all managers
- `/auction_result` - Get final results
- `/broadcast message` - Send announcement

### For Managers

#### Bidding
- `/bid amount` - Place a bid
  - Examples: `/bid 15` (for 15M), `/bid +5` (current + 5M)
- Use quick bid buttons for faster bidding
- Watch your balance!

#### Commands
- `/start` - Open main menu
- `/balance` - Check your balance
- `/mystats` - View detailed statistics
- `/leaderboard` - See top managers
- `/help` - Get help

## 🏗️ Project Structure

```
efootball_auction_bot/
├── bot.py                    # Main entry point
├── config/
│   └── settings.py          # Configuration and constants
├── database/
│   ├── db.py               # Database operations
│   └── models.py           # Data models
├── handlers/
│   ├── admin_handlers.py   # Admin command handlers
│   ├── user_handlers.py    # User command handlers
│   ├── callback_handlers.py # Button callback handlers
│   ├── auction_handlers.py # Auction-specific handlers
│   └── error_handlers.py   # Error handling
├── utilities/
│   ├── formatters.py       # Message formatting
│   ├── helpers.py          # Validation and utilities
│   ├── countdown.py        # Timer management
│   ├── analytics.py        # Analytics and reporting
│   └── animations.py       # Visual effects
├── requirements.txt         # Python dependencies
├── .env.example            # Environment template
└── README.md               # Documentation
```

## 🎮 Game Modes

### Auto Mode (Default)
- Automatic timer countdown
- Auction ends when timer expires
- Configurable duration (default: 60s)

### Manual Mode
- Admin controls auction flow
- Use `/final_call` to end auction
- More control over pacing

## 🏆 Achievement System

Managers can unlock achievements:
- 🎯 **First Blood**: Place your first bid
- 🏆 **Winner Winner**: Win your first auction
- ⚔️ **Bid Warrior**: Win 10 auctions
- 💎 **Big Spender**: Spend over 100M
- ⭐ **Perfect XI**: Build a team of 11 players
- 👑 **Auction Master**: Win 50 auctions

## 📊 Analytics Features

### For Managers
- Personal statistics and trends
- Bidding patterns analysis
- Win rate tracking
- Position preferences

### For Admins
- Session summaries
- Revenue reports
- Peak hour analysis
- Manager rankings
- Auction success rates

## 🔧 Advanced Configuration

### Auction Settings
Edit in `settings.py`:
```python
DEFAULT_BALANCE = 200_000_000  # Starting balance
BID_INCREMENT = 1_000_000      # Minimum increment
AUCTION_TIMER = 60             # Seconds
```

### Visual Customization
Modify emojis and animations in `settings.py`:
```python
EMOJI_ICONS = {
    'fire': '🔥',
    'money': '💰',
    # Add custom emojis
}
```

## 🐛 Troubleshooting

### Common Issues

1. **"No valid player data found"**
   - Check message format: `'Player Name' price`
   - Ensure quotes around player name

2. **Bot not responding in groups**
   - Verify bot is admin in groups
   - Check group IDs in `.env`

3. **Database connection errors**
   - Ensure MongoDB is running
   - Check `MONGODB_URI` in `.env`

### Debug Mode
Enable debug logging:
```env
DEBUG=True
LOG_LEVEL=DEBUG
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📈 Roadmap

- [ ] Web dashboard for analytics
- [ ] Mobile app integration
- [ ] AI-powered bid recommendations
- [ ] Voice command support
- [ ] Multi-language support
- [ ] Custom team formations
- [ ] Season-long tournaments
- [ ] Trading system

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Telegram Bot API documentation
- MongoDB documentation
- Python-telegram-bot community
- All contributors and testers

## 📞 Support

- Create an issue on GitHub
- Contact: [@YourTelegramUsername](https://t.me/YourUsername)
- Email: your.email@example.com

---

Made with ❤️ for the eFootball community