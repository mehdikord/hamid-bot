import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from datetime import datetime
import logging
import httpx
import json

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
dp.include_router(auth.router)  # Authentication router (highest priority)
dp.include_router(common.router)  # Common commands like /start
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
    
    class Config:
        json_schema_extra = {
            "example": {
                "group_id": -1001234567890,
                "topic_id": 12345,
                "group_name": "Customer Support",
                "description": "Main support group for customer inquiries"
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
    assignee: str = Field(..., description="Assignee username or name")
    group_id: int = Field(..., description="Telegram group ID")
    topic_id: Optional[int] = Field(None, description="Topic ID for posting the receipt")
    
    class Config:
        json_schema_extra = {
            "example": {
                "price_deal": 1500.00,
                "price_deposit": 500.00,
                "date": "2024-01-15",
                "image": "https://example.com/receipt.jpg",
                "customer_name": "John Doe",
                "customer_phone": "+1234567890",
                "assignee": "agent_username",
                "group_id": -1001234567890,
                "topic_id": 12345
            }
        }

# Group and receipt service functions
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
        
        message = f"""
🧾 <b>اطلاعات رسید</b>

👤 <b>مشتری:</b> {receipt_data.customer_name}
📞 <b>تلفن:</b> {receipt_data.customer_phone}
👨‍💼 <b>مسئول:</b> {receipt_data.assignee}
📅 <b>تاریخ:</b> {receipt_data.date}

💰 <b>قیمت کل:</b> ${receipt_data.price_deal:,.2f}
💳 <b>پیش پرداخت:</b> ${receipt_data.price_deposit:,.2f}
📊 <b>باقی مانده:</b> ${remaining_amount:,.2f}

{'📷 <b>تصویر رسید:</b> ضمیمه شده' if receipt_data.image else ''}
        """.strip()
        
        # Send message to group/topic
        # Only use message_thread_id for groups/supergroups, not channels
        send_params = {
            "chat_id": group_id,
            "parse_mode": "HTML"
        }
        
        # Only add message_thread_id if it's provided (for groups with topics)
        if topic_id is not None:
            send_params["message_thread_id"] = topic_id
        
        # If there's an image, send as photo with caption, otherwise send as text message
        if receipt_data.image and receipt_data.image.startswith('http'):
            try:
                # Send image with receipt text as caption
                send_params["photo"] = receipt_data.image
                send_params["caption"] = message
                sent_message = await bot.send_photo(**send_params)
            except Exception as e:
                logger.error(f"Could not send image, falling back to text: {e}")
                # Fallback to text message if image fails
                send_params["text"] = message
                sent_message = await bot.send_message(**send_params)
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
        
        # Add additional information from request
        group_metadata.update({
            "topic_id": request.topic_id,
            "custom_name": request.group_name,
            "custom_description": request.description,
            "registered_at": datetime.now().isoformat(),
            "topic_info": {
                "has_topics": group_metadata.get("type") in ["supergroup"],
                "supports_topics": group_metadata.get("type") in ["supergroup"],
                "topic_id_provided": request.topic_id is not None,
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
                    "price_deal": request.price_deal,
                    "price_deposit": request.price_deposit,
                    "remaining_amount": request.price_deal - request.price_deposit,
                    "date": request.date,
                    "assignee": request.assignee,
                    "group_id": request.group_id,
                    "topic_id": request.topic_id,
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

@app.get("/api/groups/{group_id}/topics")
async def get_group_topics(group_id: int):
    """Get available topics for a group (if supported)"""
    try:
        logger.info(f"Fetching topics for group_id: {group_id}")
        
        # Note: Telegram Bot API doesn't provide a direct way to list topics
        # This is a placeholder endpoint that could be enhanced with custom logic
        # You might need to maintain a list of topics manually or use other methods
        
        return {
            "success": True,
            "message": "Topics endpoint - implementation depends on your topic management strategy",
            "group_id": group_id,
            "note": "Telegram Bot API doesn't provide direct topic listing. Consider maintaining topic list manually or using message_thread_id from previous messages."
        }
        
    except Exception as e:
        logger.error(f"Error fetching group topics: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Auto-registration handler for when bot is added to groups
@dp.message()
async def handle_new_chat_members(message: Message):
    """Handle when bot is added to a group/channel"""
    try:
        # Only handle messages with new_chat_members (when someone is added)
        if message.new_chat_members:
            bot_was_added = any(member.id == bot.id for member in message.new_chat_members)
            
            if bot_was_added and message.chat.type in ['group', 'supergroup', 'channel']:
                logger.info(f"Bot was added to {message.chat.type}: {message.chat.id}")
                
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
                            "has_topics": group_metadata.get("type") in ["supergroup"],
                            "supports_topics": group_metadata.get("type") in ["supergroup"],
                            "topic_id_provided": False,
                            "recommended_usage": "Use topic_id for supergroups, ignore for channels and simple groups"
                        },
                        "auto_registered_at": datetime.now().isoformat(),
                        "registration_source": "bot_added_to_group"
                    })
                    
                    # Send to backend using the same format as the API response
                    success = await auto_register_group_to_backend(group_metadata)
                    
                    if success:
                        # Send confirmation message to group
                        await bot.send_message(
                            chat_id=message.chat.id,
                            text="🤖 <b>Bot Added Successfully!</b>\n\n✅ Group registered automatically\n✅ Ready to receive receipts\n\nUse the API to send receipts to this group!",
                            parse_mode="HTML"
                        )
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
    
    # Run both services concurrently
    await asyncio.gather(
        run_bot(),
        run_webhook()
    )

if __name__ == "__main__":
    asyncio.run(main())
