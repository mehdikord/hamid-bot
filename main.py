import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram import F
from datetime import datetime
import logging
import httpx
import json
import signal
import sys

import config
from handlers import seller_main, reports, auth, common

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create bot and dispatcher with FSM storage
storage = MemoryStorage()
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=storage)

# Include handler routers for essential functionality
dp.include_router(common.router)  # Common commands like /start (highest priority)
dp.include_router(auth.router)  # Authentication router
dp.include_router(seller_main.router)  # Main seller dashboard
dp.include_router(reports.router)  # Basic reports

# Create FastAPI app for webhook
app = FastAPI(
    title="Telegram Bot Webhook API",
    description="API for sending notifications to Telegram users via webhook",
    version="1.0.0"
)

# Pydantic models for webhook requests
class NotificationRequest(BaseModel):
    """Request model for sending notifications"""
    chat_id: int = Field(..., description="Telegram chat ID of the user")
    message: str = Field(..., description="Message text to send")
    parse_mode: Optional[str] = Field("HTML", description="Message parsing mode (HTML, Markdown)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "chat_id": 1327318563,
                "message": "Hello! This is a test notification from your CRM system.",
                "parse_mode": "HTML"
            }
        }

class NotificationWithButtonsRequest(BaseModel):
    """Request model for sending notifications with buttons"""
    chat_id: int = Field(..., description="Telegram chat ID of the user")
    message: str = Field(..., description="Message text to send")
    buttons: Optional[List[Dict[str, str]]] = Field(None, description="List of inline keyboard buttons")
    
    class Config:
        json_schema_extra = {
            "example": {
                "chat_id": 1327318563,
                "message": "Please choose an action:",
                "buttons": [
                    {"text": "View Details", "callback_data": "view_details"},
                    {"text": "Mark as Read", "callback_data": "mark_read"}
                ]
            }
        }

class BulkNotificationRequest(BaseModel):
    """Request model for sending notifications to multiple users"""
    chat_ids: List[int] = Field(..., description="List of Telegram chat IDs")
    message: str = Field(..., description="Message text to send")
    parse_mode: Optional[str] = Field("HTML", description="Message parsing mode")
    
    class Config:
        json_schema_extra = {
            "example": {
                "chat_ids": [1327318563, 1234567890],
                "message": "Bulk notification to multiple users",
                "parse_mode": "HTML"
            }
        }

class GroupRegistrationRequest(BaseModel):
    """Request model for registering a group with the bot"""
    group_id: int = Field(..., description="Telegram group ID (usually negative)")
    topic_id: Optional[int] = Field(None, description="Specific topic ID for the group (optional)")
    group_name: Optional[str] = Field(None, description="Group name")
    description: Optional[str] = Field(None, description="Group description")
    topic_names: Optional[Dict[int, str]] = Field(None, description="Mapping of topic IDs to their real names")
    
    class Config:
        json_schema_extra = {
            "example": {
                "group_id": -1001234567890,
                "topic_id": 12345,
                "group_name": "Customer Support",
                "description": "Main support group for customer inquiries",
                "topic_names": {
                    1: "General",
                    2: "Customer Support",
                    3: "Technical Issues"
                }
            }
        }

class ReceiptRequest(BaseModel):
    """Request model for creating a receipt in a group topic"""
    price_deal: float = Field(..., description="Total deal price", gt=0)
    price_deposit: float = Field(..., description="Deposit amount", ge=0)
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    image: Optional[str] = Field(None, description="Image URL or base64 encoded image")
    customer_name: str = Field(..., description="Customer full name")
    customer_phone: str = Field(..., description="Customer phone number")
    customer_province: Optional[str] = Field(None, description="Customer province/state")
    customer_city: Optional[str] = Field(None, description="Customer city")
    customer_id: Optional[str] = Field(None, description="Customer ID")
    assignee: str = Field(..., description="Assignee username or name")
    group_id: int = Field(..., description="Telegram group ID")
    topic_id: Optional[int] = Field(None, description="Topic ID for posting the receipt")
    topic_name: Optional[str] = Field(None, description="Topic name for display in receipt message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "price_deal": 1500.00,
                "price_deposit": 500.00,
                "date": "2024-01-15",
                "image": "https://example.com/receipt.jpg",
                "customer_name": "احمد محمدی",
                "customer_phone": "+989123456789",
                "customer_province": "تهران",
                "customer_city": "تهران",
                "customer_id": "CUST001",
                "assignee": "علی فروشنده",
                "group_id": -1001234567890,
                "topic_id": 12345,
                "topic_name": "Sales Department"
            }
        }

# Group and receipt service functions
async def discover_group_topics_with_telethon(group_id: int) -> List[Dict[str, Any]]:
    """Discover available topics using Telethon for real topic names"""
    try:
        from telethon import TelegramClient
        from telethon.tl.functions.channels import GetFullChannelRequest
        from telethon.tl.types import InputChannel, MessageActionTopicCreate
        from telethon.errors import FloodWaitError, ChatAdminRequiredError
        
        logger.info(f"🔍 Starting Telethon topic discovery for group {group_id}")
        available_topics = []
        
        # Initialize Telethon client with user account (not bot)
        # This requires phone number authentication for full API access
        client = TelegramClient(
            'topic_discovery_session',
            int(config.API_ID),
            config.API_HASH
        )
        
        # Start with user account (requires phone authentication)
        # This will prompt for phone number and code on first run
        # If session file exists, it will use that automatically
        await client.start()
        
        # Check if we're logged in as a user (not bot)
        me = await client.get_me()
        if me.bot:
            logger.error("❌ Telethon is using bot account, but we need user account for full API access")
            logger.error("❌ Please run 'python3 setup_user_auth.py' to authenticate with your personal account")
            raise Exception("Bot account cannot access forum topics. Need user account.")
        
        logger.info(f"✅ Telethon authenticated as user: {me.first_name} (@{me.username or 'no username'})")
        logger.info(f"✅ User ID: {me.id}, Is Bot: {me.bot}")
        
        try:
            # Get the channel/group entity
            entity = await client.get_entity(group_id)
            
            # Get full channel info which includes forum topics
            full_channel = await client(GetFullChannelRequest(entity))
            logger.info(f"🔍 Full channel info retrieved for group {group_id}")
            
            # Try to get topics by iterating through messages and looking for topic creation messages
            seen_topic_ids = set()  # Track seen topic IDs to avoid duplicates
            
            async for message in client.iter_messages(entity, limit=200):
                # Look for messages that create topics
                if hasattr(message, 'action') and isinstance(message.action, MessageActionTopicCreate):
                    topic_id = message.id
                    topic_name = message.action.title
                    
                    # Only add if we haven't seen this topic ID before
                    if topic_id not in seen_topic_ids:
                        available_topics.append({
                            "topic_id": topic_id,
                            "name": topic_name,
                            "status": "active",
                            "discovered_at": datetime.now().isoformat(),
                            "discovery_method": "telethon"
                        })
                        seen_topic_ids.add(topic_id)
                        logger.info(f"✅ Found topic {topic_id} with name: '{topic_name}'")
                
                # Also look for messages in topics to discover existing topics
                elif hasattr(message, 'reply_to') and message.reply_to and hasattr(message.reply_to, 'reply_to_msg_id'):
                    topic_id = message.reply_to.reply_to_msg_id
                    
                    # Only process if we haven't seen this topic ID before
                    if topic_id not in seen_topic_ids:
                        # Try to get the topic name from the first message in the topic
                        topic_name = f"Topic {topic_id}"  # Default name
                        
                        # Look for the topic creation message to get the real name
                        try:
                            topic_creation_msg = await client.get_messages(entity, ids=topic_id)
                            if topic_creation_msg and hasattr(topic_creation_msg, 'action') and isinstance(topic_creation_msg.action, MessageActionTopicCreate):
                                topic_name = topic_creation_msg.action.title
                                logger.info(f"✅ Found real topic name: '{topic_name}' for topic {topic_id}")
                        except Exception as e:
                            logger.info(f"🔍 Could not get topic creation message for {topic_id}: {e}")
                        
                        available_topics.append({
                            "topic_id": topic_id,
                            "name": topic_name,
                            "status": "active",
                            "discovered_at": datetime.now().isoformat(),
                            "discovery_method": "telethon"
                        })
                        seen_topic_ids.add(topic_id)
                        logger.info(f"✅ Found topic {topic_id} with name: '{topic_name}'")
            
            # Always add General topic (topic_id=1) if topics are enabled
            # But try to get its real name first
            general_topic_found = any(topic["topic_id"] == 1 for topic in available_topics)
            if not general_topic_found:
                # Try to get the real name of the General topic
                general_topic_name = "General"  # Default name
                
                try:
                    # Try to get the General topic creation message
                    general_creation_msg = await client.get_messages(entity, ids=1)
                    if general_creation_msg and hasattr(general_creation_msg, 'action') and isinstance(general_creation_msg.action, MessageActionTopicCreate):
                        general_topic_name = general_creation_msg.action.title
                        logger.info(f"✅ Found real General topic name: '{general_topic_name}'")
                    else:
                        logger.info(f"🔍 Could not find General topic creation message, using default name")
                except Exception as e:
                    logger.info(f"🔍 Could not get General topic name: {e}")
                
                available_topics.insert(0, {
                    "topic_id": 1,
                    "name": general_topic_name,
                    "status": "active",
                    "discovered_at": datetime.now().isoformat(),
                    "discovery_method": "telethon"
                })
                logger.info(f"✅ Added General topic with name: '{general_topic_name}'")
            
        except FloodWaitError as e:
            logger.warning(f"⚠️ FloodWait: {e}")
            await asyncio.sleep(e.seconds)
        except ChatAdminRequiredError as e:
            logger.error(f"❌ Admin required: {e}")
        except Exception as e:
            logger.error(f"❌ Error getting channel info: {e}")
        
        finally:
            await client.disconnect()
        
        # Final deduplication - remove any remaining duplicates by topic_id
        unique_topics = []
        seen_ids = set()
        for topic in available_topics:
            if topic["topic_id"] not in seen_ids:
                unique_topics.append(topic)
                seen_ids.add(topic["topic_id"])
        
        logger.info(f"📋 Telethon topic discovery completed. Found {len(unique_topics)} unique topics")
        return unique_topics
        
    except Exception as e:
        logger.error(f"❌ Error during Telethon topic discovery for group {group_id}: {e}")
        # Fallback to Telegram API method
        logger.info("🔄 Falling back to Telegram API topic discovery...")
        return await discover_group_topics_with_telegram_api(group_id)

async def discover_group_topics_with_telegram_api(group_id: int) -> List[Dict[str, Any]]:
    """Discover available topics using direct Telegram Bot API calls"""
    try:
        import httpx
        
        logger.info(f"🔍 Starting Telegram API topic discovery for group {group_id}")
        available_topics = []
        
        # Test common topic IDs (skip 1 as it's always General)
        common_topic_ids = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
        
        async with httpx.AsyncClient() as client:
            for topic_id in common_topic_ids:
                try:
                    logger.info(f"🔍 Testing topic {topic_id} with Telegram API...")
                    
                    # Send a test message to the topic
                    send_response = await client.post(
                        f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": group_id,
                            "text": "🔍",
                            "message_thread_id": topic_id
                        }
                    )
                    
                    if send_response.status_code == 200:
                        message_data = send_response.json()
                        if message_data.get("ok"):
                            message_info = message_data.get("result", {})
                            topic_name = f"Topic {topic_id}"  # Default name
                            
                            # Try to extract topic name from the message info
                            # The message might contain thread information
                            if "reply_to_message" in message_info:
                                reply_info = message_info["reply_to_message"]
                                if "message_thread_info" in reply_info:
                                    thread_info = reply_info["message_thread_info"]
                                    if "name" in thread_info:
                                        topic_name = thread_info["name"]
                                        logger.info(f"✅ Extracted topic name from API: '{topic_name}'")
                            
                            available_topics.append({
                                "topic_id": topic_id,
                                "name": topic_name,
                                "status": "active",
                                "discovered_at": datetime.now().isoformat(),
                                "discovery_method": "telegram_api"
                            })
                            
                            # Clean up the test message
                            message_id = message_info.get("message_id")
                            if message_id:
                                try:
                                    await client.post(
                                        f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteMessage",
                                        json={
                                            "chat_id": group_id,
                                            "message_id": message_id
                                        }
                                    )
                                except:
                                    pass
                            
                            logger.info(f"✅ Found topic {topic_id} with name: '{topic_name}'")
                        else:
                            logger.info(f"❌ Topic {topic_id} not available: {message_data.get('description', 'Unknown error')}")
                    else:
                        logger.info(f"❌ Topic {topic_id} not available: HTTP {send_response.status_code}")
                        
                except Exception as e:
                    logger.info(f"❌ Topic {topic_id} not available: {e}")
                    # Stop testing if we get consecutive failures
                    if len(available_topics) == 0 and topic_id > 5:
                        break
                    continue
        
        # Always add General topic (topic_id=1) if topics are enabled
        if not any(topic["topic_id"] == 1 for topic in available_topics):
            available_topics.insert(0, {
                "topic_id": 1,
                "name": "General",
                "status": "active",
                "discovered_at": datetime.now().isoformat(),
                "discovery_method": "telegram_api"
            })
            logger.info("✅ Added General topic (always exists in groups with topics)")
        
        logger.info(f"📋 Telegram API topic discovery completed. Found {len(available_topics)} topics")
        return available_topics
        
    except Exception as e:
        logger.error(f"❌ Error during Telegram API topic discovery for group {group_id}: {e}")
        # Fallback to aiogram method
        logger.info("🔄 Falling back to aiogram topic discovery...")
        return await discover_group_topics_aiogram(group_id)

async def discover_group_topics_aiogram(group_id: int) -> List[Dict[str, Any]]:
    """Discover available topics in a group using aiogram 3.x compatible methods"""
    try:
        from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
        import httpx
        
        logger.info(f"🔍 Starting topic discovery for group {group_id}")
        available_topics = []
        
        # Test common topic IDs (skip 1 as it's always General)
        common_topic_ids = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
        
        for topic_id in common_topic_ids:
            try:
                logger.info(f"🔍 Testing topic {topic_id}...")
                
                # Try to send a test message to the topic to see if it exists
                # This is the most reliable way to test topic existence in aiogram 3.x
                test_message = await bot.send_message(
                    chat_id=group_id,
                    text="🔍",  # Minimal test message
                    message_thread_id=topic_id
                )
                
                if test_message:
                    # Message sent successfully, topic exists
                    topic_name = f"Topic {topic_id}"  # Default name
                    
                    # Try to get the real topic name from the first message in the topic
                    try:
                        # The message object might contain thread info
                        if hasattr(test_message, 'message_thread_id') and test_message.message_thread_id:
                            logger.info(f"✅ Found topic {topic_id} with thread_id: {test_message.message_thread_id}")
                        
                        # Try to extract topic name from message thread info
                        if hasattr(test_message, 'message_thread_info') and test_message.message_thread_info:
                            thread_info = test_message.message_thread_info
                            logger.info(f"🔍 Thread info found: {thread_info}")
                            
                            # Try different attributes that might contain the topic name
                            if hasattr(thread_info, 'name') and thread_info.name:
                                topic_name = thread_info.name
                                logger.info(f"✅ Extracted topic name from thread_info.name: '{topic_name}'")
                            elif hasattr(thread_info, 'title') and thread_info.title:
                                topic_name = thread_info.title
                                logger.info(f"✅ Extracted topic name from thread_info.title: '{topic_name}'")
                            else:
                                logger.info(f"🔍 Thread info available but no name/title found: {dir(thread_info)}")
                        else:
                            logger.info(f"🔍 No message_thread_info found in message: {dir(test_message)}")
                        
                        # If we still have default name, try to get it from the message itself
                        if topic_name == f"Topic {topic_id}":
                            # Try to get the message content or other attributes
                            logger.info(f"🔍 Message attributes: {[attr for attr in dir(test_message) if not attr.startswith('_')]}")
                            
                            # Check if there's any way to get topic name from the message
                            if hasattr(test_message, 'reply_to_message') and test_message.reply_to_message:
                                reply_msg = test_message.reply_to_message
                                logger.info(f"🔍 Reply message found: {reply_msg}")
                        
                        logger.info(f"✅ Found topic {topic_id} with name: '{topic_name}'")
                        
                    except Exception as e:
                        logger.info(f"✅ Found topic {topic_id} but couldn't get name: {e}")
                    
                    available_topics.append({
                        "topic_id": topic_id,
                        "name": topic_name,
                        "status": "active",
                        "discovered_at": datetime.now().isoformat()
                    })
                    
                    # Clean up test message
                    try:
                        await bot.delete_message(
                            chat_id=group_id,
                            message_id=test_message.message_id
                        )
                        logger.info(f"✅ Cleaned up test message for topic {topic_id}")
                    except Exception as e:
                        logger.warning(f"Could not delete test message for topic {topic_id}: {e}")
                
            except TelegramBadRequest as e:
                logger.info(f"❌ Topic {topic_id} not available: {e}")
                # Stop testing if we get consecutive failures
                if len(available_topics) == 0 and topic_id > 5:
                    break
            except Exception as e:
                logger.warning(f"⚠️ Error testing topic {topic_id}: {e}")
                # Continue with next topic
                continue
        
        # Always add General topic (topic_id=1) if topics are enabled
        # because General topic always exists in groups with topics
        if not any(topic["topic_id"] == 1 for topic in available_topics):
            available_topics.insert(0, {
                "topic_id": 1,
                "name": "General",
                "status": "active",
                "discovered_at": datetime.now().isoformat()
            })
            logger.info("✅ Added General topic (always exists in groups with topics)")
        
        logger.info(f"📋 Topic discovery completed. Found {len(available_topics)} topics")
        return available_topics
        
    except Exception as e:
        logger.error(f"❌ Error during topic discovery for group {group_id}: {e}")
        # Return at least the General topic if topics are enabled
        return [{
            "topic_id": 1,
            "name": "General",
            "status": "active",
            "discovered_at": datetime.now().isoformat(),
            "error": f"Discovery failed: {str(e)}"
        }]

async def fetch_group_metadata(group_id: int) -> Dict[str, Any]:
    """Fetch group metadata from Telegram API"""
    try:
        from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
        
        # Get basic chat information
        chat = await bot.get_chat(group_id)
        
        # Get chat administrators
        administrators = []
        try:
            admins = await bot.get_chat_administrators(group_id)
            administrators = [
                {
                    "user_id": admin.user.id,
                    "username": admin.user.username,
                    "first_name": admin.user.first_name,
                    "status": admin.status
                }
                for admin in admins
            ]
        except Exception as e:
            logger.warning(f"Could not fetch administrators for group {group_id}: {e}")
        
        # Get member count
        member_count = 0
        try:
            member_count = await bot.get_chat_member_count(group_id)
        except Exception as e:
            logger.warning(f"Could not fetch member count for group {group_id}: {e}")
        
        # Check if topics are enabled in the group (simple check)
        has_topics_enabled = False
        logger.info(f"🔍 Checking topics for group {group_id}, type: {chat.type}")
        
        if chat.type in ["group", "supergroup"]:
            # Simple approach: Check if the chat object has is_forum property
            if hasattr(chat, 'is_forum') and chat.is_forum:
                has_topics_enabled = True
                logger.info(f"✅ Group {group_id} has topics enabled (is_forum=True)")
            else:
                # Fallback: assume topics are enabled for supergroups
                has_topics_enabled = chat.type == "supergroup"
                logger.info(f"Fallback: assuming topics enabled for {chat.type}: {has_topics_enabled}")
        else:
            # Channels don't have topics
            has_topics_enabled = False
            logger.info(f"❌ Group {group_id} is a {chat.type}, no topics supported")
        
        logger.info(f"🎯 Final result: has_topics_enabled = {has_topics_enabled}")
        
        # Topic discovery functionality - get topic names from first messages
        available_topics = []
        if has_topics_enabled:
            logger.info(f"🔍 Discovering available topics for group {group_id}...")
            # Use Telethon for topic discovery (Telethon has bot restrictions)
            # For real topic names, users can manually configure them in the backend
            available_topics = await discover_group_topics_with_telethon(group_id)
            logger.info(f"📋 Discovered {len(available_topics)} topics: {[t['topic_id'] for t in available_topics]}")
        
        metadata = {
            "group_id": chat.id,
            "title": chat.title,
            "type": chat.type,
            "description": getattr(chat, 'description', None),
            "username": getattr(chat, 'username', None),
            "member_count": member_count,
            "administrators": administrators,
            "has_protected_content": getattr(chat, 'has_protected_content', False),
            "slow_mode_delay": getattr(chat, 'slow_mode_delay', 0),
            "message_auto_delete_time": getattr(chat, 'message_auto_delete_time', None),
            "permissions": {
                "can_send_messages": True,  # Bot permissions
                "can_send_media_messages": True,
                "can_send_polls": True,
                "can_send_other_messages": True,
                "can_add_web_page_previews": True,
                "can_change_info": False,
                "can_invite_users": False,
                "can_pin_messages": False,
                "can_manage_topics": False
            },
            "has_topics_enabled": has_topics_enabled,  # Simple topic detection
            "available_topics": available_topics,  # Discovered topics with names
            "fetched_at": datetime.now().isoformat()
        }
        
        logger.info(f"Successfully fetched metadata for group {group_id}")
        return metadata
        
    except TelegramBadRequest as e:
        logger.error(f"Bad request when fetching group {group_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid group ID or bot not in group: {str(e)}")
        
    except TelegramForbiddenError as e:
        logger.error(f"Forbidden when fetching group {group_id}: {e}")
        raise HTTPException(status_code=403, detail=f"Bot doesn't have permission to access group: {str(e)}")
        
    except Exception as e:
        logger.error(f"Unexpected error when fetching group {group_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

async def check_topic_exists(group_id: int, topic_id: int) -> bool:
    """Check if a topic exists in a group by trying to send a test message"""
    try:
        # Try to send a very short test message to the topic
        test_message = await bot.send_message(
            chat_id=group_id,
            message_thread_id=topic_id,
            text=".",
            parse_mode="HTML"
        )
        # If successful, delete the test message
        try:
            await bot.delete_message(chat_id=group_id, message_id=test_message.message_id)
        except:
            pass  # Ignore if deletion fails
        return True
    except Exception as e:
        logger.info(f"Topic {topic_id} does not exist or is not accessible: {e}")
        return False

async def send_receipt_to_group(
    group_id: int,
    topic_id: Optional[int],
    receipt_data: ReceiptRequest
) -> Dict[str, Any]:
    """Send receipt message to group topic"""
    try:
        from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
        
        # Format the receipt message
        remaining_amount = receipt_data.price_deal - receipt_data.price_deposit
        
        # Create hashtag for assignee (replace spaces with underscores and add #)
        assignee_hashtag = f"#{receipt_data.assignee.replace(' ', '_')}"
        
        # Create simple Telegram ID with @
        telegram_id_mention = ""
        if receipt_data.customer_id:
            telegram_id_mention = f'🔗 <b>آیدی:</b> @{receipt_data.customer_id}'
        
        message = f"""💠💎💠💎💠💎💠💎

👤 <b>نام:</b> {receipt_data.customer_name}
📞 <b>شماره:</b> {receipt_data.customer_phone}
{'🗺 <b>استان:</b> ' + receipt_data.customer_province if receipt_data.customer_province else ''}
{'🏡 <b>شهر:</b> ' + receipt_data.customer_city if receipt_data.customer_city else ''}
{telegram_id_mention}
📅 <b>تاریخ:</b> {receipt_data.date}

💰 — — — — — — — 💰

💲 <b>مبلغ کل:</b> {receipt_data.price_deal:,.0f} تومان
💵 <b>مبلغ واریزی:</b> {receipt_data.price_deposit:,.0f} تومان

💰 — — — — — — — 💰

👨‍💼 <b>کارشناس:</b> {assignee_hashtag}

💠💎💠💎💠💎💠💎

{'📷 <b>تصویر رسید:</b> ضمیمه شده' if receipt_data.image else ''}
{'🏷️ <b>موضوع:</b> ' + receipt_data.topic_name if receipt_data.topic_name else ''}"""
        
        # Send message to group/topic
        # Only use message_thread_id for groups/supergroups, not channels
        send_params = {
            "chat_id": group_id,
            "parse_mode": "HTML"
        }
        
        # Only add message_thread_id if it's provided (for groups with topics)
        if topic_id is not None:
            # Check if topic exists before trying to send
            topic_exists = await check_topic_exists(group_id, topic_id)
            if topic_exists:
                send_params["message_thread_id"] = topic_id
                logger.info(f"Topic {topic_id} exists, sending to topic")
            else:
                logger.warning(f"Topic {topic_id} does not exist, sending to main group instead")
                topic_id = None  # Remove topic_id to send to main group
        
        # If there's an image, send as photo with caption, otherwise send as text message
        if receipt_data.image and receipt_data.image.startswith('http'):
            try:
                # Send image with receipt text as caption
                photo_params = send_params.copy()
                photo_params["photo"] = receipt_data.image
                photo_params["caption"] = message
                sent_message = await bot.send_photo(**photo_params)
            except Exception as e:
                logger.error(f"Could not send image, falling back to text: {e}")
                # Fallback to text message if image fails - remove photo param
                text_params = send_params.copy()
                text_params["text"] = message
                sent_message = await bot.send_message(**text_params)
        else:
            # Send as text message
            send_params["text"] = message
            sent_message = await bot.send_message(**send_params)
        
        logger.info(f"Successfully sent receipt to group {group_id}, topic {topic_id}")
        
        return {
            "success": True,
            "message_id": sent_message.message_id,
            "group_id": group_id,
            "topic_id": topic_id,
            "message": "Receipt sent successfully"
        }
        
    except TelegramBadRequest as e:
        logger.error(f"Bad request when sending receipt to group {group_id}: {e}")
        
        # If it's a "message thread not found" error and we have a topic_id, try without topic
        if "message thread not found" in str(e).lower() and topic_id is not None:
            logger.info(f"Topic {topic_id} not found, attempting to send to main group without topic")
            try:
                # Remove topic_id and try again
                fallback_params = {
                    "chat_id": group_id,
                    "parse_mode": "HTML",
                    "text": message
                }
                sent_message = await bot.send_message(**fallback_params)
                
                logger.info(f"Successfully sent receipt to main group {group_id} (topic fallback)")
                return {
                    "success": True,
                    "message_id": sent_message.message_id,
                    "group_id": group_id,
                    "topic_id": None,  # Sent to main group
                    "message": "Receipt sent to main group (topic not found)",
                    "fallback": True
                }
            except Exception as fallback_error:
                logger.error(f"Fallback to main group also failed: {fallback_error}")
        
        return {
            "success": False,
            "error": "Invalid group ID or message format",
            "details": str(e)
        }
        
    except TelegramForbiddenError as e:
        logger.error(f"Forbidden when sending receipt to group {group_id}: {e}")
        return {
            "success": False,
            "error": "Bot doesn't have permission to send messages to this group",
            "details": str(e)
        }
        
    except Exception as e:
        logger.error(f"Unexpected error when sending receipt to group {group_id}: {e}")
        return {
            "success": False,
            "error": "Internal server error",
            "details": str(e)
        }

async def check_and_promote_bot_permissions(group_id: int) -> bool:
    """Check if bot has admin rights and try to promote if possible"""
    try:
        from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
        
        # Get bot's current status in the group
        try:
            bot_member = await bot.get_chat_member(group_id, bot.id)
            logger.info(f"Bot status in group {group_id}: {bot_member.status}")
            
            # Check if bot is already admin
            if bot_member.status in ['administrator', 'creator']:
                logger.info(f"Bot already has admin rights in group {group_id}")
                return True
            
            # If bot is not admin, we can't promote it ourselves
            # Only group admins can promote the bot
            logger.warning(f"Bot is not admin in group {group_id}, status: {bot_member.status}")
            return False
            
        except TelegramBadRequest as e:
            logger.error(f"Bad request when checking bot status in group {group_id}: {e}")
            return False
        except TelegramForbiddenError as e:
            logger.error(f"Forbidden when checking bot status in group {group_id}: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error checking bot permissions in group {group_id}: {e}")
        return False

async def auto_register_group_to_backend(group_metadata: Dict[str, Any]) -> bool:
    """Automatically send complete group metadata to backend when bot is added to group"""
    try:
        # Prepare the complete response data structure to save
        response_data = {
            "success": True,
            "message": "Group registered successfully",
            "group_metadata": group_metadata
        }
        
        logger.info(f"Sending complete group metadata for group {group_metadata.get('group_id')} to backend")
        logger.info(f"Data structure: {json.dumps(response_data, indent=2)}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config.AUTO_REGISTER_ENDPOINT,
                json=response_data,
                timeout=10.0
            )
            
            if response.status_code == 200:
                backend_response = response.json()
                logger.info(f"Successfully saved group metadata for group {group_metadata.get('group_id')} to backend")
                logger.info(f"Backend response: {backend_response}")
                return True
            else:
                logger.error(f"Backend save failed: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Error saving group metadata to backend: {e}")
        return False

# Webhook service functions
async def send_notification(
    chat_id: int, 
    message: str, 
    parse_mode: str = "HTML",
    reply_markup: Optional[InlineKeyboardMarkup] = None
) -> Dict[str, Any]:
    """Send a notification message to a specific Telegram user"""
    try:
        from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
        
        sent_message = await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        
        logger.info(f"Successfully sent notification to chat_id {chat_id}")
        
        return {
            "success": True,
            "message_id": sent_message.message_id,
            "chat_id": chat_id,
            "message": "Notification sent successfully"
        }
        
    except TelegramBadRequest as e:
        logger.error(f"Bad request when sending to chat_id {chat_id}: {e}")
        logger.error(f"Message content: {message}")
        logger.error(f"Parse mode: {parse_mode}")
        return {
            "success": False,
            "error": "Invalid chat_id or message format",
            "details": str(e),
            "message_content": message,
            "parse_mode": parse_mode
        }
        
    except TelegramForbiddenError as e:
        logger.error(f"Forbidden when sending to chat_id {chat_id}: {e}")
        return {
            "success": False,
            "error": "Bot is blocked by user or chat not found",
            "details": str(e)
        }
        
    except Exception as e:
        logger.error(f"Unexpected error when sending to chat_id {chat_id}: {e}")
        return {
            "success": False,
            "error": "Internal server error",
            "details": str(e)
        }

# FastAPI routes
@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "status": "healthy",
        "service": "Telegram Bot with Webhook API",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Bot and webhook server are running"}

@app.post("/webhook/notify")
async def webhook_notify(request: NotificationRequest):
    """Send a notification to a specific Telegram user"""
    try:
        logger.info(f"Received notification request for chat_id: {request.chat_id}")
        logger.info(f"Message content: {request.message}")
        logger.info(f"Parse mode: {request.parse_mode}")
        
        result = await send_notification(
            chat_id=request.chat_id,
            message=request.message,
            parse_mode=request.parse_mode
        )
        
        if result["success"]:
            logger.info(f"Successfully sent notification to chat_id: {request.chat_id}")
            return {
                "success": True,
                "message": "Notification sent successfully",
                "data": result
            }
        else:
            logger.error(f"Failed to send notification to chat_id: {request.chat_id}")
            logger.error(f"Error details: {result}")
            raise HTTPException(status_code=400, detail=result)
            
    except Exception as e:
        logger.error(f"Error processing notification request: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/webhook/notify-with-buttons")
async def webhook_notify_with_buttons(request: NotificationWithButtonsRequest):
    """Send a notification with inline keyboard buttons to a specific Telegram user"""
    try:
        logger.info(f"Received notification with buttons request for chat_id: {request.chat_id}")
        
        reply_markup = None
        if request.buttons:
            keyboard_buttons = []
            for button in request.buttons:
                keyboard_buttons.append(
                    InlineKeyboardButton(
                        text=button.get('text', 'Button'),
                        callback_data=button.get('callback_data', 'default')
                    )
                )
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[keyboard_buttons])
        
        result = await send_notification(
            chat_id=request.chat_id,
            message=request.message,
            reply_markup=reply_markup
        )
        
        if result["success"]:
            logger.info(f"Successfully sent notification with buttons to chat_id: {request.chat_id}")
            return {
                "success": True,
                "message": "Notification with buttons sent successfully",
                "data": result
            }
        else:
            logger.error(f"Failed to send notification with buttons to chat_id: {request.chat_id}")
            raise HTTPException(status_code=400, detail=result)
            
    except Exception as e:
        logger.error(f"Error processing notification with buttons request: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/webhook/bulk-notify")
async def webhook_bulk_notify(request: BulkNotificationRequest):
    """Send a notification to multiple Telegram users"""
    try:
        logger.info(f"Received bulk notification request for {len(request.chat_ids)} users")
        
        results = []
        success_count = 0
        
        for chat_id in request.chat_ids:
            result = await send_notification(
                chat_id=chat_id,
                message=request.message,
                parse_mode=request.parse_mode
            )
            results.append({"chat_id": chat_id, "result": result})
            if result["success"]:
                success_count += 1
        
        logger.info(f"Bulk notification completed: {success_count}/{len(request.chat_ids)} successful")
        
        return {
            "success": True,
            "message": f"Bulk notification completed: {success_count}/{len(request.chat_ids)} successful",
            "total_sent": success_count,
            "total_requested": len(request.chat_ids),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error processing bulk notification request: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/webhook/raw")
async def webhook_raw(request: dict):
    """Raw webhook endpoint that accepts any JSON payload for testing"""
    try:
        logger.info(f"Received raw webhook request: {request}")
        
        # Extract chat_id and message from the request
        chat_id = request.get("chat_id")
        message = request.get("message", "Test notification from webhook")
        
        if not chat_id:
            raise HTTPException(status_code=400, detail="chat_id is required")
        
        result = await send_notification(
            chat_id=chat_id,
            message=message
        )
        
        return {
            "success": result["success"],
            "message": "Raw webhook processed",
            "data": result,
            "received_payload": request
        }
        
    except Exception as e:
        logger.error(f"Error processing raw webhook request: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Group Management Endpoints
@app.post("/api/groups/register")
async def register_group(request: GroupRegistrationRequest):
    """Register a group and fetch its metadata"""
    try:
        logger.info(f"Received group registration request for group_id: {request.group_id}")
        
        # Fetch group metadata from Telegram
        group_metadata = await fetch_group_metadata(request.group_id)
        
        # Apply custom topic names if provided
        available_topics = group_metadata.get("available_topics", [])
        if request.topic_names:
            logger.info(f"🔧 Applying custom topic names: {request.topic_names}")
            for topic in available_topics:
                topic_id = topic["topic_id"]
                if topic_id in request.topic_names:
                    old_name = topic["name"]
                    new_name = request.topic_names[topic_id]
                    topic["name"] = new_name
                    topic["custom_name"] = True
                    logger.info(f"✅ Updated topic {topic_id}: '{old_name}' → '{new_name}'")
        
        # Add additional information from request
        group_metadata.update({
            "topic_id": request.topic_id,
            "custom_name": request.group_name,
            "custom_description": request.description,
            "registered_at": datetime.now().isoformat(),
            "topic_info": {
                "has_topics": group_metadata.get("has_topics_enabled", False),
                "supports_topics": group_metadata.get("has_topics_enabled", False),
                "topic_id_provided": request.topic_id is not None,
                "topic_count": len(available_topics),
                "custom_topic_names": request.topic_names is not None,
                "recommended_usage": "Use topic_id for supergroups, ignore for channels and simple groups"
            }
        })
        
        logger.info(f"Successfully registered group {request.group_id}")
        
        return {
            "success": True,
            "message": "Group registered successfully",
            "group_metadata": group_metadata
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions from fetch_group_metadata
        raise
    except Exception as e:
        logger.error(f"Error processing group registration request: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/groups/{group_id}/metadata")
async def get_group_metadata(group_id: int):
    """Get current metadata for a registered group"""
    try:
        logger.info(f"Fetching metadata for group_id: {group_id}")
        
        # Fetch fresh metadata from Telegram
        group_metadata = await fetch_group_metadata(group_id)
        
        return {
            "success": True,
            "message": "Group metadata retrieved successfully",
            "group_metadata": group_metadata
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions from fetch_group_metadata
        raise
    except Exception as e:
        logger.error(f"Error fetching group metadata: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/groups/{group_id}/basic")
async def get_group_basic_info(group_id: int):
    """Get basic group info without topic discovery (lightweight)"""
    try:
        logger.info(f"Fetching basic info for group_id: {group_id}")
        
        from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
        
        # Get basic chat information only
        chat = await bot.get_chat(group_id)
        
        # Get member count
        member_count = 0
        try:
            member_count = await bot.get_chat_member_count(group_id)
        except Exception as e:
            logger.warning(f"Could not fetch member count for group {group_id}: {e}")
        
        # Simple topic check without discovery
        has_topics_enabled = False
        if chat.type in ["group", "supergroup"]:
            if hasattr(chat, 'is_forum') and chat.is_forum:
                has_topics_enabled = True
        
        basic_info = {
            "group_id": chat.id,
            "title": chat.title,
            "type": chat.type,
            "description": getattr(chat, 'description', None),
            "username": getattr(chat, 'username', None),
            "member_count": member_count,
            "has_topics_enabled": has_topics_enabled,
            "fetched_at": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "message": "Basic group info retrieved successfully",
            "group_info": basic_info
        }
        
    except TelegramBadRequest as e:
        logger.error(f"Bad request when fetching group {group_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid group ID or bot not in group: {str(e)}")
        
    except TelegramForbiddenError as e:
        logger.error(f"Forbidden when fetching group {group_id}: {e}")
        raise HTTPException(status_code=403, detail=f"Bot doesn't have permission to access group: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error fetching basic group info: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Receipt Management Endpoints
@app.post("/api/receipts")
async def create_receipt(request: ReceiptRequest):
    """Create and send a receipt to a group topic"""
    try:
        logger.info(f"Received receipt creation request for group_id: {request.group_id}")
        logger.info(f"Customer: {request.customer_name}, Deal: ${request.price_deal}")
        
        # Validate date format
        try:
            datetime.strptime(request.date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Validate deposit doesn't exceed deal price
        if request.price_deposit > request.price_deal:
            raise HTTPException(status_code=400, detail="Deposit amount cannot exceed deal price")
        
        # Get group type to determine if topic_id is needed
        try:
            group_metadata = await fetch_group_metadata(request.group_id)
            group_type = group_metadata.get("type", "unknown")
            
            # For channels, topic_id should be None
            if group_type == "channel" and request.topic_id is not None:
                logger.warning(f"Topic ID provided for channel {request.group_id}, ignoring topic_id")
                request.topic_id = None
                
            # For groups/supergroups, topic_id is optional but recommended
            elif group_type in ["group", "supergroup"]:
                logger.info(f"Group type: {group_type}, topic_id: {request.topic_id}")
                
        except Exception as e:
            logger.warning(f"Could not fetch group metadata: {e}, proceeding with original topic_id")
        
        # Send receipt to group
        result = await send_receipt_to_group(
            group_id=request.group_id,
            topic_id=request.topic_id,
            receipt_data=request
        )
        
        if result["success"]:
            logger.info(f"Successfully created receipt for customer: {request.customer_name}")
            return {
                "success": True,
                "message": "Receipt created and sent successfully",
                "receipt_data": {
                    "customer_name": request.customer_name,
                    "customer_phone": request.customer_phone,
                    "customer_province": request.customer_province,
                    "customer_city": request.customer_city,
                    "customer_id": request.customer_id,
                    "price_deal": request.price_deal,
                    "price_deposit": request.price_deposit,
                    "remaining_amount": request.price_deal - request.price_deposit,
                    "date": request.date,
                    "assignee": request.assignee,
                    "assignee_hashtag": f"#{request.assignee.replace(' ', '_')}",
                    "group_id": request.group_id,
                    "topic_id": request.topic_id,
                    "topic_name": request.topic_name,
                    "message_id": result["message_id"],
                    "created_at": datetime.now().isoformat()
                },
                "telegram_result": result
            }
        else:
            logger.error(f"Failed to send receipt to group: {result}")
            raise HTTPException(status_code=400, detail=result)
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error processing receipt creation request: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

class TopicNamesUpdateRequest(BaseModel):
    """Request model for updating topic names"""
    topic_names: Dict[int, str] = Field(..., description="Mapping of topic IDs to their real names")
    
    class Config:
        json_schema_extra = {
            "example": {
                "topic_names": {
                    1: "General",
                    2: "Customer Support", 
                    3: "Technical Issues"
                }
            }
        }

@app.post("/api/groups/{group_id}/topics/names")
async def update_topic_names(group_id: int, request: TopicNamesUpdateRequest):
    """Update topic names for a group"""
    try:
        logger.info(f"Updating topic names for group_id: {group_id}")
        logger.info(f"Topic names: {request.topic_names}")
        
        # Fetch current group metadata
        group_metadata = await fetch_group_metadata(group_id)
        available_topics = group_metadata.get("available_topics", [])
        
        # Apply custom topic names
        updated_topics = []
        for topic in available_topics:
            topic_id = topic["topic_id"]
            if topic_id in request.topic_names:
                old_name = topic["name"]
                new_name = request.topic_names[topic_id]
                topic["name"] = new_name
                topic["custom_name"] = True
                topic["updated_at"] = datetime.now().isoformat()
                logger.info(f"✅ Updated topic {topic_id}: '{old_name}' → '{new_name}'")
            updated_topics.append(topic)
        
        return {
            "success": True,
            "message": "Topic names updated successfully",
            "group_id": group_id,
            "updated_topics": updated_topics,
            "topic_count": len(updated_topics)
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions from fetch_group_metadata
        raise
    except Exception as e:
        logger.error(f"Error updating topic names: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/groups/{group_id}/topics")
async def get_group_topics(group_id: int):
    """Get available topics for a group (if supported)"""
    try:
        logger.info(f"Fetching topics for group_id: {group_id}")
        
        # Fetch fresh group metadata which includes topic discovery
        group_metadata = await fetch_group_metadata(group_id)
        
        return {
            "success": True,
            "message": "Topics retrieved successfully",
            "group_id": group_id,
            "has_topics_enabled": group_metadata.get("has_topics_enabled", False),
            "available_topics": group_metadata.get("available_topics", []),
            "topic_count": len(group_metadata.get("available_topics", []))
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions from fetch_group_metadata
        raise
    except Exception as e:
        logger.error(f"Error fetching group topics: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Auto-registration handler for when bot is added to groups
@dp.message(F.new_chat_members)
async def handle_new_chat_members(message: Message):
    """Handle when bot is added to a group/channel"""
    try:
        # Only handle messages with new_chat_members (when someone is added)
        if message.new_chat_members:
            bot_was_added = any(member.id == bot.id for member in message.new_chat_members)
            
            if bot_was_added and message.chat.type in ['group', 'supergroup', 'channel']:
                logger.info(f"Bot was added to {message.chat.type}: {message.chat.id}")
                
                # Check bot permissions and try to promote to admin
                bot_has_admin_rights = await check_and_promote_bot_permissions(message.chat.id)
                
                if not bot_has_admin_rights:
                    # Send message asking for permissions
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text="⚠️ <b>لطفا دسترسی‌ها را به ربات بدهید</b>\n\n"
                             "برای عملکرد صحیح ربات، لطفاً:\n"
                             "• ربات را به عنوان ادمین اضافه کنید\n"
                             "• تمام دسترسی‌های لازم را به ربات بدهید",
                        parse_mode="HTML"
                    )
                    logger.warning(f"Bot added to group {message.chat.id} but doesn't have admin rights")
                    # Don't return here - continue with group registration
                
                # Fetch group metadata
                try:
                    group_metadata = await fetch_group_metadata(message.chat.id)
                    
                    # Add additional information to match the API response format
                    group_metadata.update({
                        "topic_id": None,  # No specific topic when auto-registering
                        "custom_name": message.chat.title,  # Use group title as custom name
                        "custom_description": getattr(message.chat, 'description', None),
                        "registered_at": datetime.now().isoformat(),
                        "topic_info": {
                            "has_topics": group_metadata.get("has_topics_enabled", False),
                            "supports_topics": group_metadata.get("has_topics_enabled", False),
                            "topic_id_provided": False,
                            "topic_count": len(group_metadata.get("available_topics", [])),
                            "recommended_usage": "Use topic_id for supergroups, ignore for channels and simple groups"
                        },
                        "auto_registered_at": datetime.now().isoformat(),
                        "registration_source": "bot_added_to_group"
                    })
                    
                    # Send to backend using the same format as the API response
                    success = await auto_register_group_to_backend(group_metadata)
                    
                    if success:
                        # Send success message to group
                        admin_status = "✅ ادمین" if bot_has_admin_rights else "⚠️ عضو عادی"
                        await bot.send_message(
                            chat_id=message.chat.id,
                            text="✅ <b>ربات با موفقیت اضافه شد!</b>\n\n"
                                 f"🎉 گروه به صورت خودکار ثبت شد\n"
                                 f"🤖 ربات آماده دریافت رسیدها است\n"
                                 f"👤 وضعیت ربات: {admin_status}\n"
                                 "📋 از API برای ارسال رسید به این گروه استفاده کنید",
                            parse_mode="HTML"
                        )
                        logger.info(f"Bot successfully added and registered in group {message.chat.id}")
                    else:
                        logger.error(f"Failed to auto-register group {message.chat.id}")
                        
                except Exception as e:
                    logger.error(f"Error auto-registering group {message.chat.id}: {e}")
        
        # For all other messages, let the existing handlers process them
        # Don't return here - let the message continue to other handlers
        
    except Exception as e:
        logger.error(f"Error in handle_new_chat_members: {e}")
        # Don't return here - let the message continue to other handlers

# Define startup event for bot
@dp.startup()
async def on_startup():
    """Actions to run on bot startup"""
    print("Bot startup complete: API-based authentication system ready.")
    print("Webhook API available at: http://localhost:3030")
    print("API documentation at: http://localhost:3030/docs")
    print(f"Auto-registration endpoint: {config.AUTO_REGISTER_ENDPOINT}")

async def run_bot():
    """Run the Telegram bot polling"""
    await dp.start_polling(bot)

async def run_webhook():
    """Run the webhook server"""
    config_uvicorn = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=3030,
        log_level="info"
    )
    server = uvicorn.Server(config_uvicorn)
    await server.serve()

async def main():
    """Main function to run both bot and webhook server concurrently"""
    print("Starting Telegram Bot with Webhook API...")
    print("Bot will handle Telegram messages")
    print("Webhook API will handle external notifications")
    print("Press Ctrl+C to stop both services")
    
    try:
        # Run both services concurrently
        await asyncio.gather(
            run_bot(),
            run_webhook()
        )
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        # Close bot session
        try:
            await bot.session.close()
        except:
            pass
        logger.info("Shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
