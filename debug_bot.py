#!/usr/bin/env python3
# debug_bot.py - Debug script for eFootball Auction Bot

import asyncio
import logging
from colorama import init, Fore, Style
import motor.motor_asyncio
from config.settings import *

# Initialize colorama
init()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mongodb():
    """Test MongoDB connection"""
    print(f"{Fore.YELLOW}Testing MongoDB connection...{Style.RESET_ALL}")
    try:
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        await client.admin.command('ping')
        print(f"{Fore.GREEN}✅ MongoDB connected successfully!{Style.RESET_ALL}")
        
        # List databases
        dbs = await client.list_database_names()
        print(f"{Fore.CYAN}Available databases: {dbs}{Style.RESET_ALL}")
        
        # Check if our database exists
        if DATABASE_NAME in dbs:
            print(f"{Fore.GREEN}✅ Database '{DATABASE_NAME}' exists{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}⚠️ Database '{DATABASE_NAME}' will be created on first use{Style.RESET_ALL}")
            
        return True
    except Exception as e:
        print(f"{Fore.RED}❌ MongoDB connection failed: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Make sure MongoDB is running with: sudo systemctl start mongod{Style.RESET_ALL}")
        return False

async def test_bot_token():
    """Test bot token validity"""
    print(f"\n{Fore.YELLOW}Testing bot token...{Style.RESET_ALL}")
    
    if not BOT_TOKEN:
        print(f"{Fore.RED}❌ BOT_TOKEN is not set in .env file{Style.RESET_ALL}")
        return False
        
    if len(BOT_TOKEN) < 40:
        print(f"{Fore.RED}❌ BOT_TOKEN appears to be invalid (too short){Style.RESET_ALL}")
        return False
        
    print(f"{Fore.GREEN}✅ BOT_TOKEN is configured (length: {len(BOT_TOKEN)}){Style.RESET_ALL}")
    return True

def test_environment():
    """Test environment variables"""
    print(f"\n{Fore.YELLOW}Checking environment variables...{Style.RESET_ALL}")
    
    required_vars = {
        'BOT_TOKEN': BOT_TOKEN,
        'SUPER_ADMIN_ID': SUPER_ADMIN_ID,
        'AUCTION_GROUP_ID': AUCTION_GROUP_ID,
        'DATA_GROUP_ID': DATA_GROUP_ID
    }
    
    all_good = True
    for var_name, var_value in required_vars.items():
        if var_value:
            if var_name == 'BOT_TOKEN':
                print(f"{Fore.GREEN}✅ {var_name}: ***...{var_value[-6:]}{Style.RESET_ALL}")
            else:
                print(f"{Fore.GREEN}✅ {var_name}: {var_value}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ {var_name}: Not set{Style.RESET_ALL}")
            all_good = False
            
    # Optional variables
    optional_vars = {
        'UNSOLD_GROUP_ID': UNSOLD_GROUP_ID,
        'REDIS_URL': getattr(settings, 'REDIS_URL', None) if 'settings' in globals() else None
    }
    
    print(f"\n{Fore.CYAN}Optional variables:{Style.RESET_ALL}")
    for var_name, var_value in optional_vars.items():
        if var_value:
            print(f"{Fore.GREEN}✅ {var_name}: {var_value}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}⚠️ {var_name}: Not set (optional){Style.RESET_ALL}")
            
    return all_good

def test_imports():
    """Test all imports"""
    print(f"\n{Fore.YELLOW}Testing imports...{Style.RESET_ALL}")
    
    imports_to_test = [
        ('telegram', 'python-telegram-bot'),
        ('motor', 'motor'),
        ('pymongo', 'pymongo'),
        ('bson', 'pymongo'),
        ('dotenv', 'python-dotenv'),
        ('redis', 'redis'),
        ('pandas', 'pandas'),
        ('PIL', 'Pillow')
    ]
    
    all_good = True
    for module_name, package_name in imports_to_test:
        try:
            __import__(module_name)
            print(f"{Fore.GREEN}✅ {module_name} ({package_name}){Style.RESET_ALL}")
        except ImportError:
            print(f"{Fore.RED}❌ {module_name} - Install with: pip install {package_name}{Style.RESET_ALL}")
            all_good = False
            
    return all_good

async def main():
    """Run all tests"""
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}eFootball Auction Bot - Debug Tool{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
    
    # Test imports
    imports_ok = test_imports()
    
    # Test environment
    env_ok = test_environment()
    
    # Test bot token
    token_ok = await test_bot_token()
    
    # Test MongoDB
    mongo_ok = await test_mongodb()
    
    # Summary
    print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Summary:{Style.RESET_ALL}")
    print(f"Imports: {'✅ OK' if imports_ok else '❌ Failed'}")
    print(f"Environment: {'✅ OK' if env_ok else '❌ Failed'}")
    print(f"Bot Token: {'✅ OK' if token_ok else '❌ Failed'}")
    print(f"MongoDB: {'✅ OK' if mongo_ok else '❌ Failed'}")
    
    if all([imports_ok, env_ok, token_ok, mongo_ok]):
        print(f"\n{Fore.GREEN}✅ All tests passed! You can run: python3 bot.py{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.RED}❌ Some tests failed. Please fix the issues above.{Style.RESET_ALL}")
        
        if not mongo_ok:
            print(f"\n{Fore.YELLOW}To start MongoDB:{Style.RESET_ALL}")
            print("  Ubuntu/Debian: sudo systemctl start mongod")
            print("  macOS: brew services start mongodb-community")
            print("  Or run directly: mongod --dbpath /path/to/data")

if __name__ == "__main__":
    asyncio.run(main())