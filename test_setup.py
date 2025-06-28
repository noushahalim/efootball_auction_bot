# test_setup.py - Test if all dependencies are properly installed

import sys
import importlib
from colorama import init, Fore, Style

# Initialize colorama for colored output
init()

def test_import(module_name, package_name=None):
    """Test if a module can be imported"""
    try:
        if package_name:
            importlib.import_module(module_name, package=package_name)
        else:
            importlib.import_module(module_name)
        print(f"{Fore.GREEN}✅ {module_name}{Style.RESET_ALL}")
        return True
    except ImportError as e:
        print(f"{Fore.RED}❌ {module_name}: {e}{Style.RESET_ALL}")
        return False

def main():
    print(f"{Fore.CYAN}🔍 Testing eFootball Auction Bot Setup{Style.RESET_ALL}")
    print("=" * 40)
    
    # Test Python version
    print(f"\n{Fore.YELLOW}Python Version:{Style.RESET_ALL}")
    python_version = sys.version_info
    if python_version >= (3, 9):
        print(f"{Fore.GREEN}✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}❌ Python 3.9+ required, you have {python_version.major}.{python_version.minor}{Style.RESET_ALL}")
    
    # Test core dependencies
    print(f"\n{Fore.YELLOW}Core Dependencies:{Style.RESET_ALL}")
    core_deps = [
        'telegram',
        'telegram.ext',
        'motor',
        'motor.motor_asyncio',
        'pymongo',
        'bson',
        'dotenv',
        'asyncio',
    ]
    
    all_good = True
    for dep in core_deps:
        if not test_import(dep):
            all_good = False
    
    # Test optional dependencies
    print(f"\n{Fore.YELLOW}Optional Dependencies:{Style.RESET_ALL}")
    optional_deps = [
        'redis',
        'aioredis',
        'pandas',
        'numpy',
        'PIL',
        'colorlog',
        'pytz',
    ]
    
    for dep in optional_deps:
        test_import(dep)
    
    # Test local modules
    print(f"\n{Fore.YELLOW}Local Modules:{Style.RESET_ALL}")
    local_modules = [
        'config.settings',
        'database.db',
        'database.models',
        'handlers.admin_handlers',
        'handlers.user_handlers',
        'handlers.error_handlers',
        'handlers.callback_handlers',
        'handlers.auction_handlers',
        'utilities.formatters',
        'utilities.helpers',
        'utilities.countdown',
        'utilities.analytics',
        'utilities.animations',
    ]
    
    for module in local_modules:
        if not test_import(module):
            all_good = False
    
    # Test environment variables
    print(f"\n{Fore.YELLOW}Environment Variables:{Style.RESET_ALL}")
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    required_env = [
        'BOT_TOKEN',
        'SUPER_ADMIN_ID',
        'AUCTION_GROUP_ID',
        'DATA_GROUP_ID',
    ]
    
    for env in required_env:
        if os.getenv(env):
            print(f"{Fore.GREEN}✅ {env} is set{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ {env} is not set{Style.RESET_ALL}")
            all_good = False
    
    # Final result
    print("\n" + "=" * 40)
    if all_good:
        print(f"{Fore.GREEN}✅ All required components are properly installed!{Style.RESET_ALL}")
        print(f"{Fore.CYAN}You can now run: python3 bot.py{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}❌ Some components are missing. Please check the errors above.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Run: pip install -r requirements.txt{Style.RESET_ALL}")

if __name__ == "__main__":
    main()