from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
import config
from keyboards import main_menu
from keyboards.navigation import home_button

router = Router()

@router.message(F.text == "/report")
async def command_report(message: types.Message):
    """Handle /report command - show user's detailed daily report."""
    user_id = message.from_user.id
    
    if user_id not in config.SELLER_IDS and user_id not in config.MANAGER_IDS:
        await message.answer("❌ شما مجاز به استفاده از این دستور نیستید.")
        return
    
    # Get today's date
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    if user_id in config.SELLER_IDS:
        # Simple report for seller (placeholder)
        detailed_report = f"📊 گزارش روزانه شما - {date_str}\n\n"
        detailed_report += "• لیدهای جدید: 0\n"
        detailed_report += "• تماس‌های انجام شده: 0\n"
        detailed_report += "• فروش امروز: 0 تومان\n\n"
        detailed_report += "گزارش‌گیری کامل در حال توسعه است."
        
        await message.answer(detailed_report)
    
    elif user_id in config.MANAGER_IDS:
        # Manager report (placeholder)
        manager_report = f"📊 گزارش مدیریتی - {date_str}\n\n"
        manager_report += "• کل فروشندگان: 0\n"
        manager_report += "• کل لیدها: 0\n"
        manager_report += "• فروش کل: 0 تومان\n\n"
        manager_report += "گزارش‌گیری کامل در حال توسعه است."
        
        await message.answer(manager_report)

@router.message(F.text == "📊 گزارش‌ها")
async def show_reports_menu(message: types.Message):
    """Show reports menu"""
    user_id = message.from_user.id
    
    if user_id not in config.SELLER_IDS and user_id not in config.MANAGER_IDS:
        await message.answer("❌ شما مجاز به استفاده از این قابلیت نیستید.")
        return
    
    # Simple reports menu
    text = "📊 گزارش‌های موجود:\n\n"
    text += "• 📈 گزارش روزانه\n"
    text += "• 📈 گزارش هفتگی\n"
    text += "• 📈 گزارش ماهانه\n\n"
    text += "برای مشاهده گزارش‌ها، از دستور /report استفاده کنید."
    
    await message.answer(text)
