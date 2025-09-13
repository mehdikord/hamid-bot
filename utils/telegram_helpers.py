"""
Telegram Helper Functions
Utilities for handling common Telegram operations safely
"""
from aiogram import types

async def safe_edit_message(callback: types.CallbackQuery, text: str, reply_markup=None):
    """Safely edit a message, handling the 'message not modified' error"""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
        await callback.answer()
    except Exception as e:
        if "message is not modified" in str(e):
            await callback.answer("🔄 بروزرسانی شد")
        else:
            await callback.answer(f"خطا: {str(e)}", show_alert=True)
            raise e

async def safe_send_message(bot, chat_id: int, text: str, reply_markup=None):
    """Safely send a message with error handling"""
    try:
        return await bot.send_message(chat_id, text, reply_markup=reply_markup)
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")
        return None
