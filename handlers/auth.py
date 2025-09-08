"""
Authentication Handler
Handles user login via backend API
"""
import httpx
import re
from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from keyboards import main_menu

router = Router()

class AuthStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_code = State()

# Real API endpoint - replace with your actual endpoint
AUTH_API_URL = "https://your-real-api-domain.com/auth/start"

async def send_telegram_id_to_api(telegram_id: int) -> dict:
    """Send Telegram ID to backend API and return response data"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                AUTH_API_URL,
                json={"telegram_id": telegram_id},
                timeout=10.0
            )
            print(f"API Response: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "status_code": response.status_code
                }
    except Exception as e:
        print(f"Error sending Telegram ID to API: {e}")
        return {
            "success": False,
            "error": str(e),
            "status_code": None
        }

async def send_phone_to_api(telegram_id: int, phone: str) -> dict:
    """Send phone number to backend API for SMS verification"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                AUTH_API_URL.replace("/auth/start", "/auth/send-sms"),
                json={"telegram_id": telegram_id, "phone": phone},
                timeout=10.0
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "status_code": response.status_code
                }
    except Exception as e:
        print(f"Error sending phone to API: {e}")
        return {
            "success": False,
            "error": str(e),
            "status_code": None
        }

async def verify_code_with_api(telegram_id: int, phone: str, code: str) -> dict:
    """Verify SMS code with backend API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                AUTH_API_URL.replace("/auth/start", "/auth/verify-code"),
                json={"telegram_id": telegram_id, "phone": phone, "code": code},
                timeout=10.0
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "status_code": response.status_code
                }
    except Exception as e:
        print(f"Error verifying code with API: {e}")
        return {
            "success": False,
            "error": str(e),
            "status_code": None
        }

def validate_phone_number(phone: str) -> bool:
    """Validate phone number format (+989123456789)"""
    pattern = r'^\+98[0-9]{10}$'
    return bool(re.match(pattern, phone))

@router.message(F.text == "/start")
async def start_auth(message: types.Message, state: FSMContext):
    """Handle /start command - get data from backend API"""
    chat_id = message.chat.id
    
    # Send Telegram ID to backend API and get response
    api_response = await send_telegram_id_to_api(chat_id)
    
    if api_response["success"]:
        # Backend returned data successfully
        backend_data = api_response["data"]
        
        # Display the response from backend
        # You can customize this based on your backend response structure
        if backend_data.get("is_logged_in", False):
            # User is logged in according to backend
            user_info = backend_data.get("user_info", {})
            phone = user_info.get("phone", "نامشخص")
            name = user_info.get("name", "کاربر")
            
            await message.answer(
                f"👋 خوش آمدید {name}!\n"
                f"شماره تلفن: {phone}\n\n"
                "برای شروع کار، یکی از گزینه‌های زیر را انتخاب کنید:",
                reply_markup=main_menu.get_main_menu_keyboard(message.chat.id)
            )
        else:
            # User needs to authenticate
            auth_message = backend_data.get("message", "برای استفاده از امکانات ربات، لطفاً وارد شوید:")
            await message.answer(
                f"🔐 به ربات CRM خوش آمدید!\n\n{auth_message}",
                reply_markup=get_auth_keyboard()
            )
    else:
        # API error - show authentication options
        await message.answer(
            "🔐 به ربات CRM خوش آمدید!\n\n"
            "برای استفاده از امکانات ربات، لطفاً وارد شوید:",
            reply_markup=get_auth_keyboard()
        )

@router.message(F.text == "📱 اشتراک‌گذاری شماره تلفن")
async def share_phone_button(message: types.Message, state: FSMContext):
    """Handle phone sharing button"""
    # This will be handled by the contact handler when user shares their phone
    await message.answer(
        "📱 لطفاً دکمه اشتراک‌گذاری شماره تلفن را فشار دهید تا شماره شما به صورت خودکار وارد شود."
    )

@router.message(F.text == "📝 ورود با شماره تلفن")
async def manual_phone_entry(message: types.Message, state: FSMContext):
    """Handle manual phone number entry"""
    await message.answer(
        "📱 لطفاً شماره تلفن خود را وارد کنید:\n\n"
        "فرمت: +989123456789",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AuthStates.waiting_for_phone)

@router.message(AuthStates.waiting_for_phone)
async def handle_phone_input(message: types.Message, state: FSMContext):
    """Handle manual phone number input"""
    phone = message.text.strip()
    
    if not validate_phone_number(phone):
        await message.answer(
            "❌ فرمت شماره تلفن صحیح نیست!\n\n"
            "لطفاً شماره را به فرمت زیر وارد کنید:\n"
            "مثال: +989123456789"
        )
        return
    
    # Send phone to backend API for SMS verification
    api_response = await send_phone_to_api(message.chat.id, phone)
    
    if api_response["success"]:
        await message.answer(
            f"📱 کد تایید برای شماره {phone} ارسال شد.\n\n"
            "لطفاً کد 6 رقمی را وارد کنید:"
        )
        await state.set_state(AuthStates.waiting_for_code)
        # Store phone in state for verification
        await state.update_data(phone=phone)
    else:
        await message.answer("❌ خطا در ارسال کد تایید. لطفاً دوباره تلاش کنید.")

@router.message(F.contact)
async def handle_contact_shared(message: types.Message, state: FSMContext):
    """Handle shared contact (phone number)"""
    if not message.contact:
        await message.answer("❌ خطا در دریافت شماره تلفن.")
        return
    
    phone = message.contact.phone_number
    
    # Ensure phone number starts with +98
    if not phone.startswith('+98'):
        if phone.startswith('0'):
            phone = '+98' + phone[1:]
        elif phone.startswith('98'):
            phone = '+' + phone
        else:
            phone = '+98' + phone
    
    # Send phone to backend API for SMS verification
    api_response = await send_phone_to_api(message.chat.id, phone)
    
    if api_response["success"]:
        await message.answer(
            f"📱 کد تایید برای شماره {phone} ارسال شد.\n\n"
            "لطفاً کد 6 رقمی را وارد کنید:",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(AuthStates.waiting_for_code)
        # Store phone in state for verification
        await state.update_data(phone=phone)
    else:
        await message.answer("❌ خطا در ارسال کد تایید. لطفاً دوباره تلاش کنید.")

@router.message(AuthStates.waiting_for_code)
async def handle_code_input(message: types.Message, state: FSMContext):
    """Handle SMS verification code input"""
    code = message.text.strip()
    
    if not code.isdigit() or len(code) != 6:
        await message.answer("❌ کد تایید باید 6 رقم باشد. لطفاً دوباره وارد کنید:")
        return
    
    # Get phone from state
    state_data = await state.get_data()
    phone = state_data.get('phone')
    
    if not phone:
        await message.answer("❌ خطا در دریافت اطلاعات. لطفاً دوباره تلاش کنید.")
        await state.clear()
        return
    
    # Verify the code with backend API
    api_response = await verify_code_with_api(message.chat.id, phone, code)
    
    if api_response["success"]:
        # Code is valid, user is authenticated
        backend_data = api_response["data"]
        user_info = backend_data.get("user_info", {})
        name = user_info.get("name", "کاربر")
        
        await message.answer(
            f"✅ ورود موفقیت‌آمیز! خوش آمدید {name}!\n\n"
            "برای شروع کار، یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=main_menu.get_main_menu_keyboard(message.chat.id)
        )
        await state.clear()
    else:
        await message.answer("❌ کد تایید نامعتبر است. لطفاً دوباره وارد کنید:")

@router.message(F.text == "/profile")
async def show_profile(message: types.Message):
    """Show user profile information from backend"""
    chat_id = message.chat.id
    
    # Get user data from backend
    api_response = await send_telegram_id_to_api(chat_id)
    
    if api_response["success"]:
        backend_data = api_response["data"]
        user_info = backend_data.get("user_info", {})
        
        if user_info:
            phone = user_info.get("phone", "نامشخص")
            name = user_info.get("name", "کاربر")
            email = user_info.get("email", "نامشخص")
            role = user_info.get("role", "کاربر")
            
            await message.answer(
                f"👤 پروفایل شما:\n\n"
                f"👤 نام: {name}\n"
                f"📱 شماره تلفن: {phone}\n"
                f"📧 ایمیل: {email}\n"
                f"🎭 نقش: {role}\n"
                f"🆔 شناسه تلگرام: {chat_id}\n"
                f"✅ وضعیت: فعال"
            )
        else:
            await message.answer(
                "❌ اطلاعات کاربر یافت نشد.\n\n"
                "برای ورود، دستور /start را اجرا کنید."
            )
    else:
        await message.answer(
            "❌ خطا در دریافت اطلاعات کاربر.\n\n"
            "برای ورود، دستور /start را اجرا کنید."
        )

@router.message(F.text == "/logout")
async def logout_user(message: types.Message):
    """Logout user via backend API"""
    chat_id = message.chat.id
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                AUTH_API_URL.replace("/auth/start", "/auth/logout"),
                json={"telegram_id": chat_id, "action": "logout"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                await message.answer(
                    "✅ شما با موفقیت خارج شدید.\n\n"
                    "برای ورود مجدد، دستور /start را اجرا کنید.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
            else:
                await message.answer("❌ خطا در خروج. لطفاً دوباره تلاش کنید.")
    except Exception as e:
        print(f"Error during logout: {e}")
        await message.answer("❌ خطا در خروج. لطفاً دوباره تلاش کنید.")

def get_auth_keyboard():
    """Get authentication keyboard"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📱 اشتراک‌گذاری شماره تلفن", request_contact=True),
                KeyboardButton(text="📝 ورود با شماره تلفن")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard
