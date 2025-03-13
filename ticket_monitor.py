import requests
from bs4 import BeautifulSoup
import re
import threading
import time
import asyncio
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, ContextTypes
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

# Constants
CHECK_INTERVAL = 60  # Fixed monitoring interval in seconds

# Search data for each direction
SEARCH_DATA_WOODLANDS_TO_JB = "tC3dfsxiWMaKt1Nvdm3vWnL/t9iv7tOKqeRjCYtwvTyfaHtg/iHXihQ7SOvTuVPAxxHrDBv6RsMbV4cae87VZASB5ITVUG2scB44wxTMDbOyPfZvLZSTcGLsAJKuBGdbTPq5vFDsv16M1qHvkxTc7pDrVndjI2W0B+fSpqHuHsFg+D4R7hk+c7JJPhp48O0vV1XbIALH2VKyscdhOM4tF4SHcANHTn7HNtmO2bxmDGsBH5GojaLeirgvig06SVCId2oLeypjxYm5YcBcFS5MbmSdjke716Eghk3yUdBOmEE3gn5JfLuEq6UFJ/7f0LwptmfO2AmK7egjih78zpizbjL8YoTL0MJcw8VbPX227mw9HtH6v6Z9S87b1bdip8RLQAGRIMZcoDCA3Nxm/L1yrxmUQL0Wi9+hi0N/VQ4dAIhA5KBgyeKDsKeRegRTuKY3MsC8VHLE3AameYI8hxYsDBrn0Y/PnE2FDVnLNKt3GhaIQ5VEjO8ch/kERbG+13aDbPbbdnHNa/wBK+mz708k5Q=="
SEARCH_DATA_JB_TO_WOODLANDS = "Gr84iXeicKg7w1+ddyMkediAbSqqrjZJXNKWvNhKLVpXgnDDhDhsHV7/Amne7duOsC0Y6thSS/AuUIgfeVXK3Rf6k4EXIL7MyWN0D7ySgJEKmLaFhLalt5CfqSTUV3X8+05Nnow+7+Ewiqu2etuWjRRi4+EloDza6GjL81D3BedYoiNp81cqDVQzQ5DHO2fudxQTur0S1hqGSbtF3QE4fTcNIUcrFNBYfdLFOjt3CHvHTWvxja16ytk59z0B90Snmc1kGNDSYxKpgbw4neHxVGN2dF1WLwUEEaMvbbguw63W3VTkqEsDvhp47x7We6boIL57X8iq4vmCk23mdd9Q9JwWAj/EOLMMVcSbVKUaWdvYzpsO3UjeqvKWgkEWO90m1lPfpFS3Hd/HJPVIzEzrwP9nPzdzypUrU7h62b4kWDbXAuXZ19/nvZAjKrqZOXrwsCjHbBzYyIi+BYUdwnDKlvgTR5pkDQXK5S2OqF8JTsQRTjR+6nPYbw7/Tu7VePaquUEm6vsw7QtWMQwHVHyyuQ=="

# Dictionary to store active monitoring tasks
active_tasks = {}

# Cached departure times (updated daily or on demand)
DEPARTURE_TIMES = {"WOODLANDS_TO_JB": [], "JB_TO_WOODLANDS": []}

# Minimal HTTP server for Render.com
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.send_header("Content-Length", "2")
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

def fetch_departure_times(date):
    """Fetch dynamic departure times from KTMB for both directions."""
    session = requests.Session()
    session.cookies.set(
        'X-CSRF-TOKEN-COOKIENAME',
        'CfDJ8BLO63HXnMZGiQayUJVcLEp0JE7-Cb9D2zTM8L-xpg3kjYrYxGNF9c63fB5g5KT1ug74mCn0-hMNsRX_aVXmF2tI0At1d_kLOXsOim25UhN9INHTpAvnkdfKX_9_Y2bX2R_0V-GS5To76BhTtEzEUyQ'
    )
    form_validation_code = "I9GTDWsCQsYe9QreH7nJRmaJuylznM1L+nRGoOyGhVv6UXRKLmEpMbP+HyWhoNHZnP7tRWyEBB7xOsDHIHpCi1nJF7O0FV5YbGt+t8qIg7GHP6JmMCVorIYXnD3p2YwRgpsDt31+gNVyCjWllfBRbQ=="

    directions = {
        "WOODLANDS_TO_JB": SEARCH_DATA_WOODLANDS_TO_JB,
        "JB_TO_WOODLANDS": SEARCH_DATA_JB_TO_WOODLANDS
    }
    times = {"WOODLANDS_TO_JB": [], "JB_TO_WOODLANDS": []}

    for direction, search_data in directions.items():
        try:
            trip_data = get_trip_data(session, search_data, form_validation_code, date)
            if trip_data.get('status', False):
                html = trip_data['data']
                soup = BeautifulSoup(html, 'html.parser')
                rows = soup.find_all('tr', class_='text-nowrap')
                for row in rows:
                    depart_td = row.find('td', class_='text-center f22')
                    if depart_td:
                        time = depart_td.get_text(strip=True)
                        times[direction].append(time)
                times[direction].sort()  # Sort times for consistency
                logger.info(f"Fetched {len(times[direction])} departure times for {direction}")
            else:
                logger.warning(f"Failed to fetch trip data for {direction}")
        except Exception as e:
            logger.error(f"Error fetching times for {direction}: {str(e)}")
            times[direction] = TIMES.get(direction, [])  # Fallback to static times

    return times

def monitor_tickets(chat_id, date, departure_time, check_interval, stop_event, callback, loop, search_data):
    """Monitor ticket availability and notify when tickets are found."""
    session = requests.Session()
    session.cookies.set(
        'X-CSRF-TOKEN-COOKIENAME',
        'CfDJ8BLO63HXnMZGiQayUJVcLEp0JE7-Cb9D2zTM8L-xpg3kjYrYxGNF9c63fB5g5KT1ug74mCn0-hMNsRX_aVXmF2tI0At1d_kLOXsOim25UhN9INHTpAvnkdfKX_9_Y2bX2R_0V-GS5To76BhTtEzEUyQ'
    )
    form_validation_code = "I9GTDWsCQsYe9QreH7nJRmaJuylznM1L+nRGoOyGhVv6UXRKLmEpMbP+HyWhoNHZnP7tRWyEBB7xOsDHIHpCi1nJF7O0FV5YbGt+t8qIg7GHP6JmMCVorIYXnD3p2YwRgpsDt31+gNVyCjWllfBRbQ=="
    
    logger.info(f"Starting ticket monitoring for {departure_time} on {date} for chat {chat_id}")
    
    while not stop_event.is_set():
        try:
            trip_data = get_trip_data(session, search_data, form_validation_code, date)
            if trip_data.get('status', False):
                html = trip_data['data']
                available_seats = parse_availability(html, departure_time)
                if available_seats > 0:
                    message = f"There are {available_seats} seats available for the train at {departure_time} on {date}."
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

async def send_telegram_message(chat_id, text, stop_event=None):
    """Send a Telegram message and clean up if tickets are found."""
    await application.bot.send_message(chat_id=chat_id, text=text)
    if stop_event and chat_id in active_tasks:
        task = active_tasks[chat_id]
        task["stop_event"].set()
        task["thread"].join()
        del active_tasks[chat_id]
        logger.info(f"Cleaned up monitoring thread for chat {chat_id} after tickets found")
    logger.debug("Bot remains operational, ready to accept new commands")

# Conversation States
DIRECTION, DATE, TIME = range(3)

# Static fallback times in case fetching fails
TIMES = {
    "WOODLANDS_TO_JB": ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"],
    "JB_TO_WOODLANDS": ["07:00", "09:00", "11:00", "13:00", "15:00", "17:00", "19:00", "21:00"]
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask for the direction."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    logger.info(f"User ID {user_id} (@{username}) started the conversation")
    
    if user_id not in ALLOWED_IDS:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "Please choose the direction by replying with the number:\n"
        "1. WOODLANDS CIQ to JB SENTRAL\n"
        "2. JB SENTRAL to WOODLANDS CIQ"
    )
    return DIRECTION

async def choose_direction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the direction choice and ask for the date."""
    text = update.message.text
    if text == "1":
        context.user_data['direction'] = 'WOODLANDS_TO_JB'
    elif text == "2":
        context.user_data['direction'] = 'JB_TO_WOODLANDS'
    else:
        await update.message.reply_text("Invalid choice. Please reply with 1 or 2.")
        return DIRECTION
    
    await update.message.reply_text("Please enter the departure date in YYYY-MM-DD format (e.g., 2025-03-13).")
    return DATE

async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the date input and fetch times dynamically."""
    text = update.message.text
    if re.match(r'\d{4}-\d{2}-\d{2}', text):
        context.user_data['date'] = text
        # Fetch departure times dynamically for the selected date
        global DEPARTURE_TIMES
        if not DEPARTURE_TIMES["WOODLANDS_TO_JB"] or not DEPARTURE_TIMES["JB_TO_WOODLANDS"]:
            DEPARTURE_TIMES = fetch_departure_times(text)
        
        direction = context.user_data['direction']
        times = DEPARTURE_TIMES.get(direction, TIMES[direction])  # Fallback to static if fetch fails
        if not times:
            await update.message.reply_text("Unable to fetch departure times. Please try again later.")
            return ConversationHandler.END
        
        time_options = "\n".join([f"{i+1}. {t}" for i, t in enumerate(times)])
        await update.message.reply_text(
            f"Please choose the departure time by replying with the number:\n{time_options}"
        )
        return TIME
    else:
        await update.message.reply_text("Invalid date format. Please enter the date in YYYY-MM-DD format (e.g., 2025-03-13).")
        return DATE

async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the time choice and start monitoring."""
    text = update.message.text
    direction = context.user_data['direction']
    times = DEPARTURE_TIMES.get(direction, TIMES[direction])
    
    try:
        choice = int(text) - 1
        if 0 <= choice < len(times):
            context.user_data['time'] = times[choice]
        else:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Invalid choice. Please reply with a number from the list.")
        return TIME
    
    chat_id = update.message.chat_id
    date = context.user_data['date']
    departure_time = context.user_data['time']
    search_data = SEARCH_DATA_WOODLANDS_TO_JB if direction == 'WOODLANDS_TO_JB' else SEARCH_DATA_JB_TO_WOODLANDS
    
    if chat_id in active_tasks:
        await update.message.reply_text("You already have an active monitoring task. Use /stop to terminate it first.")
        return ConversationHandler.END
    
    stop_event = threading.Event()
    loop = asyncio.get_running_loop()
    thread = threading.Thread(
        target=monitor_tickets,
        args=(chat_id, date, departure_time, CHECK_INTERVAL, stop_event, send_telegram_message, loop, search_data)
    )
    active_tasks[chat_id] = {"thread": thread, "stop_event": stop_event, "date": date, "time": departure_time}
    thread.start()
    
    direction_text = "WOODLANDS CIQ to JB SENTRAL" if direction == 'WOODLANDS_TO_JB' else "JB SENTRAL to WOODLANDS CIQ"
    await update.message.reply_text(
        f"Started monitoring tickets for {departure_time} on {date} from {direction_text}."
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop the active monitoring task."""
    user_id = update.effective_user.id
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
    """Check the status of the monitoring task."""
    user_id = update.effective_user.id
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

# Define the conversation handler
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        DIRECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_direction)],
        DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_date)],
        TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_time)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

# Add handlers to the application
application.add_handler(conv_handler)
application.add_handler(CommandHandler("stop", stop))
application.add_handler(CommandHandler("status", status))

# Start the bot and HTTP server
if __name__ == "__main__":
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # Optionally fetch times at startup (e.g., for tomorrow's date)
    from datetime import datetime, timedelta
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    DEPARTURE_TIMES = fetch_departure_times(tomorrow)
    
    logger.info("Bot is running")
    application.run_polling(allowed_updates=Update.ALL_TYPES)