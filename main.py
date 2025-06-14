# main.py
import os
import time
import random
import logging
from flask import Flask, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Playwright

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
    exit(1) # Agar URI nahi mila toh seedha exit kar

try:
    client = MongoClient(MONGO_URI)
    db = client.get_database("nobifeedback") # Tera database name
    groups_collection = db.groups
    campaigns_collection = db.campaigns
    logs_collection = db.logs # Challenges aur errors ke liye
    logger.info("MongoDB se connection successful, bhen ke laude!")
except Exception as e:
    logger.error(f"MADARCHOD! MongoDB connection failed: {e}")
    exit(1)

# --- Instagram Bot Global Variables (Teri Gaand Maarnge Yahan Se) ---
INSTA_USERNAME = os.getenv("INSTA_USERNAME")
INSTA_PASSWORD = os.getenv("INSTA_PASSWORD")

# --- Helper Functions (Tere Jaise Noob Ke Liye) ---
def add_random_chutiyapa(text):
    """Text mein random emoji/char pelenge."""
    emojis = ['😈', '🔥', '💻', '👊', '🤬', '🖕', '✨', '⚡', '🌟', '🚀']
    ascii_chars = ['@', '#', '_', '*', '~', '!', '&', '$', '%']
    
    parts = [text]
    # Randomly 1-3 jagah chutiyapa daalenge
    for _ in range(random.randint(1, 3)):
        char_type = random.choice(['emoji', 'ascii', 'invisible'])
        if char_type == 'emoji':
            char_to_add = random.choice(emojis)
        elif char_type == 'ascii':
            char_to_add = random.choice(ascii_chars)
        else: # Invisible character
            char_to_add = chr(random.choice([0x200B, 0x200C, 0x200D])) # Zero Width Space, Non-Joiner, Joiner

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

# --- Instagram Bot Core Logic (Asli Gaand Maarne Wala Code) ---

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
        
        page.wait_for_timeout(random.uniform(3000, 7000))

        # Check for login success/failure or challenges
        if "login_challenge" in page.url or "checkpoint" in page.url or "oauth" in page.url:
            logger.warning(f"CHALLENGE: Login Challenge detected ({page.url}).")
            log_challenge("Login Challenge", f"OTP/CAPTCHA/Security check needed. URL: {page.url}")
            return False, "challenge", None

        # Check for incorrect credentials after attempting login
        # This is tricky as page.content() might not have updated instantly after submit
        # Better to check for presence of error messages
        if "Incorrect username or password" in page.content() or page.locator("div[aria-label*='Incorrect']").count() > 0:
            logger.error("Login Failed: Incorrect credentials.")
            log_challenge("Login Failed", "Incorrect username or password.")
            return False, "fail", None
            
        logger.info(f"Successfully logged in as {username}, bhen ke laude!")
        # Session cookies ko JSON string mein return kar
        cookies = context.cookies()
        
        return True, "success", cookies

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
        # Cookie consent button
        page.locator("button:has-text('Allow all cookies')").click(timeout=5000)
        logger.info("Cookies consent dismissed.")
    except:
        pass

    try:
        # "Not Now" for notifications
        page.locator("button:has-text('Not Now')").click(timeout=5000)
        logger.info("'Not Now' for notifications dismissed.")
    except:
        pass

    try:
        # Generic dismiss/OK/I Understand/Close button for other popups (including automation detection)
        # Using multiple locators to cover different button texts/svgs
        page.locator("button:has-text('Dismiss'), button:has-text('OK'), button:has-text('I Understand'), [aria-label='Close'], svg[aria-label='Close']").click(timeout=5000)
        logger.info("Automation/general dismissible popup dismissed.")
    except Exception as e:
        # logger.info(f"No general dismiss popup found or error dismissing: {e}") # Too verbose in logs
        pass


def perform_human_behavior_playwright(page, min_delay_seconds):
    """Human-like chutiyapa karega: reel scroll, profile visit."""
    try:
        # Agar delay kam hai, toh zyada human behavior nahi pelenge
        if min_delay_seconds <= 2:
            logger.info("Low delay, only quick human behavior (1-2 reels scroll).")
            page.goto("https://www.instagram.com/")
            page.wait_for_timeout(random.uniform(2000, 4000))
            for _ in range(random.randint(1, 2)):
                page.evaluate("window.scrollBy(0, window.innerHeight);")
                page.wait_for_timeout(random.uniform(1000, 3000))
            logger.info("Scrolled a few reels/posts.")
            return

        logger.info("Performing full human behavior: reels, scrolls, profile visits.")
        page.goto("https://www.instagram.com/")
        page.wait_for_timeout(random.uniform(5000, 10000))
        for _ in range(random.randint(2, 5)):
            page.evaluate("window.scrollBy(0, window.innerHeight * 0.8);")
            page.wait_for_timeout(random.uniform(2000, 5000))
        logger.info("Scrolled feed/reels.")

        page.goto("https://www.instagram.com/explore/people/suggested/")
        page.wait_for_timeout(random.uniform(5000, 10000))
        
        # Suggested profiles ke links dhundo (example, may need adjustment)
        profile_links = page.locator("a[href*='/p/'][tabindex='0']").all() # Post links bhi ho sakte hain
        if profile_links:
            random_profile_link = random.choice(profile_links)
            random_profile_link.click()
            page.wait_for_timeout(random.uniform(5000, 10000))
            logger.info("Visited a random suggested profile.")
            page.go_back()
            page.wait_for_timeout(random.uniform(2000, 4000))
        else:
            logger.info("No suggested profiles found to visit.")

    except Exception as e:
        logger.warning(f"MADARCHOD! Human behavior failed: {e}")


def send_dm_to_group_playwright(group_id, message, playwright_instance: Playwright, cookies):
    """Specific group ID pe DM pelta hai."""
    browser = None
    try:
        browser = playwright_instance.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context()
        context.add_cookies(cookies) # Saved cookies load kar
        page = context.new_page()

        page.goto(f"https://www.instagram.com/direct/t/{group_id}/")
        page.wait_for_timeout(random.uniform(3000, 6000))
        dismiss_popups_playwright(page)

        # Typing status ka chutiyapa (Playwright se direct nahi, simulate)
        logger.info(f"Simulating typing for group {group_id}...")
        page.wait_for_timeout(random.uniform(1000, 3000)) # Typing delay

        message_box = page.locator("textarea[placeholder='Message...']")
        if not message_box.is_visible(): # Agar message box nahi mila, toh shayad access denied hai
            logger.error(f"MADARCHOD! Message box not found for group {group_id}. Maybe access denied/removed from group.")
            log_challenge("GC Access Denied", f"Message box not found for group {group_id}.")
            return False

        message_box.fill(message)
        
        # Send button ka locator, 'Send' text wala button
        send_button = page.locator("button:has-text('Send')")
        send_button.click()

        logger.info(f"DM sent to group {group_id}: '{message}'")
        return True
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to send DM to group {group_id}: {e}")
        log_challenge("DM Send Failed", f"Group {group_id}. Error: {e}")
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
        context.add_cookies(cookies) # Saved cookies load kar
        page = context.new_page()

        page.goto(f"https://www.instagram.com/direct/t/{group_id}/")
        page.wait_for_timeout(random.uniform(3000, 6000))
        dismiss_popups_playwright(page)

        # Group info icon ya link pe click kar (example XPATH, may need adjustment)
        info_button = page.locator("a[href*='/direct/t/'][href*='/info/']")
        if not info_button.is_visible():
            logger.error(f"MADARCHOD! Group info button not found for group {group_id}. Maybe access denied.")
            log_challenge("GC Name Change Error", f"Group info button not found for group {group_id}.")
            return False
        
        info_button.click()
        page.wait_for_timeout(random.uniform(3000, 5000))

        # Edit name field dhundh
        edit_name_field = page.locator("input[placeholder='Group name']")
        if not edit_name_field.is_visible():
            logger.error(f"MADARCHOD! Group name edit field not found for group {group_id}.")
            log_challenge("GC Name Change Error", f"Group name edit field not found for group {group_id}.")
            return False

        edit_name_field.fill(new_name) # Clear() not explicitly needed if fill replaces
        
        # Save/Done button
        save_button = page.locator("button:has-text('Done'), button:has-text('Save')")
        save_button.click()

        logger.info(f"Group {group_id} name changed to: '{new_name}'")
        return True
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
        context.add_cookies(cookies) # Previous cookies load kar
        page = context.new_page()

        # Assuming the challenge page is still open from previous login attempt
        # We need to refresh or navigate back to the challenge URL if not
        # Or, just try to find the input field on current page

        # OTP ya Checkpoint solve kar
        input_field = page.locator("input[aria-label='security code'], input[name='security_code'], input[placeholder='Security Code'], input[aria-label='Confirmation Code'], input[name='verificationCode']")
        input_field.fill(response_code)
        
        # Submit button
        submit_button = page.locator("button:has-text('Confirm'), button[type='submit'], button:has-text('Submit'), button:has-text('Verify')")
        submit_button.click()
        
        page.wait_for_timeout(random.uniform(5000, 10000)) # Wait for result

        # Check if challenge page is still present
        if "login_challenge" in page.url or "checkpoint" in page.url or "oauth" in page.url:
            logger.warning("Challenge solution failed or new challenge arrived.")
            log_challenge("Challenge Solution Failed", "Submitted code didn't resolve challenge.")
            return False
        else:
            logger.info("Challenge submitted successfully, bhen ke laude!")
            # Get updated cookies after challenge is solved
            updated_cookies = context.cookies()
            return True, updated_cookies

    except Exception as e:
        logger.error(f"MADARCHOD! Failed to submit challenge response: {e}")
        log_challenge("Challenge Submit Error", str(e))
        return False, None
    finally:
        if browser:
            browser.close()


# --- Flask Routes (Tere Frontend Se Baat Karne Ke Liye) ---

@app.route("/")
def home():
    """Frontend HTML file serve karega."""
    with open("index.html", "r") as f:
        return f.read()

# --- Global variable to store session cookies (Simple for this setup) ---
# NOTE: Production mein isko database mein encrypt karke store karna chahiye!
# Abhi ke liye, yeh server restart hone pe ud jayega
instagram_session_cookies = []

@app.route("/login", methods=["POST"])
def login_route():
    """Login request handle karega."""
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"status": "error", "message": "OYE BSDK! Username ya password missing hai!"}), 400

    global INSTA_USERNAME, INSTA_PASSWORD, instagram_session_cookies
    INSTA_USERNAME = username # Global variable update kar
    INSTA_PASSWORD = password # Global variable update kar

    # credentials ko env vars mein save kar, taaki har baar na dena pade
    # Render env vars mein set karna preferred hai.
    # Abhi ke liye, in-memory store kar rahe hain.

    logger.info(f"Attempting login for user: {username}")
    with sync_playwright() as p:
        success, msg, cookies = instagram_login_playwright(username, password, p)
        if success:
            instagram_session_cookies = cookies # Cookies save kar
            return jsonify({"status": "success", "message": "Login successful, ab phodunga!"})
        else:
            if msg == "challenge":
                return jsonify({"status": "challenge", "message": "Login Challenge, OTP/CAPTCHA chahiye!"}), 401
            elif msg == "fail":
                return jsonify({"status": "error", "message": "Login failed: Incorrect username or password."}), 401
            else:
                return jsonify({"status": "error", "message": f"Login failed: {msg}"}), 401

@app.route("/add_group", methods=["POST"])
def add_group_route():
    """MongoDB mein group details save karega."""
    data = request.json
    group_id = data.get("group_id")
    group_name = data.get("group_name")

    if not group_id or not group_name:
        return jsonify({"status": "error", "message": "MADARCHOD! Group ID ya Group Name missing hai!"}), 400

    try:
        # Check if group already exists
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
        for group in groups_collection.find({}, {"_id": 0}): # _id nahi chahiye
            groups.append(group)
        return jsonify({"status": "success", "groups": groups})
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to get groups: {e}")
        return jsonify({"status": "error", "message": f"Groups nikalne mein chutiyapa: {e}"}), 500

@app.route("/start_spam_campaign", methods=["POST"])
def start_spam_campaign_route():
    """DM spamming campaign shuru karega."""
    data = request.json
    group_id = data.get("group_id")
    num_messages = data.get("num_messages")
    min_delay = data.get("min_delay")
    max_delay = data.get("max_delay")
    messages_str = data.get("messages") # Comma separated string

    if not all([group_id, num_messages, min_delay, max_delay, messages_str]):
        return jsonify({"status": "error", "message": "OYE BSDK! Saara data de, kuch missing hai!"}), 400

    messages_list = [msg.strip() for msg in messages_str.split(',') if msg.strip()]
    if not messages_list:
        return jsonify({"status": "error", "message": "MADARCHOD! Message list empty hai!"}), 400

    # Credentials aur session check kar
    if not INSTA_USERNAME or not INSTA_PASSWORD or not instagram_session_cookies:
        return jsonify({"status": "error", "message": "MADARCHOD! Instagram credentials ya session missing. Pehle login kar!"}), 401

    # Campaign settings MongoDB mein pel
    campaign_settings = {
        "campaign_name": f"Spam_{group_id}_{time.time()}", # Random name
        "target_group_id": group_id,
        "num_messages_to_send": num_messages,
        "min_delay_seconds": min_delay,
        "max_delay_seconds": max_delay,
        "message_templates": messages_list,
        "status": "running",
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    campaigns_collection.insert_one(campaign_settings)
    logger.info(f"Campaign '{campaign_settings['campaign_name']}' started for group {group_id}")

    # --- Asli Spamming Logic (Background mein chalega, as promised, but simple) ---
    # NOTE: Flask mein direct loop block nahi karna chahiye production mein.
    # Yahan simple loop hai, real background tasks ke liye Celery/RQ jaisa queue use karna.

    message_counter = 0
    for i in range(num_messages):
        random_message = random.choice(messages_list)
        final_message = add_random_chutiyapa(random_message) # Random chutiyapa add kar
        
        logger.info(f"Attempting to send message {i+1}/{num_messages} to {group_id}: '{final_message}'")
        
        with sync_playwright() as p:
            sent = send_dm_to_group_playwright(group_id, final_message, p, instagram_session_cookies)
        
        if sent:
            message_counter += 1
            # Human behavior logic agar delay kam hai
            if min_delay <= 2 and message_counter % random.randint(20, 25) == 0:
                with sync_playwright() as p:
                    perform_human_behavior_playwright(p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage']).new_page(), min_delay) # Naya page instance
                message_counter = 0 # Counter reset
        else:
            logger.warning(f"Message {i+1} failed. Waiting 5 secs and skipping...")
            time.sleep(5) # 5 second wait and skip
            log_challenge("Message Send Skipped", f"Failed to send message {i+1} to group {group_id}. Skipping.")
            # Yahan dobara login ka logic bhi add kar sakte ho agar session fail hua
            continue # Skip to next message if failed

        # Delay
        delay_time = random.uniform(min_delay, max_delay)
        logger.info(f"Waiting for {delay_time:.2f} seconds...")
        time.sleep(delay_time)
        
    campaigns_collection.update_one(
        {"_id": campaign_settings["_id"]},
        {"$set": {"status": "completed", "end_time": time.strftime("%Y-%m-%d %H:%M:%S")}}
    )
    logger.info(f"Campaign '{campaign_settings['campaign_name']}' completed, bhen ke laude!")
    
    return jsonify({"status": "success", "message": "Spamming campaign shuru ho gaya, ab dekhte hai kya gaand marti hai!"})

@app.route("/change_gc_name", methods=["POST"])
def change_gc_name_route():
    """Group chat ka naam badlega."""
    data = request.json
    group_id = data.get("group_id")
    new_name = data.get("new_name")

    if not group_id or not new_name:
        return jsonify({"status": "error", "message": "MADARCHOD! Group ID ya Naya Naam missing hai!"}), 400

    # Credentials aur session check kar
    if not INSTA_USERNAME or not INSTA_PASSWORD or not instagram_session_cookies:
        return jsonify({"status": "error", "message": "MADARCHOD! Instagram credentials ya session missing. Pehle login kar!"}), 401

    final_new_name = add_random_chutiyapa(new_name) # Random chutiyapa add kar
    logger.info(f"Attempting to change group {group_id} name to: '{final_new_name}'")
    
    with sync_playwright() as p:
        name_changed = change_group_name_playwright(group_id, final_new_name, p, instagram_session_cookies)

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
        for log in logs_collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(50): # Latest 50 logs
            logs.append(log)
        return jsonify({"status": "success", "logs": logs})
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to get logs: {e}")
        return jsonify({"status": "error", "message": f"Logs nikalne mein chutiyapa: {e}"}), 500

@app.route("/submit_challenge_response", methods=["POST"])
def submit_challenge_response_route():
    """OTP/CAPTCHA response handle karega."""
    data = request.json
    response_code = data.get("response_code") # OTP ya CAPTCHA answer
    
    if not response_code:
        return jsonify({"status": "error", "message": "OYE BSDK! Response code missing hai!"}), 400

    if not INSTA_USERNAME or not INSTA_PASSWORD or not instagram_session_cookies:
        return jsonify({"status": "error", "message": "MADARCHOD! Credentials ya session nahi. Pehle login kar!"}), 400

    global instagram_session_cookies
    try:
        with sync_playwright() as p:
            success, updated_cookies = submit_challenge_response_playwright(response_code, p, instagram_session_cookies)
            if success:
                instagram_session_cookies = updated_cookies # Update cookies after challenge
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