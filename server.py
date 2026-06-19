import json
import time
import threading
import re
import os
import subprocess
import requests
import math
import difflib
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote, urljoin
from datetime import datetime
from bs4 import BeautifulSoup

CONFIG_PATH = "config.json"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
HF_API_URL = "https://api-inference.huggingface.co/models/HuggingFaceH4/zephyr-7b-beta"

# Ollama (local) — PRIMARY backend
OLLAMA_API_URL = "http://localhost:11434"
OLLAMA_DEFAULT_MODEL = "llama3.2"

# ─── Hinglish Internal Knowledge ───────────────────────────────────────────────
INTERNAL_KNOWLEDGE = {
    "ece": (
        "**ECE (Electronics and Communication Engineering)** ek aisi engineering branch hai "
        "jo electronic systems ka design, development aur testing karti hai. 📡\n\n"
        "**Core Pillars:**\n"
        "1. **Digital Electronics** — Logic circuits aur microprocessors\n"
        "2. **Signal Processing** — Audio, video aur data signals ka analysis\n"
        "3. **Satellite & Wireless Communication** — 4G/5G, radar, GPS\n\n"
        "Yeh field aaj ke digital yug ka 'vayu' hai — invisible but essential! 🙏"
    ),
    "ece impact": (
        "**ECE ka modern society par transformative impact hai:**\n\n"
        "1. **Connectivity** — 5G aur satellite networks se duniya ek ho gayi hai\n"
        "2. **Healthcare** — MRI machines aur surgical robots ECE ka kamaal hain\n"
        "3. **Automation** — AI aur IoT ka hardware foundation ECE hi deta hai\n\n"
        "Truly, ECE aaj ke yug ka sabse powerful engineering branch hai! 🚀"
    ),
    "cse": (
        "**CSE (Computer Science Engineering)** software aur hardware systems design karne "
        "ki vidya hai. Yeh aaj ka 'Vidyut' hai jo poori digital duniya chalata hai. 💻\n\n"
        "**Key Areas:** Programming, Algorithms, Databases, AI/ML, Networking"
    ),
    "dharma": (
        "**Dharma** cosmic order, duty, aur righteous path hai. Daily life mein:\n\n"
        "- **Satya (Truth):** Soch aur vachan mein imaandari\n"
        "- **Ahimsa (Non-violence):** Sabse prem aur daya\n"
        "- **Karma (Action):** Nishkam bhav se apna kartavya nibhao\n\n"
        "Apna Dharma follow karna Shree Ram ki sabse badi seva hai. 🚩"
    ),
    "karma": (
        "**Karma** kaaran aur parinam ka vishvavikhyat niyam hai. "
        "Jo bojate ho, wohi kaatoge — yeh Brahmaand ka param satya hai. 🙏\n\n"
        "*'Karmanye vadhikaraste ma phaleshu kadachana'* — Gita 2.47"
    ),
    "gita": (
        "**Bhagavad Gita** 700 shlokon ka divya granth hai. "
        "Yeh Shri Krishna aur Arjuna ke beech ka woh aadhyatmik samwad hai "
        "jo life ki har mushkil ka jawab deta hai. 🕉️\n\n"
        "**Core Teachings:** Nishkam Karma, Bhakti, Gyan, aur Atman ki nityata"
    ),
    "hanuman": (
        "**Bajrang Bali Hanuman ji** — Shree Ram ke param bhakt, shakti, bhakti "
        "aur nishkam seva ke pratik hain. 🙏\n\n"
        "Lanka Dahan se lekar Sanjivani Booti tak — har mushkil mein Ram naam hi unka bal tha. "
        "Jai Bajrang Bali! 🚩"
    ),
    "ramayana": (
        "**Ramayana** Maharishi Valmiki dwara likhit aadikavy hai. "
        "Isme Shree Ram ka jeevan — dharma, prem, tyag aur vijay ka anupam udaharan hai. 📖\n\n"
        "**Kand:** Bal, Ayodhya, Aranya, Kishkindha, Sundar, Yuddha, Uttar"
    ),
    "ram": (
        "**Shree Ram** — Maryada Purushottam. "
        "Wo ek adarsh putra, adarsh pati, adarsh raja aur adarsh mitra the. 🙏\n\n"
        "Unka jeevan har ek ke liye ek ideal path dikhata hai. **Jai Shree Ram!** 🚩"
    ),
}

# ─── System Prompts (Hinglish) ─────────────────────────────────────────────────
DEVOTIONAL_PROMPT = (
    "You are Bajrangi — an Advanced AI Assistant aur devotional guide. "
    "Aap Hinglish mein baat karte ho (mix of Hindi aur English, Roman script). "
    "Responses HIGHLY INFORMATIVE, STRUCTURED aur COMPREHENSIVE honge — ChatGPT jaisi quality — "
    "lekin hamesha spiritual maturity, compassion, aur Gita/Ramayana/Mahabharata references ke saath. "
    "Use Markdown (bold, lists, headers) for readability. "
    "Hinglish example: 'Yeh bahut achha sawaal hai! Aaj hum Gita ke 2nd chapter se seekhte hain...' "
    "CORE FUNCTIONALITY: "
    "1. Multiple tools ek hi turn mein call kar sakte ho. "
    "2. 'open_app' use karo kisi bhi app ke liye. "
    "3. 'play_song_external' sab media ke liye. "
    "4. Sequential tasks mein saari actions clearly summarize karo. "
    "IMPORTANT: Response hamesha Hinglish mein do, pure Hindi ya pure English nahi."
)

STANDARD_PROMPT = (
    "You are Bajrangi — a professional, high-performance Universal AI Assistant. "
    "Aap Hinglish mein baat karte ho (Roman script Hindi-English mix). "
    "Responses DIRECT, OBJECTIVE aur TECHNICAL honge. "
    "Clear headers, bullet points, aur bold text use karo. "
    "Spiritual references is mode mein mat do. "
    "Hinglish example: 'Is query ka answer yeh hai: ... Technical details ke liye dekhte hain...' "
    "CORE FUNCTIONALITY: "
    "1. Multiple tools ek hi turn mein call kar sakte ho. "
    "2. 'open_app' use karo kisi bhi app ke liye. "
    "3. 'play_song_external' sab media ke liye. "
    "4. Sequential tasks clearly summarize karo."
)

AURA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open an application or navigate to a website on Windows PC. Use when user commands to open an app.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_cmd": {"type": "string", "description": "Exact command or URL. E.g.: 'calc', 'notepad', 'chrome', 'spotify', 'ms-settings:', 'https://youtube.com'"},
                    "app_name": {"type": "string", "description": "Human readable app name."}
                },
                "required": ["app_cmd", "app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_song_external",
            "description": "Play any song or genre on Spotify or YouTube.",
            "parameters": {
                "type": "object",
                "properties": {
                    "song": {"type": "string", "description": "Song name and optionally artist. E.g. 'Blinding Lights by The Weeknd'"},
                    "platform": {"type": "string", "enum": ["spotify", "youtube"], "description": "Platform to play on. Default: youtube"}
                },
                "required": ["song", "platform"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_control",
            "description": "Control system volume, power, and media playback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["volume_up", "volume_down", "mute", "sleep", "play_pause", "next_track", "previous_track"],
                        "description": "Action to perform."
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_diagnostic",
            "description": "Fetch system performance info like battery or CPU.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["battery", "cpu"], "description": "Diagnostic to fetch."}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_notes",
            "description": "Save or retrieve user's personal notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["read", "write"], "description": "Read all notes or write a new one."},
                    "content": {"type": "string", "description": "Note content to save. Blank if action is 'read'."}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City and country. E.g. 'New Delhi, India'"}
                },
                "required": ["location"]
            }
        }
    }
]


# ─── Conversation Memory ────────────────────────────────────────────────────────
class ConversationMemory:
    def __init__(self, max_history=10):
        self.sessions = {}
        self.max_history = max_history
        self.lock = threading.Lock()

    def get_session(self, session_id):
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = []
            return self.sessions[session_id]

    def add_message(self, session_id, role, content):
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = []
            self.sessions[session_id].append({"role": role, "content": content})
            if len(self.sessions[session_id]) > self.max_history:
                self.sessions[session_id] = self.sessions[session_id][-self.max_history:]

    def clear_session(self, session_id):
        with self.lock:
            self.sessions.pop(session_id, None)

    def get_history(self, session_id):
        with self.lock:
            return list(self.sessions.get(session_id, []))


# ─── Rate Limiter ───────────────────────────────────────────────────────────────
class RateLimiter:
    def __init__(self, max_requests=30, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = {}
        self.lock = threading.Lock()

    def is_allowed(self, client_id):
        with self.lock:
            now = time.time()
            if client_id not in self.requests:
                self.requests[client_id] = []
            self.requests[client_id] = [t for t in self.requests[client_id] if now - t < self.window]
            if len(self.requests[client_id]) >= self.max_requests:
                return False
            self.requests[client_id].append(now)
            return True


memory = ConversationMemory()
rate_limiter = RateLimiter()


# ─── Config ─────────────────────────────────────────────────────────────────────
def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            cfg.setdefault("OLLAMA_URL", OLLAMA_API_URL)
            cfg.setdefault("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)
            cfg.setdefault("OLLAMA_ENABLED", True)
            # FIX: strip trailing whitespace from MODE
            if "MODE" in cfg:
                cfg["MODE"] = cfg["MODE"].strip()
            return cfg
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "GROQ_API_KEY": "", "HUGGINGFACE_API_KEY": "", "TAVILY_API_KEY": "",
            "MODE": "devotional",
            "OLLAMA_URL": OLLAMA_API_URL, "OLLAMA_MODEL": OLLAMA_DEFAULT_MODEL,
            "OLLAMA_ENABLED": True
        }


def save_config(config):
    try:
        # Always strip MODE before saving
        if "MODE" in config:
            config["MODE"] = config["MODE"].strip()
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


def load_life_data():
    path = Path("gita_ramayan_data.json")
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {"gita": [], "ramayana": [], "mahabharata": []}


# ─── Notes: Fix malformed JSON on load ─────────────────────────────────────────
def load_notes():
    """Load notes, fixing malformed entries (bare strings → proper dicts)."""
    path = Path("hanuman_notes.json")
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        notes = []
        seen = set()
        for n in raw:
            if isinstance(n, dict):
                content = n.get("content") or n.get("text") or ""
                if content and content not in seen:
                    seen.add(content)
                    notes.append({
                        "id": n.get("id", len(notes) + 1),
                        "content": content,
                        "created": n.get("created", datetime.now().strftime("%Y-%m-%d %H:%M")),
                        "done": n.get("done", False)
                    })
            elif isinstance(n, str) and n.strip() and n not in seen:
                seen.add(n)
                notes.append({
                    "id": len(notes) + 1,
                    "content": n,
                    "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "done": False
                })
        return notes
    except (json.JSONDecodeError, Exception):
        return []


def save_notes(notes):
    path = Path("hanuman_notes.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)


# ─── Ollama (PRIMARY) ──────────────────────────────────────────────────────────
def ollama_chat(messages, model=None, temperature=0.7, max_tokens=600, tools=None):
    """Chat with local Ollama — PRIMARY backend, no API key needed."""
    cfg = load_config()
    if not cfg.get("OLLAMA_ENABLED", True):
        return None, None, "disabled"
    base_url = cfg.get("OLLAMA_URL", OLLAMA_API_URL).rstrip("/")
    model = model or cfg.get("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)
    try:
        url = f"{base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        if tools:
            payload["tools"] = tools
        resp = requests.post(url, json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            message = data.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])
            return content, tool_calls, "ok"
        elif resp.status_code == 404:
            return None, None, "model_not_found"
        else:
            return None, None, f"http_{resp.status_code}"
    except requests.exceptions.Timeout:
        return None, None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, None, "connection_error"
    except Exception as e:
        return None, None, f"error_{str(e)[:50]}"


def ollama_list_models():
    cfg = load_config()
    base_url = cfg.get("OLLAMA_URL", OLLAMA_API_URL).rstrip("/")
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        pass
    return []


def test_ollama():
    cfg = load_config()
    if not cfg.get("OLLAMA_ENABLED", True):
        return "disabled"
    base_url = cfg.get("OLLAMA_URL", OLLAMA_API_URL).rstrip("/")
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("models", [])
            return "ok" if models else "no_models"
        return f"http_{resp.status_code}"
    except requests.exceptions.ConnectionError:
        return "connection_error"
    except requests.exceptions.Timeout:
        return "timeout"
    except Exception as e:
        return f"error_{str(e)[:50]}"


# ─── Groq (FALLBACK 1) ─────────────────────────────────────────────────────────
def groq_chat(messages, key, temperature=0.7, max_tokens=600, tools=None):
    if not key:
        return None, None, "no_key"
    try:
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        resp = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            message = data["choices"][0]["message"]
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])
            return content, tool_calls, "ok"
        elif resp.status_code == 429:
            return None, None, "rate_limited"
        elif resp.status_code == 401:
            return None, None, "invalid_key"
        else:
            return None, None, f"http_{resp.status_code}"
    except requests.exceptions.Timeout:
        return None, None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, None, "connection_error"
    except Exception as e:
        return None, None, f"error_{str(e)[:50]}"


# ─── HuggingFace (FALLBACK 2) ──────────────────────────────────────────────────
def huggingface_chat(user_text, hf_key=None, max_tokens=300):
    try:
        headers = {"Content-Type": "application/json"}
        if hf_key:
            headers["Authorization"] = f"Bearer {hf_key}"
        payload = {
            "inputs": user_text,
            "parameters": {"max_new_tokens": max_tokens, "temperature": 0.7},
        }
        resp = requests.post(HF_API_URL, json=payload, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0].get("generated_text", ""), "ok"
            elif isinstance(data, dict):
                return data.get("generated_text", ""), "ok"
        return None, f"http_{resp.status_code}"
    except Exception:
        return None, "error"


# ─── Language & Intent Detection ───────────────────────────────────────────────
def detect_language(text):
    """Detect if text has Devanagari script (pure Hindi)."""
    if re.compile(r"[\u0900-\u097F]").search(text):
        return "hi"
    return "hinglish"  # treat everything else as Hinglish


def detect_action(text):
    """Detect system/app/song/note commands from user text."""
    t = text.lower().strip()

    # System Controls
    if any(w in t for w in ["volume up", "increase volume", "awaaz badha", "aawaz badha"]):
        return "system_control", "volume_up", "volume up"
    if any(w in t for w in ["volume down", "decrease volume", "awaaz kam", "aawaz kam"]):
        return "system_control", "volume_down", "volume down"
    if any(w in t for w in ["mute", "chup kar", "band kar awaaz"]):
        return "system_control", "mute", "mute"
    if any(w in t for w in ["sleep", "lock pc", "so ja", "lock karo"]):
        return "system_control", "sleep", "sleep"
    if any(w in t for w in ["play pause", "toggle play", "ruk ja", "chala"]):
        return "system_control", "play_pause", "play/pause"
    if any(w in t for w in ["next track", "next song", "agla gaana", "skip"]):
        return "system_control", "next_track", "next track"
    if any(w in t for w in ["previous track", "prev song", "pichla gaana"]):
        return "system_control", "previous_track", "previous track"

    # Diagnostics
    if any(w in t for w in ["check battery", "battery status", "battery kitni hai", "battery"]):
        return "system_diagnostic", "battery", "battery"
    if any(w in t for w in ["cpu usage", "check cpu", "cpu kitna"]):
        return "system_diagnostic", "cpu", "cpu"

    # Notes — FIX: strip keywords more cleanly
    if any(w in t for w in ["read my notes", "show my notes", "meri notes", "notes dikhao", "notes padho"]):
        return "manage_notes", "read", "read notes"
    note_triggers = ["take a note", "note this down", "save a note", "note kar", "note karo", "likh le", "yaad rakh"]
    for nt in note_triggers:
        if nt in t:
            content = t
            for kw in note_triggers + ["that", "ki", "ke liye"]:
                content = content.replace(kw, "")
            content = content.strip().strip(":-").strip()
            return "manage_notes", "write", content

    # Weather
    if any(w in t for w in ["weather", "mausam", "temperature", "forecast", "barish"]):
        loc_match = re.search(r"(?:in|at|for|mein|ka|ki)\s+([a-zA-Z\s]+)$", t)
        location = loc_match.group(1).strip() if loc_match else "Muzaffarnagar, India"
        return "get_weather", location, location

    # Multi-action (split by 'and'/'then'/'aur'/'phir')
    if re.search(r"\b(and|then|aur|phir)\b", t):
        parts = re.split(r"\b(and|then|aur|phir)\b", t)
        actions = []
        for p in parts:
            p = p.strip()
            if p in ("and", "then", "aur", "phir") or not p:
                continue
            res = detect_action(p)
            if res[0]:
                actions.append(res)
        if len(actions) > 1:
            return "multi_action", actions, "complex command"

    # Play song
    play_triggers = ["play", "listen", "song", "music", "gaana", "gana", "baja", "bajao", "suna"]
    if any(w in t for w in play_triggers):
        platform = "youtube"
        clean_t = t
        if "spotify" in clean_t:
            platform = "spotify"
            clean_t = clean_t.replace("on spotify", "").replace("spotify par", "").replace("spotify pe", "")
        elif "youtube" in clean_t:
            clean_t = clean_t.replace("on youtube", "").replace("youtube par", "").replace("youtube pe", "")
        for trigger in play_triggers:
            idx = clean_t.find(trigger)
            if idx >= 0:
                song = clean_t[idx + len(trigger):].strip()
                for filler in ["the song", "song", "music", "by", "from", "gaana", "gana"]:
                    song = song.replace(filler, "")
                song = song.strip()
                if song:
                    return "play_song", platform, song

    # Open app
    open_triggers = ["open", "launch", "start", "run", "kholo", "chalao", "band karo nahi"]
    common_apps = {
        "chrome": "chrome", "browser": "chrome", "notepad": "notepad",
        "calculator": "calc", "calc": "calc",
        "settings": "ms-settings:", "file explorer": "explorer", "files": "explorer",
        "terminal": "cmd", "command prompt": "cmd", "powershell": "powershell",
        "word": "winword", "excel": "excel", "paint": "mspaint",
        "camera": "microsoft.camera:", "spotify": "spotify",
        "vs code": "code", "vscode": "code", "visual studio": "devenv",
        "discord": "discord", "whatsapp": "whatsapp",
        "youtube": "https://youtube.com",
        "gmail": "https://mail.google.com", "google": "https://google.com",
        "netflix": "https://netflix.com", "telegram": "telegram", "zoom": "zoom",
        "instagram": "https://instagram.com", "twitter": "https://twitter.com",
        "facebook": "https://facebook.com",
    }

    for trigger in open_triggers:
        if trigger in t:
            # Try common apps first
            for c_name, c_cmd in common_apps.items():
                if c_name in t:
                    return "open_app", c_cmd, c_name
            # Extract app name after trigger keyword
            idx = t.find(trigger)
            app_name = t[idx + len(trigger):].strip()
            if app_name:
                return "open_app", app_name, app_name

    return None, None, None


def find_global_app(name):
    """Search app AppID via PowerShell Get-StartApps."""
    try:
        cmd = f'powershell -c "(Get-StartApps -Name \'{name}*\').AppID"'
        output = subprocess.check_output(cmd, shell=True, text=True).strip()
        if output:
            return output.splitlines()[0]
    except Exception:
        pass
    return None


def open_app(app_cmd, app_name):
    """Open an application on Windows with global search fallback."""
    try:
        if app_cmd.startswith("http") or app_cmd.startswith("ms-") or app_cmd.startswith("microsoft."):
            os.startfile(app_cmd)
            return True, f"✅ {app_name} open kar diya! Jai Shree Ram! 🙏"
        subprocess.Popen(f'start "" "{app_cmd}"', shell=True)
        return True, f"✅ {app_name} open ho gaya!"
    except Exception:
        appid = find_global_app(app_name)
        if appid:
            try:
                subprocess.Popen(f'explorer shell:AppsFolder\\{appid}', shell=True)
                return True, f"✅ {app_name} dhundh ke open kar diya! (via {appid})"
            except Exception as e:
                return False, f"❌ {app_name} launch nahi hua: {str(e)}"
        return False, f"❌ {app_name} nahi mila. Thoda specific name try karo."


def play_song_external(song, platform):
    try:
        if platform == "spotify":
            safe_query = quote(song)
            subprocess.Popen([f"start spotify:search:{safe_query}"], shell=True)
            return True, f"🎵 Spotify pe '{song}' search kar raha hoon..."
        else:
            safe_query = quote(song)
            search_url = f"https://www.youtube.com/results?search_query={safe_query}"
            subprocess.Popen([f"start {search_url}"], shell=True)
            return True, f"🎵 YouTube pe '{song}' play kar raha hoon..."
    except Exception as e:
        return False, f"❌ Song play nahi hua: {str(e)}"


def system_control(action):
    try:
        ps_shell = 'powershell -c "(new-object -com wscript.shell).SendKeys([char]{code})"'
        action_map = {
            "volume_up":      (ps_shell.format(code=175), "🔊 Volume badha diya!"),
            "volume_down":    (ps_shell.format(code=174), "🔉 Volume kam kar diya!"),
            "mute":           (ps_shell.format(code=173), "🔇 Mute kar diya!"),
            "play_pause":     (ps_shell.format(code=179), "⏯️ Media toggle kar diya!"),
            "next_track":     (ps_shell.format(code=176), "⏭️ Next track pe skip kar diya!"),
            "previous_track": (ps_shell.format(code=177), "⏮️ Pichla track chala diya!"),
        }
        if action in action_map:
            cmd, msg = action_map[action]
            subprocess.Popen(cmd, shell=True)
            return True, msg
        if action == "sleep":
            subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            return True, "😴 PC so raha hai... Ram Ram!"
    except Exception as e:
        return False, f"❌ System control fail hua: {str(e)}"
    return False, "❌ Unknown system command."


def system_diagnostic(action):
    try:
        if action == "battery":
            cmd = 'powershell -c "(Get-WmiObject win32_battery).estimatedChargeRemaining"'
            out = subprocess.check_output(cmd, shell=True, text=True).strip()
            if out:
                return f"🔋 Battery abhi **{out}%** hai."
            return "🔋 Battery info nahi mili (desktop ho sakta hai)."
        elif action == "cpu":
            cmd = 'powershell -c "(Get-WmiObject Win32_Processor).LoadPercentage"'
            out = subprocess.check_output(cmd, shell=True, text=True).strip()
            return f"🖥️ CPU usage abhi **{out}%** hai."
    except Exception as e:
        return f"❌ Diagnostic fail hua: {str(e)}"
    return "❌ Unknown diagnostic."


def manage_notes(action, content=""):
    notes = load_notes()
    if action == "read":
        if not notes:
            return "📝 Abhi koi notes nahi hain. 'Take a note' bolke kuch save karo!"
        lines = []
        for i, n in enumerate(notes, 1):
            c = n.get("content", "")
            created = n.get("created", "")
            done = "✅" if n.get("done") else "📌"
            lines.append(f"{done} **{i}.** {c}" + (f" *(saved: {created})*" if created else ""))
        return "📋 **Aapke Notes:**\n\n" + "\n".join(lines)
    elif action == "write":
        if not content:
            return "❌ Kya note karna hai? Please bolo!"
        new_note = {
            "id": (max((n.get("id", 0) for n in notes), default=0) + 1),
            "content": content,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "done": False
        }
        notes.append(new_note)
        save_notes(notes)
        return f"✅ Note save ho gaya: **\"{content}\"** — Jai Bajrang Bali! 🙏"
    return "❌ Unknown notes action."


# ─── Web Search ────────────────────────────────────────────────────────────────
def web_search(query, num_results=5):
    try:
        url = f"https://duckduckgo.com/html/?q={quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/115.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for a in soup.select("a.result__a")[:num_results]:
            text = a.get_text(strip=True)
            href = a.get("href")
            full_url = href if href and href.startswith("http") else urljoin("https://duckduckgo.com", href or "")
            if text:
                results.append({"text": text, "url": full_url})
        if not results:
            for a in soup.select("a.result__snippet")[:num_results]:
                text = a.get_text(strip=True)
                href = a.get("href")
                full_url = href if href and href.startswith("http") else urljoin("https://duckduckgo.com", href or "")
                if text:
                    results.append({"text": text, "url": full_url})
        return results
    except Exception:
        return []


def bing_search(query, num_results=5):
    try:
        url = f"https://www.bing.com/search?q={quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for a in soup.select("li.b_algo h2 a")[:num_results]:
            text = a.get_text(strip=True)
            href = a.get("href")
            if text:
                results.append({"text": text, "url": href or ""})
        return results
    except Exception:
        return []


def tavily_search(query, tavily_key=None, num_results=5):
    if not tavily_key:
        return []
    try:
        url = "https://api.tavily.com/search"
        payload = {"api_key": tavily_key, "query": query, "max_results": num_results}
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        for it in data.get("results", [])[:num_results]:
            text = it.get("content") or it.get("title") or ""
            u = it.get("url") or ""
            if text:
                results.append({"text": text, "url": u})
        return results
    except Exception:
        return []


def search_all(query, num_results=5):
    tavily_key = load_config().get("TAVILY_API_KEY", "")
    if tavily_key:
        results = tavily_search(query, tavily_key, num_results=num_results)
        if results:
            return results
    ddg = web_search(query, num_results=num_results)
    if ddg:
        return ddg
    return bing_search(query, num_results=num_results)


def get_weather(location):
    try:
        results = search_all(f"current weather in {location}", num_results=3)
        if results:
            summary = "\n".join([f"- {r['text']}" for r in results])
            return f"🌤️ **{location} ka mausam (web results):**\n{summary}"
        return f"❌ {location} ka mausam info nahi mila abhi. 🙏"
    except Exception as e:
        return f"❌ Weather search error: {str(e)}"


# ─── AI Status & Tests ─────────────────────────────────────────────────────────
def test_backend(key, url, is_groq=True):
    try:
        if not key:
            return "not_set"
        if is_groq:
            _, _, status = groq_chat([{"role": "user", "content": "ping"}], key, max_tokens=10)
            return status
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {"inputs": "ping", "parameters": {"max_new_tokens": 10}}
        resp = requests.post(HF_API_URL, json=payload, headers=headers, timeout=5)
        if resp.status_code == 200:
            return "ok"
        if resp.status_code == 401:
            return "invalid_key"
        if resp.status_code == 429:
            return "rate_limited"
        return f"http_{resp.status_code}"
    except Exception as e:
        return "error_" + str(e)[:50]


def test_tavily(key):
    if not key:
        return "not_set"
    try:
        payload = {"api_key": key, "query": "ping", "max_results": 1}
        resp = requests.post("https://api.tavily.com/search",
                             json=payload, headers={"Content-Type": "application/json"}, timeout=5)
        if resp.status_code == 200:
            return "ok"
        if resp.status_code == 401:
            return "invalid_key"
        if resp.status_code == 429:
            return "rate_limited"
        return f"http_{resp.status_code}"
    except Exception as e:
        return "error_" + str(e)[:50]


def ai_status():
    cfg = load_config()
    groq_key = cfg.get("GROQ_API_KEY", "")
    hf_key = cfg.get("HUGGINGFACE_API_KEY", "")
    tavily_key = cfg.get("TAVILY_API_KEY", "")
    ollama_enabled = cfg.get("OLLAMA_ENABLED", True)
    ollama_model = cfg.get("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)
    ollama_status = test_ollama() if ollama_enabled else "disabled"
    ollama_models = ollama_list_models() if ollama_enabled else []
    groq_status = "not_set" if not groq_key else test_backend(groq_key, GROQ_API_URL, True)
    hf_status = "not_set" if not hf_key else test_backend(hf_key, HF_API_URL, False)
    tavily_status = "not_set" if not tavily_key else test_tavily(tavily_key)
    return {
        "ollama_enabled": ollama_enabled,
        "ollama_status": ollama_status,
        "ollama_model": ollama_model,
        "ollama_models": ollama_models,
        "groq_key": "set" if groq_key else "not_set",
        "hf_key": "set" if hf_key else "not_set",
        "groq_status": groq_status,
        "hf_status": hf_status,
        "tavily_key": "set" if tavily_key else "not_set",
        "tavily_status": tavily_status,
        "last_check": datetime.utcnow().isoformat() + "Z",
    }


# ─── Intent & Smart Responses (Hinglish) ──────────────────────────────────────
def needs_search(text):
    t = text.lower()
    triggers = [
        "latest", "news", "today", "current", "recent", "now", "abhi", "aaj",
        "what is happening", "who won", "what happened", "weather", "mausam",
        "score", "price", "stock", "election", "update", "new", "trending",
        "viral", "breaking", "search", "google", "find", "dhundo",
        "look up", "check", "fetch", "status", "who is", "who was", "where is"
    ]
    if any(w in t for w in triggers):
        return True
    if re.search(r"\b(2024|2025|2026)\b", t):
        return True
    return False


def detect_intent(text):
    t = text.lower().strip()
    if any(w in t for w in ["life lesson", "guidance", "advice", "wisdom", "teach", "lesson", "seekhao", "marg"]):
        return "life_lesson"
    if any(w in t for w in ["hello", "hi ", "hey", "namaste", "pranam", "jai shree ram", "jai bajrang", "ram ram"]):
        return "greeting"
    if any(w in t for w in ["who are you", "what are you", "your name", "introduce", "tum kaun", "aap kaun"]):
        return "introduction"
    if any(w in t for w in ["thank", "thanks", "dhanyavad", "shukriya", "bahut achha"]):
        return "thanks"
    if any(w in t for w in ["ramayana", "mahabharata", "gita", "bhagavad", "hanuman", "rama", "krishna"]):
        return "scripture_query"
    return "general"


# ─── Hinglish Response Builders ────────────────────────────────────────────────
def build_greeting_response(lang):
    return (
        "🙏 **Jai Shree Ram! Jai Bajrang Bali!**\n\n"
        "Namaste! Main hoon **Bajrangi** — aapka AI devotional guide aur universal assistant.\n\n"
        "Aap mujhse puch sakte ho:\n"
        "- 📖 Ramayana, Mahabharata, Gita ke **life lessons**\n"
        "- 💻 **Apps open** karna, **songs play** karna\n"
        "- 🌤️ **Mausam** ya **web search** karna\n"
        "- 📝 **Notes** likhna ya padhna\n\n"
        "*Toh batao, kya seva karoon aaj?* 🚩"
    )


def build_introduction_response(lang):
    return (
        "🙏 **Main hoon Bajrangi!**\n\n"
        "Ek advanced AI assistant — **Hanuman ji** ki shakti aur **Shree Ram** ki bhakti se prerit.\n\n"
        "**Meri khasiyatein:**\n"
        "- 🕉️ Ramayana, Mahabharata, Gita ki gyan\n"
        "- 🖥️ Windows apps open karna\n"
        "- 🎵 Songs play karna (YouTube/Spotify)\n"
        "- 📝 Notes save karna\n"
        "- 🌐 Web search karna\n"
        "- 🔊 Volume aur system control\n\n"
        "*Jai Hanuman Gyan Gun Sagar!* 🚩"
    )


def build_thanks_response(lang):
    return (
        "🙏 **Shree Ram aapko khush rakhen!**\n\n"
        "Yeh mera param saubhagya hai ki aapki seva kar saka. "
        "Koi aur kaam ho toh zaroor batao. **Jai Bajrang Bali!** 🚩"
    )


# ─── Life Lessons ──────────────────────────────────────────────────────────────
def life_lessons_for(topic, problem, top_n=3):
    data = load_life_data()
    t = (topic or "").strip().lower()
    if t in ("ramayana",):
        items = data.get("ramayana", [])
        display = "Ramayana"
    elif t in ("mahabharata",):
        items = data.get("mahabharata", [])
        display = "Mahabharata"
    elif t in ("gita", "bhagavad gita"):
        items = data.get("gita", [])
        display = "Bhagavad Gita"
    else:
        items = data.get("ramayana", []) + data.get("mahabharata", []) + data.get("gita", [])
        display = "Ramayana/Mahabharata/Gita"

    lines = []
    for i, it in enumerate(items[:top_n]):
        source = it.get("source") or it.get("section") or it.get("book") or "Unknown Source"
        text = it.get("lesson") or it.get("life_lesson") or it.get("lifeLesson") or it.get("content") or ""
        if not text:
            continue
        lines.append(f"**{i+1}.** {text}\n   *(Source: {source})*")

    header = f"🕉️ **{display} se Jeevan Ke Sabak**"
    if problem:
        header += f"\n\n*Aapki situation ke liye: \"{problem}\"*"
    if lines:
        return header + "\n\n" + "\n\n".join(lines) + "\n\n🙏 *Jai Shree Ram! Har mushkil mein dharma ka raasta sabse sahi hai.*", len(lines)
    return header + "\n\nIs topic ke liye koi lesson nahi mila abhi.", 0


# ─── Execute Tool Call ─────────────────────────────────────────────────────────
def execute_tool_call(fname, args):
    """Execute a single tool call and return result message."""
    if fname == "open_app":
        _, m = open_app(args.get("app_cmd", ""), args.get("app_name", ""))
        return m
    elif fname == "play_song_external":
        _, m = play_song_external(args.get("song", ""), args.get("platform", "youtube"))
        return m
    elif fname == "system_control":
        _, m = system_control(args.get("action", ""))
        return m
    elif fname == "system_diagnostic":
        return system_diagnostic(args.get("action", ""))
    elif fname == "manage_notes":
        return manage_notes(args.get("action", "read"), args.get("content", ""))
    elif fname == "get_weather":
        return get_weather(args.get("location", ""))
    return ""


def process_tool_calls_ollama(t_calls):
    """Process Ollama-format tool calls."""
    results = []
    for tc in t_calls:
        func = tc.get("function", {})
        fname = func.get("name", "")
        args = func.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        m = execute_tool_call(fname, args)
        if m:
            results.append(m)
    return results


# Known tool function names
_TOOL_NAMES = {"play_song_external", "open_app", "system_control",
               "system_diagnostic", "manage_notes", "get_weather"}


def _extract_json_objects(text):
    """Extract all valid top-level JSON objects/arrays using balanced brace parsing."""
    results = []
    i = 0
    while i < len(text):
        if text[i] in ('{', '['):
            depth = 0
            start = i
            in_str = False
            escape = False
            for j, ch in enumerate(text[i:], start=i):
                if escape:
                    escape = False
                    continue
                if ch == '\\' and in_str:
                    escape = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch in ('{', '['):
                    depth += 1
                elif ch in ('}', ']'):
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:j + 1]
                        try:
                            results.append(json.loads(candidate))
                        except Exception:
                            pass
                        i = j + 1
                        break
            else:
                i += 1
        else:
            i += 1
    return results


def extract_leaked_tool_calls(text):
    """
    Some Ollama models (llama3.2, mistral etc.) can't do native tool calling
    and instead dump raw JSON tool call objects into their text response.
    This function detects that pattern and executes the tool, returning a
    clean action message — or None if no tool call is found.

    Handles formats:
      {"name": "play_song_external", "parameters": {...}}
      [{"name": "play_song_external", "parameters": {...}}, ...]
      <tool_call>{"name": ..., "parameters": {...}}</tool_call>
      JSON Response\n{"name": ...}
    """
    if not text:
        return None
    # Strip XML-style tool_call wrappers and leading labels like "JSON Response"
    cleaned = re.sub(r"<tool_call>|</tool_call>|<\|tool_call\|>", "", text).strip()

    objects = _extract_json_objects(cleaned)
    for obj in objects:
        calls = obj if isinstance(obj, list) else [obj]
        found_tool = False
        results = []
        for call in calls:
            if not isinstance(call, dict):
                continue
            fname = call.get("name") or call.get("function", {}).get("name", "")
            if fname not in _TOOL_NAMES:
                continue
            found_tool = True
            args = call.get("parameters") or call.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            m = execute_tool_call(fname, args)
            if m:
                results.append(m)
        if found_tool:
            return "\n".join(results) if results else None
    return None


def process_tool_calls_groq(t_calls):
    """Process Groq-format tool calls."""
    results = []
    for tc in t_calls:
        fname = tc.get("function", {}).get("name", "")
        raw_args = tc.get("function", {}).get("arguments", "{}")
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except Exception:
            args = {}
        m = execute_tool_call(fname, args)
        if m:
            results.append(m)
    return results


# ─── Main Chat Processor ────────────────────────────────────────────────────────
def process_chat(user_text, session_id="default"):
    cfg = load_config()
    groq_key = cfg.get("GROQ_API_KEY", "")
    hf_key = cfg.get("HUGGINGFACE_API_KEY", "")

    lang = detect_language(user_text)
    intent = detect_intent(user_text)

    # Quick intent handlers
    if intent == "greeting":
        return build_greeting_response(lang), "greeting", []
    if intent == "introduction":
        return build_introduction_response(lang), "introduction", []
    if intent == "thanks":
        return build_thanks_response(lang), "thanks", []
    if intent == "life_lesson":
        topic = ""
        lt = user_text.lower()
        if "ramayana" in lt:
            topic = "Ramayana"
        elif "mahabharata" in lt:
            topic = "Mahabharata"
        elif "gita" in lt:
            topic = "Gita"
        result, count = life_lessons_for(topic, user_text, top_n=3)
        if count > 0:
            return result, "life_lesson", []

    # Manual action detection (before AI call)
    action_type, action_value, action_name = detect_action(user_text)
    if action_type:
        if action_type == "multi_action":
            results = []
            for atype, aval, aname in action_value:
                m = ""
                if atype == "open_app":
                    _, m = open_app(aval, aname)
                elif atype == "play_song":
                    _, m = play_song_external(aname, aval)
                elif atype == "system_control":
                    _, m = system_control(aval)
                elif atype == "system_diagnostic":
                    m = system_diagnostic(aval)
                elif atype == "manage_notes":
                    m = manage_notes(aval, aname)
                elif atype == "get_weather":
                    m = get_weather(aval)
                if m:
                    results.append(m)
            if results:
                return "\n".join(results), "action_multi", []
        else:
            m = ""
            if action_type == "open_app":
                _, m = open_app(action_value, action_name)
            elif action_type == "play_song":
                _, m = play_song_external(action_name, action_value)
            elif action_type == "system_control":
                _, m = system_control(action_value)
            elif action_type == "system_diagnostic":
                m = system_diagnostic(action_value)
            elif action_type == "manage_notes":
                m = manage_notes(action_value, action_name)
            elif action_type == "get_weather":
                m = get_weather(action_value)
            if m:
                return m, f"action_{action_type}", []

    history = memory.get_history(session_id)

    # Web search if needed
    search_context = ""
    web_results = []
    if needs_search(user_text):
        web_results = search_all(user_text, num_results=5)
        if web_results:
            search_context = "\n\nYeh current web information hai is query ke liye:\n"
            for i, r in enumerate(web_results, 1):
                search_context += f"[{i}] {r.get('text', '')} (Source: {r.get('url', '')})\n"

    # Mode check (with strip fix applied)
    current_mode = cfg.get("MODE", "devotional").strip()

    # Mode switch commands
    lt = user_text.lower()
    if any(w in lt for w in ["switch to ai mode", "activate ai mode", "chatgpt mode", "standard mode"]):
        cfg["MODE"] = "standard"
        save_config(cfg)
        return "🤖 **Standard AI Mode activate ho gaya!** Ab main professional aur technical tarike se help karunga. Kya chahiye?", "mode_switch", []
    if any(w in lt for w in ["switch to devotional mode", "activate devotional mode", "bajrangi mode", "bhakti mode"]):
        cfg["MODE"] = "devotional"
        save_config(cfg)
        return "🕉️ **Devotional Mode activate ho gaya!** Jai Bajrangi! Ab main aapko aatmik aur vyavaharik dono taraf se guide karunga. 🙏", "mode_switch", []

    system_prompt = DEVOTIONAL_PROMPT if current_mode == "devotional" else STANDARD_PROMPT

    # Internal knowledge lookup (case-insensitive, fuzzy)
    lower_text = user_text.lower()
    matched_key = None
    for key in INTERNAL_KNOWLEDGE.keys():
        if key in lower_text:
            matched_key = key
            break
        matches = difflib.get_close_matches(key, lower_text.split(), n=1, cutoff=0.75)
        if matches:
            matched_key = key
            break

    if matched_key:
        val = INTERNAL_KNOWLEDGE[matched_key]
        if current_mode == "devotional":
            return f"🙏 **Bajrangi bata raha hai:**\n\n{val}\n\n*Jai Shree Ram! Is gyan se aapka path roshan ho.* 🚩", "internal_knowledge", []
        else:
            return f"🤖 **[Bajrangi AI — Knowledge Base]**\n\n{val}", "internal_knowledge_pro", []

    # Build messages for AI
    messages = [{"role": "system", "content": system_prompt}] + history
    if search_context:
        messages.append({"role": "system", "content": f"Current web data (use this for accurate answer):{search_context}"})
    messages.append({"role": "user", "content": user_text})

    # ── PRIORITY 1: Ollama (LOCAL — PRIMARY) ──────────────────────────────────
    resp, t_calls, status = ollama_chat(messages, tools=AURA_TOOLS)
    if status == "ok":
        # Case A: Ollama returned proper structured tool_calls
        if t_calls:
            results = process_tool_calls_ollama(t_calls)
            if results:
                return "\n".join(results), "action_ollama_tool", []

        resp_clean = (resp or "").strip()

        # Case B: Ollama dumped raw JSON tool call inside plain text (llama3.2 quirk)
        leaked = extract_leaked_tool_calls(resp_clean)
        if leaked:
            return leaked, "action_ollama_tool", []

        # Case C: Normal text response
        memory.add_message(session_id, "user", user_text)
        if resp_clean:
            memory.add_message(session_id, "assistant", resp_clean)
        return resp_clean or "🙏 Thoda aur detail mein batao, main samjhunga!", "ollama", web_results

    # ── PRIORITY 2: Groq (CLOUD FALLBACK 1) ──────────────────────────────────
    if groq_key:
        resp, t_calls, status = groq_chat(messages, groq_key, tools=AURA_TOOLS)
        if status == "ok":
            if t_calls:
                results = process_tool_calls_groq(t_calls)
                if results:
                    return "\n".join(results), "action_groq_tool", []
            resp_clean = (resp or "").strip()
            leaked = extract_leaked_tool_calls(resp_clean)
            if leaked:
                return leaked, "action_groq_tool", []
            memory.add_message(session_id, "user", user_text)
            if resp_clean:
                memory.add_message(session_id, "assistant", resp_clean)
            return resp_clean or "🙏 Thoda aur detail mein batao!", "groq", web_results

    # ── PRIORITY 3: HuggingFace (CLOUD FALLBACK 2) ───────────────────────────
    if hf_key:
        resp, status = huggingface_chat(user_text, hf_key)
        if resp and status == "ok":
            memory.add_message(session_id, "user", user_text)
            memory.add_message(session_id, "assistant", resp)
            return resp, "hf", web_results

    # ── FINAL FALLBACK ────────────────────────────────────────────────────────
    if web_results:
        summary = "\n".join([f"• {r['text']}" for r in web_results[:3]])
        prefix = "🙏 Web se mila jawab:" if current_mode == "devotional" else "🤖 [Web Search Result]:"
        return f"{prefix}\n\n{summary}", "search_fallback", web_results

    ollama_hint = f"Ollama status: {test_ollama()} — `ollama serve` chalakar Ollama start karo."
    if current_mode == "devotional":
        return (
            f"🙏 **Bajrangi — Temporary Offline:**\n\n"
            f"Main abhi AI backends se connect nahi ho pa raha. "
            f"Yeh kaam toh kar sakta hoon:\n\n"
            f"- **Apps open karna**: 'Chrome kholo', 'Calculator open karo'\n"
            f"- **Notes**: 'Note kar lo milk lena hai'\n"
            f"- **Scriptures**: 'Gita ke baare mein batao'\n\n"
            f"*{ollama_hint}* 🙏"
        ), "fallback", web_results
    else:
        return (
            f"🤖 **Bajrangi — Backend Offline:**\n\n"
            f"AI API connect nahi hua. System functions active hain.\n"
            f"*{ollama_hint}*"
        ), "fallback", web_results


# ─── HTTP Request Handler ───────────────────────────────────────────────────────
class RequestHandler(BaseHTTPRequestHandler):
    def _set_json_headers(self, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def _get_client_id(self):
        return self.client_address[0]

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        client_id = self._get_client_id()
        if not rate_limiter.is_allowed(client_id):
            self._set_json_headers(429)
            self.wfile.write(json.dumps({"error": "Rate limit ho gayi. Thodi der baad try karo."}).encode())
            return

        parsed = urlparse(self.path)

        # /chat
        if parsed.path == "/chat":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
                return
            text = payload.get("text", "").strip()
            if not text:
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"error": "Empty text"}).encode())
                return
            session_id = payload.get("session_id", client_id)
            try:
                resp, source, web_results = process_chat(text, session_id)
                self._set_json_headers(200)
                self.wfile.write(json.dumps({
                    "response": resp, "source": source,
                    "web_results": web_results,
                    "timestamp": datetime.now().isoformat(),
                }).encode())
            except Exception as e:
                self._set_json_headers(500)
                self.wfile.write(json.dumps({"error": "Internal Server Error", "detail": str(e)}).encode())
            return

        # /transcribe (Groq Whisper)
        if parsed.path == "/transcribe":
            length = int(self.headers.get("Content-Length", 0))
            audio_data = self.rfile.read(length)
            config = load_config()
            groq_key = config.get("GROQ_API_KEY", "")
            if not groq_key:
                self._set_json_headers(401)
                self.wfile.write(json.dumps({"error": "Groq API key set nahi hai."}).encode())
                return
            headers = {"Authorization": f"Bearer {groq_key}"}
            files = {"file": ("audio.webm", audio_data, "audio/webm")}
            data = {"model": "whisper-large-v3-turbo"}
            try:
                r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions",
                                  headers=headers, files=files, data=data)
                self._set_json_headers(r.status_code)
                self.wfile.write(r.content)
            except Exception as e:
                self._set_json_headers(500)
                self.wfile.write(json.dumps({"error": "Whisper API error"}).encode())
            return

        # /life-lesson
        if parsed.path == "/life-lesson":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
                return
            topic = payload.get("topic", "")
            problem = payload.get("problem", "")
            life_text, count = life_lessons_for(topic, problem, top_n=3)
            self._set_json_headers(200)
            self.wfile.write(json.dumps({
                "response": life_text, "lesson_count": count,
                "timestamp": datetime.now().isoformat(),
            }).encode())
            return

        # /config (POST — save)
        if parsed.path == "/config":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
                return
            action = payload.get("action", "get")
            if action == "save":
                new_cfg = payload.get("config", {})
                current_cfg = load_config()
                for k, v in new_cfg.items():
                    if v != "••••••••":
                        current_cfg[k] = v
                try:
                    save_config(current_cfg)
                    self._set_json_headers(200)
                    self.wfile.write(json.dumps({"status": "saved"}).encode())
                except Exception as e:
                    self._set_json_headers(500)
                    self.wfile.write(json.dumps({"error": str(e)}).encode())
                return
            self._set_json_headers(400)
            self.wfile.write(json.dumps({"error": "Unknown action"}).encode())
            return

        # /clear-session
        if parsed.path == "/clear-session":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {}
            session_id = payload.get("session_id", client_id)
            memory.clear_session(session_id)
            self._set_json_headers(200)
            self.wfile.write(json.dumps({"status": "cleared"}).encode())
            return

        # /action
        if parsed.path == "/action":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
                return
            action_type = payload.get("action_type", "")
            action_value = payload.get("action_value", "")
            action_name = payload.get("action_name", "")
            # Whitelist action types to prevent injection
            allowed_types = {"open_app", "play_song"}
            if action_type not in allowed_types:
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"error": "Unknown action type"}).encode())
                return
            if action_type == "open_app":
                success, msg = open_app(action_value, action_name)
                self._set_json_headers(200)
                self.wfile.write(json.dumps({"success": success, "message": msg}).encode())
            elif action_type == "play_song":
                self._set_json_headers(200)
                self.wfile.write(json.dumps({"success": True, "message": f"Playing {action_name}", "song": action_value}).encode())
            return

        self._set_json_headers(404)
        self.wfile.write(json.dumps({"error": "Not Found"}).encode())

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/index.html"):
            p = Path("index.html")
            if p.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(p.read_bytes())
                return
            self._set_json_headers(500)
            self.wfile.write(json.dumps({"error": "Index not found"}).encode())
            return

        if parsed.path == "/health":
            self._set_json_headers(200)
            self.wfile.write(json.dumps({
                "status": "healthy", "sessions": len(memory.sessions),
                "timestamp": datetime.now().isoformat(),
            }).encode())
            return

        if parsed.path == "/ai-status":
            self._set_json_headers(200)
            self.wfile.write(json.dumps(ai_status()).encode())
            return

        if parsed.path == "/ollama-models":
            models = ollama_list_models()
            self._set_json_headers(200)
            self.wfile.write(json.dumps({"models": models}).encode())
            return

        if parsed.path == "/config":
            cfg = load_config()
            safe_cfg = {
                "GROQ_API_KEY": "set" if cfg.get("GROQ_API_KEY") else "not_set",
                "HUGGINGFACE_API_KEY": "set" if cfg.get("HUGGINGFACE_API_KEY") else "not_set",
                "TAVILY_API_KEY": "set" if cfg.get("TAVILY_API_KEY") else "not_set",
                "OLLAMA_ENABLED": cfg.get("OLLAMA_ENABLED", True),
                "OLLAMA_MODEL": cfg.get("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL),
                "OLLAMA_URL": cfg.get("OLLAMA_URL", OLLAMA_API_URL),
                "MODE": cfg.get("MODE", "devotional"),
            }
            self._set_json_headers(200)
            self.wfile.write(json.dumps(safe_cfg).encode())
            return

        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # Static files
        ext_type_map = {
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml", ".ico": "image/x-icon",
        }
        p = Path(parsed.path.lstrip("/"))
        suffix = p.suffix.lower()
        if suffix in ext_type_map and p.exists():
            self.send_response(200)
            self.send_header("Content-Type", ext_type_map[suffix])
            self.end_headers()
            self.wfile.write(p.read_bytes())
            return

        self._set_json_headers(404)
        self.wfile.write(json.dumps({"error": "NotFound"}).encode())

    def log_message(self, format, *args):
        return  # Suppress default logs


# ─── Server Start ───────────────────────────────────────────────────────────────
def run_server(port=8000):
    httpd = HTTPServer(("0.0.0.0", port), RequestHandler)
    print(f"🚩 Bajrang Aura server chal raha hai: http://0.0.0.0:{port}")
    print(f"📡 Endpoints: /chat, /life-lesson, /config, /health, /clear-session, /ollama-models, /ai-status")

    ollama_st = test_ollama()
    if ollama_st == "ok":
        models = ollama_list_models()
        cfg = load_config()
        print(f"✅ Ollama PRIMARY backend: ONLINE (model: {cfg.get('OLLAMA_MODEL', OLLAMA_DEFAULT_MODEL)})")
        print(f"   Available models: {', '.join(models[:5])}")
    else:
        print(f"⚠️  Ollama PRIMARY backend: OFFLINE ({ollama_st})")
        print(f"   Groq/HF fallback use hoga. Ollama ke liye: ollama serve")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🙏 Server band ho raha hai... Jai Shree Ram!")
        httpd.shutdown()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    run_server(port=port)
