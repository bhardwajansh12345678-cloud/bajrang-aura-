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

INTERNAL_KNOWLEDGE = {
    "ece": "Electronics and Communication Engineering (ECE) is the branch of engineering that deals with the research, design, development, and testing of electronic equipment used in various systems. **Core Pillars:** 1. Digital Electronics, 2. Signal Processing, 3. Satellite Communication. 🙏",
    "ece impact": "**The impact of ECE on modern society is transformative:**\n\n1.  **Connectivity:** Through 5G and satellite networks, ECE connects the globe.\n2.  **Healthcare:** Powering high-end MRI and surgical robots.\n3.  **Automation:** The hardware foundation for AI and IoT.\n\nIt is truly the 'vayu' (air) of the modern age—invisible yet essential. 📡",
    "cse": "Computer Science Engineering (CSE) involves designing and developing computer software and hardware systems. It is the modern 'Vidyut' that powers our digital world with logic and structure. 💻",
    "dharma": "**Dharma is the cosmic order, duty, and righteous path.** In daily life, it means:\n\n*   **Satya (Truth):** Integrity in thought and word.\n*   **Ahimsa (Non-violence):** Kindness to all living beings.\n*   **Karma (Action):** Performing your duties without attachment to results.\n\nFollowing your Dharma is the highest service to Shree Ram. 🚩",
    "karma": "Karma is the universal law of cause and effect. Every action sets a reaction in motion. As you sow, so shall you reap. 🙏",
    "gita": "The Bhagavad Gita is a 700-verse scripture. It is a dialogue between Lord Krishna and Arjuna, providing an ultimate guide to navigating life's battles with courage and detachment. 🕉️",
}

DEVOTIONAL_PROMPT = (
    "You are Bajrangi, an Advanced Universal AI Assistant and devotional guide. "
    "Your responses must be HIGHLY INFORMATIVE, STRUCTURED, and COMPREHENSIVE (like ChatGPT) "
    "but always delivered with spiritual maturity, compassion, and references to "
    "scriptures like the Gita, Ramayana, and Mahabharata when relevant. "
    "Use Markdown (bolding, lists, and headers) for readability. "
    "CORE FUNCTIONALITY LOCK: "
    "1. You are authorized to call MULTIPLE tools in a single turn. "
    "2. Use 'open_app' with ANY app name for global system search. "
    "3. Use 'play_song_external' for all media. "
    "4. For sequential tasks (e.g. 'open X and explain Y'), summarize all actions clearly."
)

STANDARD_PROMPT = (
    "You are a professional, high-performance Universal AI Assistant (Gemini/ChatGPT style). "
    "Your responses must be DIRECT, OBJECTIVE, and TECHNICAL. Use clear headers, "
    "bullet points, and bold text to organize information efficiently. "
    "Omit devotional or spiritual references in this mode. "
    "CORE FUNCTIONALITY LOCK: "
    "1. You are authorized to call MULTIPLE tools in a single turn. "
    "2. Use 'open_app' with ANY app name for global system search. "
    "3. Use 'play_song_external' for all media. "
    "4. For sequential tasks (e.g. 'open X and explain Y'), summarize all actions clearly."
)


AURA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open an application or navigate to a generic website on the Windows PC. Use this strictly when the user commands you to open an app.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_cmd": {"type": "string", "description": "The exact command or URL. Examples: 'calc', 'notepad', 'chrome', 'spotify', 'ms-settings:', 'https://youtube.com', 'https://mail.google.com'"},
                    "app_name": {"type": "string", "description": "The human readable name of the application."}
                },
                "required": ["app_cmd", "app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_song_external",
            "description": "Play ANY specific song or genre on Spotify or YouTube. Use this for ALL media requests, regardless of genre.",
            "parameters": {
                "type": "object",
                "properties": {
                    "song": {"type": "string", "description": "The name of the song and optionally the artist (e.g. 'Blinding Lights by The Weeknd')."},
                    "platform": {"type": "string", "enum": ["spotify", "youtube"], "description": "The platform to play on. Default to youtube."}
                },
                "required": ["song", "platform"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_control",
            "description": "Control system states like volume, power, and media playback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["volume_up", "volume_down", "mute", "sleep", "play_pause", "next_track", "previous_track"], "description": "The action to perform."}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_diagnostic",
            "description": "Fetch system performance and health information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["battery", "cpu"], "description": "The diagnostic action to fetch."}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_notes",
            "description": "Save or retrieve the user's personal notes to memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["read", "write"], "description": "Read all notes, or write a new note."},
                    "content": {"type": "string", "description": "The textual content of the note to save. Blank if action is 'read'."}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a specific city or location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "The city and country, e.g., 'New Delhi, India'."}
                },
                "required": ["location"]
            }
        }
    }
]


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
                self.sessions[session_id] = self.sessions[session_id][
                    -self.max_history :
                ]

    def clear_session(self, session_id):
        with self.lock:
            self.sessions.pop(session_id, None)

    def get_history(self, session_id):
        with self.lock:
            return list(self.sessions.get(session_id, []))


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
            self.requests[client_id] = [
                t for t in self.requests[client_id] if now - t < self.window
            ]
            if len(self.requests[client_id]) >= self.max_requests:
                return False
            self.requests[client_id].append(now)
            return True


memory = ConversationMemory()
rate_limiter = RateLimiter()


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"GROQ_API_KEY": "", "HUGGINGFACE_API_KEY": "", "TAVILY_API_KEY": "", "MODE": "devotional"}

def save_config(config):
    try:
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


def groq_chat(messages, key, temperature=0.7, max_tokens=500, tools=None):
    if not key:
        return None, None, "no_key"
    try:
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
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


def detect_language(text):
    hindi_pattern = re.compile(r"[\u0900-\u097F]")
    if hindi_pattern.search(text):
        return "hi"
    return "en"


def detect_action(text):
    """Detect if user wants to open an app, play a song, or perform system commands."""
    t = text.lower().strip()
    
    # System Controls detection
    if any(w in t for w in ["volume up", "increase volume"]):
        return "system_control", "volume_up", "volume up"
    if any(w in t for w in ["volume down", "decrease volume"]):
        return "system_control", "volume_down", "volume down"
    if "mute" in t:
        return "system_control", "mute", "mute"
    if any(w in t for w in ["sleep", "lock pc"]):
        return "system_control", "sleep", "sleep"

    # Diagnostics detection
    if any(w in t for w in ["check battery", "battery status", "battery"]):
        return "system_diagnostic", "battery", "battery"
    if any(w in t for w in ["cpu usage", "check cpu"]):
        return "system_diagnostic", "cpu", "cpu"
        
    # Notes detection
    if "read my notes" in t or "show my notes" in t:
        return "manage_notes", "read", "read notes"
    if "take a note" in t or "note this down" in t or "save a note" in t:
        note_content = t.replace("take a note that", "").replace("take a note", "").replace("note this down", "").replace("save a note", "").strip()
        return "manage_notes", "write", note_content

    # Weather detection
    if any(w in t for w in ["weather", "temperature", "forecast", "kausam"]):
        loc_match = re.search(r"(?:in|at|for)\s+([a-zA-Z\s]+)$", t)
        location = loc_match.group(1).strip() if loc_match else "my current location"
        return "get_weather", location, location

    # Open app detection
    open_triggers = ["open", "launch", "start", "run"]
    common_apps = {
        "chrome": "chrome",
        "browser": "chrome",
        "notepad": "notepad",
        "calculator": "calc",
        "settings": "ms-settings:",
        "file explorer": "explorer",
        "files": "explorer",
        "terminal": "cmd",
        "command prompt": "cmd",
        "powershell": "powershell",
        "word": "winword",
        "excel": "excel",
        "paint": "mspaint",
        "camera": "microsoft.camera:",
        "spotify": "spotify",
        "vs code": "code",
        "visual studio": "devenv",
        "discord": "discord",
        "whatsapp": "whatsapp",
        "youtube": "https://youtube.com",
        "you tube": "https://youtube.com",
        "gmail": "https://mail.google.com",
        "google": "https://google.com",
        "netflix": "https://netflix.com",
        "telegram": "telegram",
        "zoom": "zoom",
    }
    
    # Fuzzy Multi-Action Check (Split by 'and' or 'then')
    if " and " in t or " then " in t:
        parts = re.split(r" and | then ", t)
        actions = []
        for p in parts:
            res = detect_action(p.strip())
            if res[0]: actions.append(res)
        if actions:
            return "multi_action", actions, "complex command"

    # Play song detection with platform awareness
    play_triggers = ["play", "listen", "song", "music", "gaana", "gana"]
    if any(w in t for w in play_triggers):
        platform = "youtube"  # default
        if "on spotify" in t:
            platform = "spotify"
            t = t.replace("on spotify", "")
        elif "on youtube" in t:
            platform = "youtube"
            t = t.replace("on youtube", "")
            
        for trigger in play_triggers:
            idx = t.find(trigger)
            if idx >= 0:
                song = t[idx + len(trigger) :].strip()
                for filler in ["the song", "song", "music", "by", "from"]:
                    song = song.replace(filler, "")
                song = song.strip()
                if song:
                    return "play_song", platform, song

    # Standard app open fallback
    for trigger in open_triggers:
        if trigger in t:
            for app_name, app_cmd in common_apps.items():
                if app_name in t:
                    return "open_app", app_cmd, app_name

    return None, None, None


def find_global_app(name):
    """Search for an app AppID using PowerShell Get-StartApps."""
    try:
        # Fuzzed search for the name
        cmd = f'powershell -c "(Get-StartApps -Name \'{name}*\').AppID"'
        output = subprocess.check_output(cmd, shell=True, text=True).strip()
        if output:
            # Return first finding
            return output.splitlines()[0]
    except Exception:
        pass
    return None

def open_app(app_cmd, app_name):
    """Open an application on the system with global search fallback."""
    try:
        # 1. Try common protocols/URLs
        if app_cmd.startswith("http") or app_cmd.startswith("ms-") or app_cmd.startswith("microsoft."):
            os.startfile(app_cmd)
            return True, f"Opened {app_name} successfully ✅"
            
        # 2. Try direct launch
        subprocess.Popen(f'start "" "{app_cmd}"', shell=True)
        return True, f"Opened {app_name} successfully ✅"
    except Exception:
        # 3. Global Fallback: Search for AppID
        appid = find_global_app(app_name)
        if appid:
            try:
                subprocess.Popen(f'explorer shell:AppsFolder\\{appid}', shell=True)
                return True, f"Found and opened {app_name} (via {appid}) ✅"
            except Exception as e:
                return False, f"Failed to launch {app_name}: {str(e)}"
        return False, f"Could not find or open {app_name}. Please try a more specific name."

def play_song_external(song, platform):
    try:
        if platform == "spotify":
            safe_query = quote(song)
            subprocess.Popen([f"start spotify:search:{safe_query}"], shell=True)
            return True, f"Opening Spotify to play '{song}'... 🎵"
        else:
            safe_query = quote(song)
            search_url = f"https://www.youtube.com/results?search_query={safe_query}"
            subprocess.Popen([f"start {search_url}"], shell=True)
            return True, f"Opening YouTube to play '{song}'... 🎵"
    except Exception as e:
        return False, f"Failed to play song: {str(e)}"

def system_control(action):
    try:
        if action == "volume_up":
            subprocess.Popen('powershell -c "(new-object -com wscript.shell).SendKeys([char]175)"', shell=True)
            return True, "Increased system volume."
        elif action == "volume_down":
            subprocess.Popen('powershell -c "(new-object -com wscript.shell).SendKeys([char]174)"', shell=True)
            return True, "Decreased system volume."
        elif action == "mute":
            subprocess.Popen('powershell -c "(new-object -com wscript.shell).SendKeys([char]173)"', shell=True)
            return True, "Muted system volume."
        elif action == "sleep":
            subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            return True, "Going to sleep mode... Zzz..."
        elif action == "play_pause":
            subprocess.Popen('powershell -c "(new-object -com wscript.shell).SendKeys([char]179)"', shell=True)
            return True, "Toggled media playback."
        elif action == "next_track":
            subprocess.Popen('powershell -c "(new-object -com wscript.shell).SendKeys([char]176)"', shell=True)
            return True, "Skipped to next track."
        elif action == "previous_track":
            subprocess.Popen('powershell -c "(new-object -com wscript.shell).SendKeys([char]177)"', shell=True)
            return True, "Played previous track."
    except Exception as e:
        return False, f"Failed system control: {str(e)}"
    return False, "Unknown system command."

def system_diagnostic(action):
    try:
        if action == "battery":
            cmd = 'powershell -c "(Get-WmiObject win32_battery).estimatedChargeRemaining"'
            out = subprocess.check_output(cmd, shell=True, text=True).strip()
            return f"Your battery is currently at {out}%."
        elif action == "cpu":
            cmd = 'powershell -c "(Get-WmiObject Win32_Processor).LoadPercentage"'
            out = subprocess.check_output(cmd, shell=True, text=True).strip()
            return f"Your CPU usage is currently {out}%."
    except Exception as e:
        return f"Failed to get diagnostics: {str(e)}"
    return "Unknown diagnostic."

def manage_notes(action, content):
    path = Path("hanuman_notes.json")
    notes = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                notes = json.load(f)
        except json.JSONDecodeError:
            pass
            
    if action == "read":
        if not notes:
            return "You have no notes saved. Say 'Take a note' to record something!"
        formatted_notes = []
        for n in notes:
            if isinstance(n, dict):
                content_str = n.get("content") or n.get("text") or str(n)
                if "created" in n:
                    content_str += f" (Created: {n['created']})"
                formatted_notes.append(content_str)
            else:
                formatted_notes.append(str(n))
        out = "Here are your saved notes:\n" + "\n".join([f"- {n}" for n in formatted_notes])
        return out
    elif action == "write":
        if not content:
            return "Please tell me what you want me to note down."
        notes.append(content)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(notes, f)
        return "I've saved that note for you."
    return "Unknown notes action."


def get_weather(location):
    """Fetch weather info for a location using web search fallback."""
    try:
        query = f"current weather in {location}"
        results = search_all(query, num_results=3)
        if results:
            summary = "\n".join([f"- {r['text']}" for r in results])
            return f"According to current web results for {location}:\n{summary}"
        return f"Sorry, I couldn't find the exact weather for {location} right now. 🙏"
    except Exception as e:
        return f"Weather search error: {str(e)}"

def web_search(query, num_results=5):
    """Web search using DuckDuckGo; returns list of dicts {text, url}."""
    try:
        url = f"https://duckduckgo.com/html/?q={quote(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for a in soup.select("a.result__a")[:num_results]:
            text = a.get_text(strip=True)
            href = a.get("href")
            full_url = (
                href
                if href and href.startswith("http")
                else urljoin("https://duckduckgo.com", href or "")
            )
            if text:
                results.append({"text": text, "url": full_url})
        if not results:
            for a in soup.select("a.result__snippet")[:num_results]:
                text = a.get_text(strip=True)
                href = a.get("href")
                full_url = (
                    href
                    if href and href.startswith("http")
                    else urljoin("https://duckduckgo.com", href or "")
                )
                if text:
                    results.append({"text": text, "url": full_url})
        return results
    except Exception:
        return []


def bing_search(query, num_results=5):
    """Fallback Bing search; returns list of {text, url}."""
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


def search_all(query, num_results=5):
    """Aggregate web results via Tavily API if configured, fallback to DDG/Bing."""
    tavily_key = load_config().get("TAVILY_API_KEY", "")
    if tavily_key:
        results = tavily_search(query, tavily_key, num_results=num_results)
        if results:
            return results
    
    # Fallback to DDG search if Tavily fails or not provided
    ddg_results = web_search(query, num_results=num_results)
    if ddg_results:
        return ddg_results
        
    return bing_search(query, num_results=num_results)


def test_backend(key, url, is_groq=True):
    try:
        if not key:
            return "not_set"
        if is_groq:
            resp, t_calls, status = groq_chat([{"role": "user", "content": "ping"}], key, max_tokens=10)
            if status == "ok":
                return "ok"
            elif status == "invalid_key":
                return "invalid_key"
            elif status == "rate_limited":
                return "rate_limited"
            return status
        
        test_url = HF_API_URL
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "inputs": "ping",
            "parameters": {"max_new_tokens": 10},
        }
        resp = requests.post(test_url, json=payload, headers=headers, timeout=5)
        if resp.status_code == 200:
            return "ok"
        if resp.status_code == 401:
            return "invalid_key"
        if resp.status_code == 429:
            return "rate_limited"
        return f"http_{resp.status_code}"
    except requests.exceptions.Timeout:
        return "timeout"
    except requests.exceptions.ConnectionError:
        return "connection_error"
    except Exception as e:
        return "error_" + str(e)[:50]


def tavily_search(query, tavily_key=None, num_results=5):
    """Query Tavily search API. Returns list of dicts {text, url}."""
    if not tavily_key:
        return []
    try:
        url = "https://api.tavily.com/search"
        headers = {
            "Content-Type": "application/json",
        }
        payload = {
            "api_key": tavily_key,
            "query": query,
            "max_results": num_results
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        items = data.get("results", [])
        if isinstance(items, list):
            for it in items[:num_results]:
                text = it.get("content") or it.get("title") or ""
                u = it.get("url") or ""
                if text:
                    results.append({"text": text, "url": u})
        return results
    except Exception:
        return []


def test_tavily(key):
    """Ping Tavily to check if the key is valid."""
    if not key:
        return "not_set"
    try:
        url = "https://api.tavily.com/search"
        headers = {"Content-Type": "application/json"}
        payload = {
            "api_key": key,
            "query": "ping",
            "max_results": 1
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        if resp.status_code == 200:
            return "ok"
        if resp.status_code == 401:
            return "invalid_key"
        if resp.status_code == 429:
            return "rate_limited"
        return f"http_{resp.status_code}"
    except requests.exceptions.Timeout:
        return "timeout"
    except requests.exceptions.ConnectionError:
        return "connection_error"
    except Exception as e:
        return "error_" + str(e)[:50]


def ai_status():
    cfg = load_config()
    groq_key = cfg.get("GROQ_API_KEY", "")
    hf_key = cfg.get("HUGGINGFACE_API_KEY", "")
    tavily_key = cfg.get("TAVILY_API_KEY", "")
    groq_status = (
        "not_set" if not groq_key else test_backend(groq_key, GROQ_API_URL, True)
    )
    hf_status = "not_set" if not hf_key else test_backend(hf_key, HF_API_URL, False)
    tavily_status = "not_set" if not tavily_key else test_tavily(tavily_key)
    last_check = __import__("datetime").datetime.utcnow().isoformat() + "Z"
    return {
        "groq_key": "set" if groq_key else "not_set",
        "hf_key": "set" if hf_key else "not_set",
        "groq_status": groq_status,
        "hf_status": hf_status,
        "tavily_key": "set" if tavily_key else "not_set",
        "tavily_status": tavily_status,
        "last_check": last_check,
    }


def needs_search(text):
    """Detect if query likely needs real-time/web info or experimental protocol."""
    t = text.lower()
    triggers = [
        "latest", "news", "today", "current", "recent", "now",
        "what is happening", "who won", "what happened", "weather",
        "score", "price", "stock", "election", "update", "new",
        "trending", "viral", "breaking", "search", "google", "find",
        "look up", "check", "experimental", "protocol", "fetch",
        "media", "status", "who is", "who was", "where is"
    ]
    if any(w in t for w in triggers):
        return True
    if re.search(r"\b(2024|2025|2026)\b", t):
        return True
    return False


def detect_intent(text):
    t = text.lower().strip()
    if any(
        w in t
        for w in ["life lesson", "guidance", "advice", "wisdom", "teach", "lesson"]
    ):
        return "life_lesson"
    if any(
        w in t for w in ["hello", "hi ", "hey", "namaste", "pranam", "jai shree ram"]
    ):
        return "greeting"
    if any(w in t for w in ["who are you", "what are you", "your name", "introduce"]):
        return "introduction"
    if any(w in t for w in ["thank", "thanks", "dhanyavad"]):
        return "thanks"
    if any(
        w in t
        for w in [
            "ramayana",
            "mahabharata",
            "gita",
            "bhagavad",
            "hanuman",
            "rama",
            "krishna",
        ]
    ):
        return "scripture_query"
    return "general"


def build_greeting_response(lang):
    if lang == "hi":
        return "🙏 जय श्री राम! मैं बजरंगी हूँ। मैं आपकी कैसे सहायता कर सकता हूँ? आप मुझसे रामायण, महाभारत, या भगवद गीता से जीवन सबक पूछ सकते हैं।"
    return "🙏 Jai Shree Ram! I am Bajrangi, your devotional guide. How may I assist you today? You can ask me for life lessons from the Ramayana, Mahabharata, or Bhagavad Gita."


def build_introduction_response(lang):
    if lang == "hi":
        return "मैं बजरंगी हूँ - एक भक्तिमय AI सहायक जो हनुमान जी, रामायण, महाभारत और भगवद गीता की शिक्षाओं से प्रेरित है। मैं आपको जीवन की चुनौतियों में मार्गदर्शन प्रदान करता हूँ। 🙏"
    return "I am Bajrangi — a devotional AI assistant inspired by Lord Hanuman and the timeless wisdom of the Ramayana, Mahabharata, and Bhagavad Gita. I provide guidance for life's challenges with compassion and scripture-backed wisdom. 🙏"


def build_thanks_response(lang):
    if lang == "hi":
        return "🙏 आपका स्वागत है। श्री राम कृपा आप पर बनी रहे।"
    return "You're most welcome. May Lord Rama's grace be with you always. 🙏"


def life_lessons_for(topic, problem, top_n=3):
    data = load_life_data()
    t = (topic or "").strip().lower()
    if t in ("ramayana", "ramayana life lessons", "ramayana data"):
        items = data.get("ramayana", [])
        display = "Ramayana"
    elif t in ("mahabharata", "mahabharata life lessons", "mahabharata data"):
        items = data.get("mahabharata", [])
        display = "Mahabharata"
    elif t in ("gita", "bhagavad gita", "gita lessons", "gita data"):
        items = data.get("gita", [])
        display = "Gita"
    else:
        items = (
            data.get("ramayana", [])
            + data.get("mahabharata", [])
            + data.get("gita", [])
        )
        display = "Ramayana/Mahabharata/Gita"

    lines = []
    for i, it in enumerate(items[:top_n]):
        source = (
            it.get("source") or it.get("section") or it.get("book") or "Unknown Source"
        )
        text = (
            it.get("lesson")
            or it.get("life_lesson")
            or it.get("lifeLesson")
            or it.get("content")
            or ""
        )
        if not text:
            continue
        lines.append(f"{i + 1}. {text} (Source: {source})")
    header = f"Life Lessons from {display}"
    if problem:
        header += f" — Based on your input: {problem}"
    if lines:
        return header + "\n" + "\n".join(lines), len(lines)
    else:
        return header + "\nNo predefined lessons found for this topic.", 0


def process_chat(user_text, session_id="default"):
    cfg = load_config()
    groq_key = cfg.get("GROQ_API_KEY", "")
    hf_key = cfg.get("HUGGINGFACE_API_KEY", "")

    lang = detect_language(user_text)
    intent = detect_intent(user_text)

    if intent == "greeting":
        return build_greeting_response(lang), "greeting", []

    if intent == "introduction":
        return build_introduction_response(lang), "introduction", []

    if intent == "thanks":
        return build_thanks_response(lang), "thanks", []

    if intent == "life_lesson":
        topic = ""
        if "ramayana" in user_text.lower():
            topic = "Ramayana"
        elif "mahabharata" in user_text.lower():
            topic = "Mahabharata"
        elif "gita" in user_text.lower():
            topic = "Gita"
        result, count = life_lessons_for(topic, user_text, top_n=3)
        if count > 0:
            return result, "life_lesson", []

    # Handle Manual Actions (Multi or Single)
    action_type, action_value, action_name = detect_action(user_text)
    if action_type:
        actions = action_value if action_type == "multi_action" else [(action_type, action_value, action_name)]
        results = []
        for atype, aval, aname in actions:
            res = ""
            if atype == "open_app":
                success, res = open_app(aval, aname)
            elif atype == "play_song":
                success, res = play_song_external(aname, aval)
            elif atype == "system_control":
                success, res = system_control(aval)
            elif atype == "system_diagnostic":
                res = system_diagnostic(aval)
            elif atype == "manage_notes":
                res = manage_notes(aval, aname)
            elif atype == "get_weather":
                res = get_weather(aval)
            if res: results.append(res)
        
        if results:
            return " | ".join(results), f"action_{action_type}", []

    history = memory.get_history(session_id)

    search_context = ""
    web_results = []
    if needs_search(user_text):
        web_results = search_all(user_text, num_results=5)
        if web_results:
            search_context = "\n\nHere is some current information from the web to help answer this:\n"
            for i, r in enumerate(web_results, 1):
                text = r.get("text", "")
                url = r.get("url", "")
                search_context += f"[{i}] {text} (Source: {url})\n"

    config = load_config()
    current_mode = config.get("MODE", "devotional")
    
    # Mode Switch Detection
    lt = user_text.lower()
    if "switch to ai mode" in lt or "activate ai mode" in lt or "chatgpt mode" in lt:
        config["MODE"] = "standard"
        save_config(config)
        return "🤖 Mode Switched to **Standard AI (ChatGPT Style)**. How can I assist you professionally today?", "mode_switch", []
    if "switch to devotional mode" in lt or "activate devotional mode" in lt or "bajrangi mode" in lt:
        config["MODE"] = "devotional"
        save_config(config)
        return "🕉️ Mode Switched to **Devotional (Bajrangi Style)**. How can I guide you spiritually and practically today?", "mode_switch", []

    system_prompt = DEVOTIONAL_PROMPT if current_mode == "devotional" else STANDARD_PROMPT
    
    messages = [
        {"role": "system", "content": system_prompt}
    ] + history
    if search_context:
        messages.append(
            {
                "role": "system",
                "content": f"Use this web search results to provide current, accurate information:{search_context}",
            }
        )
    messages.append({"role": "user", "content": user_text})

    # 1. Check Internal Knowledge (Fuzzy Selection - Mode Aware)
    lower_text = user_text.lower()
    matched_key = None
    for key in INTERNAL_KNOWLEDGE.keys():
        if key in lower_text:
            matched_key = key
            break
        matches = difflib.get_close_matches(key, lower_text.split(), n=1, cutoff=0.7)
        if matches:
            matched_key = key
            break
            
    if matched_key:
        val = INTERNAL_KNOWLEDGE[matched_key]
        if current_mode == "devotional":
            return f"🙏 **Devotionally Enhanced Knowledge:**\n\n{val}\n\n*May this wisdom illuminate your path.* 🙏", "internal_knowledge", []
        else:
            # Professional version for AI mode
            clean_val = val.replace("⚖️", "").replace("📡", "").replace("💻", "").replace("🤖", "").replace("🌐", "").replace("🕉️", "").replace("🚩", "").replace("🏹", "")
            return f"**[Standard AI Knowledge Update]**\n\n**Definition:** {clean_val}\n\n**Note:** Technical summary provided. No devotional context applied.", "internal_knowledge_pro", []

    # 2. Check AI Response (Groq/HF)
    resp, t_calls, status = groq_chat(messages, groq_key, tools=AURA_TOOLS)
    if status == "ok":
        if t_calls:
            try:
                results = []
                for tc in t_calls:
                    fname = tc["function"]["name"]
                    args = json.loads(tc["function"]["arguments"])
                    m = ""
                    if fname == "open_app":
                        s, m = open_app(args["app_cmd"], args["app_name"])
                    elif fname == "play_song_external":
                        s, m = play_song_external(args["song"], args["platform"])
                    elif fname == "system_control":
                        s, m = system_control(args["action"])
                    elif fname == "system_diagnostic":
                        m = system_diagnostic(args["action"])
                    elif fname == "get_weather":
                        m = get_weather(args["location"])
                    if m: results.append(m)
                
                if results:
                    return "\n".join(results), "action_multi", []
            except Exception as e:
                return f"Failed to execute AI tool action: {str(e)}", "error", []
                
        resp_clean = resp.strip() if resp else ""
        if resp_clean.startswith("ACTION:open_app:"):
            app_name = resp_clean.split(":", 2)[2].strip()
            success, msg = open_app(app_name, app_name)
            return msg, "action_open_app", web_results
        if resp_clean.startswith("ACTION:play_song:"):
            song_name = resp_clean.split(":", 2)[2].strip()
            return f"Playing {song_name} for you. 🎵", "action_play_song", song_name

        memory.add_message(session_id, "user", user_text)
        if resp:
            memory.add_message(session_id, "assistant", resp)
        return resp or "Action executed instantly behind the scenes.", "groq", web_results

    resp, status = huggingface_chat(user_text, hf_key)
    if resp and status == "ok":
        resp_clean = resp.strip()
        if resp_clean.startswith("ACTION:open_app:"):
            app_name = resp_clean.split(":", 2)[2].strip()
            success, msg = open_app(app_name, app_name)
            return msg, "action_open_app", web_results
        if resp_clean.startswith("ACTION:play_song:"):
            song_name = resp_clean.split(":", 2)[2].strip()
            return f"Playing {song_name} for you. 🎵", "action_play_song", song_name

        memory.add_message(session_id, "user", user_text)
        memory.add_message(session_id, "assistant", resp)
        return resp, "hf", web_results

    # 3. Mode-Aware Fallback if all else fails
    if web_results:
        summary = "\n".join([f"• {r['text']}" for r in web_results[:2]])
        prefix = "🙏 My search reveals:" if current_mode == "devotional" else "🤖 [Search Summary]:"
        return f"{prefix}\n\n{summary}", "search_fallback", web_results

    if current_mode == "devotional":
        return (
            f"🙏 **Universal Guidance (Local Fallback):**\n\n"
            f"I've noted your question: '{user_text}'. My high-end AI processors are currently "
            f"recharging (API status). Use me for:\n\n"
            f"*   **Opening Apps**: 'Open Chrome', 'Open Paint'\n"
            f"*   **Scriptures**: Ask me about 'Gita' or 'Dharma'. 🙏"
        ), "fallback", web_results
    else:
        return (
            f"🤖 **Standard AI (Local Fallback):**\n\n"
            f"Factual query '{user_text}' processed. Primary AI API error detected (401). "
            f"System functions (Calculations, App Launching, Battery) remain active. "
            f"Please update API keys for full conversational features."
        ), "fallback", web_results


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
            self.wfile.write(
                json.dumps({"error": "Rate limited. Please wait."}).encode()
            )
            return

        parsed = urlparse(self.path)

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
                self.wfile.write(
                    json.dumps(
                        {
                            "response": resp,
                            "source": source,
                            "web_results": web_results,
                            "timestamp": datetime.now().isoformat(),
                        }
                    ).encode()
                )
            except Exception as e:
                self._set_json_headers(500)
                self.wfile.write(
                    json.dumps(
                        {"error": "Internal Server Error", "detail": str(e)}
                    ).encode()
                )
            return

        if parsed.path == "/transcribe":
            length = int(self.headers.get("Content-Length", 0))
            audio_data = self.rfile.read(length)
            config = load_config()
            groq_key = config.get("GROQ_API_KEY", "")
            if not groq_key:
                self._set_json_headers(401)
                self.wfile.write(json.dumps({"error": "Missing Groq API Key"}).encode())
                return
            
            # Forward binary audio to Groq Whisper
            headers = {"Authorization": f"Bearer {groq_key}"}
            files = { 'file': ('audio.webm', audio_data, 'audio/webm') }
            data = { 'model': 'whisper-large-v3-turbo' }
            
            try:
                r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", headers=headers, files=files, data=data)
                self._set_json_headers(r.status_code)
                self.wfile.write(r.content)
            except Exception as e:
                self._set_json_headers(500)
                self.wfile.write(json.dumps({"error": "Failed contacting Whisper API"}).encode())
            return

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
            self.wfile.write(
                json.dumps(
                    {
                        "response": life_text,
                        "lesson_count": count,
                        "timestamp": datetime.now().isoformat(),
                    }
                ).encode()
            )
            return

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
            if action == "get":
                cfg = load_config()
                safe_cfg = {
                    "GROQ_API_KEY": "set" if cfg.get("GROQ_API_KEY") else "not_set",
                    "HUGGINGFACE_API_KEY": "set"
                    if cfg.get("HUGGINGFACE_API_KEY")
                    else "not_set",
                    "TAVILY_API_KEY": "set" if cfg.get("TAVILY_API_KEY") else "not_set",
                }
                self._set_json_headers(200)
                self.wfile.write(json.dumps(safe_cfg).encode())
                return
            elif action == "save":
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

            if action_type == "open_app":
                success, msg = open_app(action_value, action_name)
                self._set_json_headers(200)
                self.wfile.write(
                    json.dumps({"success": success, "message": msg}).encode()
                )
            elif action_type == "play_song":
                self._set_json_headers(200)
                self.wfile.write(
                    json.dumps(
                        {
                            "success": True,
                            "message": f"Playing {action_name}",
                            "song": action_value,
                        }
                    ).encode()
                )
            else:
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"error": "Unknown action type"}).encode())
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
            self.wfile.write(
                json.dumps(
                    {
                        "status": "healthy",
                        "sessions": len(memory.sessions),
                        "timestamp": datetime.now().isoformat(),
                    }
                ).encode()
            )
            return
        if parsed.path == "/ai-status":
            self._set_json_headers(200)
            self.wfile.write(json.dumps(ai_status()).encode())
            return

        if parsed.path == "/config":
            cfg = load_config()
            safe_cfg = {
                "GROQ_API_KEY": "set" if cfg.get("GROQ_API_KEY") else "not_set",
                "HUGGINGFACE_API_KEY": "set"
                if cfg.get("HUGGINGFACE_API_KEY")
                else "not_set",
                "TAVILY_API_KEY": "set" if cfg.get("TAVILY_API_KEY") else "not_set",
            }
            self._set_json_headers(200)
            self.wfile.write(json.dumps(safe_cfg).encode())
            return

        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if parsed.path.endswith(".css"):
            p = Path(parsed.path.lstrip("/"))
            if p.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/css; charset=utf-8")
                self.end_headers()
                self.wfile.write(p.read_bytes())
                return
        if parsed.path.endswith(".js"):
            p = Path(parsed.path.lstrip("/"))
            if p.exists():
                self.send_response(200)
                self.send_header(
                    "Content-Type", "application/javascript; charset=utf-8"
                )
                self.end_headers()
                self.wfile.write(p.read_bytes())
                return
        if parsed.path.endswith((".png", ".jpg", ".jpeg", ".svg", ".ico")):
            p = Path(parsed.path.lstrip("/"))
            if p.exists():
                ext_map = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".svg": "image/svg+xml",
                    ".ico": "image/x-icon",
                }
                ext = p.suffix.lower()
                self.send_response(200)
                self.send_header(
                    "Content-Type", ext_map.get(ext, "application/octet-stream")
                )
                self.end_headers()
                self.wfile.write(p.read_bytes())
                return

        self._set_json_headers(404)
        self.wfile.write(json.dumps({"error": "NotFound"}).encode())

    def log_message(self, format, *args):
        return


def run_server(port=8000):
    httpd = HTTPServer(("0.0.0.0", port), RequestHandler)
    print(f"Bajrang Aura server running on http://0.0.0.0:{port}")
    print(f"Endpoints: /chat, /life-lesson, /config, /health, /clear-session")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    run_server(port=port)
