from flask import Flask, request, jsonify, render_template
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ClientError # Nayi import, bhenchod!
import time
import os
import json

app = Flask(__name__)

# --- FILE-BASED Session Setup ---
SESSION_FILE_PATH = "session.json" # Root directory mein hi banegi/dhoondegi.

# --- Instagrapi Client (Global Instance) ---
cl = Client()
USERNAME = os.getenv("INSTA_USERNAME", "noncence._")
PASSWORD = os.getenv("INSTA_PASSWORD", "shammu@love3")

# --- Helper Functions (Modified for File Session & New Test) ---

# Function to save Instagrapi session to File
def save_instagrapi_session_to_file():
    try:
        settings = cl.get_settings()
        with open(SESSION_FILE_PATH, "w") as f:
            json.dump(settings, f)
        print(f"Instagrapi session saved to file: {SESSION_FILE_PATH}. 😈")
    except Exception as e:
        print(f"Session file mein save karte hue gaand phat gayi: {e} 🤬")

# Function to load Instagrapi session from File
def load_instagrapi_session_from_file():
    try:
        if os.path.exists(SESSION_FILE_PATH):
            with open(SESSION_FILE_PATH, "r") as f:
                settings = json.load(f)
            cl.set_settings(settings)
            print("Instagrapi session loaded from file. Now verifying account by API call... 💻")
            
            try:
                cl.get_timeline_feed(amount=1) # Koi bhi simple API call
                print("Instagrapi session from file is valid. 🔥")
                return True
            except (LoginRequired, ClientError) as e: # Agar login error aaya
                print(f"Instagrapi session from file invalid during API test: {e}. Deleting and retrying. 👊")
                os.remove(SESSION_FILE_PATH) # Delete invalid file
                return False
        else:
            print(f"No session file found at {SESSION_FILE_PATH}. 👊")
            return False
    except Exception as e:
        print(f"Session file se load/test karte hue gaand phat gayi: {e} 🤬")
        if os.path.exists(SESSION_FILE_PATH):
            os.remove(SESSION_FILE_PATH) # Delete corrupt file
        return False

# Initial check for session on server start (USING FILE)
if load_instagrapi_session_from_file():
    print("Starting with a valid session from file.")
else:
    print("Starting without a valid session. Need manual login or session file.")

# --- Dummy collections for now, since MongoDB is not being used for DMs ---
dm_collection = None
session_collection = None

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/web_login', methods=['POST'])
def web_login():
    return jsonify({
        "status": "error",
        "message": "Web login via browser automation (Selenium) is NOT supported directly on this server. "
                   "Generate Instagram session manually (e.g., using a PC) and SAVE 'session.json' to the root of the project. "
                   "NOTE: This session will be lost on server restarts/deploys. 🤬"
    }), 400


@app.route('/check_session', methods=['GET'])
def check_session():
    try:
        cl.get_timeline_feed(amount=1) # Direct API call to check session
        return jsonify({"status": "success", "message": "Session is active, bhenchod!"})
    except (LoginRequired, ClientError) as e:
        print(f"Session check failed during API call: {e}. Session invalid. 🤬")
        if os.path.exists(SESSION_FILE_PATH):
            os.remove(SESSION_FILE_PATH) # Delete invalid file
        return jsonify({"status": "session_expired", "message": "Session expired! Naya login kar, chutiye!"}), 401
    except Exception as e:
        print(f"Session check encountered an unexpected error: {e}. Session invalid. 🤬")
        if os.path.exists(SESSION_FILE_PATH):
            os.remove(SESSION_FILE_PATH) # Delete corrupt file
        return jsonify({"status": "session_expired", "message": f"Session check failed: {e}. Naya login kar, chutiye!"}), 401


# --- DM Fetching and Sending (No DB persistence for DMs now) ---

def is_logged_in_wrapper():
    # Ab is wrapper ko bhi API call se check karenge
    try:
        cl.get_timeline_feed(amount=1)
        return True
    except (LoginRequired, ClientError):
        return False
    except Exception as e:
        print(f"Login check wrapper unexpected error: {e}")
        return False


@app.route('/fetch_all_dms', methods=['GET'])
def fetch_all_dms():
    if not is_logged_in_wrapper():
        return jsonify({"status": "session_expired", "message": "Session expired or not logged in. Login kar pehle, chutiye!"}), 401
    try:
        all_conversations = cl.direct_threads()
        all_dms_data = []
        for thread in all_conversations:
            other_user = next((u for u in thread.users if u.username != USERNAME), None)
            thread_name = thread.thread_title if len(thread.users) > 2 else (other_user.username if other_user else "Unknown User")
            is_group = True if len(thread.users) > 2 else False
            all_dms_data.append({"id": thread.id, "name": thread_name, "is_group": is_group})

        return jsonify({
            "status": "success",
            "message": f"Successfully fetched {len(all_dms_data)} DMs (Not saved locally).",
            "data": all_dms_data
        })
    except Exception as e:
        print(f"Error fetching all DMs: {e}")
        if isinstance(e, (LoginRequired, ClientError)) or not is_logged_in_wrapper():
            if os.path.exists(SESSION_FILE_PATH): os.remove(SESSION_FILE_PATH)
            return jsonify({"status": "session_expired", "message": f"Failed to fetch DMs: Session invalid or expired. Error: {e}"}), 401
        return jsonify({"status": "error", "message": f"Failed to fetch DMs, teri maa ki chut: {e}"}), 500

@app.route('/fetch_new_dms', methods=['GET'])
def fetch_new_dms():
    if not is_logged_in_wrapper():
        return jsonify({"status": "session_expired", "message": "Session expired or not logged in. Login kar pehle, chutiye!"}), 401
    try:
        all_conversations = cl.direct_threads()
        new_dms_data = []
        for thread in all_conversations:
            other_user = next((u for u in thread.users if u.username != USERNAME), None)
            thread_name = thread.thread_title if len(thread.users) > 2 else (other_user.username if other_user else "Unknown User")
            is_group = True if len(thread.users) > 2 else False
            new_dms_data.append({"id": thread.id, "name": thread_name, "is_group": is_group})
        
        return jsonify({
            "status": "success",
            "message": f"Successfully fetched {len(new_dms_data)} DMs (Not saved locally).",
            "data": new_dms_data
        })
    except Exception as e:
        print(f"Error fetching new DMs: {e}")
        if isinstance(e, (LoginRequired, ClientError)) or not is_logged_in_wrapper():
            if os.path.exists(SESSION_FILE_PATH): os.remove(SESSION_FILE_PATH)
            return jsonify({"status": "session_expired", "message": f"Failed to fetch new DMs: Session invalid or expired. Error: {e}"}), 401
        return jsonify({"status": "error", "message": f"Failed to fetch new DMs, teri maa ki chut: {e}"}), 500

@app.route('/get_fetched_dms', methods=['GET'])
def get_fetched_dms():
    # Ye function ab kuch return nahi karega agar DMs DB mein save nahi ho rahe.
    # Frontend ko empty list dega ya "Not implemented"
    return jsonify({"status": "info", "message": "DM history not stored locally, fetch live.", "data": []})


@app.route('/send_gc_message', methods=['POST'])
def send_gc_message():
    if not is_logged_in_wrapper():
        return jsonify({"status": "session_expired", "message": "Session expired or not logged in. Login kar pehle, chutiye!"}), 401
    data = request.json
    message_text = data.get('message')
    gc_name = data.get('gc_name')
    delay_seconds = data.get('delay', 0)
    if not message_text or not gc_name:
        return jsonify({"status": "error", "message": "Message text aur GC Name required hai, bhen ke laude!"}), 400
    
    try:
        # Ab GC name se thread ID dynamically dhundhni padegi, kyunki DB nahi hai.
        print(f"Searching for GC '{gc_name}' to send message...")
        all_conversations = cl.direct_threads()
        target_thread_id = None
        for thread in all_conversations:
            if len(thread.users) > 2 and thread.thread_title == gc_name:
                target_thread_id = thread.id
                break
        
        if not target_thread_id:
            return jsonify({"status": "error", "message": f"GC '{gc_name}' not found. Check exact name. Pehle fetch kar, chutiye!"}), 404

        cl.direct_send_text(message_text, [target_thread_id])
        print(f"Message '{message_text}' sent to GC: {gc_name} (ID: {target_thread_id}) after {delay_seconds}s delay. 😈")
        
        if delay_seconds > 0:
            time.sleep(delay_seconds)
            
        return jsonify({"status": "success", "message": f"Message sent to {gc_name}!"})

    except Exception as e:
        print(f"Error sending message to GC: {e}")
        if isinstance(e, (LoginRequired, ClientError)) or not is_logged_in_wrapper():
            if os.path.exists(SESSION_FILE_PATH): os.remove(SESSION_FILE_PATH)
            return jsonify({"status": "session_expired", "message": f"Failed to send message: Session invalid or expired. Error: {e}"}), 401
        return jsonify({"status": "error", "message": f"Failed to send message: {e}"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=os.getenv('PORT', 5000))