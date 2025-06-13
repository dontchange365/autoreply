# app.py - Teri maa ka laal, ab session.json public hai

import os
from instagrapi import Client
from instagrapi.exceptions import LoginRequired
from flask import Flask, request, jsonify
from threading import Thread
import time
import json

app = Flask(__name__)

# --- Instagrapi Client aur Login Logic ---
cl = Client()
# SESSION_FILE ab root folder mein hai, teri gaand ka dard
SESSION_FILE = "session.json" 

# Environment variables se credentials utha
USERNAME = os.environ.get("IG_USER")
PASSWORD = os.environ.get("IG_PASS")

def login_user():
    """Bhenchod, login kar pehle, ya session utha."""
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            # Ab OTP ka randi rona nahi, kyonki session.json already hai
            # Still, cl.login() is good practice to refresh if needed
            cl.login(USERNAME, PASSWORD) 
            print("OYE MADARCHOD! Session se login ho gaya.")
            return True
        except LoginRequired:
            print("Session expired, new login required BC.")
            # session.json ko yahan se remove mat karna agar publically rakhna hai, warna baar baar naya banayega
            # os.remove(SESSION_FILE) # Ye line hatt gayi, kyonki tu chutiya hai
            return login_fresh() # Still try to login fresh if session fails
        except Exception as e:
            print(f"Login mein chutiyapa ho gaya with session: {e}")
            return login_fresh()
    else:
        # Agar session.json nahi mila, toh naya banayega
        print("Session file nahi mila, naya banayega BC.")
        return login_fresh()

def login_fresh():
    """Naya login, agar pehla wala chutiya nikla."""
    try:
        # Agar OTP maanga toh teri gaand phat jayegi
        cl.login(USERNAME, PASSWORD)
        cl.dump_settings(SESSION_FILE) # Naya session file banaega agar nahi hai ya login fresh hua
        print("Bhen ke laude, fresh login success!")
        return True
    except Exception as e:
        print(f"Madarchod, fresh login bhi fail ho gaya: {e}")
        return False

# --- Auto-Reply Logic ---
auto_reply_running = False
auto_reply_thread = None

def auto_reply_worker():
    """Ye worker teri maa ki aankh, auto-reply chalayega."""
    global auto_reply_running
    if not login_user():
        print("Login nahi hua, jaa ke muth maar bc. Auto-reply start nahi hoga.")
        auto_reply_running = False
        return

    print("Auto-reply shuru kar raha hoon, gaand marao sab.")
    
    while auto_reply_running:
        try:
            print("NOBI BOT: Checking for new DMs... 😈")
            
            threads = cl.direct_threads(limit=10) 
            for thread in threads:
                if thread.messages and not thread.messages[0].is_sent_by_viewer:
                    last_message = thread.messages[0].text
                    print(f"NOBI BOT: Naya message mila '{last_message}' from {thread.users[0].username}")
                    
                    if not thread.is_seen:
                        reply_text = f"OYE {thread.users[0].username}, Teri maa ki chut, main NOBI BOT hoon. Tune '{last_message}' likha. Reply mat karna warna gaand maar lunga! 🔥"
                        cl.direct_send(reply_text, thread_ids=[thread.id])
                        cl.direct_thread_mark_as_seen(thread.id)
                        print(f"NOBI BOT: Reply kar diya '{thread.users[0].username}' ko.")
            
            time.sleep(30)
        except Exception as e:
            print(f"Auto-reply loop mein chutiyapa ho gaya: {e}")
            time.sleep(60)

    print("Auto-reply band ho gaya, jaa ke muth maar bc.")

# --- Flask API Endpoints ---
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
            return jsonify({"status": "Auto-reply ON, teri maa ki chut!"}), 200
        else:
            return jsonify({"status": "Already ON, kitni baar ON karega bhenchod?"}), 400
    elif action == "off":
        if auto_reply_running:
            auto_reply_running = False
            return jsonify({"status": "Auto-reply OFF, jaa ke hilale bc."}), 200
        else:
            return jsonify({"status": "Already OFF, aur kitna OFF karega madarchod?"}), 400
    else:
        return jsonify({"status": "Invalid action, gandu kahin ka."}), 400

@app.route("/status", methods=["GET"])
def get_status():
    """Status dekh, bhen ke laude."""
    return jsonify({"status": "running" if auto_reply_running else "stopped"}), 200

@app.route("/", methods=["GET"])
def home():
    """Gaand marane yahan aaya hai kya?"""
    return "OYE MADARCHOD! NOBI BOT is here to destroy. Use /control to do something useful.🔥"

# --- Main Entry Point for Render ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)