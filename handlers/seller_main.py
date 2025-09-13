"""
Main Seller Dashboard
Project-based workflow for sellers - API-based
"""
from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
from keyboards.navigation import home_button

from datetime import datetime, timedelta

router = Router()

class SellerStates(StatesGroup):
    project_selected = State()

# Add reminder states
class ReminderStates(StatesGroup):
    waiting_title = State()
    waiting_text = State()
    waiting_time = State()
    waiting_project = State()
    waiting_lead = State()

# Store user's current project selection
user_projects = {}

# API endpoints - replace with your actual endpoints
API_BASE_URL = "https://your-real-api-domain.com"

async def call_api(endpoint: str, data: dict = None, method: str = "GET") -> dict:
    """Generic API call function"""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            if method.upper() == "GET":
                response = await client.get(f"{API_BASE_URL}{endpoint}", timeout=10.0)
            elif method.upper() == "POST":
                response = await client.post(f"{API_BASE_URL}{endpoint}", json=data, timeout=10.0)
            elif method.upper() == "PUT":
                response = await client.put(f"{API_BASE_URL}{endpoint}", json=data, timeout=10.0)
            elif method.upper() == "DELETE":
                response = await client.delete(f"{API_BASE_URL}{endpoint}", timeout=10.0)
            
            if response.status_code in [200, 201]:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"API returned status {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.message(F.text == "🏢 پروژه‌های من")
async def seller_projects(message: types.Message):
    """Show seller's projects - requires authentication"""
    user_id = message.from_user.id
    
    # Check if user is in seller list (additional security)
    if user_id not in config.SELLER_IDS:
        await message.answer("❌ شما مجاز به استفاده از این ربات نیستید.")
        return
    
    # Get seller's projects from API
    api_response = await call_api(f"/api/sellers/{user_id}/projects")
    
    if not api_response["success"]:
        await message.answer("❌ خطا در دریافت پروژه‌ها. لطفاً دوباره تلاش کنید.")
        return
    
    projects = api_response["data"].get("projects", [])
    
    if not projects:
        await message.answer(
            "❌ هیچ پروژه‌ای به شما واگذار نشده است.\n"
            "لطفاً با مدیر خود تماس بگیرید."
        )
        return
    
    # Create projects keyboard
    builder = InlineKeyboardBuilder()
    for project in projects:
        builder.button(
            text=f"📁 {project['name']} ({project.get('total_leads', 0)} لید)",
            callback_data=f"project_{project['id']}"
        )
    
    builder.button(text="🏠 بازگشت به منوی اصلی", callback_data="nav_home")
    builder.adjust(1)
    
    await message.answer(
        " پروژه‌های شما:\n\n"
        "لطفاً یکی از پروژه‌ها را انتخاب کنید:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("project_"))
async def handle_project_selection(callback: types.CallbackQuery, state: FSMContext):
    """Handle project selection"""
    project_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    # Store selected project
    await state.update_data(selected_project_id=project_id)
    await state.set_state(SellerStates.project_selected)
    
    # Get project details from API
    api_response = await call_api(f"/api/projects/{project_id}")
    
    if not api_response["success"]:
        await callback.answer("❌ خطا در دریافت اطلاعات پروژه", show_alert=True)
        return
    
    project = api_response["data"]
    
    # Show project menu
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 لیدهای جدید", callback_data=f"leads_new_{project_id}")
    builder.button(text="📞 لیدهای تماس گرفته شده", callback_data=f"leads_contacted_{project_id}")
    builder.button(text="✅ لیدهای واجد شرایط", callback_data=f"leads_qualified_{project_id}")
    builder.button(text="📋 پیشنهادات ارسال شده", callback_data=f"leads_proposal_{project_id}")
    builder.button(text=" مذاکرات", callback_data=f"leads_negotiation_{project_id}")
    builder.button(text="🔔 ایجاد یادآور", callback_data=f"reminder_project_{project_id}")
    builder.button(text="📊 گزارش پروژه", callback_data=f"report_project_{project_id}")
    builder.button(text="🏠 بازگشت", callback_data="nav_home")
    
    builder.adjust(2, 2, 2, 1, 1)
    
    await callback.message.edit_text(
        f"📁 پروژه: {project['name']}\n\n"
        f"📊 آمار کلی:\n"
        f"• کل لیدها: {project.get('total_leads', 0)}\n"
        f"• لیدهای جدید: {project.get('new_leads', 0)}\n"
        f"• لیدهای تماس گرفته شده: {project.get('contacted_leads', 0)}\n"
        f"• لیدهای واجد شرایط: {project.get('qualified_leads', 0)}\n\n"
        "لطفاً یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("leads_"))
async def handle_leads_view(callback: types.CallbackQuery):
    """Handle leads view by status"""
    parts = callback.data.split("_")
    status = parts[1]
    project_id = int(parts[2])
    user_id = callback.from_user.id
    
    # Get leads with this status from API
    api_response = await call_api(f"/api/projects/{project_id}/leads?status={status}&user_id={user_id}")
    
    if not api_response["success"]:
        await callback.answer("❌ خطا در دریافت لیدها", show_alert=True)
        return
    
    leads = api_response["data"].get("leads", [])
    status_name = {
        "new": "جدید",
        "contacted": "تماس گرفته شده", 
        "qualified": "واجد شرایط",
        "proposal": "پیشنهاد ارسال شده",
        "negotiation": "مذاکره"
    }.get(status, status)
    
    if not leads:
        await callback.answer(f"❌ هیچ لید {status_name}ی یافت نشد", show_alert=True)
        return
    
    # Create leads keyboard
    builder = InlineKeyboardBuilder()
    for lead in leads[:10]:  # Limit to 10 leads
        builder.button(
            text=f"👤 {lead.get('customer_name', 'نامشخص')} - {lead.get('value', 0):,} تومان",
            callback_data=f"lead_{lead['id']}"
        )
    
    builder.button(text="🏠 بازگشت", callback_data=f"project_{project_id}")
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"👥 لیدهای {status_name}:\n\n"
        f"تعداد: {len(leads)} لید\n\n"
        "لطفاً یکی از لیدها را انتخاب کنید:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("lead_"))
async def handle_lead_details(callback: types.CallbackQuery):
    """Handle lead details view"""
    lead_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    # Get lead details from API
    api_response = await call_api(f"/api/leads/{lead_id}?user_id={user_id}")
    
    if not api_response["success"]:
        await callback.answer("❌ خطا در دریافت اطلاعات لید", show_alert=True)
        return
    
    lead = api_response["data"]
    
    if not lead:
        await callback.answer("❌ لید یافت نشد", show_alert=True)
        return
    
    # Create lead actions keyboard
    builder = InlineKeyboardBuilder()
    builder.button(text="📞 تماس گرفته شد", callback_data=f"update_lead_{lead_id}_contacted")
    builder.button(text="✅ واجد شرایط", callback_data=f"update_lead_{lead_id}_qualified")
    builder.button(text="📋 ارسال پیشنهاد", callback_data=f"update_lead_{lead_id}_proposal")
    builder.button(text=" شروع مذاکره", callback_data=f"update_lead_{lead_id}_negotiation")
    builder.button(text="🔔 ایجاد یادآور", callback_data=f"reminder_lead_{lead_id}")
    builder.button(text="📝 افزودن یادداشت", callback_data=f"note_lead_{lead_id}")
    builder.button(text="🏠 بازگشت", callback_data="nav_home")
    
    builder.adjust(2, 2, 2, 1)
    
    await callback.message.edit_text(
        f" اطلاعات لید:\n\n"
        f"📋 نام: {lead.get('customer_name', 'نامشخص')}\n"
        f"🏢 شرکت: {lead.get('company', 'نامشخص')}\n"
        f"📱 تلفن: {lead.get('phone', 'نامشخص')}\n"
        f" ایمیل: {lead.get('email', 'نامشخص')}\n"
        f"💰 ارزش: {lead.get('value', 0):,} تومان\n"
        f" وضعیت: {lead.get('stage', 'نامشخص')}\n"
        f"⭐ اولویت: {lead.get('priority', 'متوسط')}\n"
        f" تاریخ ایجاد: {lead.get('created_at', 'نامشخص')}\n\n"
        f"📝 توضیحات:\n{lead.get('description', 'بدون توضیحات')}",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("update_lead_"))
async def handle_lead_status_update(callback: types.CallbackQuery):
    """Handle lead status update"""
    parts = callback.data.split("_")
    lead_id = int(parts[2])
    new_status = parts[3]
    user_id = callback.from_user.id
    
    # Update lead status via API
    api_response = await call_api(
        f"/api/leads/{lead_id}/status",
        {"status": new_status, "user_id": user_id},
        "PUT"
    )
    
    if api_response["success"]:
        status_names = {
            "contacted": "تماس گرفته شده",
            "qualified": "واجد شرایط", 
            "proposal": "پیشنهاد ارسال شده",
            "negotiation": "مذاکره"
        }
        status_name = status_names.get(new_status, new_status)
        await callback.answer(f"✅ وضعیت لید به '{status_name}' تغییر یافت", show_alert=True)
        
        # Refresh lead details
        await handle_lead_details(callback)
    else:
        await callback.answer("❌ خطا در به‌روزرسانی وضعیت", show_alert=True)

@router.callback_query(F.data.startswith("reminder_"))
async def handle_reminder_creation(callback: types.CallbackQuery, state: FSMContext):
    """Handle reminder creation"""
    parts = callback.data.split("_")
    reminder_type = parts[1]  # 'project' or 'lead'
    target_id = int(parts[2])
    user_id = callback.from_user.id
    
    if reminder_type == "project":
        # Get project details from API
        api_response = await call_api(f"/api/projects/{target_id}")
        if not api_response["success"]:
            await callback.answer("❌ خطا در دریافت اطلاعات پروژه", show_alert=True)
            return
        project = api_response["data"]
        project_name = project['name']
    else:  # lead
        # Get lead details from API
        api_response = await call_api(f"/api/leads/{target_id}?user_id={user_id}")
        if not api_response["success"]:
            await callback.answer("❌ خطا در دریافت اطلاعات لید", show_alert=True)
            return
        lead = api_response["data"]
        project_name = lead.get('customer_name', 'نامشخص')
    
    # Store reminder context
    await state.update_data(
        reminder_type=reminder_type,
        target_id=target_id,
        project_name=project_name
    )
    await state.set_state(ReminderStates.waiting_title)
    
    await callback.message.edit_text(
        f"🔔 ایجاد یادآور برای {project_name}\n\n"
        "لطفاً عنوان یادآور را وارد کنید:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ لغو", callback_data="cancel_reminder")]
        ])
    )

@router.message(ReminderStates.waiting_title)
async def handle_reminder_title(message: types.Message, state: FSMContext):
    """Handle reminder title input"""
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("❌ عنوان یادآور باید حداقل 3 کاراکتر باشد. لطفاً دوباره وارد کنید:")
        return
    
    await state.update_data(title=title)
    await state.set_state(ReminderStates.waiting_text)
    
    await message.answer("📝 لطفاً متن یادآور را وارد کنید:")

@router.message(ReminderStates.waiting_text)
async def handle_reminder_text(message: types.Message, state: FSMContext):
    """Handle reminder text input"""
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("❌ متن یادآور باید حداقل 5 کاراکتر باشد. لطفاً دوباره وارد کنید:")
        return
    
    await state.update_data(text=text)
    await state.set_state(ReminderStates.waiting_time)
    
    await message.answer(
        "⏰ لطفاً زمان یادآور را وارد کنید:\n\n"
        "فرمت: YYYY-MM-DD HH:MM\n"
        "مثال: 2024-01-15 14:30"
    )

@router.message(ReminderStates.waiting_time)
async def handle_reminder_time(message: types.Message, state: FSMContext):
    """Handle reminder time input"""
    time_str = message.text.strip()
    user_id = message.from_user.id
    
    try:
        # Parse datetime
        due_datetime = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        due_timestamp = int(due_datetime.timestamp())
        
        # Get reminder data
        state_data = await state.get_data()
        title = state_data["title"]
        text = state_data["text"]
        reminder_type = state_data["reminder_type"]
        target_id = state_data["target_id"]
        
        # Create reminder via API
        reminder_data = {
            "user_id": user_id,
            "title": title,
            "text": text,
            "due_at": due_timestamp,
            "reminder_type": reminder_type,
            "target_id": target_id
        }
        
        api_response = await call_api("/api/reminders", reminder_data, "POST")
        
        if api_response["success"]:
            await message.answer(
                f"✅ یادآور با موفقیت ایجاد شد!\n\n"
                f" عنوان: {title}\n"
                f"📄 متن: {text}\n"
                f"⏰ زمان: {time_str}"
            )
        else:
            await message.answer("❌ خطا در ایجاد یادآور. لطفاً دوباره تلاش کنید.")
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ فرمت زمان صحیح نیست!\n\n"
            "لطفاً زمان را به فرمت زیر وارد کنید:\n"
            "YYYY-MM-DD HH:MM\n"
            "مثال: 2024-01-15 14:30"
        )

@router.callback_query(F.data == "cancel_reminder")
async def cancel_reminder(callback: types.CallbackQuery, state: FSMContext):
    """Cancel reminder creation"""
    await state.clear()
    await callback.message.edit_text("❌ ایجاد یادآور لغو شد.")
    await callback.answer()

@router.callback_query(F.data.startswith("report_project_"))
async def handle_project_report(callback: types.CallbackQuery):
    """Handle project report generation"""
    project_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    # Get project report from API
    api_response = await call_api(f"/api/projects/{project_id}/report?user_id={user_id}")
    
    if not api_response["success"]:
        await callback.answer("❌ خطا در تولید گزارش", show_alert=True)
        return
    
    report = api_response["data"]
    
    # Create report keyboard
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 گزارش تفصیلی", callback_data=f"detailed_report_{project_id}")
    builder.button(text="📈 نمودارها", callback_data=f"charts_{project_id}")
    builder.button(text="📋 خروجی Excel", callback_data=f"excel_{project_id}")
    builder.button(text="🏠 بازگشت", callback_data=f"project_{project_id}")
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        f" گزارش پروژه:\n\n"
        f"📁 نام پروژه: {report.get('project_name', 'نامشخص')}\n"
        f"📅 دوره: {report.get('period', 'نامشخص')}\n\n"
        f"📈 آمار کلی:\n"
        f"• کل لیدها: {report.get('total_leads', 0)}\n"
        f"• لیدهای جدید: {report.get('new_leads', 0)}\n"
        f"• لیدهای تماس گرفته شده: {report.get('contacted_leads', 0)}\n"
        f"• لیدهای واجد شرایط: {report.get('qualified_leads', 0)}\n"
        f"• پیشنهادات ارسال شده: {report.get('proposal_leads', 0)}\n"
        f"• مذاکرات: {report.get('negotiation_leads', 0)}\n\n"
        f"💰 ارزش کل: {report.get('total_value', 0):,} تومان\n"
        f"📊 نرخ تبدیل: {report.get('conversion_rate', 0):.1f}%",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "nav_home")
async def navigate_home(callback: types.CallbackQuery, state: FSMContext):
    """Navigate back to home"""
    await state.clear()
    await callback.message.edit_text(
        "🏠 منوی اصلی\n\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🏢 پروژه‌های من", callback_data="my_projects")],
            [types.InlineKeyboardButton(text="📊 گزارش‌ها", callback_data="reports")],
            [types.InlineKeyboardButton(text="🔔 یادآوری‌ها", callback_data="reminders")],
            [types.InlineKeyboardButton(text=" پروفایل", callback_data="profile")]
        ])
    )
