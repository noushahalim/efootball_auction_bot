#!/bin/bash

# setup.sh - eFootball Auction Bot Setup Script

echo "🚀 eFootball Auction Bot Setup"
echo "=============================="

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.9"

# Convert versions to comparable integers (e.g., 3.10 -> 310, 3.9 -> 309)
version_int=$(echo "$python_version" | awk -F. '{print $1 * 100 + $2}')
required_int=$(echo "$required_version" | awk -F. '{print $1 * 100 + $2}')

if (( version_int < required_int )); then
    echo "❌ Python $required_version or higher is required. You have $python_version"
    exit 1
fi

echo "✅ Python version: $python_version"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📦 Installing requirements..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p data

# Create __init__.py files
echo "📝 Creating package files..."
touch config/__init__.py
touch database/__init__.py
touch handlers/__init__.py
touch utilities/__init__.py

# Check if .env exists
if [ ! -f .env ]; then
    echo "📋 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your configuration!"
else
    echo "✅ .env file already exists"
fi

# Check MongoDB
if command -v mongod &> /dev/null; then
    echo "✅ MongoDB is installed"
else
    echo "⚠️  MongoDB is not installed. Please install MongoDB."
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your bot token and configuration"
echo "2. Make sure MongoDB is running"
echo "3. Run: python3 bot.py"
echo ""
echo "Happy auctioning! 🎉"