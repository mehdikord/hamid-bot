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

import config
from keyboards import main_menu

router = Router()

class AuthStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_code = State()

def convert_phone_to_iranian_format(phone: str) -> str:
    """
    Convert phone number from +989123456789 format to 09123456789 format
    """
    # Remove any spaces or special characters
    phone = re.sub(r'[^\d+]', '', phone)
    
    # If it starts with +98, convert to 09xx format
    if phone.startswith('+98'):
        return '0' + phone[3:]
    
    # If it starts with 98, convert to 09xx format
    if phone.startswith('98'):
        return '0' + phone[2:]
    
    # If it already starts with 0, return as is
    if phone.startswith('0'):
        return phone
    
    # If it's just 9 digits, add 0 prefix
    if len(phone) == 10 and phone.startswith('9'):
        return '0' + phone
    
    # Default: return as is
    return phone

async def send_auth_request(phone: str, telegram_id: int) -> dict:
    """
    Send authentication request to backend API
    POST to BASE_URL/bot/auth/send
    """
    try:
        url = f"{config.BASE_URL}/bot/auth/send"
        
        payload = {
            "phone": phone,
            "telegram_id": str(telegram_id)
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=10.0
            )
            
            print(f"Auth API Response: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                response_data = response.json()
                return {
                    "success": True,
                    "data": response_data,
                    "status_code": response.status_code
                }
            elif response.status_code == 409:
                response_data = response.json()
                return {
                    "success": False,
                    "error": response_data.get("error", "user not found"),
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "status_code": response.status_code
                }
                
    except Exception as e:
        print(f"Error sending auth request to API: {e}")
        return {
            "success": False,
            "error": str(e),
            "status_code": None
        }

async def verify_sms_code(telegram_id: int, code: str) -> dict:
    """
    Verify SMS code with backend API
    POST to BASE_URL/bot/auth/verify
    """
    try:
        url = f"{config.BASE_URL}/bot/auth/verify"
        
        payload = {
            "telegram_id": str(telegram_id),
            "code": code
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=10.0
            )
            
            print(f"Verify API Response: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                response_data = response.json()
                return {
                    "success": True,
                    "data": response_data,
                    "status_code": response.status_code
                }
            elif response.status_code == 409:
                response_data = response.json()
                return {
                    "success": False,
                    "error": response_data.get("error", "کد تایید اشتباه است"),
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "status_code": response.status_code
                }
                
    except Exception as e:
        print(f"Error verifying SMS code with API: {e}")
        return {
            "success": False,
            "error": str(e),
            "status_code": None
        }

def validate_phone_number(phone: str) -> bool:
    """Validate phone number format (Iranian format)"""
    # Remove any spaces or special characters
    clean_phone = re.sub(r'[^\d+]', '', phone)
    
    # Check if it's in +989123456789 format
    if re.match(r'^\+98[0-9]{10}$', clean_phone):
        return True
    
    # Check if it's in 09123456789 format
    if re.match(r'^09[0-9]{9}$', clean_phone):
        return True
    
    # Check if it's in 989123456789 format
    if re.match(r'^98[0-9]{10}$', clean_phone):
        return True
    
    return False

@router.message(F.text == "/start")
async def start_auth(message: types.Message, state: FSMContext):
    """Handle /start command - show authentication options"""
    await message.answer(
        "🔐 به ربات خوش آمدید!\n\n"
        "برای ورود، یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=get_auth_keyboard()
    )

@router.message(F.text == "📱 اشتراک‌گذاری شماره تلفن")
async def share_phone_button(message: types.Message, state: FSMContext):
    """Handle phone sharing button"""
    await message.answer(
        "📱 لطفاً دکمه اشتراک‌گذاری شماره تلفن را فشار دهید تا شماره شما به صورت خودکار وارد شود."
    )

@router.message(F.text == "📝 ورود با شماره تلفن")
async def manual_phone_entry(message: types.Message, state: FSMContext):
    """Handle manual phone number entry"""
    await message.answer(
        "📱 لطفاً شماره تلفن خود را وارد کنید:",
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
            "لطفاً شماره را به یکی از فرمت‌های زیر وارد کنید:\n"
            "• +989123456789\n"
            "• 09123456789\n"
            "• 989123456789"
        )
        return
    
    # Convert to Iranian format (09xx)
    iranian_phone = convert_phone_to_iranian_format(phone)
    
    # Send authentication request to backend
    api_response = await send_auth_request(iranian_phone, message.chat.id)
    
    if api_response["success"]:
        # Success response
        response_data = api_response["data"]
        if response_data.get("message") == "success":
            await message.answer(
                f"✅ کد تایید برای شماره {iranian_phone} ارسال شد.\n\n"
                "لطفاً کد 6 رقمی دریافتی را وارد کنید:"
            )
            await state.set_state(AuthStates.waiting_for_code)
            # Store phone in state for verification
            await state.update_data(phone=iranian_phone)
        else:
            await message.answer("❌ خطا در ارسال کد تایید. لطفاً دوباره تلاش کنید.")
    else:
        # Error response
        if api_response["status_code"] == 409:
            await message.answer(
                "❌ کاربری با این شماره تلفن یافت نشد.\n\n"
                "لطفاً شماره صحیح خود را وارد کنید یا با پشتیبانی تماس بگیرید."
            )
        else:
            await message.answer("❌ خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید.")

@router.message(F.contact)
async def handle_contact_shared(message: types.Message, state: FSMContext):
    """Handle shared contact (phone number)"""
    if not message.contact:
        await message.answer("❌ خطا در دریافت شماره تلفن.")
        return
    
    phone = message.contact.phone_number
    
    # Convert to Iranian format (09xx)
    iranian_phone = convert_phone_to_iranian_format(phone)
    
    # Send authentication request to backend
    api_response = await send_auth_request(iranian_phone, message.chat.id)
    
    if api_response["success"]:
        # Success response
        response_data = api_response["data"]
        if response_data.get("message") == "success":
            await message.answer(
                f"✅ کد تایید برای شماره {iranian_phone} ارسال شد.\n\n"
                "لطفاً کد 6 رقمی دریافتی را وارد کنید:",
                reply_markup=types.ReplyKeyboardRemove()
            )
            await state.set_state(AuthStates.waiting_for_code)
            # Store phone in state for verification
            await state.update_data(phone=iranian_phone)
        else:
            await message.answer("❌ خطا در ارسال کد تایید. لطفاً دوباره تلاش کنید.")
    else:
        # Error response
        if api_response["status_code"] == 409:
            await message.answer(
                "❌ کاربری با این شماره تلفن یافت نشد.\n\n"
                "لطفاً شماره صحیح خود را وارد کنید یا با پشتیبانی تماس بگیرید."
            )
        else:
            await message.answer("❌ خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید.")

@router.message(AuthStates.waiting_for_code)
async def handle_code_input(message: types.Message, state: FSMContext):
    """Handle SMS verification code input"""
    code = message.text.strip()
    
    # Validate code format (6 digits)
    if not code.isdigit() or len(code) != 6:
        await message.answer("❌ کد تایید باید 6 رقم باشد. لطفاً دوباره وارد کنید:")
        return
    
    # Verify the code with backend API
    api_response = await verify_sms_code(message.chat.id, code)
    
    if api_response["success"]:
        # Code is valid, user is authenticated
        response_data = api_response["data"]
        result = response_data.get("result", {})
        user_name = result.get("name", "کاربر")
        
        await message.answer(
            f"سلام {user_name} خوش آمدید!",
            reply_markup=main_menu.get_main_menu_keyboard(message.chat.id)
        )
        await state.clear()
    else:
        # Code is invalid
        if api_response["status_code"] == 409:
            await message.answer("❌ کد تایید اشتباه است. لطفاً دوباره وارد کنید:")
        else:
            await message.answer("❌ خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید.")

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