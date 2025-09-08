import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

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

# Define startup event for bot
@dp.startup()
async def on_startup():
    """Actions to run on bot startup"""
    print("Bot startup complete: API-based authentication system ready.")
    print("Webhook API available at: http://localhost:3030")
    print("API documentation at: http://localhost:3030/docs")

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
