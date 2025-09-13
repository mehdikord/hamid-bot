#!/bin/bash

# Hamid Bot Startup Script
# This script ensures the bot runs with proper environment setup

# Set the working directory to the bot's directory
cd "$(dirname "$0")"

# Activate the virtual environment
source venv/bin/activate

# Set environment variables
export PYTHONPATH="$PWD:$PYTHONPATH"
export PYTHONUNBUFFERED=1

# Start the bot
echo "Starting Hamid Telegram Bot..."
echo "Working directory: $PWD"
echo "Python path: $(which python)"
echo "Bot will run on port 3030 for webhook API"
echo "Press Ctrl+C to stop the bot"

# Run the bot
python main.py

