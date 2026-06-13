(function(){
  const wakeEl = document.getElementById('wake');
  const alwaysListenToggle = document.getElementById('alwaysListen');
  const chatArea = document.getElementById('chat-area');
  const userInput = document.getElementById('userInput');
  const sendBtn = document.getElementById('sendBtn');
  const lifeBtn = document.getElementById('lifeLessonBtn');
  const lifeModal = document.getElementById('lifeModal');
  const lifeClose = document.getElementById('lifeClose');
  const lifeSubmit = document.getElementById('lifeSubmit');
  const lifeTopic = document.getElementById('lifeTopic');
  const lifeProblem = document.getElementById('lifeProblem');
  const listeningIndicator = document.getElementById('listeningIndicator');
  const micBtnEl = document.getElementById('micBtn');

  let shlokaIndex = 0;
  let recognition = null;
  let isListening = false;
  let alwaysListening = false;
  let isTyping = false;

  const shlokas = [
    { text: 'Karmanye vadhikaraste ma phaleshu kadachana', translation: 'You have the right to action, but not to the fruits of action.' },
    { text: 'Yada yada hi dharmasya glanir bhavati bharata', translation: 'Whenever there is decline of dharma, I manifest myself.' },
    { text: 'Dharmakshetre kurukshetre...', translation: 'On the field of dharma, in the field of Kurukshetra.' },
    { text: 'Manmana bhava mad-bhakto mad-yaji mam namaskuru', translation: 'Always think of Me, be My devotee, worship Me, and bow to Me.' },
    { text: 'Ram naam satya hai', translation: 'The name of Ram is the ultimate truth.' }
  ];

  function createParticles(){
    const container = document.getElementById('particles');
    if(!container) return;
    for(let i = 0; i < 30; i++){
      const p = document.createElement('div');
      p.className = 'particle';
      p.style.left = Math.random() * 100 + '%';
      p.style.animationDuration = (8 + Math.random() * 12) + 's';
      p.style.animationDelay = (Math.random() * 10) + 's';
      p.style.width = p.style.height = (2 + Math.random() * 4) + 'px';
      container.appendChild(p);
    }
  }

  function parseMarkdown(md){
    if(!md) return '';
    let html = md
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
      .replace(/^\d+\.\s+(.+)$/gm, '<li class="ordered">$1</li>')
      .replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>');

    html = html.replace(/(<li[^>]*>.*?<\/li>\n*)+/gs, match => {
      const isOrdered = match.includes('class="ordered"');
      const cleanMatch = match.replace(/\n/g, '');
      return isOrdered ? `<ol>${cleanMatch}</ol>` : `<ul>${cleanMatch}</ul>`;
    });

    html = html
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n/g, '<br>');
    return html;
  }

  function getTimestamp(){
    return new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
  }

  function addUserMessage(text){
    if(!chatArea) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper user-wrapper';
    wrapper.innerHTML = `
      <div class="message-bubble user-bubble">
        <div class="message-content">${escapeHtml(text)}</div>
        <div class="message-time">${getTimestamp()}</div>
      </div>
      <div class="avatar user-avatar">Y</div>
    `;
    chatArea.appendChild(wrapper);
    chatArea.scrollTop = chatArea.scrollHeight;
  }

  function createBotBubble(){
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper bot-wrapper';
    wrapper.innerHTML = `
      <div class="avatar bot-avatar">
        <img src="assets/hanuman.png" alt="Bajrangi" />
      </div>
      <div class="message-bubble bot-bubble">
        <div class="message-content typing-indicator">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        </div>
        <div class="message-time">${getTimestamp()}</div>
        <div class="message-actions" style="display:none;">
          <button class="action-btn copy-btn" title="Copy">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
          </button>
          <button class="action-btn speak-btn" title="Speak">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19"/><path d="M19.07 4.93a10 10 0 010 14.14"/><path d="M15.54 8.46a5 5 0 010 7.07"/></svg>
          </button>
        </div>
      </div>
    `;
    chatArea.appendChild(wrapper);
    chatArea.scrollTop = chatArea.scrollHeight;
    return wrapper;
  }

  function escapeHtml(text){
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  // AI status banner helpers
  function renderAiBanner(data){
    const el = document.getElementById('aiStatus');
    if(!el) return;
    if(!data){
      el.style.display = 'none';
      return;
    }
    const groqKey = data.groq_key === 'set';
    const hfKey = data.hf_key === 'set';
    const tavilyKey = data.tavily_key === 'set';
    const tavilyOk = data.tavily_status === 'ok';
    const groqOk = data.groq_status === 'ok';
    const hfOk = data.hf_status === 'ok';
    const last = data.last_check ? new Date(data.last_check) : null;
    const timeStr = last ? last.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '';
    const text = `AI status: GROQ ${groqKey ? '(set)' : '(not_set)'} ${groqOk ? '[OK]' : '[ERR]'} | HF ${hfKey ? '(set)' : '(not_set)'} ${hfOk ? '[OK]' : '[ERR]'} | Tavily ${tavilyKey ? '(set)' : '(not_set)'} ${tavilyOk ? '[OK]' : '[ERR]'}${timeStr ? ' • ' + timeStr : ''}`;
    el.textContent = text;
    el.style.display = 'flex';
  }
  async function fetchAiStatus(){
    try {
      const res = await fetch('/ai-status');
      if(res.ok){
        const data = await res.json();
        renderAiBanner(data);
      }
    } catch(e){
      // ignore
    }
  }

  // Render web results panel (list of text + URL)
  function renderWebResults(results){
    const el = document.getElementById('webResults');
    if(!el) return;
    if(!results || results.length === 0){
      el.style.display = 'none';
      el.innerHTML = '';
      return;
    }
    el.style.display = 'block';
    let html = '<div class="web-results-title" style="font-weight:600; margin-bottom:6px;">Web Results</div>';
    html += '<ul style="margin:0; padding-left:16px; list-style:none;">';
    results.forEach((r, idx) => {
      const t = r.text || '';
      const u = r.url || '#';
      html += `<li style="margin:6px 0;"><a href="${u}" target="_blank" rel="noopener" style="color:#9bd; text-decoration:none;">[${idx+1}] ${t} </a><span style="font-family:monospace; font-size:0.8em; color:#9bd;">${u}</span></li>`;
    });
    html += '</ul>';
    el.innerHTML = html;
  }

  async function streamText(wrapper, fullText, onDone){
    const contentEl = wrapper.querySelector('.message-content');
    const actionsEl = wrapper.querySelector('.message-actions');
    const timeEl = wrapper.querySelector('.message-time');
    contentEl.classList.remove('typing-indicator');
    
    // Clean leaked function tags from the UI display
    const filteredText = fullText.replace(/<function=[^>]+>.*?<\/function>/gs, '').trim();
    
    let displayed = '';
    const chars = filteredText.split('');
    let i = 0;
    
    return new Promise(resolve => {
      function typeChar(){
        if(i < chars.length){
          displayed += chars[i];
          contentEl.innerHTML = parseMarkdown(displayed);
          chatArea.scrollTop = chatArea.scrollHeight;
          i++;
          const delay = chars[i-1] === '.' || chars[i-1] === ',' || chars[i-1] === '\n' ? 40 : 12;
          setTimeout(typeChar, delay);
        } else {
          contentEl.innerHTML = parseMarkdown(fullText);
          if(actionsEl) actionsEl.style.display = 'flex';
          if(timeEl) timeEl.textContent = getTimestamp();
          
          // Bind copy button
          const copyBtn = wrapper.querySelector('.copy-btn');
          if(copyBtn){
            copyBtn.addEventListener('click', () => {
              navigator.clipboard.writeText(fullText).then(() => {
                copyBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
                setTimeout(() => {
                  copyBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>';
                }, 2000);
              });
            });
          }
          
          // Bind speak button
          const speakBtn = wrapper.querySelector('.speak-btn');
          if(speakBtn){
            speakBtn.addEventListener('click', () => speak(filteredText));
          }
          
          // Auto-speak response
          if(autoSpeak){
            speak(filteredText);
          }
          
          if(onDone) onDone();
          resolve();
        }
      }
      typeChar();
    });
  }

  // Pretty female English voice preference list (soft, clear, no Hindi)
  const FEMALE_VOICE_PREFS = [
    'microsoft zira',           // Windows — soft US female ✨
    'microsoft hazel',          // Windows — British female
    'microsoft susan',          // Windows — female
    'google uk english female', // Chrome — British female
    'google us english female', // Chrome — US female
    'samantha',                 // macOS — clear US female
    'victoria',                 // macOS — US female
    'karen',                    // macOS/iOS — Australian female
    'moira',                    // macOS — Irish female
    'tessa',                    // macOS — South African female
    'fiona',                    // macOS — Scottish female
  ];

  function loadVoices(){
    return new Promise(resolve => {
      let voices = window.speechSynthesis.getVoices();
      if(voices.length) return resolve(voices);
      window.speechSynthesis.onvoiceschanged = () => {
        voices = window.speechSynthesis.getVoices();
        resolve(voices);
      };
      setTimeout(() => resolve(voices), 1500);
    });
  }

  function pickFemaleVoice(voices){
    if(!voices || !voices.length) return null;
    // Try each preferred female voice in order — English ONLY
    for(const pref of FEMALE_VOICE_PREFS){
      const match = voices.find(v =>
        v.name.toLowerCase().includes(pref) && v.lang.startsWith('en')
      );
      if(match) return match;
    }
    // Fallback: any English voice that sounds female by name keyword
    const femaleKeywords = ['female', 'zira', 'samantha', 'girl', 'woman'];
    for(const kw of femaleKeywords){
      const match = voices.find(v => v.name.toLowerCase().includes(kw) && v.lang.startsWith('en'));
      if(match) return match;
    }
    // Last resort: first English voice
    return voices.find(v => v.lang.startsWith('en')) || voices[0];
  }

  let voicesLoaded = null;
  let selectedVoice = null;

  let autoSpeak = true;

  // Retry and command learning state
  let lastUserCommand = null;
  let isRetrying = false;
  let retryCount = 0;
  const MAX_RETRIES = 2;
  let commandHistory = [];

  // Sound Assets (Base64)
  const SOUNDS = {
    bell: 'data:audio/wav;base64,UklGRm4HAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YWsHAAC5ALkAiwBvAGwAbwCLALkAuwCzAIEAdQB1AIEAuQC7ALMAgQB1AHUAgQC5ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7ALsAuwC7A...', // Minimal placeholder
    ping: 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA='
  };

  function playSound(type){
    // Soft, gentle notification tones
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    if(type === 'bell'){
      // Gentle, melodic chime
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(1046, audioCtx.currentTime + 0.1);
      osc.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 0.4);
      gain.gain.setValueAtTime(0.25, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 1.0);
    } else {
      // Light, airy ping
      osc.type = 'sine';
      osc.frequency.setValueAtTime(1000, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(1200, audioCtx.currentTime + 0.06);
      gain.gain.setValueAtTime(0.07, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.2);
    }

    osc.connect(gain); gain.connect(audioCtx.destination);
    osc.start(); osc.stop(audioCtx.currentTime + 1.2);
  }

  function pickHindiFemaleVoice(voices){
    if(!voices) return null;
    const hiKeywords = ['swara', 'neerja', 'aditi', 'kalpana', 'kavita', 'google hindi', 'google indiana'];
    // 1. Try to find a known female Hindi/Indian voice by name
    for(const kw of hiKeywords) {
      const match = voices.find(v => v.name.toLowerCase().includes(kw));
      if(match) return match;
    }
    // 2. Try generic female hi-IN
    let match = voices.find(v => v.lang.startsWith('hi') && v.name.toLowerCase().includes('female'));
    if(match) return match;
    // 3. Try any hi-IN voice
    match = voices.find(v => v.lang.startsWith('hi'));
    if(match) return match;
    // 4. Try any Indian English voice (they usually support Devanagari)
    match = voices.find(v => v.lang.startsWith('en-in') || v.lang.startsWith('en-IN'));
    return match || null;
  }


  function speak(text){
    if(!('speechSynthesis' in window) || !text) return;
    window.speechSynthesis.cancel();

    // Strip markdown and raw function tags
    const cleanText = text
      .replace(/<function=[^>]+>.*?<\/function>/gs, '') // Remove tool code leakage
      .replace(/[#*`_~>]/g, '')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/\n+/g, ' ')
      .trim();

    if(!cleanText) return;

    // Split into sentences so Chrome doesn't silently fail on long text
    const sentences = cleanText.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [cleanText];

    let delay = 0;
    sentences.forEach((sentence, idx) => {
      const trimmed = sentence.trim();
      if(!trimmed) return;

      const hasHindi = /[\u0900-\u097F]/.test(trimmed);
      const utter = new SpeechSynthesisUtterance(trimmed);
      
      utter.rate   = hasHindi ? 0.95 : 0.88;
      utter.pitch  = hasHindi ? 1.05 : 1.25;
      utter.volume = 0.95;

      if(hasHindi) {
        const hiVoice = pickHindiFemaleVoice(voicesLoaded);
        if(hiVoice) {
          // Native local Hindi voice available
          utter.lang = 'hi-IN';
          utter.voice = hiVoice;
          setTimeout(() => { window.speechSynthesis.speak(utter); }, delay);
          delay += trimmed.length * 60; 
        } else {
          // Absolute Fallback: No Hindi voice is installed on OS.
          // We use the Google Translate TTS Audio endpoint to force it to read Hindi.
          // Google TTS limits strings to ~200 chars, so short sentences are perfect.
          const url = `https://translate.googleapis.com/translate_tts?client=gtx&ie=UTF-8&tl=hi&q=${encodeURIComponent(trimmed.substring(0, 199))}`;
          setTimeout(() => { 
            const audio = new Audio(url);
            audio.volume = 0.95;
            audio.play().catch(e => console.log('Audio Fallback Error:', e));
          }, delay);
          delay += trimmed.length * 90; // Audio streaming takes slightly longer
        }
      } else {
        utter.lang = 'en-US';
        if(selectedVoice) {
          utter.voice = selectedVoice;
        }
        setTimeout(() => { window.speechSynthesis.speak(utter); }, delay);
        delay += trimmed.length * 60; 
      }
    });
  }
  
  // Expose globally for console testing
  window.speak = speak;

  async function groqChat(text){
    try {
      const langEl = document.getElementById('langSwitch');
      const lang = langEl ? langEl.value : 'auto';
      let payloadText = text;
      
      if(lang === 'hi'){
        payloadText = `${text}\n[SYSTEM: You MUST respond entirely in Hindi (Devanagari script). DONT show raw <function> tags or code to the user.]`;
      } else if(lang === 'en'){
        payloadText = `${text}\n[SYSTEM: You MUST respond entirely in English. DONT show raw <function> tags or code to the user.]`;
      }

      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: payloadText })
      });
      const data = await res.json();
      return { response: data.response, source: data.source, web_results: data.web_results || [] };
    } catch(e){
      return { response: 'Error contacting AI backend.', source: 'error', web_results: [] };
    }
  }

  async function lifeLessonCall(topic, problem){
    try {
      const langEl = document.getElementById('langSwitch');
      const lang = langEl ? langEl.value : 'auto';
      let payloadProblem = problem || '';
      
      if(lang === 'hi'){
        payloadProblem += `\n[SYSTEM: Respond ENTIRELY in Hindi. DO NOT show raw tags or XML code.]`;
      } else if(lang === 'en'){
        payloadProblem += `\n[SYSTEM: Respond ENTIRELY in English. DO NOT show raw tags or XML code.]`;
      }

      const res = await fetch('/life-lesson', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, problem: payloadProblem })
      });
      const data = await res.json();
      return data.response;
    } catch(e){
      return 'Error contacting Life Lesson backend.';
    }
  }

  function rotateShloka(){
    const s = shlokas[shlokaIndex % shlokas.length];
    const el = document.getElementById('shlokaDisplay');
    if(el){
      el.textContent = `"${s.text}" — ${s.translation}`;
    }
    shlokaIndex++;
  }

  function initSpeechRecognition(){
    if (!('SpeechRecognition' in window) && !('webkitSpeechRecognition' in window)) return null;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = false;
    rec.lang = 'en-IN';
    rec.onresult = (e) => {
      const transcript = e.results[e.results.length - 1][0].transcript.trim();
      if (transcript) {
        handleUserInput(transcript);
      }
    };
    rec.onend = () => {
      if (alwaysListening) {
        try { rec.start(); } catch(_) {}
      } else {
        isListening = false;
        updateUI();
      }
    };
    rec.onerror = (e) => {
      if (e.error === 'not-allowed') {
        appendErrorMessage('Microphone access denied.');
        alwaysListening = false; isListening = false; updateUI();
      }
    };
    return rec;
  }

  let mediaRecorder = null;
  let audioChunks = [];
  let isWhisperRecording = false;

  function updateUI(){
    const active = isListening || isWhisperRecording;
    if (wakeEl) wakeEl.classList.toggle('active', active);
    if (listeningIndicator) {
      listeningIndicator.classList.toggle('active', active);
      listeningIndicator.querySelector('span:last-child').textContent = isWhisperRecording ? 'Listening (High-Quality)...' : 'Listening...';
    }
    if (micBtnEl) micBtnEl.classList.toggle('listening', active);
  }

  function startListening(){
    if (!recognition) recognition = initSpeechRecognition();
    if (recognition) { try { recognition.start(); } catch(_) {} isListening = true; updateUI(); }
  }

  function stopListening(){
    if (recognition) recognition.stop();
    isListening = false;
    updateUI();
  }

  async function toggleWhisperRecording() {
    if(isWhisperRecording && mediaRecorder) {
      mediaRecorder.stop();
      return;
    }
    if (recognition) { recognition.stop(); isListening = false; }
    
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      audioChunks = [];
      
      mediaRecorder.addEventListener('dataavailable', event => {
        audioChunks.push(event.data);
      });
      
      mediaRecorder.addEventListener('stop', async () => {
        isWhisperRecording = false;
        updateUI();
        stream.getTracks().forEach(track => track.stop());
        
        appendErrorMessage('Transcribing high-quality audio...', 'info');
        playSound('ping');
        
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        try {
          const res = await fetch('/transcribe', {
            method: 'POST',
            body: audioBlob
          });
          const contentType = res.headers.get("content-type");
          if(contentType && contentType.includes("application/json")){
             const data = await res.json();
             if(data.text) {
                console.log("Whisper transcription:", data.text);
                handleUserInput(data.text);
             } else {
                appendErrorMessage('Transcription error: ' + (data.error || 'Unknown error. Are API keys set?'));
             }
          } else {
             const html = await res.text();
             appendErrorMessage('Server error. Check backend logs.');
          }
        } catch(e) {
          appendErrorMessage('Error sending audio to server: ' + e.message);
        }
      });
      
      mediaRecorder.start();
      isWhisperRecording = true;
      updateUI();
      playSound('ping');
    } catch(err) {
      appendErrorMessage('Microphone access denied for high-quality audio API.');
    }
  }

  function appendErrorMessage(msg){
    if(!chatArea) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper bot-wrapper';
    wrapper.innerHTML = `
      <div class="avatar bot-avatar"><img src="assets/hanuman.png" alt="Bajrangi" /></div>
      <div class="message-bubble bot-bubble error-bubble">
        <div class="message-content">${escapeHtml(msg)}</div>
        <div class="message-time">${getTimestamp()}</div>
      </div>
    `;
    chatArea.appendChild(wrapper);
    chatArea.scrollTop = chatArea.scrollHeight;
  }

  function showToast(message, icon, type){
    const container = document.getElementById('toastContainer');
    if(!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type || 'info'}`;
    toast.innerHTML = `
      <div class="toast-icon">${icon}</div>
      <div class="toast-body">
        <div class="toast-message">${escapeHtml(message)}</div>
        <div class="toast-time">${getTimestamp()}</div>
      </div>
      <button class="toast-close">&times;</button>
    `;
    container.appendChild(toast);
    toast.querySelector('.toast-close').addEventListener('click', () => {
      toast.classList.add('toast-exit');
      setTimeout(() => toast.remove(), 400);
    });
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      if(toast.parentNode){
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 400);
      }
    }, 5000);
  }

  async function handleUserInput(text){
    if(!text || isTyping) return;
    performAction(text, { silent: false });
  }

  async function performAction(text, options = {}){
    const isSilent = options.silent || false;
    const skipTyping = options.skipTypingCheck || false;
    
    if(!text || (!skipTyping && isTyping)) return;
    
    // Reset retry state on new user-initiated commands
    if(!isSilent && text !== lastUserCommand){
      retryCount = 0;
      commandHistory.push({ text, time: Date.now(), status: 'sent' });
    }
    if(!isSilent) lastUserCommand = text;
    
    if(!isSilent){
      isTyping = true;
      addUserMessage(text);
      playSound('ping');
      if(userInput) userInput.value = '';
    }
    
    let botWrapper = null;
    if(!isSilent){
      botWrapper = createBotBubble();
    }
    
    try {
      const chat = await groqChat(text);
      const reply = chat?.response ?? '';
      const source = chat?.source ?? '';
      const webResults = chat?.web_results ?? [];
      const success = source !== 'error' && source !== 'fallback';
      
      if(!isSilent && commandHistory.length > 0){
        commandHistory[commandHistory.length - 1].status = success ? 'ok' : 'error';
        commandHistory[commandHistory.length - 1].source = source;
      }
      
      // Handle action responses with toasts
      const actionToasts = {
        'action_open_app': { icon: '🖥️', type: 'success' },
        'action_play_song': { icon: '🎵', type: 'success' },
        'action_system_control': { icon: '⚙️', type: 'success' },
        'action_system_diagnostic': { icon: '📊', type: 'info' },
        'action_manage_notes': { icon: '📝', type: 'success' }
      };

      if(actionToasts[source]){
        playSound('bell');
        showToast(reply, actionToasts[source].icon, actionToasts[source].type);
        if(botWrapper) botWrapper.remove();
        if(!isSilent) isTyping = false;
        return;
      }
      
      if(!isSilent && botWrapper){
        await streamText(botWrapper, reply);
        if (webResults && webResults.length > 0) renderWebResults(webResults);
      }
    } catch(e){
      console.error('Action failed:', e);
      if(!isSilent && botWrapper){
        const contentEl = botWrapper.querySelector('.message-content');
        if(contentEl){
          contentEl.classList.remove('typing-indicator');
          contentEl.textContent = 'Sorry, I encountered an error. Please try again.';
        }
      }
    }
    if(!isSilent) isTyping = false;
  }

  function retryLastCommand(){
    console.log('Retry last command called:', { lastUserCommand, isRetrying, retryCount });
    if(!lastUserCommand){
      appendErrorMessage('No previous command to retry.');
      return;
    }
    if(isRetrying){
      console.log('Already retrying, ignoring');
      return;
    }
    if(retryCount >= MAX_RETRIES){
      appendErrorMessage(`Retry limit reached (${MAX_RETRIES} attempts). Please try a different command.`);
      retryCount = 0;
      return;
    }
    
    retryCount++;
    isRetrying = true;
    
    const retryBtn = document.getElementById('retryBtn');
    if(retryBtn){
      retryBtn.disabled = true;
      retryBtn.textContent = `⏳ Retrying (${retryCount}/${MAX_RETRIES})...`;
    }
    
    appendErrorMessage(`🔄 Retry attempt ${retryCount}/${MAX_RETRIES} for: "${lastUserCommand}"`);
    
    handleUserInput(lastUserCommand).finally(() => {
      console.log('Retry attempt finished');
      isRetrying = false;
      if(retryBtn){
        retryBtn.disabled = false;
        retryBtn.textContent = '🔄 Retry';
      }
    });
  }

  function appendActionMessage(msg, type){
    if(!chatArea) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper bot-wrapper';
    const icon = type === 'app-opened' ? '🖥️' : '🎵';
    wrapper.innerHTML = `
      <div class="avatar bot-avatar"><img src="assets/hanuman.png" alt="Bajrangi" /></div>
      <div class="message-bubble bot-bubble action-bubble">
        <div class="message-content">${icon} ${escapeHtml(msg)}</div>
        <div class="message-time">${getTimestamp()}</div>
      </div>
    `;
    chatArea.appendChild(wrapper);
    chatArea.scrollTop = chatArea.scrollHeight;
  }

  function playSong(songName){
    const player = document.getElementById('musicPlayer');
    const title = document.getElementById('songTitle');
    const status = document.getElementById('songStatus');
    if(player){
      player.style.display = 'block';
      if(title) title.textContent = songName;
      if(status) status.textContent = 'Playing on YouTube...';
    }
    // Open YouTube search for the song
    const searchUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(songName + ' song')}`;
    window.open(searchUrl, '_blank');
  }

  async function handleLifeLesson(topic, problem){
    if(isTyping) return;
    isTyping = true;
    
    const summary = `Seeking guidance from ${topic}: ${problem || 'General wisdom'}`;
    addUserMessage(summary);
    
    const botWrapper = createBotBubble();
    
    try {
      const response = await lifeLessonCall(topic, problem);
      await streamText(botWrapper, response);
    } catch(e){
      const contentEl = botWrapper.querySelector('.message-content');
      contentEl.classList.remove('typing-indicator');
      contentEl.textContent = 'Sorry, I encountered an error. Please try again.';
    }
    isTyping = false;
  }

  function bootstrap(){
    createParticles();
    loadVoices().then(v => {
      voicesLoaded = v;
      selectedVoice = pickFemaleVoice(v);
      if(selectedVoice) console.log('🎀 Female voice selected:', selectedVoice.name, selectedVoice.lang);
    });
    rotateShloka();
    setInterval(rotateShloka, 12000);

    // Welcome message with streaming
    groqChat('Hello').then(res => {
      const botWrapper = createBotBubble();
      const reply = res?.response ?? '';
      const webResults = res?.web_results ?? [];
      streamText(botWrapper, reply).then(() => {
        if (webResults.length) renderWebResults(webResults);
      });
    });

    if (alwaysListenToggle) {
      alwaysListenToggle.addEventListener('change', function(){
        alwaysListening = this.checked;
        if (this.checked) startListening(); else stopListening();
      });
      if (alwaysListenToggle.checked) {
        alwaysListening = true;
        startListening();
      }
    }
    // Check AI status banner on startup
    fetchAiStatus();

    // Sound greeting on first interaction (Autoplay safety)
    let greetingDone = false;
    const triggerGreeting = () => {
      if(greetingDone) return;
      greetingDone = true;
      playSound('bell');
      setTimeout(() => speak("Hello! I am ready to help you."), 300);
      document.removeEventListener('click', triggerGreeting);
      document.removeEventListener('keydown', triggerGreeting);
    };
    document.addEventListener('click', triggerGreeting);
    document.addEventListener('keydown', triggerGreeting);
  }



  if(lifeBtn){
    lifeBtn.addEventListener('click', () => { lifeModal.style.display = 'flex'; });
  }
  if(lifeClose){
    lifeClose.addEventListener('click', () => { lifeModal.style.display = 'none'; });
  }
  if(lifeModal){
    lifeModal.addEventListener('click', (e) => {
      if(e.target === lifeModal) lifeModal.style.display = 'none';
    });
  }
  if(lifeSubmit){
    lifeSubmit.addEventListener('click', async () => {
      const topic = lifeTopic.value || 'Ramayana';
      const problem = lifeProblem.value || '';
      lifeModal.style.display = 'none';
      lifeProblem.value = '';
      handleLifeLesson(topic, problem);
    });
  }

  if(userInput && sendBtn){
    function sendChat(){
      const t = userInput.value.trim();
      if(!t || isTyping) return;
      handleUserInput(t);
    }
    sendBtn.addEventListener('click', sendChat);
    userInput.addEventListener('keydown', (e) => { if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); sendChat(); } });
  }

  const readShlokaBtn = document.getElementById('readShloka');
  if(readShlokaBtn){
    readShlokaBtn.addEventListener('click', () => {
      const shlokaText = document.getElementById('shlokaDisplay').textContent;
      if(shlokaText) speak(shlokaText);
    });
  }

  if(micBtnEl){
    micBtnEl.addEventListener('click', () => {
      if(alwaysListening) {
        if(isListening) stopListening();
        else startListening();
      } else {
        toggleWhisperRecording();
      }
    });
  }

  if(document.getElementById('stopBtn')){
    document.getElementById('stopBtn').addEventListener('click', stopListening);
  }

  // Retry button
  const retryBtn = document.getElementById('retryBtn');
  if(retryBtn){
    retryBtn.addEventListener('click', retryLastCommand);
  }

  // Music player controls
  const closePlayerBtn = document.getElementById('closePlayer');
  if(closePlayerBtn){
    closePlayerBtn.addEventListener('click', () => {
      document.getElementById('musicPlayer').style.display = 'none';
    });
  }

  const playPauseBtn = document.getElementById('playPauseBtn');
  if(playPauseBtn){
    playPauseBtn.addEventListener('click', () => {
      performAction("toggle play pause", { silent: true, skipTypingCheck: true });
      const isPlaying = playPauseBtn.textContent === '⏸';
      playPauseBtn.textContent = isPlaying ? '▶' : '⏸';
    });
  }

  const nextBtn = document.getElementById('nextBtn');
  if(nextBtn) {
    nextBtn.addEventListener('click', () => {
      performAction("play next track", { silent: true, skipTypingCheck: true });
    });
  }

  const prevBtn = document.getElementById('prevBtn');
  if(prevBtn) {
    prevBtn.addEventListener('click', () => {
      performAction("play previous track", { silent: true, skipTypingCheck: true });
    });
  }

  const volumeSlider = document.getElementById('volumeSlider');
  if(volumeSlider){
    volumeSlider.addEventListener('change', (e) => {
      const val = e.target.value;
      if(val > 80) performAction("increase volume", { silent: true, skipTypingCheck: true });
      else if(val < 20) performAction("decrease volume", { silent: true, skipTypingCheck: true });
    });
  }

  // Settings modal
  const settingsBtn = document.getElementById('settingsBtn');
  const settingsModal = document.getElementById('settingsModal');
  const settingsClose = document.getElementById('settingsClose');
  const saveSettings = document.getElementById('saveSettings');
  const testSettings = document.getElementById('testSettings');
  const settingsStatus = document.getElementById('settingsStatus');

  if(settingsBtn){
    settingsBtn.addEventListener('click', async () => {
      settingsModal.style.display = 'flex';
      // Load current keys
      try {
        const res = await fetch('/config');
        if(res.ok){
          const data = await res.json();
          document.getElementById('groqKey').value = data.GROQ_API_KEY === 'set' ? '••••••••' : '';
          document.getElementById('hfKey').value = data.HUGGINGFACE_API_KEY === 'set' ? '••••••••' : '';
          document.getElementById('tavilyKey').value = data.TAVILY_API_KEY === 'set' ? '••••••••' : '';
        }
      } catch(e){}
    });
  }
  if(settingsClose){
    settingsClose.addEventListener('click', () => { settingsModal.style.display = 'none'; });
  }
  if(settingsModal){
    settingsModal.addEventListener('click', (e) => {
      if(e.target === settingsModal) settingsModal.style.display = 'none';
    });
  }

  if(saveSettings){
    saveSettings.addEventListener('click', async () => {
      const groq = document.getElementById('groqKey').value.trim();
      const hf = document.getElementById('hfKey').value.trim();
      const tavily = document.getElementById('tavilyKey').value.trim();
      
      settingsStatus.style.display = 'block';
      settingsStatus.className = 'settings-status loading';
      settingsStatus.textContent = 'Saving keys...';
      
      try {
        const res = await fetch('/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'save',
            config: {
              GROQ_API_KEY: groq,
              HUGGINGFACE_API_KEY: hf,
              TAVILY_API_KEY: tavily
            }
          })
        });
        if(res.ok){
          settingsStatus.className = 'settings-status success';
          settingsStatus.textContent = '✓ Keys saved successfully! Restarting server...';
          setTimeout(() => {
            settingsModal.style.display = 'none';
            settingsStatus.style.display = 'none';
            location.reload();
          }, 1500);
        } else {
          settingsStatus.className = 'settings-status error';
          settingsStatus.textContent = '✗ Failed to save keys.';
        }
      } catch(e){
        settingsStatus.className = 'settings-status error';
        settingsStatus.textContent = '✗ Error saving keys: ' + e.message;
      }
    });
  }

  if(testSettings){
    testSettings.addEventListener('click', async () => {
      settingsStatus.style.display = 'block';
      settingsStatus.className = 'settings-status loading';
      settingsStatus.textContent = 'Testing keys...';
      
      try {
        const res = await fetch('/ai-status');
        if(res.ok){
          const data = await res.json();
          let msg = '';
          msg += `Groq: ${data.groq_key === 'set' ? '✓ Set' : '✗ Not set'} (${data.groq_status})\n`;
          msg += `HF: ${data.hf_key === 'set' ? '✓ Set' : '✗ Not set'} (${data.hf_status})\n`;
          msg += `Tavily: ${data.tavily_key === 'set' ? '✓ Set' : '✗ Not set'} (${data.tavily_status})`;
          const allOk = data.groq_status === 'ok' && data.tavily_status === 'ok';
          settingsStatus.className = allOk ? 'settings-status success' : 'settings-status error';
          settingsStatus.textContent = msg;
        }
      } catch(e){
        settingsStatus.className = 'settings-status error';
        settingsStatus.textContent = '✗ Error testing keys: ' + e.message;
      }
    });
  }

  document.addEventListener('DOMContentLoaded', bootstrap);
})();
