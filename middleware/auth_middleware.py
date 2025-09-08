"""
Authentication Middleware
Checks if users are authenticated via backend API before allowing access to protected routes
"""
import httpx
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

# Real API endpoint - replace with your actual endpoint
AUTH_API_URL = "https://your-real-api-domain.com/auth/check-session"

class AuthMiddleware(BaseMiddleware):
    """Middleware to check user authentication via API"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # Get chat_id from the event
        chat_id = event.chat.id if isinstance(event, Message) else event.message.chat.id
        
        # Check if user has active session via API
        is_authenticated = await check_user_auth_via_api(chat_id)
        
        if not is_authenticated:
            # User is not authenticated
            if isinstance(event, Message):
                await event.answer(
                    "🔐 برای استفاده از این قابلیت، لطفاً ابتدا وارد شوید.\n\n"
                    "دستور /start را اجرا کنید."
                )
            else:
                await event.answer(
                    "🔐 برای استفاده از این قابلیت، لطفاً ابتدا وارد شوید.",
                    show_alert=True
                )
            return
        
        # Add user data to context (you can fetch more user info from API if needed)
        data['user_authenticated'] = True
        data['user_chat_id'] = chat_id
        
        # Continue with the handler
        return await handler(event, data)

async def check_user_auth_via_api(chat_id: int) -> bool:
    """Check if user is authenticated via backend API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                AUTH_API_URL,
                json={"telegram_id": chat_id},
                timeout=5.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("is_authenticated", False)
            else:
                return False
                
    except Exception as e:
        print(f"Error checking user auth via API: {e}")
        return False
