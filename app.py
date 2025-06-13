# app.py - Teri maa ka laal, sab kuch ek hi file mein aur ab ready to run

import os
import time
import json
from threading import Thread

# Third-party libraries
from flask import Flask, request, jsonify, send_from_directory
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired, TwoFactorRequired

app = Flask(__name__, static_folder='static', static_url_path='') # Static files ke liye folder 'static'

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
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] NOBI BOT: {msg}")

def login_user():
    """Bhenchod, login kar pehle, ya session utha."""
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(USERNAME, PASSWORD) # Session load hone ke baad bhi login try karna zaroori hai
            log_message("Session se login ho gaya. OYE MADARCHOD!")
            return True
        except LoginRequired:
            log_message("Session expired, new login required BC.", "WARNING")
            #os.remove(SESSION_FILE) # Agar publicly session rakhna hai, toh yahan remove mat karna
            return login_fresh()
        except ChallengeRequired:
            log_message("Challenge required BC! Jaake browser se solve kar ya code mein add kar isko.", "ERROR")
            # Agar challenge aaye toh, isko proper handle karna padega, user input chahiye hoga
            return False
        except TwoFactorRequired:
            log_message("Two-factor authentication required! Teri maa ki chut, OTP dalwa BC!", "ERROR")
            # 2FA aaye toh, isko proper handle karna padega
            return False
        except Exception as e:
            log_message(f"Login mein chutiyapa ho gaya with session: {e}", "ERROR")
            return login_fresh()
    else:
        log_message("Session file nahi mila, naya banayega BC.", "INFO")
        return login_fresh()

def login_fresh():
    """Naya login, agar pehla wala chutiya nikla."""
    try:
        cl.login(USERNAME, PASSWORD)
        cl.dump_settings(SESSION_FILE) # Naya session file banayega agar nahi hai ya login fresh hua
        log_message("Fresh login success! Bhen ke laude, ab chalega.", "INFO")
        return True
    except Exception as e:
        log_message(f"Madarchod, fresh login bhi fail ho gaya: {e}", "ERROR")
        return False

# --- Auto-Reply Logic ---
def auto_reply_worker():
    """Ye worker teri maa ki aankh, auto-reply chalayega."""
    global auto_reply_running
    
    if not login_user():
        log_message("Login nahi hua, jaa ke muth maar bc. Auto-reply start nahi hoga.", "ERROR")
        auto_reply_running = False # Agar login fail toh worker ko band kar de
        return

    log_message("Auto-reply shuru kar raha hoon, gaand marao sab.", "INFO")
    
    while auto_reply_running:
        try:
            log_message("Checking for new DMs... 😈", "INFO")
            
            # Fetch direct message threads
            threads = cl.direct_threads(limit=10) # Last 10 threads check kar

            for thread in threads:
                # Agar thread mein messages hain aur latest message user ne nahi bheja (matlab received hai)
                if thread.messages and not thread.messages[0].is_sent_by_viewer:
                    last_message_obj = thread.messages[0]
                    last_message_text = last_message_obj.text
                    sender_username = thread.users[0].username if thread.users else "Unknown"

                    log_message(f"Naya message mila '{last_message_text}' from {sender_username}", "INFO")
                    
                    # Agar thread unread hai (ya tune manually mark as unread rakha hai) toh reply kar
                    # Note: Instagrapi automatically marks as seen when fetching, so you might need to adjust logic
                    # A better way is to store replied message IDs to avoid duplicate replies
                    
                    # For simplicity, if not (last_message_obj.is_seen or last_message_obj.has_replied)
                    # For now, we will reply if it's new message and mark as seen later
                    
                    # Prevent replying to old messages repeatedly by checking timestamp
                    # Or better: Maintain a list of processed message_ids (requires a simple DB or in-memory set)
                    # For this simple example, we'll just check if it's "recent" (e.g., in last 5 minutes)
                    
                    # This is a very basic check. For production, store processed message IDs in a DB.
                    # Current example will reply to every unread message from the last 10 threads on each loop.
                    
                    # To avoid spamming, we need a better check. Let's assume we reply if NOT seen by self.
                    if not last_message_obj.is_seen_by_viewer: # This check is more reliable for new messages
                        reply_text = f"OYE {sender_username}, Teri maa ki chut, main NOBI BOT hoon. Tune '{last_message_text}' likha. Reply mat karna warna gaand maar lunga! 🔥"
                        cl.direct_send(reply_text, thread_ids=[thread.id])
                        cl.direct_thread_mark_as_seen(thread.id) # Message seen mark kar de
                        log_message(f"Reply kar diya '{sender_username}' ko.", "INFO")
                    else:
                        log_message(f"Message from {sender_username} already seen, skipping reply.", "INFO")
                        
            time.sleep(30) # Har 30 second mein check kar, bhenchod, spam mat karna
        except Exception as e:
            log_message(f"Auto-reply loop mein chutiyapa ho gaya: {e}", "ERROR")
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
            # thread.join() yahan lagane se server block ho jayega jab tak thread band na ho
            # isliye, bas flag set kar diya hai. Worker loop khud break ho jayega.
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
    # Yeha Render ke liye entry point hai.
    # Render automatically PORT environment variable deta hai.
    port = int(os.environ.get("PORT", 5000))
    log_message(f"NOBI BOT server starting on port {port}...", "INFO")
    app.run(host="0.0.0.0", port=port, debug=False) # Debug mode production mein OFF rakhna