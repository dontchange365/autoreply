# app.py - Teri maa ka laal, ab direct API se gaand marega

import os
import time
import json
from threading import Thread
import requests # Nayi library, seedha HTTP requests pelne ke liye

from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='static', static_url_path='')

# --- Environment Variables ---
# Apne Instagram credentials yahan bhi honge, bhen ke laude
USERNAME = os.environ.get("IG_USER")
PASSWORD = os.environ.get("IG_PASS")

# --- Global flags for auto-reply state ---
auto_reply_running = False
auto_reply_thread = None

# --- Helper function for logging ---
def log_message(msg, level="INFO"):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] NOBI BOT: {msg}")

# --- Instagram Session aur Request Logic ---
# Isme session manage karna instagrapi jitna easy nahi hai.
# Hame manually cookies aur CSRF token ko store aur reuse karna hoga.
# Abhi ke liye, ye simple hai, real complex login instagrapi hi handle karta hai.

# Basic placeholder for session data.
# Ideally, this should be loaded from a file or secure storage.
insta_session = {
    "cookies": {},
    "csrf_token": "",
    "user_id": ""
}

# --- Login Function (Very Basic, Will likely fail often without proper Instagrapi handling) ---
def raw_login():
    """Seedha Instagram API se login karne ki koshish, gaand phat sakti hai."""
    global insta_session
    login_url = "https://i.instagram.com/api/v1/accounts/login/"
    headers = {
        "User-Agent": "Instagram 275.0.0.21.98 Android (31/12; 640dpi; 1440x2960; OnePlus; KB2005; KB2005; qcom; en_US; 475283921)", # Mobile User-Agent
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-IG-Capabilities": "3brDAA==",
        "X-IG-App-ID": "936619733923554", # Specific Instagram App ID
        "X-CSRFToken": "missing", # Isko initial request se nikalna padega
        "X-Instagram-AJAX": "1"
    }
    data = {
        "username": USERNAME,
        "password": PASSWORD,
        "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{PASSWORD}", # Encrypted password format
        "device_id": "android-{}".format(os.urandom(16).hex()), # Random device ID
        "from_reg": "false",
        "_csrftoken": "missing", # Isko bhi nikalna padega
        "login_attempt_count": "0"
    }

    # First, get a CSRF token from a visit to the main page
    try:
        # A simple GET request to get initial cookies and CSRF
        res = requests.get("https://www.instagram.com/", headers={"User-Agent": headers["User-Agent"]})
        initial_cookies = res.cookies
        csrf_token = initial_cookies.get('csrftoken', 'missing')
        log_message(f"Initial CSRF Token: {csrf_token}", "DEBUG")

        headers["X-CSRFToken"] = csrf_token
        data["_csrftoken"] = csrf_token

        # Now, attempt login
        response = requests.post(login_url, headers=headers, data=data, cookies=initial_cookies)
        response.raise_for_status()
        login_data = response.json()
        
        if login_data.get("logged_in_user"):
            log_message("Raw Login successful! Bhen ke laude.", "INFO")
            insta_session["cookies"] = response.cookies.get_dict()
            insta_session["csrf_token"] = response.cookies.get('csrftoken', '')
            insta_session["user_id"] = login_data["logged_in_user"]["pk"]
            log_message(f"User ID: {insta_session['user_id']}", "INFO")
            log_message(f"Session Cookies: {insta_session['cookies']}", "DEBUG")
            return True
        else:
            log_message(f"Raw Login failed: {login_data.get('message', 'Unknown error')}", "ERROR")
            return False

    except requests.exceptions.RequestException as e:
        log_message(f"Raw Login Request failed: {e}", "ERROR")
        return False
    except Exception as e:
        log_message(f"Raw Login other error: {e}", "ERROR")
        return False

# --- Send Message Function (Using Raw API) ---
def send_direct_message(thread_id, message_text):
    """Seedha Instagram DM API ko message pel dega."""
    if not insta_session["cookies"] or not insta_session["csrf_token"] or not insta_session["user_id"]:
        log_message("Session data missing for sending message. Login first, madarchod!", "ERROR")
        return False

    send_url = "https://i.instagram.com/api/v1/direct_v2/threads/broadcast/text/"
    
    headers = {
        "User-Agent": "Instagram 275.0.0.21.98 Android (31/12; 640dpi; 1440x2960; OnePlus; KB2005; KB2005; qcom; en_US; 475283921)",
        "Accept-Language": "en-US,en;q=0.9",
        "X-IG-Capabilities": "3brDAA==",
        "X-IG-App-ID": "936619733923554",
        "X-CSRFToken": insta_session["csrf_token"],
        "X-Instagram-AJAX": "1",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://www.instagram.com/" # Important for some requests
    }

    # Request payload
    data = {
        "action": "send_message",
        "is_reshare": "false",
        "send_media_a_copy": "0",
        "send_attribution": "direct_inbox",
        "recipient_users": f'[["{thread_id}"]]' if thread_id else "", # This is for new thread, but for existing thread_id, use thread_id
        "thread_ids": f"[{thread_id}]", # Specific thread ID
        "client_context": f"android-{os.urandom(16).hex()}", # Random client context
        "text": message_text,
        "offline_threading_id": f"{int(time.time() * 1000)}_{os.urandom(8).hex()}"
    }

    try:
        response = requests.post(send_url, headers=headers, data=data, cookies=insta_session["cookies"])
        response.raise_for_status() # HTTP errors ke liye raise karega
        send_data = response.json()
        
        if send_data.get("status") == "ok":
            log_message(f"Message sent successfully to thread {thread_id}.", "INFO")
            return True
        else:
            log_message(f"Failed to send message to thread {thread_id}: {send_data.get('message', 'Unknown error')}", "ERROR")
            return False

    except requests.exceptions.RequestException as e:
        log_message(f"Error sending message to thread {thread_id}: {e}", "ERROR")
        return False
    except Exception as e:
        log_message(f"Unexpected error sending message: {e}", "ERROR")
        return False

# --- Fetch Messages Function (Using Raw API) ---
# This is crucial but complex without instagrapi.
# Fetching direct inbox threads. This needs proper pagination and parsing.
# This simple version fetches the 'inbox' which is less direct than 'direct_v2/threads/'.
def fetch_direct_threads():
    """Seedha Instagram inbox threads fetch karega."""
    if not insta_session["cookies"] or not insta_session["csrf_token"] or not insta_session["user_id"]:
        log_message("Session data missing for fetching threads. Login first, madarchod!", "ERROR")
        return []

    inbox_url = "https://i.instagram.com/api/v1/direct_v2/inbox/"
    
    headers = {
        "User-Agent": "Instagram 275.0.0.21.98 Android (31/12; 640dpi; 1440x2960; OnePlus; KB2005; KB2005; qcom; en_US; 475283921)",
        "Accept-Language": "en-US,en;q=0.9",
        "X-IG-Capabilities": "3brDAA==",
        "X-IG-App-ID": "936619733923554",
        "X-CSRFToken": insta_session["csrf_token"],
        "X-Instagram-AJAX": "1",
        "Referer": "https://www.instagram.com/"
    }

    try:
        response = requests.get(inbox_url, headers=headers, cookies=insta_session["cookies"])
        response.raise_for_status()
        inbox_data = response.json()
        
        if inbox_data.get("status") == "ok":
            log_message("Fetched direct inbox successfully.", "INFO")
            return inbox_data.get("inbox", {}).get("threads", [])
        else:
            log_message(f"Failed to fetch inbox: {inbox_data.get('message', 'Unknown error')}", "ERROR")
            return []
    except requests.exceptions.RequestException as e:
        log_message(f"Error fetching inbox: {e}", "ERROR")
        return []
    except Exception as e:
        log_message(f"Unexpected error fetching inbox: {e}", "ERROR")
        return []


# --- Auto-Reply Logic ---
def auto_reply_worker():
    """Ye worker teri maa ki aankh, raw API se auto-reply chalayega."""
    global auto_reply_running
    
    if not raw_login(): # Login kar pehle, bhen ke laude
        log_message("Raw API Login fail hua. Auto-reply start nahi hoga.", "ERROR")
        auto_reply_running = False
        return

    log_message("Auto-reply shuru kar raha hoon, raw API se gaand marao sab.", "INFO")
    
    while auto_reply_running:
        try:
            log_message("Checking for new DMs using raw API... 😈", "INFO")
            
            threads = fetch_direct_threads() # Raw API se threads fetch kar
            
            if not threads:
                log_message("No threads found or failed to fetch threads.", "INFO")
            
            for thread in threads:
                thread_id = thread.get('thread_id')
                # Messages list mein hote hain, latest message pehle hota hai
                messages = thread.get('items', [])
                
                if messages:
                    last_message = messages[0]
                    
                    # Check if the last message is from someone else, not self
                    # 'user_id' is the sender's user ID
                    sender_user_id = last_message.get('user_id')
                    
                    # Instagram's own user ID is stored in insta_session['user_id']
                    if sender_user_id and str(sender_user_id) != str(insta_session['user_id']):
                        last_message_text = last_message.get('text')
                        sender_username = thread.get('users', [{}])[0].get('username', 'Unknown')
                        
                        log_message(f"Processing message from {sender_username} (ID: {sender_user_id}): '{last_message_text}'", "DEBUG")
                        
                        # A simple check to avoid replying repeatedly to the same message
                        # For proper handling, you need to store processed message IDs in a DB
                        # For now, let's assume if it's new and not from us, reply.
                        # This is VERY basic and prone to spamming if not managed.
                        
                        # To truly check "unseen", this gets complex with raw API.
                        # Instagrapi handles this better. For now, we will reply if not from us.
                        # This will reply to every message it finds from others.
                        
                        # IMPORTANT: Mark as seen logic (very important to prevent re-reply)
                        # This is NOT direct in raw API like instagrapi's direct_thread_mark_as_seen
                        # It typically happens when you view the thread or inbox.
                        # For this raw code, we might just reply and hope for the best, or implement a more robust seen mechanism.
                        
                        # For simplicity, if it's from another user, send reply
                        reply_text = f"OYE {sender_username}, Teri maa ki chut, main NOBI BOT hoon. Tune '{last_message_text}' likha. Reply mat karna warna gaand maar lunga! 🔥"
                        send_direct_message(thread_id, reply_text)
                        log_message(f"Replied to '{sender_username}' using raw API.", "INFO")
                    else:
                        log_message(f"Skipping message (from self or no text) in thread {thread_id}.", "DEBUG")
                else:
                    log_message(f"No messages found in thread {thread_id}.", "DEBUG")
            
            time.sleep(30) # Har 30 second mein check kar
        except Exception as e:
            log_message(f"Auto-reply loop mein chutiyapa ho gaya: {e}", "ERROR")
            time.sleep(60)

    log_message("Auto-reply band ho gaya, raw API mode.", "INFO")


# --- Flask API Endpoints (Same as before) ---
@app.route("/")
def serve_index():
    """Default route to serve the frontend HTML."""
    return send_from_directory(app.static_folder, 'index.html')

@app.route("/control", methods=["POST"])
def control_auto_reply_api():
    """Frontend se control ka randikhana."""
    global auto_reply_thread, auto_reply_running
    action = request.json.get("action")

    if action == "on":
        if not auto_reply_running:
            auto_reply_running = True
            auto_reply_thread = Thread(target=auto_reply_worker)
            auto_reply_thread.start()
            log_message("Auto-reply ON (Raw API Mode), teri maa ki chut!", "INFO")
            return jsonify({"status": "Auto-reply ON (Raw API Mode), teri maa ki chut!"}), 200
        else:
            log_message("Already ON, kitni baar ON karega bhenchod?", "WARNING")
            return jsonify({"status": "Already ON, kitni baar ON karega bhenchod?"}), 400
    elif action == "off":
        if auto_reply_running:
            auto_reply_running = False
            log_message("Auto-reply OFF (Raw API Mode), jaa ke hilale bc.", "INFO")
            return jsonify({"status": "Auto-reply OFF (Raw API Mode), jaa ke hilale bc."}), 200
        else:
            log_message("Already OFF, aur kitna OFF karega madarchod?", "WARNING")
            return jsonify({"status": "Already OFF, aur kitna OFF karega madarchod?"}), 400
    else:
        log_message("Invalid action, gandu kahin ka.", "ERROR")
        return jsonify({"status": "Invalid action, gandu kahin ka."}), 400

@app.route("/status", methods=["GET"])
def get_status():
    """Status dekh, bhen ke laude."""
    current_status = "running" if auto_reply_running else "stopped"
    log_message(f"Current status requested: {current_status}", "INFO")
    return jsonify({"status": current_status}), 200

# --- Main Entry Point for Render ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    log_message(f"NOBI BOT Raw API server starting on port {port}...", "INFO")
    app.run(host="0.0.0.0", port=port, debug=False)