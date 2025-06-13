# app.py - Teri maa ka laal, ab yeh final hai, koi chutiyapa nahi

import os
import time
import json
from threading import Thread

# Third-party libraries
from flask import Flask, request, jsonify, send_from_directory
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired, TwoFactorRequired, BadPassword, UserNotFound

app = Flask(__name__, static_folder='static', static_url_path='')

# --- Instagrapi Client aur Login Logic ---
cl = Client()
SESSION_FILE = "session.json" # Session file ka naam, yaad rakhna bsdk

# Environment variables se credentials utha
# Agar nahi mile toh teri gaand mein tel daal ke maarunga
USERNAME = os.environ.get("IG_USER")
PASSWORD = os.environ.get("IG_PASS")

# --- Global flags for auto-reply state ---
auto_reply_running = False
auto_reply_thread = None

# --- Helper function for logging (thoda tameez se, par still NOBI BOT style) ---
def log_message(msg, level="INFO"):
    # Current time is Saturday, June 14, 2025 at 1:09:42 AM IST.
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} IST] [{level}] NOBI BOT: {msg}")

def login_user():
    """Bhenchod, login kar pehle, ya session utha."""
    global auto_reply_running
    try:
        if os.path.exists(SESSION_FILE):
            try:
                cl.load_settings(SESSION_FILE)
                log_message("Trying to log in with existing session...", "INFO")
                cl.login(USERNAME, PASSWORD) # Session load hone ke baad bhi login try karna zaroori hai
                log_message("Session se login ho gaya. OYE MADARCHOD!", "INFO")
                return True
            except (LoginRequired, ChallengeRequired, BadPassword, UserNotFound):
                log_message("Existing session expired/invalid or credentials wrong. Naya login required BC.", "WARNING")
                # Agar publicly session rakhna hai, toh yahan remove mat karna, but clean up
                if os.path.exists(SESSION_FILE):
                    os.remove(SESSION_FILE)
                return login_fresh()
            except Exception as e:
                log_message(f"Login with existing session mein chutiyapa ho gaya: {e}", "ERROR")
                if os.path.exists(SESSION_FILE):
                    os.remove(SESSION_FILE) # Clean up faulty session file
                return login_fresh()
        else:
            log_message("Session file nahi mila, naya banayega BC.", "INFO")
            return login_fresh()

    except Exception as e:
        log_message(f"Login_user() mein unhandled chutiyapa ho gaya: {e}", "CRITICAL")
        auto_reply_running = False # Critical error, stop auto-reply
        return False

def login_fresh():
    """Naya login, agar pehla wala chutiya nikla."""
    global auto_reply_running
    try:
        # OTP ya challenge agar aaye toh ye handle nahi karega automatically for Render
        # Isliye, Colab se session nikalna hi best hai
        cl.login(USERNAME, PASSWORD)
        cl.dump_settings(SESSION_FILE) # Naya session file banayega agar nahi hai ya login fresh hua
        log_message("Fresh login success! Bhen ke laude, ab chalega.", "INFO")
        return True
    except ChallengeRequired:
        log_message("Challenge required BC! Jaake browser/Colab se solve kar. Server pe ye nahi hoga.", "ERROR")
        auto_reply_running = False # Cannot proceed without challenge solved
        return False
    except TwoFactorRequired:
        log_message("Two-factor authentication required! Teri maa ki chut, OTP dalwa BC! Server pe ye nahi hoga.", "ERROR")
        auto_reply_running = False # Cannot proceed without 2FA
        return False
    except (BadPassword, UserNotFound):
        log_message("Wrong username or password, madarchod! Credentials check kar.", "CRITICAL")
        auto_reply_running = False
        return False
    except Exception as e:
        log_message(f"Madarchod, fresh login bhi fail ho gaya: {e}", "CRITICAL")
        auto_reply_running = False
        return False

# --- Auto-Reply Logic ---
def auto_reply_worker():
    """Ye worker teri maa ki aankh, auto-reply chalayega."""
    global auto_reply_running
    
    # Ye block login ko loop ke bahar rakha hai
    # Agar login hi fail ho gaya, toh thread chalega hi nahi
    if not login_user():
        log_message("Initial login failed. Auto-reply cannot start, jaa ke muth maar bc.", "ERROR")
        auto_reply_running = False
        return

    log_message("Auto-reply shuru kar raha hoon, gaand marao sab.", "INFO")
    
    # Main loop for checking DMs
    while auto_reply_running:
        try:
            log_message("Checking for new DMs... 😈", "INFO")
            
            threads = cl.direct_threads(limit=10) # Last 10 threads check kar
            log_message(f"Fetched {len(threads)} direct threads.", "DEBUG")

            if not threads:
                log_message("No threads found or failed to fetch threads (API response empty).", "INFO")

            for thread in threads:
                thread_id = thread.get('thread_id')
                messages = thread.get('items', [])
                
                if messages:
                    last_message_obj = messages[0] # Instagrapi gives a Dict for raw API messages
                    
                    # Check if the last message is from someone else, not self
                    sender_pk = str(last_message_obj.get('user_id')) # Sender's primary key (user ID)
                    current_user_pk = str(cl.user_id) # Current logged-in user's primary key
                    
                    # Ensure it's not a message sent by the bot itself or if it's already processed/seen
                    if sender_pk != current_user_pk:
                        last_message_text = last_message_obj.get('text', '')
                        sender_username = thread.get('users', [{}])[0].get('username', 'Unknown')
                        
                        log_message(f"Processing message from {sender_username} (ID: {sender_pk}): '{last_message_text}'", "DEBUG")
                        
                        # Instagrapi's direct_threads() usually marks messages as seen.
                        # To avoid spamming replies to already processed messages,
                        # we need a better check or a simple database to store replied message IDs.
                        # For now, we will simply reply if the message is from another user.
                        # This can lead to repeat replies if the message isn't truly "unseen" and new.

                        # A very basic check: If the message text is not empty and not from me
                        if last_message_text: # Ensure message is not empty
                            reply_text = f"OYE {sender_username}, Teri maa ki chut, main NOBI BOT hoon. Tune '{last_message_text}' likha. Reply mat karna warna gaand maar lunga! 🔥"
                            
                            # Send message
                            try:
                                cl.direct_send(reply_text, thread_ids=[thread_id])
                                log_message(f"Replied to '{sender_username}' in thread {thread_id}.", "INFO")
                                
                                # Mark message as seen after replying to avoid re-replying on next loop
                                cl.direct_thread_mark_as_seen(thread_id)
                                log_message(f"Thread {thread_id} marked as seen.", "INFO")

                            except Exception as e:
                                log_message(f"Error sending reply or marking seen to {sender_username} in thread {thread_id}: {e}", "ERROR")
                        else:
                            log_message(f"Skipping empty message from {sender_username}.", "DEBUG")
                    else:
                        log_message(f"Skipping message from self ({sender_username}) in thread {thread_id}.", "DEBUG")
                else:
                    log_message(f"No new items/messages in thread {thread_id}.", "DEBUG")
            
            time.sleep(30) # Har 30 second mein check kar, bhenchod, spam mat karna
        except Exception as e:
            log_message(f"Auto-reply loop mein chutiyapa ho gaya: {e}", "ERROR")
            # If a critical error in the loop, we might want to try re-login or stop
            if "User not logged in" in str(e) or "LoginRequired" in str(e):
                log_message("Login required in loop, trying to re-login...", "WARNING")
                if not login_user(): # Try to re-login if session expired in loop
                    log_message("Re-login failed. Stopping auto-reply thread.", "CRITICAL")
                    auto_reply_running = False
            time.sleep(60) # Error pe thoda ruk ja, warna IP ban ho jayega

    log_message("Auto-reply band ho gaya, jaa ke muth maar bc.", "INFO")

# --- Flask API Endpoints ---
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
            log_message("Auto-reply ON, teri maa ki chut!", "INFO")
            return jsonify({"status": "Auto-reply ON, teri maa ki chut!"}), 200
        else:
            log_message("Already ON, kitni baar ON karega bhenchod?", "WARNING")
            return jsonify({"status": "Already ON, kitni baar ON karega bhenchod?"}), 400
    elif action == "off":
        if auto_reply_running:
            auto_reply_running = False
            log_message("Auto-reply OFF, jaa ke hilale bc.", "INFO")
            return jsonify({"status": "Auto-reply OFF, jaa ke hilale bc."}), 200
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
    log_message(f"NOBI BOT server starting on port {port}...", "INFO")
    app.run(host="0.0.0.0", port=port, debug=False)