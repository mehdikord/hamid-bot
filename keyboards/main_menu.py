from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import config

def get_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Return the main menu inline keyboard tailored to the user's role (Persian)."""
    buttons = []
    
    if user_id in config.MANAGER_IDS:
        # Manager menu buttons (Persian)
        buttons.append([
            InlineKeyboardButton(text="🆕 ایجاد Lead", callback_data="create_lead_wizard"),
            InlineKeyboardButton(text="📊 Import Excel", callback_data="import_excel")
        ])
        buttons.append([
            InlineKeyboardButton(text="📋 مدیریت Leads", callback_data="manage_leads"),
            InlineKeyboardButton(text="📊 گزارش‌ها", callback_data="view_reports")
        ])
        buttons.append([
            InlineKeyboardButton(text="💰 ثبت پرداخت", callback_data="record_payment"),
            InlineKeyboardButton(text="🔔 یادآورها", callback_data="add_reminder")
        ])
    elif user_id in config.SELLER_IDS:
        # Seller menu buttons (Persian)
        buttons.append([
            InlineKeyboardButton(text="📋 Leads من", callback_data="my_leads"),
            InlineKeyboardButton(text="📊 گزارش من", callback_data="my_reports")
        ])
        buttons.append([
            InlineKeyboardButton(text="✅ وظایف", callback_data="my_tasks"),
            InlineKeyboardButton(text="🔔 یادآورها", callback_data="add_reminder")
        ])
    else:
        # Fallback: no menu for unknown role
        buttons.append([InlineKeyboardButton(text="غیرمجاز", callback_data="ignore")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
