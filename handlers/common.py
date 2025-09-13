from aiogram import Router, types
from aiogram.filters import CommandStart

import config
from keyboards import main_menu

router = Router()

# This handler is now handled by auth router for unauthenticated users
# Authenticated users will be handled by other handlers after login
        

@router.callback_query(lambda c: c.data in ("nav_home", "nav_back"))
async def navigate_home(callback: types.CallbackQuery):
    """Handle navigation buttons: go back to main menu (same action for 'Back' and 'Home') - Persian."""
    user_id = callback.from_user.id
    
    # Clear any pending state (reminders are now handled differently)
    # No need to clear old reminder state as it's handled by FSM now
    
    # Edit the current message back to the main menu
    keyboard = main_menu.get_main_menu_keyboard(user_id)
    role_name = "مدیر" if user_id in config.MANAGER_IDS else "فروشنده"
    main_text = f"🏠 منو اصلی ({role_name})"
    
    await callback.message.edit_text(main_text, reply_markup=keyboard)
    await callback.answer()  # acknowledge the callback (no alert)
