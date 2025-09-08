from aiogram import Router, types
from aiogram.filters import CommandStart

import config
from keyboards import main_menu

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Handle the /start command. Send a greeting and the main menu based on user role - Persian."""
    user_id = message.from_user.id
    
    # Determine role and prepare menu
    if user_id in config.MANAGER_IDS:
        role_name = "مدیر"
    elif user_id in config.SELLER_IDS:
        role_name = "فروشنده"
    else:
        # Unauthorized user (not in config lists)
        await message.answer("❌ شما مجاز به استفاده از این ربات داخلی نیستید.")
        return
    
    # Greet user by name and role
    first_name = message.from_user.first_name
    greeting = f"سلام {first_name}! شما به عنوان {role_name} وارد شده‌اید."
    
    # Compose main menu prompt
    prompt = "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:"
    menu_text = f"{greeting}\n{prompt}"
    
    # Get the appropriate keyboard for this user
    keyboard = main_menu.get_main_menu_keyboard(user_id)
    await message.answer(menu_text, reply_markup=keyboard)

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
