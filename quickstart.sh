#!/bin/bash

# quickstart.sh - Quick start script for eFootball Auction Bot

echo "🚀 eFootball Auction Bot - Quick Start"
echo "====================================="

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for Python
if ! command_exists python3; then
    echo "❌ Python 3 is not installed. Please install Python 3.9 or higher."
    exit 1
fi

# Check for MongoDB
if ! command_exists mongod; then
    echo "⚠️ MongoDB is not installed."
    echo "Would you like to use Docker instead? (y/n)"
    read -r USE_DOCKER
    
    if [[ "$USE_DOCKER" == "y" ]]; then
        if ! command_exists docker; then
            echo "❌ Docker is not installed. Please install Docker first."
            exit 1
        fi
        
        echo "Starting with Docker..."
        docker-compose up -d
        exit 0
    else
        echo "Please install MongoDB manually."
        exit 1
    fi
fi

# Check if MongoDB is running
if ! pgrep -x mongod > /dev/null; then
    echo "⚠️ MongoDB is not running."
    echo "Starting MongoDB..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo systemctl start mongod
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew services start mongodb-community
    else
        echo "Please start MongoDB manually."
        exit 1
    fi
fi

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "Creating .env file from template..."
        cp .env.example .env
        echo "⚠️ Please edit .env file with your configuration!"
        echo "Opening .env in default editor..."
        ${EDITOR:-nano} .env
    else
        echo "❌ No .env.example file found!"
        exit 1
    fi
fi

# Run debug script
echo ""
echo "Running system check..."
python3 debug_bot.py

echo ""
echo "====================================="
echo "If all tests passed, you can now run:"
echo "  python3 bot.py"
echo ""
echo "Or use Docker:"
echo "  docker-compose up"
echo "====================================="