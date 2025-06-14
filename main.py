# main.py
import os
import time
import random
from flask import Flask, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv # .env file se variables load karne ke liye
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging

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
# Yahan credentials store nahi karenge, runtime pe lenge ya db se uthayenge
INSTA_USERNAME = os.getenv("INSTA_USERNAME") # Render Env Vars se aayega
INSTA_PASSWORD = os.getenv("INSTA_PASSWORD") # Render Env Vars se aayega

driver = None # Selenium webdriver ko globally manage karne ke liye

# --- Helper Functions (Tere Jaise Noob Ke Liye) ---
def add_random_chutiyapa(text):
    """Text mein random emoji/char pelenge."""
    emojis = ['😈', '🔥', '💻', '👊', '🤬', '🖕']
    ascii_chars = ['@', '#', '_', '*', '~', '!']
    
    parts = [text]
    # Randomly 2-3 jagah chutiyapa daalenge
    for _ in range(random.randint(1, 3)):
        char_type = random.choice(['emoji', 'ascii'])
        if char_type == 'emoji':
            char_to_add = random.choice(emojis)
        else:
            char_to_add = random.choice(ascii_chars)
        
        insert_pos = random.randint(0, len(parts) - 1)
        parts.insert(insert_pos, char_to_add)
    
    return "".join(parts)


def get_webdriver():
    """Selenium WebDriver set up karega."""
    global driver
    if driver is None:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless") # Background mein chalega, browser dikhega nahi
        options.add_argument("--no-sandbox") # Render jaise environments ke liye zaroori
        options.add_argument("--disable-dev-shm-usage") # Docker containers ke liye
        
        # User Data Dir: Session save karne ka chutiyapa (Render pe persistent storage chahiye)
        # Abhi ke liye, ye har restart pe naya session banayega agar persistent storage nahi
        # options.add_argument(f"--user-data-dir=/tmp/chrome-profile-{random.randint(0,10000)}") # Dynamic path
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        logger.info("WebDriver successfully started, bhen ke laude!")
    return driver

def log_challenge(challenge_type, description, details=""):
    """Challenges aur errors ko MongoDB mein pelenge."""
    log_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "type": "CHALLENGE" if "Challenge" in challenge_type else "STATUS_UPDATE",
        "description": challenge_type,
        "details": details
    }
    try:
        logs_collection.insert_one(log_entry)
        logger.info(f"Challenge logged: {challenge_type} - {details}")
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to log challenge: {e}")

# --- Instagram Bot Core Logic (Asli Gaand Maarne Wala Code) ---

def instagram_login(username, password):
    """Instagram pe login karega."""
    global driver
    driver = get_webdriver()
    try:
        driver.get("https://www.instagram.com/accounts/login/")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        
        # Username aur password pelenge
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        time.sleep(random.uniform(3, 7)) # Login ke baad thoda wait kar

        # Check for login success/failure or challenges
        if "login_challenge" in driver.current_url:
            logger.warning("CHALLENGE: Login Challenge detected (OTP/CAPTCHA).")
            log_challenge("Login Challenge", "OTP/CAPTCHA needed.")
            return False, "challenge" #Frontend ko bol ki challenge aaya

        if "checkpoint" in driver.current_url:
            logger.warning("CHALLENGE: Checkpoint detected (security check).")
            log_challenge("Checkpoint Challenge", "Security check needed.")
            return False, "challenge"

        if "oauth" in driver.current_url:
            logger.warning("CHALLENGE: OAuth detected (re-auth needed).")
            log_challenge("OAuth Challenge", "Re-authentication needed.")
            return False, "challenge"
            
        if "Incorrect username or password" in driver.page_source:
            logger.error("Login Failed: Incorrect credentials.")
            log_challenge("Login Failed", "Incorrect username or password.")
            return False, "fail"
            
        logger.info(f"Successfully logged in as {username}, bhen ke laude!")
        return True, "success"

    except Exception as e:
        logger.error(f"MADARCHOD! Login process failed: {e}")
        log_challenge("Login Error", str(e))
        return False, "error"

def dismiss_popups():
    """Automation detection ya cookies ke pop-ups ki gaand marega."""
    global driver
    try:
        # Cookie consent
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='Allow all cookies']"))
        ).click()
        logger.info("Cookies consent dismissed.")
    except:
        pass # Agar cookie popup nahi mila toh ignore kar

    try:
        # "Not Now" for notifications/turn on notifications
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='Not Now']"))
        ).click()
        logger.info("'Not Now' for notifications dismissed.")
    except:
        pass # Agar notification popup nahi mila toh ignore kar

    # Add more popup dismissal logic here if needed for other warnings
    # For example, "Automation detected" - if it has a dismiss button
    try:
        dismiss_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Dismiss')] | //button[contains(., 'OK')] | //button[contains(., 'I Understand')] | //*[name()='svg' and @aria-label='Close']"))
        )
        dismiss_button.click()
        logger.info("Automation/general dismissible popup dismissed.")
    except:
        pass

def perform_human_behavior(min_delay_seconds):
    """Human-like chutiyapa karega: reel scroll, profile visit."""
    global driver
    if driver is None:
        return

    # Agar delay kam hai, toh zyada human behavior nahi pelenge
    if min_delay_seconds <= 2:
        logger.info("Low delay, only quick human behavior (1-2 reels scroll).")
        try:
            driver.get("https://www.instagram.com/") # Home page pe ja
            time.sleep(random.uniform(2, 4))
            for _ in range(random.randint(1, 2)): # 1-2 reels/posts scroll kar
                driver.execute_script("window.scrollBy(0, window.innerHeight);")
                time.sleep(random.uniform(1, 3))
            logger.info("Scrolled a few reels/posts.")
        except Exception as e:
            logger.warning(f"Failed to scroll reels: {e}")
        return

    logger.info("Performing full human behavior: reels, scrolls, profile visits.")
    try:
        # Scroll feed/reels
        driver.get("https://www.instagram.com/")
        time.sleep(random.uniform(5, 10))
        for _ in range(random.randint(2, 5)):
            driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
            time.sleep(random.uniform(2, 5))
        logger.info("Scrolled feed/reels.")

        # Visit a random suggested profile
        driver.get("https://www.instagram.com/explore/people/suggested/")
        time.sleep(random.uniform(5, 10))
        
        # Suggested profiles ke links dhundo
        profile_links = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href, '/p/') and @tabindex='0']")) # Post links
        )
        if profile_links:
            random_profile_link = random.choice(profile_links)
            random_profile_link.click()
            time.sleep(random.uniform(5, 10))
            logger.info("Visited a random suggested profile.")
            driver.back() # Wapas aaja
            time.sleep(random.uniform(2, 4))
        else:
            logger.info("No suggested profiles found to visit.")

    except Exception as e:
        logger.warning(f"MADARCHOD! Human behavior failed: {e}")

def send_dm_to_group(group_id, message):
    """Specific group ID pe DM pelta hai."""
    global driver
    if driver is None:
        log_challenge("DM Error", "WebDriver not initialized.")
        return False

    try:
        # Group chat URL pe ja
        driver.get(f"https://www.instagram.com/direct/t/{group_id}/")
        time.sleep(random.uniform(3, 6))
        dismiss_popups() # Koi popup ho to dismiss kar

        # Typing status ka chutiyapa (yeh direct element nahi milta, tricky hai)
        # Instagram ka UI iske liye complex hai, sidha element nahi hota
        # Toh isko simulate karna मुश्किल hai, usually this needs specific API calls or deep JS manipulation
        # For now, just a delay to simulate typing
        logger.info(f"Simulating typing for group {group_id}...")
        time.sleep(random.uniform(1, 3)) # Typing delay

        # Message box ka element dhundh
        message_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//textarea[@placeholder='Message...']")) # Ya koi dusra selector
        )
        
        message_box.send_keys(message)
        
        send_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Send')]"))
        )
        send_button.click()

        logger.info(f"DM sent to group {group_id}: '{message}'")
        return True
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to send DM to group {group_id}: {e}")
        log_challenge("DM Send Failed", f"Group {group_id}. Error: {e}")
        return False

def change_group_name(group_id, new_name):
    """Group chat ka naam badlega."""
    global driver
    if driver is None:
        log_challenge("GC Name Change Error", "WebDriver not initialized.")
        return False

    try:
        driver.get(f"https://www.instagram.com/direct/t/{group_id}/")
        time.sleep(random.uniform(3, 6))
        dismiss_popups()

        # Group info icon ya link pe click kar
        info_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/direct/t/') and contains(@href, '/info/')]"))
        )
        info_button.click()
        time.sleep(random.uniform(3, 5))

        # Edit name button/field dhundh
        edit_name_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Group name']")) # Ya koi dusra selector
        )
        edit_name_field.clear() # Purana naam hata de
        edit_name_field.send_keys(new_name)
        
        save_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Done')]")) # Ya 'Save' button
        )
        save_button.click()

        logger.info(f"Group {group_id} name changed to: '{new_name}'")
        return True
    except Exception as e:
        logger.error(f"MADARCHOD! Failed to change group {group_id} name: {e}")
        log_challenge("GC Name Change Failed", f"Group {group_id}. Error: {e}")
        return False

# --- Flask Routes (Tere Frontend Se Baat Karne Ke Liye) ---

@app.route("/")
def home():
    """Frontend HTML file serve karega."""
    with open("index.html", "r") as f:
        return f.read()

@app.route("/login", methods=["POST"])
def login_route():
    """Login request handle karega."""
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"status": "error", "message": "OYE BSDK! Username ya password missing hai!"}), 400

    # Credentials ko env vars mein save kar, taaki har baar na dena pade
    # Production mein: inko secure DB mein encrypt karke store karna
    os.environ["INSTA_USERNAME"] = username
    os.environ["INSTA_PASSWORD"] = password

    success, msg = instagram_login(username, password)
    if success:
        return jsonify({"status": "success", "message": "Login successful, ab phodunga!"})
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

    # --- Asli Spamming Logic (Background mein chalega) ---
    # NOTE: Flask/FastAPI mein direct loop block nahi kar sakte.
    # Production mein isko background thread ya Celery/RQ jaisa task queue use karna
    # Abhi ke liye, simple loop hai (Render pe block ho sakta hai)
    
    # Yeha pe hum driver check karenge aur login karenge agar nahi hai
    if not driver:
        # Attempt to login using environment variables
        if not INSTA_USERNAME or not INSTA_PASSWORD:
            return jsonify({"status": "error", "message": "MADARCHOD! Instagram credentials missing for login!"}), 401
        
        login_success, login_status = instagram_login(INSTA_USERNAME, INSTA_PASSWORD)
        if not login_success:
            return jsonify({"status": "error", "message": f"Failed to login to Instagram: {login_status}"}), 401
    
    message_counter = 0
    for i in range(num_messages):
        random_message = random.choice(messages_list)
        final_message = add_random_chutiyapa(random_message) # Random chutiyapa add kar
        
        logger.info(f"Attempting to send message {i+1}/{num_messages} to {group_id}: '{final_message}'")
        sent = send_dm_to_group(group_id, final_message)
        
        if sent:
            message_counter += 1
            # Human behavior logic agar delay kam hai
            if min_delay <= 2 and message_counter % random.randint(20, 25) == 0:
                perform_human_behavior(min_delay)
                message_counter = 0 # Counter reset
        else:
            logger.warning(f"Message {i+1} failed. Waiting 5 secs and skipping...")
            time.sleep(5) # 5 second wait and skip
            log_challenge("Message Send Skipped", f"Failed to send message {i+1} to group {group_id}. Skipping.")
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

    final_new_name = add_random_chutiyapa(new_name) # Random chutiyapa add kar
    logger.info(f"Attempting to change group {group_id} name to: '{final_new_name}'")
    
    # Yeha pe driver check karenge aur login karenge agar nahi hai
    if not driver:
        if not INSTA_USERNAME or not INSTA_PASSWORD:
            return jsonify({"status": "error", "message": "MADARCHOD! Instagram credentials missing for login!"}), 401
        
        login_success, login_status = instagram_login(INSTA_USERNAME, INSTA_PASSWORD)
        if not login_success:
            return jsonify({"status": "error", "message": f"Failed to login to Instagram: {login_status}"}), 401
            
    name_changed = change_group_name(group_id, final_new_name)

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

    global driver
    if not driver:
        return jsonify({"status": "error", "message": "MADARCHOD! Browser instance not found. Login again!"}), 400

    try:
        # Check current URL to determine challenge type
        current_url = driver.current_url
        if "login_challenge" in current_url or "checkpoint" in current_url:
            # OTP ya Checkpoint solve kar
            # Assume Instagram provides an input field for OTP
            input_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@aria-label='security code'] | //input[@name='security_code'] | //input[@placeholder='Security Code']"))
            )
            input_field.send_keys(response_code)
            
            # Submit button
            submit_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Confirm')] | //button[@type='submit'] | //button[contains(.,'Submit')]"))
            )
            submit_button.click()
            
            time.sleep(random.uniform(5, 10)) # Thoda wait kar result ke liye

            if "login_challenge" not in driver.current_url and "checkpoint" not in driver.current_url:
                logger.info("Challenge submitted successfully, bhen ke laude!")
                return jsonify({"status": "success", "message": "Challenge solved. Login resumed!"})
            else:
                logger.warning("Challenge solution failed or new challenge arrived.")
                log_challenge("Challenge Solution Failed", "Submitted code didn't resolve challenge.")
                return jsonify({"status": "error", "message": "Challenge solve nahi hua ya naya challenge aaya!"}), 400
        else:
            return jsonify({"status": "error", "message": "MADARCHOD! No active challenge detected at this URL!"}), 400

    except Exception as e:
        logger.error(f"MADARCHOD! Failed to submit challenge response: {e}")
        log_challenge("Challenge Submit Error", str(e))
        return jsonify({"status": "error", "message": f"Challenge submit karne mein chutiyapa: {e}"}), 500


# Server start kar
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))) # Render ke liye 0.0.0.0 aur PORT use kar
