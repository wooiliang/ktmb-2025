import requests
from bs4 import BeautifulSoup
import re
import threading
import time
import asyncio
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Fetch bot token, allowed IDs, and port from environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
ALLOWED_IDS = [int(id.strip()) for id in os.environ.get("ALLOWED_IDS", "123456789").split(",")]
PORT = int(os.environ.get("PORT", 10000))

# Dictionary to store active monitoring tasks
active_tasks = {}

# Minimal HTTP server for Render.com
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.send_header("Content-Length", "2")
        self.end_headers()

def start_http_server():
    """Run a dummy HTTP server in a separate thread."""
    server = HTTPServer(("0.0.0.0", PORT), DummyHandler)
    logger.info(f"Dummy HTTP server running on port {PORT}")
    server.serve_forever()

def get_trip_data(session, search_data, form_validation_code, depart_date):
    """Fetch trip data from the KTMB API."""
    url = 'https://shuttleonline.ktmb.com.my/ShuttleTrip/Trip'
    data = {
        "SearchData": search_data,
        "FormValidationCode": form_validation_code,
        "DepartDate": depart_date,
        "IsReturn": False,
        "BookingTripSequenceNo": 1
    }
    headers = {
        'Content-Type': 'application/json',
        'RequestVerificationToken': 'CfDJ8BLO63HXnMZGiQayUJVcLEojrJUgxtLzf9MQMm_KP7jADJZJV3DZnPba56rCqg9D8SAqtU9z_wn5bsDH8uj6gushfQNqwWTVe1mrFJJAoFVHHxwVwfu3RvEd6zlS8IamMWYq8v-SgaeyPRzlcMISR1M'
    }
    response = session.post(url, json=data, headers=headers)
    return response.json()

def parse_availability(html, departure_time):
    """Parse the HTML to find available seats."""
    soup = BeautifulSoup(html, 'html.parser')
    rows = soup.find_all('tr', class_='text-nowrap')
    
    for row in rows:
        depart_td = row.find('td', class_='text-center f22')
        if depart_td and depart_td.get_text(strip=True) == departure_time:
            for td in row.find_all('td'):
                if td.find('i', class_='fa fa-th-large'):
                    seats_text = td.get_text(strip=True)
                    match = re.search(r'\d+', seats_text)
                    if match:
                        return int(match.group())
            return 0
    return 0

def monitor_tickets(chat_id, date, departure_time, check_interval, stop_event, callback, loop):
    """Monitor ticket availability and notify when tickets are found."""
    session = requests.Session()
    session.cookies.set(
        'X-CSRF-TOKEN-COOKIENAME',
        'CfDJ8BLO63HXnMZGiQayUJVcLEp0JE7-Cb9D2zTM8L-xpg3kjYrYxGNF9c63fB5g5KT1ug74mCn0-hMNsRX_aVXmF2tI0At1d_kLOXsOim25UhN9INHTpAvnkdfKX_9_Y2bX2R_0V-GS5To76BhTtEzEUyQ'
    )
    
    search_data = "tC3dfsxiWMaKt1Nvdm3vWnL/t9iv7tOKqeRjCYtwvTyfaHtg/iHXihQ7SOvTuVPAxxHrDBv6RsMbV4cae87VZASB5ITVUG2scB44wxTMDbOyPfZvLZSTcGLsAJKuBGdbTPq5vFDsv16M1qHvkxTc7pDrVndjI2W0B+fSpqHuHsFg+D4R7hk+c7JJPhp48O0vV1XbIALH2VKyscdhOM4tF4SHcANHTn7HNtmO2bxmDGsBH5GojaLeirgvig06SVCId2oLeypjxYm5YcBcFS5MbmSdjke716Eghk3yUdBOmEE3gn5JfLuEq6UFJ/7f0LwptmfO2AmK7egjih78zpizbjL8YoTL0MJcw8VbPX227mw9HtH6v6Z9S87b1bdip8RLQAGRIMZcoDCA3Nxm/L1yrxmUQL0Wi9+hi0N/VQ4dAIhA5KBgyeKDsKeRegRTuKY3MsC8VHLE3AameYI8hxYsDBrn0Y/PnE2FDVnLNKt3GhaIQ5VEjO8ch/kERbG+13aDbPbbdnHNa/wBK+mz708k5Q=="
    form_validation_code = "I9GTDWsCQsYe9QreH7nJRmaJuylznM1L+nRGoOyGhVv6UXRKLmEpMbP+HyWhoNHZnP7tRWyEBB7xOsDHIHpCi1nJF7O0FV5YbGt+t8qIg7GHP6JmMCVorIYXnD3p2YwRgpsDt31+gNVyCjWllfBRbQ=="
    
    logger.info(f"Starting ticket monitoring for {departure_time} on {date} for chat {chat_id}")
    
    while not stop_event.is_set():
        try:
            trip_data = get_trip_data(session, search_data, form_validation_code, date)
            
            if trip_data.get('status', False):
                html = trip_data['data']
                available_seats = parse_availability(html, departure_time)
                
                if available_seats > 0:
                    message = f"There are {available_seats} seats available for the train from WOODLANDS CIQ to JB SENTRAL at {departure_time} on {date}."
                    asyncio.run_coroutine_threadsafe(callback(chat_id, message, stop_event), loop)
                    logger.info(f"Tickets found: {available_seats} seats for {departure_time} on {date}. Stopping thread for chat {chat_id}")
                    break
                else:
                    logger.info(f"No tickets available for {departure_time} on {date}")
            else:
                logger.warning(f"Failed to retrieve trip data for chat {chat_id}")
            
            stop_event.wait(check_interval)
            
        except Exception as e:
            logger.error(f"Error in monitoring thread for chat {chat_id}: {str(e)}. Retrying in {check_interval} seconds")
            stop_event.wait(check_interval)

# Callback function to send messages and clean up
async def send_telegram_message(chat_id, text, stop_event=None):
    await application.bot.send_message(chat_id=chat_id, text=text)
    if stop_event and chat_id in active_tasks:
        task = active_tasks[chat_id]
        task["stop_event"].set()
        task["thread"].join()
        del active_tasks[chat_id]
        logger.info(f"Cleaned up monitoring thread for chat {chat_id} after tickets found")
    logger.debug("Bot remains operational, ready to accept new commands")

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    logger.info(f"User ID {user_id} (@{username}) attempted to use /start")
    
    if user_id not in ALLOWED_IDS:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return
    
    chat_id = update.message.chat_id
    args = context.args
    
    if len(args) < 2 or len(args) > 3:
        await update.message.reply_text("Usage: /start <date> <time> [interval]\nExample: /start 2025-03-12 21:15 600")
        return
    
    date, departure_time = args[0], args[1]
    check_interval = int(args[2]) if len(args) == 3 else 300
    
    if not re.match(r'\d{4}-\d{2}-\d{2}', date) or not re.match(r'\d{2}:\d{2}', departure_time):
        await update.message.reply_text("Invalid date (YYYY-MM-DD) or time (HH:MM) format.")
        return
    
    if chat_id in active_tasks:
        await update.message.reply_text("You already have an active monitoring task. Use /stop to terminate it first.")
        return
    
    stop_event = threading.Event()
    loop = asyncio.get_running_loop()
    thread = threading.Thread(
        target=monitor_tickets,
        args=(chat_id, date, departure_time, check_interval, stop_event, send_telegram_message, loop)
    )
    active_tasks[chat_id] = {"thread": thread, "stop_event": stop_event, "date": date, "time": departure_time}
    thread.start()
    
    await update.message.reply_text(f"Started monitoring tickets for {departure_time} on {date}. Checking every {check_interval} seconds.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    logger.info(f"User ID {user_id} (@{username}) attempted to use /stop")
    
    if user_id not in ALLOWED_IDS:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return
    
    chat_id = update.message.chat_id
    
    if chat_id not in active_tasks:
        await update.message.reply_text("No active monitoring task to stop.")
        return
    
    task = active_tasks[chat_id]
    task["stop_event"].set()
    task["thread"].join()
    del active_tasks[chat_id]
    
    await update.message.reply_text("Monitoring stopped.")
    logger.debug("Bot remains operational after stopping thread")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    logger.info(f"User ID {user_id} (@{username}) attempted to use /status")
    
    if user_id not in ALLOWED_IDS:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return
    
    chat_id = update.message.chat_id
    
    if chat_id in active_tasks:
        task = active_tasks[chat_id]
        await update.message.reply_text(f"Monitoring active for {task['time']} on {task['date']}.")
    else:
        await update.message.reply_text("No active monitoring task.")

# Set up the bot application
application = Application.builder().token(BOT_TOKEN).build()

# Add command handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("stop", stop))
application.add_handler(CommandHandler("status", status))

# Start the bot and HTTP server
if __name__ == "__main__":
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    logger.info("Bot is running")
    application.run_polling(allowed_updates=Update.ALL_TYPES)