# bot.py - Complete Virtual Number Telegram Bot with PostgreSQL
import os
import logging
import asyncio
import re
import time
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ======================= IMPORT POSTGRESQL FUNCTIONS =======================
# Instead of SQLite, we use PostgreSQL
from db_postgres import *

# ======================= CONFIGURATION =======================

# Get from environment variables (Railway)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
FIVESIM_API_KEY = os.environ.get("FIVESIM_API_KEY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# USD to NPR exchange rate (can be set via environment variable)
USD_TO_NPR = float(os.environ.get("USD_TO_NPR", 250.0))

# Validate environment variables
if not TELEGRAM_BOT_TOKEN or not FIVESIM_API_KEY or not ADMIN_ID:
    print("❌ Missing environment variables!")
    print("Please set: TELEGRAM_BOT_TOKEN, FIVESIM_API_KEY, ADMIN_ID")
    exit(1)

# Check if DATABASE_URL is set for PostgreSQL
if not os.environ.get('DATABASE_URL'):
    print("❌ DATABASE_URL not set!")
    print("Please add PostgreSQL database to Railway.")
    print("  1. Go to Railway Dashboard")
    print("  2. Click New → Database → PostgreSQL")
    print("  3. The DATABASE_URL will be auto-added to your service")
    exit(1)

# ======================= SERVICE NAMES =======================
SERVICE_NAMES = {
    "telegram": "📱 Telegram",
    "whatsapp": "💬 WhatsApp",
    "facebook": "📘 Facebook",
    "instagram": "📸 Instagram",
    "amazon": "🛒 Amazon",
    "google": "🔍 Google",
    "microsoft": "💻 Microsoft",
    "openai": "🤖 ChatGPT",
    "tiktok": "🎵 TikTok",
    "twitter": "🐦 Twitter",
    "snapchat": "👻 Snapchat",
    "linkedin": "💼 LinkedIn",
    "discord": "🎮 Discord",
    "reddit": "🔴 Reddit",
    "spotify": "🎵 Spotify",
    "netflix": "🎬 Netflix",
    "youtube": "▶️ YouTube",
    "apple": "🍎 Apple",
    "uber": "🚗 Uber",
    "airbnb": "🏠 Airbnb",
    "paypal": "💳 PayPal",
    "coinbase": "🪙 Coinbase",
    "binance": "📊 Binance",
    "twitch": "🎮 Twitch",
    "pinterest": "📌 Pinterest",
    "tumblr": "📝 Tumblr",
}

# ======================= 5SIM API =======================

HEADERS = {"Authorization": f"Bearer {FIVESIM_API_KEY}", "Accept": "application/json"}

def api_request(url, timeout=20, retries=2):
    """Make API request with retries."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"API error {resp.status_code}, attempt {attempt+1}")
        except Exception as e:
            print(f"Request failed: {e}, attempt {attempt+1}")
        time.sleep(1)
    return None

def get_balance_usd():
    """Get your 5sim account balance in USD."""
    url = "https://5sim.net/v1/user/profile"
    data = api_request(url, timeout=10)
    if data:
        return data.get("balance", 0.0)
    return None

_services_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 300

def get_all_services():
    """Fetch all activation services from 5sim (cached)."""
    now = time.time()
    if _services_cache["data"] and (now - _services_cache["timestamp"]) < CACHE_TTL:
        return _services_cache["data"]

    data = api_request("https://5sim.net/v1/guest/products/any/any", timeout=15)
    if not data:
        return []
    services = [s for s, info in data.items() if info.get("Category") == "activation"]
    services.sort()
    _services_cache["data"] = services
    _services_cache["timestamp"] = now
    return services

def get_countries_for_service(service):
    """Fetch countries with stock for a service."""
    url = f"https://5sim.net/v1/guest/prices?product={service}"
    data = api_request(url, timeout=10)
    if not data:
        return []
    countries_data = data.get(service, {})
    result = []
    for country, operators in countries_data.items():
        if operators:
            min_usd = None
            for op_info in operators.values():
                if op_info.get("count", 0) > 0 and "cost" in op_info:
                    cost = op_info["cost"]
                    if min_usd is None or cost < min_usd:
                        min_usd = cost
            if min_usd is not None:
                result.append({
                    "country": country,
                    "price_usd": min_usd,
                    "price_npr": min_usd * USD_TO_NPR,
                })
    return sorted(result, key=lambda x: x["price_usd"])

def buy_number(country, product):
    """Buy a virtual number from 5sim."""
    url = f"https://5sim.net/v1/user/buy/activation/{country}/any/{product}"
    return api_request(url, timeout=20, retries=1)

def check_order(order_id):
    """Check if SMS arrived for an order."""
    url = f"https://5sim.net/v1/user/check/{order_id}"
    return api_request(url, timeout=10, retries=2)

def finish_order(order_id):
    """Mark order as completed."""
    try:
        requests.get(f"https://5sim.net/v1/user/finish/{order_id}", headers=HEADERS, timeout=10)
    except:
        pass

def cancel_order(order_id):
    """Cancel order (refund if no SMS)."""
    try:
        requests.get(f"https://5sim.net/v1/user/cancel/{order_id}", headers=HEADERS, timeout=10)
    except:
        pass

# ======================= BOT HANDLERS =======================

def get_service_display(service):
    """Get display name for a service."""
    return SERVICE_NAMES.get(service, service.capitalize())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    add_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        "I help you buy virtual numbers for verification.\n\n"
        "📋 *Commands:*\n"
        "/buy - Purchase a virtual number\n"
        "/search <keyword> - Search for a service\n"
        "/balance - Check your balance\n"
        "/topup - Add funds to your account\n"
        "/myorders - View your purchase history\n"
        "/support - Contact support\n"
        "/help - Show this help\n\n"
        "💡 *Quick Start:*\n"
        "1. /topup - Add balance\n"
        "2. /buy - Choose a service and country\n"
        "3. Get your verification code!",
        parse_mode="Markdown",
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "🤖 *How to use this bot*\n\n"
        "1️⃣ /buy – Browse all available services\n"
        "2️⃣ /search <keyword> – Find a specific service\n"
        "3️⃣ Select a service, then a country\n"
        "4️⃣ Get your verification code!\n\n"
        "💰 Need balance? Use /topup\n"
        "📊 Check your balance: /balance\n"
        "📋 View orders: /myorders\n"
        "📞 Need help? /support\n\n"
        "Admin will manually add balance after payment.",
        parse_mode="Markdown",
    )

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command."""
    user_id = update.effective_user.id
    balance = get_user_balance(user_id)
    await update.message.reply_text(
        f"💰 *Your Balance:* NPR {balance:.2f}\n\n"
        f"Need more? Use /topup",
        parse_mode="Markdown",
    )

async def myorders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /myorders command."""
    user_id = update.effective_user.id
    orders = get_user_orders(user_id, limit=15)

    if not orders:
        await update.message.reply_text("📭 You have no past orders.")
        return

    msg = "📋 *Your Recent Orders*\n\n"
    for order in orders:
        _, service, country, phone, price, status, code, created_at = order
        phone_short = phone[-4:] if phone and len(phone) >= 4 else "N/A"
        status_emoji = "✅" if status == "SUCCESS" else "⏳" if status == "WAITING_SMS" else "❌"
        msg += f"{status_emoji} *{get_service_display(service)}* - {country.capitalize()}\n"
        msg += f"   📞 ...{phone_short} | 💸 NPR {price:.2f}\n"
        if code and status == "SUCCESS":
            msg += f"   🔑 Code: `{code}`\n"
        msg += f"   🕒 {created_at[:16]}\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /support command."""
    await update.message.reply_text(
        "📞 *Need Help?*\n\n"
        "Contact our support team:\n"
        "👤 Admin: @VIVEKASDA\n\n"
        "📌 *Before contacting:*\n"
        "• Check your balance with /balance\n"
        "• View your orders with /myorders\n"
        "• Try /help for guidance\n\n"
        "We'll respond within 24 hours!",
        parse_mode="Markdown",
    )

async def topup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /topup command - Show payment QR and instructions."""
    user = update.effective_user
    username = user.username or user.first_name

    qr_path = "payment_qr.jpeg"

    caption = (
        f"💰 *MANUAL TOP-UP INSTRUCTIONS*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*🏦 DO PAYMENT FROM BANK* 💳\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Amount: *Minimum NPR 100*\n"
        f"• *Please write only your name* in the Remarks section. 🙂\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*📌 AFTER PAYMENT:*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"1️⃣ Send your *Transaction ID* or *Payment Screenshot* to:\n"
        f"   👤 Admin: @VIVEKASDA\n\n"
        f"2️⃣ Our admin will verify and add balance to your account.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*⏰ PROCESSING TIME:*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Usually takes *5-10 minutes*\n"
        f"• In some rare cases, it may take *24 hours or more* ⏳\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*📝 IMPORTANT:*\n"
        f"• Write your name exactly as: `{username}`\n"
        f"• This helps us identify your payment quickly ✅\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*Thank you for using our service!* ❤️🔥"
    )

    try:
        with open(qr_path, "rb") as photo:
            await update.message.reply_photo(
                photo=photo, caption=caption, parse_mode="Markdown"
            )
    except FileNotFoundError:
        await update.message.reply_text(
            caption + "\n\n⚠️ *QR Code Image Not Found*\nPlease contact admin for payment details.",
            parse_mode="Markdown",
        )

# ======================= BUY FLOW =======================

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /buy command - Show services."""
    await update.message.reply_text("🔍 Fetching available services from 5sim...")

    services = get_all_services()
    if not services:
        await update.message.reply_text("❌ No services available right now. Try again later.")
        return

    context.user_data["all_services"] = services
    context.user_data["services_page"] = 0
    await send_services_page(update, context, update.effective_chat.id)

async def send_services_page(update, context, chat_id, is_search=False):
    """Send a page of services with navigation."""
    services = context.user_data.get("all_services", [])
    page = context.user_data.get("services_page", 0)
    per_page = 30
    total_pages = (len(services) + per_page - 1) // per_page

    if page >= total_pages:
        page = total_pages - 1
    start = page * per_page
    end = start + per_page
    page_services = services[start:end]

    keyboard = []
    for service in page_services:
        display = get_service_display(service)
        keyboard.append([InlineKeyboardButton(display, callback_data=f"svc_{service}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data="svc_page_prev"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data="svc_page_next"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)
    header = "Search results" if is_search else "Select a service"
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"{header} (page {page+1}/{total_pages}):",
        reply_markup=reply_markup,
    )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command."""
    if not context.args:
        await update.message.reply_text("Usage: /search <keyword>\nExample: /search telegram")
        return

    query = " ".join(context.args).lower()
    all_services = get_all_services()
    filtered = [s for s in all_services if query in s.lower()]

    if not filtered:
        await update.message.reply_text(f"No services found matching '{query}'.")
        return

    context.user_data["all_services"] = filtered
    context.user_data["services_page"] = 0
    await send_services_page(update, context, update.effective_chat.id, is_search=True)

# ======================= CALLBACKS =======================

async def service_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle service page navigation."""
    query = update.callback_query
    await query.answer()

    if query.data == "svc_page_prev":
        context.user_data["services_page"] = max(0, context.user_data.get("services_page", 0) - 1)
    elif query.data == "svc_page_next":
        context.user_data["services_page"] = context.user_data.get("services_page", 0) + 1

    await query.message.delete()
    await send_services_page(update, context, query.message.chat_id)

async def service_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle service selection."""
    query = update.callback_query
    await query.answer()

    service = query.data.replace("svc_", "")
    context.user_data["selected_service"] = service

    await query.edit_message_text(
        f"🔍 Fetching available countries for {get_service_display(service)}..."
    )

    countries = get_countries_for_service(service)
    if not countries:
        await query.edit_message_text(
            f"❌ No countries with stock for {get_service_display(service)} right now."
        )
        return

    context.user_data["service_countries"] = countries
    context.user_data["countries_page"] = 0
    await send_countries_page(update, context, query.message.chat_id)

async def send_countries_page(update, context, chat_id):
    """Send a page of countries with prices."""
    countries = context.user_data.get("service_countries", [])
    page = context.user_data.get("countries_page", 0)
    per_page = 20
    total_pages = (len(countries) + per_page - 1) // per_page

    if page >= total_pages:
        page = total_pages - 1
    start = page * per_page
    end = start + per_page
    page_countries = countries[start:end]

    keyboard = []
    for country in page_countries:
        display = f"{country['country'].capitalize()} – NPR {country['price_npr']:.2f}"
        keyboard.append([InlineKeyboardButton(display, callback_data=f"cntry_{country['country']}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data="cntry_page_prev"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data="cntry_page_next"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 Back to Services", callback_data="back_to_services")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    service = context.user_data.get("selected_service", "")
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Select a country for {get_service_display(service)} (page {page+1}/{total_pages}):",
        reply_markup=reply_markup,
    )

async def country_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle country page navigation."""
    query = update.callback_query
    await query.answer()

    if query.data == "cntry_page_prev":
        context.user_data["countries_page"] = max(0, context.user_data.get("countries_page", 0) - 1)
    elif query.data == "cntry_page_next":
        context.user_data["countries_page"] = context.user_data.get("countries_page", 0) + 1

    await query.message.delete()
    await send_countries_page(update, context, query.message.chat_id)

async def back_to_services_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to services list."""
    query = update.callback_query
    await query.answer()
    await query.message.delete()

    services = context.user_data.get("all_services", get_all_services())
    if not services:
        await query.message.reply_text("❌ No services. Use /buy again.")
        return

    context.user_data["all_services"] = services
    context.user_data["services_page"] = 0
    await send_services_page(update, context, query.message.chat_id)

# ======================= COUNTRY SELECT WITH SMART REFUND =======================

async def country_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle country selection and purchase with smart refund logic."""
    query = update.callback_query
    await query.answer()

    country = query.data.replace("cntry_", "")
    user_id = query.from_user.id
    service = context.user_data.get("selected_service")

    if not service:
        await query.edit_message_text("❌ Session expired. Please start over with /buy.")
        return

    # Get price
    countries = context.user_data.get("service_countries", [])
    price_npr = None
    for c in countries:
        if c["country"] == country:
            price_npr = c["price_npr"]
            break

    if price_npr is None:
        await query.edit_message_text("❌ Price not available. Please start over.")
        return

    # ===== STEP 1: Check user balance =====
    balance = get_user_balance(user_id)
    if balance < price_npr:
        await query.edit_message_text(
            f"❌ Insufficient balance: NPR {balance:.2f}\n"
            f"Need NPR {price_npr:.2f}\n"
            f"Use /topup to add funds."
        )
        return

    # ===== STEP 2: Deduct balance (temporarily) =====
    update_user_balance(user_id, price_npr, "deduct")

    # ===== STEP 3: Check 5sim balance FIRST =====
    fivesim_balance = get_balance_usd()
    if fivesim_balance is None:
        update_user_balance(user_id, price_npr, "add")
        await query.edit_message_text(
            "❌ 5sim API is unreachable. Please try again later.\n"
            "Your balance has been refunded."
        )
        return

    if fivesim_balance < 0.10:
        update_user_balance(user_id, price_npr, "add")
        await query.edit_message_text(
            "⚠️ Service temporarily unavailable. Our system is out of balance.\n"
            "Your balance has been refunded.\n"
            "Please try again in a few minutes."
        )
        await context.bot.send_message(
            ADMIN_ID,
            f"⚠️ LOW 5SIM BALANCE: ${fivesim_balance:.2f}\n"
            f"User {user_id} tried to purchase but was refunded.",
        )
        return

    # ===== STEP 4: Try to buy from 5sim =====
    await query.edit_message_text(
        f"🔄 Purchasing {get_service_display(service)} number from {country.capitalize()}...\n"
        f"⏳ Please wait."
    )

    order = buy_number(country, service)

    # ===== STEP 5: Check purchase result =====
    if not order:
        update_user_balance(user_id, price_npr, "add")
        await query.edit_message_text(
            f"❌ No numbers available for {country} right now.\n"
            f"Please try another country.\n"
            f"Your balance has been refunded."
        )
        return

    # ===== STEP 6: Purchase successful, wait for SMS =====
    phone = order.get("phone")
    order_id_5sim = order.get("id")
    actual_price_usd = order.get("price")

    db_order_id = record_order(
        user_id,
        order_id_5sim,
        phone,
        service,
        country,
        actual_price_usd,
        price_npr,
        "WAITING_SMS",
    )

    await query.edit_message_text(
        f"✅ Number: `{phone}`\n"
        f"💰 Cost: NPR {price_npr:.2f}\n"
        f"⏳ Waiting for SMS from {get_service_display(service)}...\n"
        f"This may take up to 5 minutes.",
        parse_mode="Markdown",
    )

    # ===== STEP 7: Poll for SMS =====
    code = None
    for attempt in range(60):
        await asyncio.sleep(5)

        if attempt % 12 == 0 and attempt > 0:
            try:
                minutes_left = 5 - (attempt // 12)
                await query.edit_message_text(
                    f"⏳ Still waiting for SMS...\n"
                    f"Number: `{phone}`\n"
                    f"⏰ {minutes_left} minutes remaining.",
                    parse_mode="Markdown",
                )
            except:
                pass

        status_data = check_order(order_id_5sim)
        if not status_data:
            continue

        sms_list = status_data.get("sms", [])
        if sms_list:
            for sms in sms_list:
                if sms.get("code"):
                    code = sms["code"]
                    break
                text = sms.get("text", "")
                match = re.search(r"\b(\d{4,7})\b", text)
                if match:
                    code = match.group(1)
                    break
            if code:
                break

    # ===== STEP 8: Final result =====
    if code:
        update_order_status(db_order_id, "SUCCESS", code)
        await query.edit_message_text(
            f"🎉 *Verification Code Received!*\n\n"
            f"Service: {get_service_display(service)}\n"
            f"Number: `{phone}`\n"
            f"Code: `{code}`\n\n"
            f"Use this code to verify your account!",
            parse_mode="Markdown",
        )
        finish_order(order_id_5sim)
        await context.bot.send_message(
            ADMIN_ID, f"✅ User {user_id} got {service} code for {phone} ({country})"
        )
    else:
        update_order_status(db_order_id, "TIMEOUT")
        update_user_balance(user_id, price_npr, "add")
        cancel_order(order_id_5sim)
        await query.edit_message_text(
            f"⏰ Timeout. No SMS received within 5 minutes.\n"
            f"Order cancelled.\n"
            f"Your balance has been refunded.\n\n"
            f"⚠️ Please try another country or service."
        )
        log_failure(user_id, service, country, actual_price_usd)

# ======================= ADMIN COMMANDS =======================

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics (admin only)."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🔒 Unauthorized.")
        return

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT SUM(balance_npr) FROM users")
    total_balance = c.fetchone()[0] or 0

    c.execute("SELECT COUNT(*) FROM orders WHERE status='SUCCESS'")
    total_success = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM orders WHERE status='TIMEOUT'")
    total_timeouts = c.fetchone()[0]

    c.execute("SELECT SUM(price_npr) FROM orders WHERE status='SUCCESS'")
    total_revenue = c.fetchone()[0] or 0

    c.execute("SELECT COUNT(*) FROM orders")
    total_orders = c.fetchone()[0]

    conn.close()

    await update.message.reply_text(
        f"📊 *Bot Statistics*\n\n"
        f"👤 Total Users: {total_users}\n"
        f"💰 User Balance Sum: NPR {total_balance:.2f}\n"
        f"📦 Total Orders: {total_orders}\n"
        f"✅ Successful Orders: {total_success}\n"
        f"⏰ Timeout Orders: {total_timeouts}\n"
        f"💸 Total Revenue: NPR {total_revenue:.2f}",
        parse_mode="Markdown",
    )

async def fivesim_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check 5sim account balance (admin only)."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🔒 Unauthorized.")
        return

    balance = get_balance_usd()
    if balance is None:
        await update.message.reply_text("❌ Could not fetch 5sim balance. API error.")
        return

    await update.message.reply_text(
        f"💰 *5sim Balance:* ${balance:.2f}\n\n"
        f"⚠️ Keep at least $2 for smooth operation.",
        parse_mode="Markdown",
    )

async def add_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add balance to user (admin only)."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🔒 Unauthorized.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /addbalance <user_id> <amount_npr>")
        return

    try:
        user_id = int(args[0])
        amount = float(args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid user_id or amount.")
        return

    update_user_balance(user_id, amount, "add")
    await update.message.reply_text(f"✅ Added NPR {amount} to user {user_id}.")

    try:
        await context.bot.send_message(
            user_id,
            f"✅ Your balance has been increased by NPR {amount}.\n"
            f"Current balance: NPR {get_user_balance(user_id):.2f}",
        )
    except:
        pass

async def refund_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refund balance from user (admin only)."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🔒 Unauthorized.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /refund <user_id> <amount_npr>")
        return

    try:
        user_id = int(args[0])
        amount = float(args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid user_id or amount.")
        return

    update_user_balance(user_id, amount, "deduct")
    await update.message.reply_text(f"✅ Deducted NPR {amount} from user {user_id}.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors and log them."""
    logger = logging.getLogger(__name__)
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Something went wrong. Please try again later."
            )
    except:
        pass

# ======================= MAIN =======================

def main():
    """Start the bot."""
    setup_database()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("myorders", myorders_command))
    app.add_handler(CommandHandler("topup", topup_command))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("support", support_command))

    # Admin commands
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("addbalance", add_balance_command))
    app.add_handler(CommandHandler("refund", refund_command))
    app.add_handler(CommandHandler("5sim", fivesim_balance_command))

    # Callbacks
    app.add_handler(CallbackQueryHandler(service_page_callback, pattern="^svc_page_"))
    app.add_handler(CallbackQueryHandler(service_select_callback, pattern="^svc_"))
    app.add_handler(CallbackQueryHandler(country_page_callback, pattern="^cntry_page_"))
    app.add_handler(CallbackQueryHandler(country_select_callback, pattern="^cntry_"))
    app.add_handler(CallbackQueryHandler(back_to_services_callback, pattern="^back_to_services$"))

    # Error handler
    app.add_error_handler(error_handler)

    logging.basicConfig(level=logging.INFO)
    print("🚀 Bot started with PostgreSQL! Polling for updates...")
    app.run_polling()

if __name__ == "__main__":
    main()