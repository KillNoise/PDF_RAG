import json
import os
from datetime import datetime

HISTORY_DIR = "history/chat_histories"

def ensure_history_dir():
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)

def save_chat_history(messages, document_name, filename=None):
    ensure_history_dir()
    if not filename:
        # Remove .pdf extension if present and add timestamp if no filename provided
        clean_name = document_name.replace('.pdf', '')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{HISTORY_DIR}/chat_{clean_name}_{timestamp}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    return filename

def load_chat_history(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def get_chat_histories():
    ensure_history_dir()
    histories = []
    if os.path.exists(HISTORY_DIR):
        files = [f for f in os.listdir(HISTORY_DIR) if f.endswith('.json')]
        for f in files:
            # Extract chat name: remove 'chat_' prefix and '.json' suffix
            display_name = f[5:-5] if f.startswith('chat_') else f[:-5]
            
            histories.append({
                "display_name": display_name,
                "filename": f,
                # No need for timestamp in display, it's part of the filename
            })
        # Sort by filename in reverse order (most recent first)
        histories.sort(key=lambda x: x['filename'], reverse=True)
    return histories

def get_full_filename(display_name):
    """Get the full filename from a display name."""
    if os.path.exists(HISTORY_DIR):
        for f in os.listdir(HISTORY_DIR):
            if f.endswith('.json'):
                # Match the display name directly against the filename
                if display_name in f:
                    return f
    return None

def delete_chat_history(display_name):
    """Delete a chat history file by its display name."""
    try:
        full_filename = get_full_filename(display_name)
        if full_filename:
            file_path = os.path.join(HISTORY_DIR, full_filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        return False
    except Exception as e:
        print(f"Error deleting chat history: {e}")
        return False