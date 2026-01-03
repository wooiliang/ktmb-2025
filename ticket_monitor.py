from datetime import datetime
import json
import os
import requests
from bs4 import BeautifulSoup
import re
import threading
import time
import asyncio
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
ALLOWED_IDS = [int(id.strip().strip('"').strip("'")) for id in os.environ.get("ALLOWED_IDS", "123456789").split(",")]
PORT = int(os.environ.get("PORT", 10000))
ACTIVE_FILE = 'active_monitors.json'

# Constants
CHECK_INTERVAL = 60  # Fixed monitoring interval in seconds
SAVE_INTERVAL = 60  # Save active monitors every 60 seconds

# Search data for each direction
SEARCH_DATA_WOODLANDS_TO_JB = "tC3dfsxiWMaKt1Nvdm3vWnL/t9iv7tOKqeRjCYtwvTyfaHtg/iHXihQ7SOvTuVPAxxHrDBv6RsMbV4cae87VZASB5ITVUG2scB44wxTMDbOyPfZvLZSTcGLsAJKuBGdbTPq5vFDsv16M1qHvkxTc7pDrVndjI2W0B+fSpqHuHsFg+D4R7hk+c7JJPhp48O0vV1XbIALH2VKyscdhOM4tF4SHcANHTn7HNtmO2bxmDGsBH5GojaLeirgvig06SVCId2oLeypjxYm5YcBcFS5MbmSdjke716Eghk3yUdBOmEE3gn5JfLuEq6UFJ/7f0LwptmfO2AmK7egjih78zpizbjL8YoTL0MJcw8VbPX227mw9HtH6v6Z9S87b1bdip8RLQAGRIMZcoDCA3Nxm/L1yrxmUQL0Wi9+hi0N/VQ4dAIhA5KBgyeKDsKeRegRTuKY3MsC8VHLE3AameYI8hxYsDBrn0Y/PnE2FDVnLNKt3GhaIQ5VEjO8ch/kERbG+13aDbPbbdnHNa/wBK+mz708k5Q=="
SEARCH_DATA_JB_TO_WOODLANDS = "Gr84iXeicKg7w1+ddyMkediAbSqqrjZJXNKWvNhKLVpXgnDDhDhsHV7/Amne7duOsC0Y6thSS/AuUIgfeVXK3Rf6k4EXIL7MyWN0D7ySgJEKmLaFhLalt5CfqSTUV3X8+05Nnow+7+Ewiqu2etuWjRRi4+EloDza6GjL81D3BedYoiNp81cqDVQzQ5DHO2fudxQTur0S1hqGSbtF3QE4fTcNIUcrFNBYfdLFOjt3CHvHTWvxja16ytk59z0B90Snmc1kGNDSYxKpgbw4neHxVGN2dF1WLwUEEaMvbbguw63W3VTkqEsDvhp47x7We6boIL57X8iq4vmCk23mdd9Q9JwWAj/EOLMMVcSbVKUaWdvYzpsO3UjeqvKWgkEWO90m1lPfpFS3Hd/HJPVIzEzrwP9nPzdzypUrU7h62b4kWDbXAuXZ19/nvZAjKrqZOXrwsCjHbBzYyIi+BYUdwnDKlvgTR5pkDQXK5S2OqF8JTsQRTjR+6nPYbw7/Tu7VePaquUEm6vsw7QtWMQwHVHyyuQ=="
SEARCH_DATA_JB_TO_SEGAMAT = "G/OmNcwIfV7u9PfAQfdCKhpjRwCvFy+8b6uELbC/ThIxCk/8j9b/RjtsdxyLikvyG514rNG7NbXqr0qldzs6phgE3eABqD5ZII/kR2nXh2LdOaHu5EwC8AGFcihSiEoDsPGQjOzlwRiydkBegBAQPbvXubNkRqVNBZA/atBRlW8GS7SckaoiwTjBV3Y3tifHsQzIwM3UAEut/K/RRRyZWCEogdw1/R2P4a2Rok0i7pfrQh7MIc1qks04jdHC3Roqyiv/GnN9K7DV5ZjUJtCmyMwOQvgdDcgRYaLF2NOdgC4BrBkrnS+vNNe8KCkkqW2NK4J/PVIVCTN+ZAc/T9I1mlWBFOYKJr3E09NJhp9Jqc/SPTukc++snloNWsLAK0S5"
SEARCH_DATA_SEGAMAT_TO_JB = "MeothUPXeel1i2G90Ka/s4yb14vORIomZlBdLWzSvT/jZEcBADn/TBVbYAWj/ls0nOgyiaLt2p2f8BrYBmo6uWlNfDKoKk/IdAWoc9aKnGNwSYfzaBuO/PveRM6xVxwP1WbF2Ys7XvdZ/1HibE+hQl6t+ZZ1A4CTwRkSXzkvq+iG91/vmGvyinfqe5lUmgltN0EWIFhEVI1lRHkOytcrswt16fjbPJe7u1Z+QZta6poZ+0slj5qaTYjxlZQoAZYlOim7kNb1iwBdBYab6EmggRCjtj+oilIV6XFwhxfVBUbeEcd1vqj1jRdQi/vQJxPScHdopnbwLwZAD9e2ert/iv7oO6GJIiJ2uXsa0ZM+3OhsogDiiL8B3CK97oUiqkTX"

# Direction configurations
DIRECTION_CONFIG = {
    "WOODLANDS_TO_JB": {
        "url": "https://shuttleonline.ktmb.com.my/ShuttleTrip/Trip",
        "search_data": SEARCH_DATA_WOODLANDS_TO_JB,
        "form_validation_code": "I9GTDWsCQsYe9QreH7nJRmaJuylznM1L+nRGoOyGhVv6UXRKLmEpMbP+HyWhoNHZnP7tRWyEBB7xOsDHIHpCi1nJF7O0FV5YbGt+t8qIg7GHP6JmMCVorIYXnD3p2YwRgpsDt31+gNVyCjWllfBRbQ==",
        "request_verification_token": "CfDJ8BLO63HXnMZGiQayUJVcLEojrJUgxtLzf9MQMm_KP7jADJZJV3DZnPba56rCqg9D8SAqtU9z_wn5bsDH8uj6gushfQNqwWTVe1mrFJJAoFVHHxwVwfu3RvEd6zlS8IamMWYq8v-SgaeyPRzlcMISR1M",
        "csrf_cookie_value": "CfDJ8BLO63HXnMZGiQayUJVcLEp0JE7-Cb9D2zTM8L-xpg3kjYrYxGNF9c63fB5g5KT1ug74mCn0-hMNsRX_aVXmF2tI0At1d_kLOXsOim25UhN9INHTpAvnkdfKX_9_Y2bX2R_0V-GS5To76BhTtEzEUyQ"
    },
    "JB_TO_WOODLANDS": {
        "url": "https://shuttleonline.ktmb.com.my/ShuttleTrip/Trip",
        "search_data": SEARCH_DATA_JB_TO_WOODLANDS,
        "form_validation_code": "I9GTDWsCQsYe9QreH7nJRmaJuylznM1L+nRGoOyGhVv6UXRKLmEpMbP+HyWhoNHZnP7tRWyEBB7xOsDHIHpCi1nJF7O0FV5YbGt+t8qIg7GHP6JmMCVorIYXnD3p2YwRgpsDt31+gNVyCjWllfBRbQ==",
        "request_verification_token": "CfDJ8BLO63HXnMZGiQayUJVcLEojrJUgxtLzf9MQMm_KP7jADJZJV3DZnPba56rCqg9D8SAqtU9z_wn5bsDH8uj6gushfQNqwWTVe1mrFJJAoFVHHxwVwfu3RvEd6zlS8IamMWYq8v-SgaeyPRzlcMISR1M",
        "csrf_cookie_value": "CfDJ8BLO63HXnMZGiQayUJVcLEp0JE7-Cb9D2zTM8L-xpg3kjYrYxGNF9c63fB5g5KT1ug74mCn0-hMNsRX_aVXmF2tI0At1d_kLOXsOim25UhN9INHTpAvnkdfKX_9_Y2bX2R_0V-GS5To76BhTtEzEUyQ"
    },
    "JB_TO_SEGAMAT": {
        "url": "https://online.ktmb.com.my/Trip/Trip",
        "search_data": SEARCH_DATA_JB_TO_SEGAMAT,
        "form_validation_code": "S/1yIg8E9BrZNSm1iUJqzv3JPnP2yHJAkqV1La/Fv0uXLsh9fj+jRGXqdxJEWaRtI7st7oBtwv1AlEHozgpYNKGrXKPU1S++zSgISOZxF+MY0kT1B1hk3RTuxbg6wAgi0oKV6d0D4k3QdxzvhpyQ7Q==",
        "request_verification_token": "CfDJ8CrScsSjTqxItTmqqK9Q1wv7Y-s_ycn37HjtYUmyzoUI-PQXuVmfU5B4AEuTKZxQdoXxC9kGWjjMzPWjQIxK4G_xgAQ09SbA12LH-RE8NwLnAnZsswatMRly_B2X73M3ZvHZJl-JL3DFL0ehzzVtkvI",
        "csrf_cookie_value": "CfDJ8CrScsSjTqxItTmqqK9Q1wsXyYWxQRqe59gs0O43YUmeF1BG-tTMxygx10Q_bOkdmuYGerki2KAXDK_nhokfOiIGWld0zKwWJbllXTU2HIGF3fABNxGqNCFujhqH7sMvHvChlSc0vSyQ-GVFOwnjULY"
    },
    "SEGAMAT_TO_JB": {
        "url": "https://online.ktmb.com.my/Trip/Trip",
        "search_data": SEARCH_DATA_SEGAMAT_TO_JB,
        "form_validation_code": "S/1yIg8E9BrZNSm1iUJqzv3JPnP2yHJAkqV1La/Fv0uXLsh9fj+jRGXqdxJEWaRtI7st7oBtwv1AlEHozgpYNKGrXKPU1S++zSgISOZxF+MY0kT1B1hk3RTuxbg6wAgi0oKV6d0D4k3QdxzvhpyQ7Q==",
        "request_verification_token": "CfDJ8CrScsSjTqxItTmqqK9Q1wv7Y-s_ycn37HjtYUmyzoUI-PQXuVmfU5B4AEuTKZxQdoXxC9kGWjjMzPWjQIxK4G_xgAQ09SbA12LH-RE8NwLnAnZsswatMRly_B2X73M3ZvHZJl-JL3DFL0ehzzVtkvI",
        "csrf_cookie_value": "CfDJ8CrScsSjTqxItTmqqK9Q1wsXyYWxQRqe59gs0O43YUmeF1BG-tTMxygx10Q_bOkdmuYGerki2KAXDK_nhokfOiIGWld0zKwWJbllXTU2HIGF3fABNxGqNCFujhqH7sMvHvChlSc0vSyQ-GVFOwnjULY"
    }
}

DIRECTION_TEXT = {
    "WOODLANDS_TO_JB": "WOODLANDS CIQ to JB SENTRAL",
    "JB_TO_WOODLANDS": "JB SENTRAL to WOODLANDS CIQ",
    "JB_TO_SEGAMAT": "JB SENTRAL to SEGAMAT",
    "SEGAMAT_TO_JB": "SEGAMAT to JB SENTRAL"
}

# Dictionary to store active monitoring tasks
active_tasks = {}
tasks_lock = threading.Lock()

def is_expired(date, departure_time):
    try:
        dt = datetime.strptime(f"{date} {departure_time}", "%Y-%m-%d %H:%M")
        return dt < datetime.now()
    except ValueError:
        return False

def is_past_date(date):
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        return dt.date() < datetime.now().date()
    except ValueError:
        return False

def save_active_monitors():
    with tasks_lock:
        data = {}
        for chat_id, tasks in active_tasks.items():
            data[str(chat_id)] = {}
            for key, info in tasks.items():
                data[str(chat_id)][key] = {
                    'date': info['date'],
                    'time': info['time'],
                    'direction': info['direction'],
                    'current_seats': info.get('current_seats')
                }
        with open(ACTIVE_FILE, 'w') as f:
            json.dump(data, f)
    logger.info("Saved active monitors")

def load_active_monitors(loop):
    if not os.path.exists(ACTIVE_FILE):
        return
    with open(ACTIVE_FILE, 'r') as f:
        data = json.load(f)
    with tasks_lock:
        for chat_id_str, tasks_data in data.items():
            chat_id = int(chat_id_str)
            active_tasks[chat_id] = {}
            for key, info in tasks_data.items():
                date = info['date']
                time_ = info['time']
                if is_expired(date, time_):
                    continue
                direction = info['direction']
                current_seats = info.get('current_seats')
                stop_event = threading.Event()
                thread = threading.Thread(
                    target=monitor_tickets,
                    args=(chat_id, date, time_, CHECK_INTERVAL, stop_event, send_telegram_message, loop, direction, current_seats, key)
                )
                active_tasks[chat_id][key] = {
                    "thread": thread,
                    "stop_event": stop_event,
                    "date": date,
                    "time": time_,
                    "direction": direction,
                    "current_seats": current_seats
                }
                thread.start()
    logger.info("Loaded active monitors")

def periodic_save(stop_event):
    while not stop_event.is_set():
        time.sleep(SAVE_INTERVAL)
        save_active_monitors()

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

def get_trip_data(session, url, search_data, form_validation_code, depart_date, request_verification_token):
    """Fetch trip data from the KTMB API."""
    data = {
        "SearchData": search_data,
        "FormValidationCode": form_validation_code,
        "DepartDate": depart_date,
        "IsReturn": False,
        "BookingTripSequenceNo": 1
    }
    headers = {
        'Content-Type': 'application/json',
        'RequestVerificationToken': request_verification_token
    }
    response = session.post(url, json=data, headers=headers)
    return response.json()

def fetch_trip_info(date, direction):
    """Fetch dynamic trip information from KTMB for a specific direction."""
    trips = []
    config = DIRECTION_CONFIG[direction]
    session = requests.Session()
    session.cookies.set('X-CSRF-TOKEN-COOKIENAME', config["csrf_cookie_value"])
    try:
        trip_data = get_trip_data(session, config["url"], config["search_data"], config["form_validation_code"], date, config["request_verification_token"])
        if trip_data.get('status', False):
            html = trip_data['data']
            soup = BeautifulSoup(html, 'html.parser')
            rows = soup.find_all('tr', class_='text-nowrap')
            for row in rows:
                tds = row.find_all('td')
                if len(tds) >= 6:
                    train = tds[0].get_text(strip=True)
                    departure = tds[1].get_text(strip=True)
                    arrival = tds[2].get_text(strip=True)
                    duration = tds[3].get_text(strip=True)
                    seats_text = tds[4].get_text(strip=True)
                    fare = tds[5].get_text(strip=True)
                    
                    match = re.search(r'\d+', seats_text)
                    seats = int(match.group()) if match else 0
                    
                    trips.append({
                        'train': train,
                        'departure': departure,
                        'arrival': arrival,
                        'duration': duration,
                        'seats': seats,
                        'fare': fare
                    })
            trips.sort(key=lambda x: x['departure'])
            logger.info(f"Fetched {len(trips)} trips for {direction} on {date}")
        else:
            logger.warning(f"Failed to fetch trip data for {direction} on {date}")
    except Exception as e:
        logger.error(f"Error fetching trip info for {direction} on {date}: {str(e)}")
    return trips

def monitor_tickets(chat_id, date, departure_time, check_interval, stop_event, callback, loop, direction, current_seats, key):
    """Monitor ticket availability and notify when tickets are found or changed."""
    if is_expired(date, departure_time):
        logger.info(f"Monitor expired for {departure_time} on {date} for {key}")
        with tasks_lock:
            if chat_id in active_tasks and key in active_tasks[chat_id]:
                del active_tasks[chat_id][key]
                if not active_tasks[chat_id]:
                    del active_tasks[chat_id]
        save_active_monitors()
        return

    config = DIRECTION_CONFIG[direction]
    session = requests.Session()
    session.cookies.set('X-CSRF-TOKEN-COOKIENAME', config["csrf_cookie_value"])
    
    logger.info(f"Starting ticket monitoring for {departure_time} on {date} for chat {chat_id}")
    
    # Initial fetch to set current_seats if None
    if current_seats is None:
        try:
            trip_data = get_trip_data(session, config["url"], config["search_data"], config["form_validation_code"], date, config["request_verification_token"])
            if trip_data.get('status', False):
                html = trip_data['data']
                available_seats = parse_availability(html, departure_time)
                current_seats = available_seats
                with tasks_lock:
                    if chat_id in active_tasks and key in active_tasks[chat_id]:
                        active_tasks[chat_id][key]['current_seats'] = current_seats
                logger.info(f"Initial seats set to {current_seats} for {departure_time} on {date}")
            else:
                logger.warning(f"Failed to retrieve initial trip data for chat {chat_id}")
        except Exception as e:
            logger.error(f"Error fetching initial seats for chat {chat_id}: {str(e)}")
    
    while not stop_event.is_set():
        if is_expired(date, departure_time):
            logger.info(f"Monitor expired for {departure_time} on {date} for {key}")
            break
        try:
            trip_data = get_trip_data(session, config["url"], config["search_data"], config["form_validation_code"], date, config["request_verification_token"])
            if trip_data.get('status', False):
                html = trip_data['data']
                available_seats = parse_availability(html, departure_time)
                if current_seats is not None and available_seats > current_seats:
                    message = f"The number of available seats has increased to {available_seats} for the train at {departure_time} on {date}."
                    asyncio.run_coroutine_threadsafe(callback(chat_id, message), loop)
                    logger.info(f"Seat increase detected: {available_seats} seats for {departure_time} on {date} for {key}")
                current_seats = available_seats
                with tasks_lock:
                    if chat_id in active_tasks and key in active_tasks[chat_id]:
                        active_tasks[chat_id][key]['current_seats'] = current_seats
                logger.info(f"Current tickets: {available_seats} for {departure_time} on {date}")
            else:
                logger.warning(f"Failed to retrieve trip data for chat {chat_id}")
            stop_event.wait(check_interval)
        except Exception as e:
            logger.error(f"Error in monitoring thread for chat {chat_id}: {str(e)}. Retrying in {check_interval} seconds")
            stop_event.wait(check_interval)
    
    with tasks_lock:
        if chat_id in active_tasks and key in active_tasks[chat_id]:
            del active_tasks[chat_id][key]
            if not active_tasks[chat_id]:
                del active_tasks[chat_id]
    save_active_monitors()
    logger.info(f"Thread ended and cleaned up for {key} chat {chat_id}")

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

async def send_telegram_message(chat_id, text):
    """Send a Telegram message."""
    await application.bot.send_message(chat_id=chat_id, text=text)
    logger.debug("Bot remains operational, ready to accept new commands")

# Conversation States
DIRECTION, DATE, TIME = range(3)
STOP = 3

# Static fallback times in case fetching fails
TIMES = {
    "WOODLANDS_TO_JB": ["08:30", "09:45", "11:00", "12:30", "13:45", "15:00", "16:15", "17:30", "18:45", "20:00", "21:15", "22:30", "23:45"],
    "JB_TO_WOODLANDS": ["05:00", "05:30", "06:00", "06:30", "07:00", "07:30", "08:45", "10:00", "11:30", "12:45", "14:00", "15:15", "16:30", "17:45", "19:00", "20:15", "21:30", "22:45"],
    "JB_TO_SEGAMAT": ["07:35", "08:40", "12:45", "16:20", "20:30", "21:05"],
    "SEGAMAT_TO_JB": ["08:46", "10:31", "17:51", "20:11", "20:36", "23:46"]
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
        "2. JB SENTRAL to WOODLANDS CIQ\n"
        "3. JB SENTRAL to SEGAMAT\n"
        "4. SEGAMAT to JB SENTRAL"
    )
    return DIRECTION

async def choose_direction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the direction choice and ask for the date."""
    text = update.message.text
    if text == "1":
        context.user_data['direction'] = 'WOODLANDS_TO_JB'
    elif text == "2":
        context.user_data['direction'] = 'JB_TO_WOODLANDS'
    elif text == "3":
        context.user_data['direction'] = 'JB_TO_SEGAMAT'
    elif text == "4":
        context.user_data['direction'] = 'SEGAMAT_TO_JB'
    else:
        await update.message.reply_text("Invalid choice. Please reply with 1, 2, 3, or 4.")
        return DIRECTION
    
    await update.message.reply_text("Please enter the departure date in YYYY-MM-DD format (e.g., 2025-03-13).")
    return DATE

async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the date input and fetch trip info dynamically."""
    text = update.message.text
    if re.match(r'\d{4}-\d{2}-\d{2}', text):
        if is_past_date(text):
            await update.message.reply_text("Cannot monitor past departure time.")
            return ConversationHandler.END
        context.user_data['date'] = text
        direction = context.user_data['direction']
        # Fetch trip info dynamically for the selected date and direction
        trips = fetch_trip_info(text, direction)
        context.user_data['trips'] = trips
        
        if not trips:
            times = TIMES.get(direction, [])
            if not times:
                await update.message.reply_text("Unable to fetch departure times. Please try again later.")
                return ConversationHandler.END
            time_options = "\n".join([f"{i+1}. {t}" for i, t in enumerate(times)])
            await update.message.reply_text(
                f"Unable to fetch real-time data. Using static departure times:\n{time_options}"
            )
            context.user_data['trips'] = [{'departure': t, 'seats': 'N/A', 'fare': 'N/A', 'train': 'N/A'} for t in times]
            return TIME
        
        time_options = "\n".join([f"{i+1}. {trip['departure']} ({trip['seats']} seats, {trip['fare']})" for i, trip in enumerate(trips)])
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
    trips = context.user_data.get('trips', [])
    
    try:
        choice = int(text) - 1
        if 0 <= choice < len(trips):
            context.user_data['time'] = trips[choice]['departure']
        else:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Invalid choice. Please reply with a number from the list.")
        return TIME
    
    return await start_monitoring(update, context)

async def start_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.message.chat_id
    date = context.user_data['date']
    departure_time = context.user_data['time']
    direction = context.user_data['direction']
    current_seats = context.user_data.get('current_seats')
    
    if is_expired(date, departure_time):
        await update.message.reply_text("Cannot monitor past departure time.")
        return ConversationHandler.END
    
    key = f"{direction}_{date}_{departure_time}"
    
    with tasks_lock:
        if chat_id not in active_tasks:
            active_tasks[chat_id] = {}
        
        if key in active_tasks[chat_id]:
            await update.message.reply_text("You are already monitoring this trip.")
            return ConversationHandler.END
        
        if len(active_tasks[chat_id]) >= 5:
            await update.message.reply_text("You have reached the maximum of 5 monitoring tasks.")
            return ConversationHandler.END
    
    stop_event = threading.Event()
    loop = asyncio.get_running_loop()
    thread = threading.Thread(
        target=monitor_tickets,
        args=(chat_id, date, departure_time, CHECK_INTERVAL, stop_event, send_telegram_message, loop, direction, current_seats, key)
    )
    
    with tasks_lock:
        active_tasks[chat_id][key] = {
            "thread": thread, 
            "stop_event": stop_event, 
            "date": date, 
            "time": departure_time, 
            "direction": direction,
            "current_seats": current_seats
        }
    
    thread.start()
    save_active_monitors()
    
    direction_text = DIRECTION_TEXT[direction]
    
    await update.message.reply_text(
        f"Started monitoring tickets for {departure_time} on {date} from {direction_text}."
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def stop_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the stop conversation."""
    user_id = update.effective_user.id
    if user_id not in ALLOWED_IDS:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return ConversationHandler.END
    
    chat_id = update.message.chat_id
    loop = asyncio.get_running_loop()
    threads_to_join = []
    with tasks_lock:
        if chat_id not in active_tasks or not active_tasks[chat_id]:
            await update.message.reply_text("No active monitoring tasks to stop.")
            return ConversationHandler.END
        
        tasks = active_tasks[chat_id]
        if len(tasks) == 1:
            key = next(iter(tasks))
            task = tasks[key]
            task["stop_event"].set()
            threads_to_join.append(task["thread"])
    if threads_to_join:
        for thread in threads_to_join:
            await loop.run_in_executor(None, thread.join)
        with tasks_lock:
            if chat_id in active_tasks:
                del active_tasks[chat_id]
        save_active_monitors()
        await update.message.reply_text("Monitoring stopped.")
        return ConversationHandler.END
    else:
        with tasks_lock:
            msg = "Active monitoring tasks:\n"
            stop_list = list(tasks.keys())
            context.user_data['stop_list'] = stop_list
            for i, key in enumerate(stop_list, 1):
                task = tasks[key]
                direction_text = DIRECTION_TEXT[task['direction']]
                msg += f"{i}. {direction_text} on {task['date']} at {task['time']}\n"
            msg += "Reply with the number to stop, or 'all' to stop all."
        await update.message.reply_text(msg)
        return STOP

async def stop_choose(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the choice to stop monitoring."""
    chat_id = update.message.chat_id
    text = update.message.text.strip().lower()
    loop = asyncio.get_running_loop()
    threads_to_join = []
    with tasks_lock:
        if chat_id not in active_tasks:
            await update.message.reply_text("No active monitoring tasks.")
            return ConversationHandler.END
        
        if text == 'all':
            for key, task in list(active_tasks[chat_id].items()):
                task["stop_event"].set()
                threads_to_join.append(task["thread"])
        else:
            try:
                num = int(text)
                stop_list = context.user_data.get('stop_list', [])
                if 1 <= num <= len(stop_list):
                    key = stop_list[num - 1]
                    if key in active_tasks[chat_id]:
                        task = active_tasks[chat_id][key]
                        task["stop_event"].set()
                        threads_to_join.append(task["thread"])
                else:
                    await update.message.reply_text("Invalid number. Please choose from the list.")
                    return STOP
            except ValueError:
                await update.message.reply_text("Invalid input. Please reply with a number or 'all'.")
                return STOP
    
    for thread in threads_to_join:
        await loop.run_in_executor(None, thread.join)
    
    save_active_monitors()
    
    if text == 'all':
        await update.message.reply_text("All monitoring stopped.")
    else:
        await update.message.reply_text("Selected monitoring stopped.")
    
    if 'stop_list' in context.user_data:
        del context.user_data['stop_list']
    return ConversationHandler.END

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check the status of the monitoring tasks."""
    user_id = update.effective_user.id
    if user_id not in ALLOWED_IDS:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return
    
    chat_id = update.message.chat_id
    with tasks_lock:
        if chat_id not in active_tasks or not active_tasks[chat_id]:
            await update.message.reply_text("No active monitoring tasks.")
        else:
            msg = "Active monitoring tasks:\n"
            for key, task in active_tasks[chat_id].items():
                direction_text = DIRECTION_TEXT[task['direction']]
                msg += f"- {direction_text} on {task['date']} at {task['time']}\n"
            await update.message.reply_text(msg)

async def post_init(application: Application) -> None:
    loop = asyncio.get_running_loop()
    load_active_monitors(loop)

# Set up the bot application
application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

# Define the main conversation handler
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        DIRECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_direction)],
        DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_date)],
        TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_time)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

# Define the stop conversation handler
stop_handler = ConversationHandler(
    entry_points=[CommandHandler('stop', stop_start)],
    states={
        STOP: [MessageHandler(filters.TEXT & ~filters.COMMAND, stop_choose)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

# Add handlers to the application
application.add_handler(conv_handler)
application.add_handler(stop_handler)
application.add_handler(CommandHandler("status", status))

# Start the bot and HTTP server
if __name__ == "__main__":
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    save_stop_event = threading.Event()
    save_thread = threading.Thread(target=periodic_save, args=(save_stop_event,))
    save_thread.start()
    
    logger.info("Bot is running")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    # On shutdown
    save_stop_event.set()
    save_thread.join()
    save_active_monitors()