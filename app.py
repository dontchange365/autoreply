from flask import Flask, request, jsonify, render_template
from instagrapi import Client
from pymongo import MongoClient
import time
import os
import json

app = Flask(__name__)

# --- MongoDB Connection ---
# Tera diya hua MongoDB URI (Environment Variable se lega ya default)
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://dontchange365:DtUiOMFzQVM0tG9l@nobifeedback.9ntuipc.mongodb.net/?retryWrites=true&w=majority&appName=nobifeedback")
DB_NAME = "instagram_dms_db"
COLLECTION_NAME = "fetched_dm_threads"
SESSION_COLLECTION_NAME = "insta_sessions" # Naya collection session ke liye

try:
    client_mongo = MongoClient(MONGO_URI)
    db = client_mongo[DB_NAME]
    dm_collection = db[COLLECTION_NAME]
    session_collection = db[SESSION_COLLECTION_NAME] # Session collection
    print("MongoDB connected, bhenchod! 🔥")
except Exception as e:
    print(f"MongoDB connection mein gaand phat gayi: {e} 🤬")

# --- Instagrapi Client (Global Instance) ---
cl = Client()
# Tere diye hue credentials (Environment Variables se lega ya default)
USERNAME = os.getenv("INSTA_USERNAME", "noncence._")
PASSWORD = os.getenv("INSTA_PASSWORD", "shammu@love3")

# --- Helper Functions ---

# Function to save Instagrapi session to MongoDB
def save_instagrapi_session():
    try:
        settings = cl.get_settings()
        session_collection.update_one(
            {"_id": "current_session"},
            {"$set": {"settings": settings, "last_updated": time.time()}},
            upsert=True # Agar nahi hai toh insert kar de
        )
        print("Instagrapi session saved to MongoDB. 😈")
    except Exception as e:
        print(f"Session save karte hue gaand phat gayi: {e} 🤬")

# Function to load Instagrapi session from MongoDB
def load_instagrapi_session():
    try:
        print("Loading session: Checking for current_session in DB...")
        session_data = session_collection.find_one({"_id": "current_session"})
        if session_data:
            print(f"Session data found: _id={session_data.get('_id')}, settings_key_exists={'settings' in session_data}, last_updated={session_data.get('last_updated')}")
            if "settings" in session_data:
                cl.set_settings(session_data["settings"])
                print("Session settings loaded into instagrapi client. Now testing account...")
                if cl.test_account(): # <-- Yahan test kar raha hoon
                    print("Instagrapi session loaded from MongoDB and is valid. 💻")
                    return True
                else:
                    print("Instagrapi session loaded but is invalid. Clearing and retrying. 👊")
                    cl.set_settings({}) # Clear invalid settings
                    session_collection.delete_one({"_id": "current_session"}) # Delete invalid session
                    return False
            else:
                print("Session data found, but 'settings' key is missing. Deleting invalid session. 👊")
                session_collection.delete_one({"_id": "current_session"})
                return False
        else:
            print("No saved session document found with _id: 'current_session'. 👊")
            return False
    except Exception as e:
        print(f"Session load/test encountered a critical error: {e} 🤬")
        # Ensure to clear client settings and db entry if a severe error occurs
        cl.set_settings({})
        session_collection.delete_one({"_id": "current_session"})
        return False

# Initial check for session on server start
if load_instagrapi_session():
    print("Starting with a valid session.")
else:
    print("Starting without a valid session. Need a web login or manual session creation.")

# Function to handle saving DM threads to MongoDB
def save_dm_thread_to_db(thread_id, thread_name, is_group=False):
    try:
        if not dm_collection.find_one({"thread_id": thread_id}):
            dm_collection.insert_one({
                "thread_id": thread_id,
                "thread_name": thread_name,
                "is_group": is_group,
                "fetched_at": time.time()
            })
            print(f"Saved DM Thread to DB: {thread_name} (ID: {thread_id})")
            return True
        else:
            return False
    except Exception as e:
        print(f"DM thread save karte hue gaand phat gayi: {e} 🤬")
        return False


# --- Routes ---

# Main HTML page serve karne ke liye
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/web_login', methods=['POST'])
def web_login():
    # Render pe direct Selenium web login karna complex hai aur recommended nahi.
    # Ye route sirf error dega aur user ko batayega ki session generate karo.
    return jsonify({
        "status": "error",
        "message": "Web login via browser automation (Selenium) is NOT supported directly on this server. "
                   "Generate Instagram session locally (e.g., using a PC) and save it to MongoDB first. "
                   "Then load it here. 🤬"
    }), 400


@app.route('/check_session', methods=['GET'])
def check_session():
    try:
        if cl.test_account(): # Naya tarika check karne ka
            return jsonify({"status": "success", "message": "Session is active, bhenchod!"})
        else:
            print("Session test failed. Session invalid. 🤬")
            cl.set_settings({}) # Clear settings
            session_collection.delete_one({"_id": "current_session"}) # Delete from DB
            return jsonify({"status": "session_expired", "message": "Session expired! Naya login kar, chutiye!"}), 401
    except Exception as e:
        print(f"Session check encountered an error: {e}. Session invalid. 🤬")
        cl.set_settings({})
        session_collection.delete_one({"_id": "current_session"})
        return jsonify({"status": "session_expired", "message": f"Session check failed: {e}. Naya login kar, chutiye!"}), 401


# --- DM Fetching and Sending ---

# Helper function to wrap login status check
def is_logged_in_wrapper():
    """Helper to check login status, replacing direct is_logged_in attribute."""
    try:
        return cl.test_account()
    except Exception as e:
        print(f"Login check wrapper error: {e}")
        return False

@app.route('/fetch_all_dms', methods=['GET'])
def fetch_all_dms():
    if not is_logged_in_wrapper():
        return jsonify({"status": "session_expired", "message": "Session expired or not logged in. Login kar pehle, chutiye!"}), 401
    try:
        all_conversations = cl.direct_threads()
        fetched_count = 0
        all_dms_data = []

        for thread in all_conversations:
            # Handle cases where thread.users might be empty or your own username is the only one
            other_user = next((u for u in thread.users if u.username != USERNAME), None)
            thread_name = thread.thread_title if len(thread.users) > 2 else (other_user.username if other_user else "Unknown User")
            is_group = True if len(thread.users) > 2 else False

            if save_dm_thread_to_db(thread.id, thread_name, is_group):
                fetched_count += 1
            all_dms_data.append({"id": thread.id, "name": thread_name, "is_group": is_group})

        return jsonify({
            "status": "success",
            "message": f"Successfully fetched and saved {fetched_count} new DMs. Total DMs in DB: {dm_collection.count_documents({})}",
            "data": all_dms_data
        })
    except Exception as e:
        print(f"Error fetching all DMs: {e}")
        if "login" in str(e).lower() or "session" in str(e).lower() or not is_logged_in_wrapper():
            cl.set_settings({})
            session_collection.delete_one({"_id": "current_session"})
            return jsonify({"status": "session_expired", "message": f"Failed to fetch DMs: Session invalid or expired. Error: {e}"}), 401
        return jsonify({"status": "error", "message": f"Failed to fetch DMs, teri maa ki chut: {e}"}), 500

@app.route('/fetch_new_dms', methods=['GET'])
def fetch_new_dms():
    if not is_logged_in_wrapper():
        return jsonify({"status": "session_expired", "message": "Session expired or not logged in. Login kar pehle, chutiye!"}), 401
    try:
        all_conversations = cl.direct_threads()
        newly_fetched_count = 0
        new_dms_data = []

        for thread in all_conversations:
            other_user = next((u for u in thread.users if u.username != USERNAME), None)
            thread_name = thread.thread_title if len(thread.users) > 2 else (other_user.username if other_user else "Unknown User")
            is_group = True if len(thread.users) > 2 else False
            if not dm_collection.find_one({"thread_id": thread.id}):
                if save_dm_thread_to_db(thread.id, thread_name, is_group):
                    newly_fetched_count += 1
                    new_dms_data.append({"id": thread.id, "name": thread_name, "is_group": is_group})

        return jsonify({
            "status": "success",
            "message": f"Successfully fetched and saved {newly_fetched_count} new DMs.",
            "data": new_dms_data
        })
    except Exception as e:
        print(f"Error fetching new DMs: {e}")
        if "login" in str(e).lower() or "session" in str(e).lower() or not is_logged_in_wrapper():
            cl.set_settings({})
            session_collection.delete_one({"_id": "current_session"})
            return jsonify({"status": "session_expired", "message": f"Failed to fetch new DMs: Session invalid or expired. Error: {e}"}), 401
        return jsonify({"status": "error", "message": f"Failed to fetch new DMs, teri maa ki chut: {e}"}), 500

@app.route('/get_fetched_dms', methods=['GET'])
def get_fetched_dms():
    try:
        dms_from_db = list(dm_collection.find({}, {"_id": 0, "thread_id": 1, "thread_name": 1, "is_group": 1}))
        return jsonify({"status": "success", "data": dms_from_db})
    except Exception as e:
        print(f"Error getting fetched DMs from DB: {e}")
        return jsonify({"status": "error", "message": f"Failed to get DMs from DB: {e}"}), 500


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
        target_gc = dm_collection.find_one({"thread_name": gc_name, "is_group": True})
        if not target_gc:
            return jsonify({"status": "error", "message": f"GC '{gc_name}' not found in fetched DMs. Pehle fetch kar, chutiye!"}), 404
        target_thread_id = target_gc['thread_id']
        cl.direct_send_text(message_text, [target_thread_id])
        print(f"Message '{message_text}' sent to GC: {gc_name} (ID: {target_thread_id}) after {delay_seconds}s delay. 😈")
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        return jsonify({"status": "success", "message": f"Message sent to {gc_name}!"})
    except Exception as e:
        print(f"Error sending message to GC: {e}")
        if "login" in str(e).lower() or "session" in str(e).lower() or not is_logged_in_wrapper():
            cl.set_settings({})
            session_collection.delete_one({"_id": "current_session"})
            return jsonify({"status": "session_expired", "message": f"Failed to send message: Session invalid or expired. Error: {e}"}), 401
        return jsonify({"status": "error", "message": f"Failed to send message: {e}"}), 500


if __name__ == '__main__':
    # Render pe `$PORT` env var se port milta hai. Local pe 5000 use hoga.
    app.run(host='0.0.0.0', debug=True, port=os.getenv('PORT', 5000))