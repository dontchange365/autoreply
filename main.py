# main.py
import os
import time
import random
import logging
import json
from flask import Flask, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

# Logging ka chutiyapa set kar, taaki backend ke logs dikhein
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# .env file se variables load kar (local development ke liye)
load_dotenv()

app = Flask(__name__)

# --- MongoDB Connection Setup ---
MONGO_URI = os.getenv("MONGODB_URI")
if not MONGO_URI:
    logger.error("OYE MADARCHOD! MONGODB_URI environment variable set nahi hai! Teri gaand phat jayegi!")
    exit(1)

try:
    client = MongoClient(MONGO_URI)
    db = client.get_database("nobifeedback")
    groups_collection = db.groups
    campaigns_collection = db.campaigns
    logs_collection = db.logs
    
    insta_sessions_collection = db.insta_sessions
    insta_sessions_collection.create_index("username", unique=True)
    
    logger.info("MongoDB se connection successful, bhen ke laude!")
except Exception as e:
    logger.error(f"MADARCHOD! MongoDB connection failed: {e}")
    exit(1)

# --- Helper Functions ---
def add_random_chutiyapa(text):
    """Text mein random emoji/char pelenge."""
    emojis = ['😈', '🔥', '💻', '👊', '🤬', '🖕', '✨', '⚡', '🌟', '🚀']
    ascii_chars = ['@', '#', '_', '*', '~', '!', '&', '$', '%']
    
    parts = [text]
    for _ in range(random.randint(1, 3)):
        char_type = random.choice(['emoji', 'ascii', 'invisible'])
        if char_type == 'emoji':
            char_to_add = random.choice(emojis)
        elif char_type == 'ascii':
            char_to_add = random.choice(ascii_chars)
        else: # Invisible character
            char_to_add = chr(random.choice([0x200B, 0x200C, 0x200D]))

        insert_pos = random.randint(0, len(parts) - 1)
        parts.insert(insert_pos, char_to_add)
    
    return "".join(parts)

def log_challenge(challenge_type, description, details=""):
    """Challenges aur errors ko MongoDB mein pelenge."""
    log_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "type": "CHALLENGE" if "Challenge" in challenge_type or "Failed" in challenge_type or "Error" in challenge_type else "STATUS_UPDATE",
        "description": challenge_type,
        "details": details
    }
    try:
        logs_collection.insert_one(log_entry)
        logger.info(f"Challenge logged: {challenge_type} - {details}")
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to log challenge: {e}")

# --- Instagram Bot Core Logic ---

def instagram_login_playwright(username, password, playwright_instance: Playwright):
    """Instagram pe login karega Playwright se."""
    browser = None
    try:
        browser = playwright_instance.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context()
        page = context.new_page()
        
        page.goto("https://www.instagram.com/accounts/login/")
        page.wait_for_selector("input[name='username']", timeout=20000)
        
        page.fill("input[name='username']", username)
        page.fill("input[name='password']", password)
        page.click("button[type='submit']")
        
        page.wait_for_timeout(random.uniform(5000, 10000)) # Increased wait after submit

        # --- ASLI LOGIN CONFIRMATION CHUTIYAPA ---
        if "login_challenge" in page.url or "checkpoint" in page.url or "oauth" in page.url:
            logger.warning(f"CHALLENGE: Login Challenge detected ({page.url}).")
            log_challenge("Login Challenge", f"OTP/CAPTCHA/Security check needed. URL: {page.url}")
            return False, "challenge", None
        
        if "instagram.com/accounts/login" in page.url: # Still on login page
            if "Incorrect username or password" in page.content() or page.locator("div[aria-label*='Incorrect']").count() > 0:
                logger.error("Login Failed: Incorrect credentials.")
                log_challenge("Login Failed", "Incorrect username or password.")
                return False, "fail", None
            else:
                logger.error("Login Failed: Still on login page, possibly stuck or blocked silently.")
                log_challenge("Login Stuck", "Still on login page after submission, no clear error.")
                return False, "stuck_on_login", None

        try:
            home_feed_element = page.locator("svg[aria-label='Home']").first # Home icon
            home_feed_element.wait_for(state='visible', timeout=15000) # 15 sec tak wait kar for home element
            logger.info(f"Successfully logged in as {username}, bhen ke laude! Home feed element found.")
            cookies = context.cookies()
            return True, "success", cookies
        except PlaywrightTimeoutError:
            logger.error("Login Failed: Home feed element not found after login. Possibly blocked or stuck silently.")
            log_challenge("Login Blocked", "Home feed element not visible after login. Account flagged?")
            return False, "blocked_after_login", None
            
    except PlaywrightTimeoutError:
        logger.error("MADARCHOD! Playwright timeout during login. Page elements not found or loaded in time.")
        log_challenge("Login Timeout", "Playwright elements not found or loaded.")
        return False, "timeout", None
    except PlaywrightError as pe:
        logger.error(f"MADARCHOD! Playwright error during login: {pe}")
        log_challenge("Login Playwright Error", str(pe))
        return False, "playwright_error", None
    except Exception as e:
        logger.error(f"MADARCHOD! Login process failed: {e}")
        log_challenge("Login Error", str(e))
        return False, "error", None
    finally:
        if browser:
            browser.close()

def dismiss_popups_playwright(page):
    """Automation detection ya cookies ke pop-ups ki gaand marega."""
    try:
        page.locator("button:has-text('Allow all cookies')").click(timeout=5000)
        logger.info("Cookies consent dismissed.")
    except PlaywrightTimeoutError:
        pass
    except Exception as e:
        logger.warning(f"Failed to dismiss cookie popup: {e}")

    try:
        page.locator("button:has-text('Not Now')").click(timeout=5000)
        logger.info("'Not Now' for notifications dismissed.")
    except PlaywrightTimeoutError:
        pass
    except Exception as e:
        logger.warning(f"Failed to dismiss notification popup: {e}")

    try:
        page.locator("button:has-text('Dismiss'), button:has-text('OK'), button:has-text('I Understand'), [aria-label='Close'], svg[aria-label='Close']").click(timeout=5000)
        logger.info("Automation/general dismissible popup dismissed.")
    except PlaywrightTimeoutError:
        pass
    except Exception as e:
        logger.warning(f"Failed to dismiss general popup: {e}")


# Removed: perform_human_behavior_playwright function (as per user request)

def send_dm_to_group_playwright(group_id, message, playwright_instance: Playwright, cookies):
    """Specific group ID pe DM pelta hai."""
    browser = None
    try:
        browser = playwright_instance.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        page.goto(f"https://www.instagram.com/direct/t/{group_id}/")
        page.wait_for_timeout(random.uniform(3000, 6000))
        dismiss_popups_playwright(page)

        logger.info(f"Simulating typing for group {group_id}...")
        page.wait_for_timeout(random.uniform(1000, 3000)) # Typing delay

        message_box = page.locator("textarea[placeholder='Message...']")
        if not message_box.is_visible(timeout=15000): # Increased timeout
            logger.error(f"MADARCHOD! Message box not found for group {group_id}. Maybe access denied/removed from group.")
            log_challenge("GC Access Denied", f"Message box not found for group {group_id}.")
            return False

        message_box.fill(message)
        
        send_button = page.locator("button:has-text('Send')")
        send_button.click()

        logger.info(f"DM sent to group {group_id}: '{message}'")
        return True
    except PlaywrightTimeoutError:
        logger.error(f"MADARCHOD! Playwright timeout during DM send to group {group_id}.")
        log_challenge("DM Send Timeout", f"Group {group_id}.")
        return False
    except PlaywrightError as pe:
        logger.error(f"MADARCHOD! Playwright error during DM send to group {group_id}: {pe}")
        log_challenge("DM Send Playwright Error", f"Group {group_id}. Error: {pe}")
        return False
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to send DM to group {group_id}: {e}")
        log_challenge("DM Send Failed", f"Group {group_id}. Error: {e}")
        return False
    finally:
        if browser:
            browser.close()

def send_dm_to_user_playwright(username, message, playwright_instance: Playwright, cookies):
    """Specific user ko DM pelta hai."""
    browser = None
    try:
        browser = playwright_instance.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        page.goto("https://www.instagram.com/direct/inbox/")
        page.wait_for_timeout(random.uniform(3000, 6000))
        dismiss_popups_playwright(page)

        new_message_button = page.locator("svg[aria-label='New message']")
        new_message_button.click(timeout=15000)
        page.wait_for_timeout(random.uniform(2000, 4000))

        search_input = page.locator("input[placeholder='Search']")
        search_input.fill(username)
        page.wait_for_timeout(random.uniform(3000, 5000))

        # Updated locator for user search result (more robust)
        user_result_selector = f"div[role='button'][role='link'][href*='/{username}/'], div[role='button']:has-text('{username}')"
        first_user_result = page.locator(user_result_selector).first

        if not first_user_result.is_visible(timeout=15000): # Increased timeout for visibility
             first_user_result = page.locator("div[role='button'][aria-selected='false']").first
             if not first_user_result.is_visible(timeout=15000):
                logger.error(f"MADARCHOD! User '{username}' not found in search results or unselectable.")
                log_challenge("DM User Failed", f"User '{username}' not found/selectable.")
                return False

        first_user_result.click(timeout=10000)
        page.wait_for_timeout(random.uniform(1000, 2000))

        chat_button = page.locator("button:has-text('Chat'), button:has-text('Next')")
        chat_button.click(timeout=15000)
        page.wait_for_timeout(random.uniform(2000, 4000))

        message_box = page.locator("textarea[placeholder='Message...']")
        if not message_box.is_visible(timeout=15000): # Increased timeout
            logger.error(f"MADARCHOD! Message box not found for user {username}. Maybe chat didn't open.")
            log_challenge("DM User Failed", f"Message box not found for user {username}.")
            return False

        message_box.fill(message)
        send_button = page.locator("button:has-text('Send')")
        send_button.click()

        logger.info(f"DM sent to user {username}: '{message}'")
        return True
    except PlaywrightTimeoutError:
        logger.error(f"MADARCHOD! Playwright timeout during DM send to user {username}.")
        log_challenge("DM User Timeout", f"User {username}.")
        return False
    except PlaywrightError as pe:
        logger.error(f"MADARCHOD! Playwright error during DM send to user {username}: {pe}")
        log_challenge("DM User Playwright Error", f"User {username}. Error: {pe}")
        return False
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to send DM to user {username}: {e}")
        log_challenge("DM User Failed", f"User {username}. Error: {e}")
        return False
    finally:
        if browser:
            browser.close()

def change_group_name_playwright(group_id, new_name, playwright_instance: Playwright, cookies):
    """Group chat ka naam badlega."""
    browser = None
    try:
        browser = playwright_instance.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        page.goto(f"https://www.instagram.com/direct/t/{group_id}/")
        page.wait_for_timeout(random.uniform(3000, 6000))
        dismiss_popups_playwright(page)

        info_button = page.locator("a[href*='/direct/t/'][href*='/info/']")
        if not info_button.is_visible(timeout=15000):
            logger.error(f"MADARCHOD! Group info button not found for group {group_id}. Maybe access denied.")
            log_challenge("GC Name Change Error", f"Group info button not found for group {group_id}.")
            return False
        
        info_button.click()
        page.wait_for_timeout(random.uniform(3000, 5000))

        edit_name_field = page.locator("input[placeholder='Group name']")
        if not edit_name_field.is_visible(timeout=15000):
            logger.error(f"MADARCHOD! Group name edit field not found for group {group_id}.")
            log_challenge("GC Name Change Error", f"Group name edit field not found for group {group_id}.")
            return False

        edit_name_field.fill(new_name)
        
        save_button = page.locator("button:has-text('Done'), button:has-text('Save')")
        save_button.click()

        logger.info(f"Group {group_id} name changed to: '{new_name}'")
        return True
    except PlaywrightTimeoutError:
        logger.error(f"MADARCHOD! Playwright timeout during GC name change for group {group_id}.")
        log_challenge("GC Name Change Timeout", f"Group {group_id}.")
        return False
    except PlaywrightError as pe:
        logger.error(f"MADARCHOD! Playwright error during GC name change for group {group_id}: {pe}")
        log_challenge("GC Name Change Playwright Error", f"Group {group_id}. Error: {pe}")
        return False
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to change group {group_id} name: {e}")
        log_challenge("GC Name Change Failed", f"Group {group_id}. Error: {e}")
        return False
    finally:
        if browser:
            browser.close()

def submit_challenge_response_playwright(response_code, playwright_instance: Playwright, cookies):
    """OTP/CAPTCHA response handle karega."""
    browser = None
    try:
        browser = playwright_instance.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        page.goto("https://www.instagram.com/challenge/")
        page.wait_for_timeout(random.uniform(2000, 4000))

        input_field = page.locator("input[aria-label='security code'], input[name='security_code'], input[placeholder='Security Code'], input[aria-label='Confirmation Code'], input[name='verificationCode'], input[type='text']")
        if not input_field.is_visible(timeout=15000):
            logger.error("MADARCHOD! Challenge input field not found on page.")
            log_challenge("Challenge Submit Error", "Input field for challenge not found.")
            return False, None

        input_field.fill(response_code)
        
        submit_button = page.locator("button:has-text('Confirm'), button[type='submit'], button:has-text('Submit'), button:has-text('Verify')")
        submit_button.click()
        
        page.wait_for_timeout(random.uniform(5000, 10000))

        if "login_challenge" in page.url or "checkpoint" in page.url or "oauth" in page.url:
            logger.warning("Challenge solution failed or new challenge arrived.")
            log_challenge("Challenge Solution Failed", "Submitted code didn't resolve challenge.")
            return False, None
        else:
            logger.info("Challenge submitted successfully, bhen ke laude!")
            updated_cookies = context.cookies()
            return True, updated_cookies

    except PlaywrightTimeoutError:
        logger.error("MADARCHOD! Playwright timeout during challenge response submission.")
        log_challenge("Challenge Submit Timeout", "Input field or submit button not found.")
        return False, None
    except PlaywrightError as pe:
        logger.error(f"MADARCHOD! Playwright error during challenge response submission: {pe}")
        log_challenge("Challenge Submit Playwright Error", str(pe))
        return False, None
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to submit challenge response: {e}")
        log_challenge("Challenge Submit Error", str(e))
        return False, None
    finally:
        if browser:
            browser.close()


# --- Flask Routes ---

@app.route("/")
def home():
    """Frontend HTML file serve karega."""
    with open("index.html", "r") as f:
        return f.read()

@app.route("/check_login_status", methods=["GET"])
def check_login_status_route():
    """Check karega kaun sa user logged in hai DB mein."""
    try:
        session_data = insta_sessions_collection.find_one({})
        
        if session_data and "cookies" in session_data and "username" in session_data and session_data["cookies"]:
            logger.info(f"Login status checked: User '{session_data['username']}' found in session DB.")
            return jsonify({"status": "logged_in", "username": session_data["username"]})
        else:
            logger.info("Login status checked: No active session found in DB.")
            return jsonify({"status": "logged_out", "message": "Koi active session nahi."})
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to check login status: {e}")
        return jsonify({"status": "error", "message": f"Login status check mein chutiyapa: {e}"}), 500


@app.route("/login", methods=["POST"])
def login_route():
    """Login request handle karega."""
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"status": "error", "message": "OYE BSDK! Username ya password missing hai!"}), 400

    insta_sessions_collection.update_one(
        {"username": username},
        {"$set": {"password": password}}, # PASSWORD IS STORED PLAIN TEXT HERE - RISKY!
        upsert=True
    )
    
    logger.info(f"Attempting login for user: {username}")
    with sync_playwright() as p:
        success, msg, cookies = instagram_login_playwright(username, password, p)
        if success:
            insta_sessions_collection.update_one(
                {"username": username},
                {"$set": {"cookies": json.dumps(cookies)}},
                upsert=True
            )
            return jsonify({"status": "success", "message": "Login successful, ab phodunga!"})
        else:
            if msg == "challenge":
                return jsonify({"status": "challenge", "message": "Login Challenge, OTP/CAPTCHA chahiye!"}), 401
            elif msg == "fail":
                return jsonify({"status": "error", "message": "Login failed: Incorrect username or password."}), 401
            elif msg == "timeout":
                return jsonify({"status": "error", "message": "Login timeout: Instagram took too long to respond."}), 500
            elif msg == "playwright_error":
                return jsonify({"status": "error", "message": "Login Playwright error. Check backend logs."}), 500
            elif msg == "stuck_on_login":
                return jsonify({"status": "error", "message": "Login stuck: Still on login/challenge page. Try again or check logs."}), 500
            elif msg == "blocked_after_login":
                return jsonify({"status": "error", "message": "Login blocked: Home page not reached. Account flagged?"}), 500
            else:
                return jsonify({"status": "error", "message": f"Login failed: {msg}"}), 500


@app.route("/logout", methods=["GET"])
def logout_route():
    """Instagram session ko DB se hata dega."""
    try:
        insta_sessions_collection.delete_many({}) # Saare sessions delete kar de
        logger.info("All Instagram sessions cleared from DB. Logged out.")
        return jsonify({"status": "success", "message": "Logout successful. Session ki gaand maar di!"})
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to logout/clear sessions: {e}")
        return jsonify({"status": "error", "message": f"Logout mein chutiyapa: {e}"}), 500


@app.route("/add_group", methods=["POST"])
def add_group_route():
    """MongoDB mein group details save karega."""
    data = request.json
    group_id = data.get("group_id")
    group_name = data.get("group_name")

    if not group_id or not group_name:
        return jsonify({"status": "error", "message": "MADARCHOD! Group ID ya Group Name missing hai!"}), 400

    try:
        if groups_collection.find_one({"group_id": group_id}):
            return jsonify({"status": "warning", "message": "Chutiye, yeh group pehle se hai!"}), 200

        groups_collection.insert_one({"group_id": group_id, "group_name": group_name})
        return jsonify({"status": "success", "message": "Group add ho gaya, ab uski gaand marenge!"})
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to add group: {e}")
        return jsonify({"status": "error", "message": f"Group add karne mein chutiyapa: {e}"}), 500

@app.route("/get_groups", methods=["GET"])
def get_groups_route():
    """MongoDB se saved groups dega."""
    try:
        groups = []
        for group in groups_collection.find({}, {"_id": 0}):
            groups.append(group)
        return jsonify({"status": "success", "groups": groups})
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to get groups: {e}")
        return jsonify({"status": "error", "message": f"Groups nikalne mein chutiyapa: {e}"}), 500

@app.route("/start_spam_campaign", methods=["POST"])
def start_spam_campaign_route():
    """DM spamming campaign shuru karega (group ke liye)."""
    data = request.json
    group_id = data.get("group_id")
    num_messages = data.get("num_messages")
    min_delay = data.get("min_delay")
    max_delay = data.get("max_delay")
    messages_str = data.get("messages")
    username_from_frontend = data.get("username")

    if not all([group_id, num_messages, min_delay, max_delay, messages_str, username_from_frontend]):
        return jsonify({"status": "error", "message": "OYE BSDK! Saara data de, kuch missing hai!"}), 400

    messages_list = [msg.strip() for msg in messages_str.split(',') if msg.strip()]
    if not messages_list:
        return jsonify({"status": "error", "message": "MADARCHOD! Message list empty hai!"}), 400

    session_data = insta_sessions_collection.find_one({"username": username_from_frontend})
    if not session_data or "cookies" not in session_data:
        return jsonify({"status": "error", "message": "MADARCHOD! Instagram session data missing for this user. Pehle login kar!"}), 401
    
    cookies = json.loads(session_data["cookies"])
    
    campaign_settings = {
        "campaign_name": f"Spam_Group_{group_id}_{time.time()}",
        "target_type": "group",
        "target_id": group_id,
        "num_messages_to_send": num_messages,
        "min_delay_seconds": min_delay,
        "max_delay_seconds": max_delay,
        "message_templates": messages_list,
        "status": "running",
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    campaigns_collection.insert_one(campaign_settings)
    logger.info(f"Campaign '{campaign_settings['campaign_name']}' started for group {group_id}")

    message_counter = 0
    for i in range(num_messages):
        random_message = random.choice(messages_list)
        final_message = add_random_chutiyapa(random_message)
        
        logger.info(f"Attempting to send message {i+1}/{num_messages} to {group_id}: '{final_message}'")
        
        with sync_playwright() as p:
            sent = send_dm_to_group_playwright(group_id, final_message, p, cookies)
        
        if not sent: # Message failed
            logger.warning(f"Message {i+1} failed. Waiting 5 secs and skipping...")
            time.sleep(5)
            log_challenge("Message Send Skipped", f"Failed to send message {i+1} to group {group_id}. Skipping.")
        
        # Delay (always happens regardless of send status)
        delay_time = random.uniform(min_delay, max_delay)
        logger.info(f"Waiting for {delay_time:.2f} seconds...")
        time.sleep(delay_time)
        
    campaigns_collection.update_one(
        {"_id": campaign_settings["_id"]},
        {"$set": {"status": "completed", "end_time": time.strftime("%Y-%m-%d %H:%M:%S")}}
    )
    logger.info(f"Campaign '{campaign_settings['campaign_name']}' completed, bhen ke laude!")
    
    return jsonify({"status": "success", "message": "Spamming campaign shuru ho gaya, ab dekhte hai kya gaand marti hai!"})

@app.route("/start_dm_to_user_campaign", methods=["POST"])
def start_dm_to_user_campaign_route():
    """DM spamming campaign shuru karega (users ke liye)."""
    data = request.json
    usernames_str = data.get("usernames")
    num_messages = data.get("num_messages")
    min_delay = data.get("min_delay")
    max_delay = data.get("max_delay")
    messages_str = data.get("messages")
    username_from_frontend = data.get("username")

    if not all([usernames_str, num_messages, min_delay, max_delay, messages_str, username_from_frontend]):
        return jsonify({"status": "error", "message": "OYE BSDK! Saara data de, kuch missing hai!"}), 400

    usernames_list = [u.strip() for u in usernames_str.split(',') if u.strip()]
    messages_list = [msg.strip() for msg in messages_str.split(',') if msg.strip()]
    if not usernames_list or not messages_list:
        return jsonify({"status": "error", "message": "MADARCHOD! Username ya Message list empty hai!"}), 400

    session_data = insta_sessions_collection.find_one({"username": username_from_frontend})
    if not session_data or "cookies" not in session_data:
        return jsonify({"status": "error", "message": "MADARCHOD! Instagram session data missing. Pehle login kar!"}), 401
    
    cookies = json.loads(session_data["cookies"])
    
    campaign_settings = {
        "campaign_name": f"Spam_Users_{usernames_list[0]}_{time.time()}",
        "target_type": "user",
        "target_usernames": usernames_list,
        "num_messages_to_send": num_messages,
        "min_delay_seconds": min_delay,
        "max_delay_seconds": max_delay,
        "message_templates": messages_list,
        "status": "running",
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    campaigns_collection.insert_one(campaign_settings)
    logger.info(f"Campaign '{campaign_settings['campaign_name']}' started for users: {usernames_list}")

    message_counter = 0
    for username_target in usernames_list:
        for i in range(num_messages):
            random_message = random.choice(messages_list)
            final_message = add_random_chutiyapa(random_message)
            
            logger.info(f"Attempting to send message {i+1}/{num_messages} to user {username_target}: '{final_message}'")
            
            with sync_playwright() as p:
                sent = send_dm_to_user_playwright(username_target, final_message, p, cookies)
            
            if not sent: # Message failed
                logger.warning(f"Message {i+1} failed for user {username_target}. Waiting 5 secs and skipping...")
                time.sleep(5)
                log_challenge("Message Send Skipped User", f"Failed to send message {i+1} to user {username_target}. Skipping.")
            
            # Delay (always happens regardless of send status)
            delay_time = random.uniform(min_delay, max_delay)
            logger.info(f"Waiting for {delay_time:.2f} seconds...")
            time.sleep(delay_time)
            
    campaigns_collection.update_one(
        {"_id": campaign_settings["_id"]},
        {"$set": {"status": "completed", "end_time": time.strftime("%Y-%m-%d %H:%M:%S")}}
    )
    logger.info(f"Campaign '{campaign_settings['campaign_name']}' completed, bhen ke laude!")
    
    return jsonify({"status": "success", "message": "DM to user campaign shuru ho gaya, ab dek देखते है kya gaand marti hai!"})


@app.route("/change_gc_name", methods=["POST"])
def change_gc_name_route():
    """Group chat ka naam badlega."""
    data = request.json
    group_id = data.get("group_id")
    new_name = data.get("new_name")
    username_from_frontend = data.get("username")

    if not all([group_id, new_name, username_from_frontend]):
        return jsonify({"status": "error", "message": "MADARCHOD! Group ID, Naya Naam ya Username missing hai!"}), 400

    session_data = insta_sessions_collection.find_one({"username": username_from_frontend})
    if not session_data or "cookies" not in session_data:
        return jsonify({"status": "error", "message": "MADARCHOD! Instagram session data missing. Pehle login kar!"}), 401
    
    cookies = json.loads(session_data["cookies"])
    
    final_new_name = add_random_chutiyapa(new_name)
    logger.info(f"Attempting to change group {group_id} name to: '{final_new_name}'")
    
    with sync_playwright() as p:
        name_changed = change_group_name_playwright(group_id, final_new_name, p, cookies)

    if name_changed:
        return jsonify({"status": "success", "message": f"Group {group_id} ka naam badal diya, bhen ke laude!"})
    else:
        log_challenge("GC Name Change Failed Final", f"Group {group_id}. Name: {final_new_name}.")
        return jsonify({"status": "error", "message": "Group ka naam badalne mein chutiyapa ho gaya!"}), 500

@app.route("/get_logs", methods=["GET"])
def get_logs_route():
    """MongoDB se logs dega."""
    try:
        logs = []
        for log in logs_collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(50):
            logs.append(log)
        return jsonify({"status": "success", "logs": logs})
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to get logs: {e}")
        return jsonify({"status": "error", "message": f"Logs nikalne mein chutiyapa: {e}"}), 500

@app.route("/submit_challenge_response", methods=["POST"])
def submit_challenge_response_route():
    """OTP/CAPTCHA response handle karega."""
    data = request.json
    response_code = data.get("response_code")
    username_from_frontend = data.get("username")
    
    if not response_code or not username_from_frontend:
        return jsonify({"status": "error", "message": "OYE BSDK! Response code ya Username missing hai!"}), 400

    session_data = insta_sessions_collection.find_one({"username": username_from_frontend})
    if not session_data or "cookies" not in session_data:
        return jsonify({"status": "error", "message": "MADARCHOD! Instagram session data missing. Pehle login kar!"}), 400
    
    cookies = json.loads(session_data["cookies"])

    try:
        with sync_playwright() as p:
            success, updated_cookies = submit_challenge_response_playwright(response_code, p, cookies)
            if success:
                insta_sessions_collection.update_one(
                    {"username": username_from_frontend},
                    {"$set": {"cookies": json.dumps(updated_cookies)}},
                    upsert=True
                )
                return jsonify({"status": "success", "message": "Challenge solved. Login resumed!"})
            else:
                return jsonify({"status": "error", "message": "Challenge solve nahi hua ya naya challenge aaya!"}), 400

    except Exception as e:
        logger.error(f"MADARCHOD! Failed to submit challenge response: {e}")
        log_challenge("Challenge Submit Error", str(e))
        return jsonify({"status": "error", "message": f"Challenge submit karne mein chutiyapa: {e}"}), 500


# Server start kar
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"NOBI BOT server starting on port {port}, bhen ke laude!")
    app.run(host="0.0.0.0", port=port)