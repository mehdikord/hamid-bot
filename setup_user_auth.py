#!/usr/bin/env python3
"""
Setup script to authenticate with your PERSONAL user account (not bot).
This will create a session file for topic discovery.
"""

import asyncio
from telethon import TelegramClient
import config
import os

async def setup_user_authentication():
    """Setup authentication with personal user account"""
    print("🔍 Setting up user authentication for topic discovery...")
    print(f"API_ID: {config.API_ID}")
    print(f"API_HASH: {config.API_HASH[:10]}...")
    
    # Remove any existing session file to force fresh authentication
    session_file = 'topic_discovery_session.session'
    if os.path.exists(session_file):
        print(f"🗑️ Removing existing session file: {session_file}")
        os.remove(session_file)
    
    # Initialize client
    client = TelegramClient(
        'topic_discovery_session',
        config.API_ID,
        config.API_HASH
    )
    
    try:
        print("\n📱 IMPORTANT: You need to authenticate with your PERSONAL Telegram account")
        print("This should be the account you use to chat with friends, NOT the bot account.")
        print("The bot account (@Leadana_bot) cannot access forum topics.")
        print("\nStarting authentication...")
        
        # Start client (this will prompt for phone number and code)
        await client.start()
        
        # Check if we're logged in as a user (not bot)
        me = await client.get_me()
        
        if me.bot:
            print(f"\n❌ ERROR: You're logged in as a BOT account: {me.first_name} (@{me.username})")
            print("❌ Bot accounts cannot access forum topics.")
            print("❌ You need to authenticate with your PERSONAL user account.")
            print("\n🔧 SOLUTION:")
            print("1. Delete the session file and try again")
            print("2. Use your personal phone number (not bot token)")
            print("3. Make sure you're not using the bot's credentials")
            
            # Clean up
            await client.disconnect()
            if os.path.exists(session_file):
                os.remove(session_file)
            return False
        
        print(f"\n✅ SUCCESS: Authenticated as USER account!")
        print(f"Name: {me.first_name} {me.last_name or ''}")
        print(f"Username: @{me.username or 'no username'}")
        print(f"User ID: {me.id}")
        print(f"Is Bot: {me.bot}")
        
        # Test accessing the group
        test_group_id = -1003036542613
        try:
            entity = await client.get_entity(test_group_id)
            print(f"\n✅ Successfully accessed group: {entity.title}")
            print(f"Group type: {entity.__class__.__name__}")
            
            # Try to get some messages to test forum access
            print("\n🔍 Testing forum topic access...")
            message_count = 0
            async for message in client.iter_messages(entity, limit=5):
                message_count += 1
                if hasattr(message, 'action'):
                    print(f"  Found action message: {message.action.__class__.__name__}")
            
            print(f"✅ Successfully accessed {message_count} messages from the group")
            
        except Exception as e:
            print(f"\n⚠️ Could not access test group: {e}")
        
        print(f"\n🎉 User authentication setup complete!")
        print("The session file 'topic_discovery_session.session' has been created.")
        print("Your bot can now use this user session for topic discovery.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        print("Please check your API_ID and API_HASH are correct.")
        return False
    
    finally:
        await client.disconnect()

if __name__ == "__main__":
    success = asyncio.run(setup_user_authentication())
    if success:
        print("\n✅ Ready to test topic discovery with real names!")
    else:
        print("\n❌ Please fix the authentication and try again.")
