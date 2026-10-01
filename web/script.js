let ws = null;
const stateLabel = document.getElementById('state-label');
const userText = document.getElementById('user-text');
const aiText = document.getElementById('ai-text');
const commandLog = document.getElementById('command-log');
const statCpu = document.getElementById('stat-cpu');
const statRam = document.getElementById('stat-ram');
const statDisk = document.getElementById('stat-disk');
const barCpu = document.getElementById('bar-cpu');
const barRam = document.getElementById('bar-ram');
const barDisk = document.getElementById('bar-disk');
const wsStatus = document.getElementById('ws-status');

// Clock & Uptime
let bootTime = Date.now();
setInterval(() => {
    const now = new Date();
    document.getElementById('clock').innerText = now.toLocaleTimeString('en-US', { hour12: false });
    
    // Uptime calculation
    let diff = Math.floor((now.getTime() - bootTime) / 1000);
    let h = Math.floor(diff / 3600).toString().padStart(2, '0');
    let m = Math.floor((diff % 3600) / 60).toString().padStart(2, '0');
    let s = (diff % 60).toString().padStart(2, '0');
    document.getElementById('uptime-val').innerText = `${h}:${m}:${s}`;
}, 1000);

// Data Streams
const ds1 = document.getElementById('ds-1');
const ds2 = document.getElementById('ds-2');
setInterval(() => {
    if (ds1) {
        const hex = Math.floor(Math.random() * 0xFFFF).toString(16).toUpperCase().padStart(4, '0');
        ds1.innerText = `SYS.OP: 0x${hex}`;
    }
    if (ds2 && Math.random() > 0.8) {
        ds2.innerText = Math.random() > 0.5 ? `CORE: SYNCING` : `CORE: OPTIMAL`;
    }
}, 200);

let idleTimer = null;

function setupWebSocket() {
    const host = window.location.hostname || "127.0.0.1";
    const port = window.location.port || "8000";
    ws = new WebSocket(`ws://${host}:${port}/ws`);

    ws.onopen = () => {
        wsStatus.innerText = 'CONNECTED';
        wsStatus.className = 'value text-primary-glow';
        addLogEntry('SYSTEM', 'WebSocket uplink established.', 'sys');
    };

    ws.onclose = () => {
        wsStatus.innerText = 'DISCONNECTED';
        wsStatus.className = 'value text-glow-warn';
        updateState('error', 'CONNECTION LOST');
        setTimeout(setupWebSocket, 3000);
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleMessage(data);
    };
    
    // Fake latency ping
    setInterval(() => {
        if(ws && ws.readyState === WebSocket.OPEN) {
            document.getElementById('latency-val').innerText = `${Math.floor(Math.random() * 10 + 2)}ms`;
        } else {
            document.getElementById('latency-val').innerText = `---`;
        }
    }, 2000);
}

function handleMessage(data) {
    if (data.type === 'state') {
        updateState(data.state);
    } else if (data.type === 'transcript') {
        userText.innerText = `[USER_INPUT]: ${data.text}`;
        aiText.innerText = '';
    } else if (data.type === 'response') {
        aiText.innerText = data.text;
        addLogEntry('USER', data.user_text, 'user');
        addLogEntry('WHIS', data.text, 'ai');
    } else if (data.type === 'stats') {
        updateStats(data.stats);
    } else if (data.type === 'action') {
        addLogEntry('SYS_ACT', `Executing directive: ${data.action}`, 'sys');
        if (data.action === 'OPEN_CHROME') window.open('https://www.google.com', '_blank');
        else if (data.action === 'OPEN_BROWSER') window.open(data.url, '_blank');
        else if (data.action === 'SEARCH') window.open('https://www.google.com/search?q=' + encodeURIComponent(data.query), '_blank');
    }
}

function updateState(state, customLabel = null) {
    const states = {
        'idle': { label: 'NEURAL CORE IDLE // AWAITING DIRECTIVE', class: '' },
        'listening': { label: 'AUDIO UPLINK ACTIVE // LISTENING', class: 'state-listening' },
        'thinking': { label: 'PROCESSING DIRECTIVE...', class: 'state-thinking' },
        'speaking': { label: 'TRANSMITTING RESPONSE', class: 'state-speaking' },
        'error': { label: 'SYSTEM ERROR // FAULT DETECTED', class: 'state-error' }
    };
    
    if (states[state]) {
        stateLabel.innerText = customLabel || states[state].label;
        document.querySelector('.rings-container').className = `rings-container ${states[state].class}`;
    }
}

function updateStats(stats) {
    statCpu.innerText = `${stats.cpu}%`;
    barCpu.style.width = `${stats.cpu}%`;
    statRam.innerText = `${stats.ram_used.toFixed(1)}/${stats.ram_total.toFixed(1)} GB`;
    barRam.style.width = `${stats.ram_pct}%`;
    statDisk.innerText = `${stats.disk_free.toFixed(1)} GB AVAIL`;
    barDisk.style.width = `${stats.disk_pct}%`;
}

function addLogEntry(prefix, text, type) {
    const empty = document.querySelector('.log-empty');
    if(empty) empty.remove();

    const entry = document.createElement('div');
    entry.className = 'log-item';
    
    const now = new Date();
    const time = now.toLocaleTimeString('en-US', { hour12: false });
    
    const meta = document.createElement('div');
    meta.className = 'log-meta';
    meta.innerText = `[${time}] [${prefix}]`;
    
    const content = document.createElement('div');
    content.className = type === 'user' ? 'log-user' : (type === 'err' ? 'log-err' : 'log-ai');
    content.innerText = text.length > 80 ? text.substring(0, 80) + '...' : text;
    
    entry.appendChild(meta);
    entry.appendChild(content);
    commandLog.prepend(entry);
    
    if (commandLog.children.length > 15) {
        commandLog.removeChild(commandLog.lastChild);
    }
}

window.onload = () => {
    document.body.classList.add('booting');
    setupWebSocket();
};

function wakeWhis() { fetch('/api/wake', { method: 'POST' }); }
function exitWhis() { fetch('/api/shutdown', { method: 'POST' }); }
function cancelProcess() {
    fetch('/api/cancel', { method: 'POST' });
    updateState('idle', 'PROCESS TERMINATED BY USER');
}
function shrinkHud() {
    if (window.pywebview && window.pywebview.api) { window.pywebview.api.minimize(); }
}
function expandHud() {
    if (window.pywebview && window.pywebview.api) { window.pywebview.api.maximize(); }
}
function systemDiag() {
    addLogEntry("DIAG", "Running deep system analysis... All neural pathways stable.", "sys");
}

const chatInput = document.getElementById('chat-input');
chatInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') sendChat();
});

function sendChat() {
    const text = chatInput.value.trim();
    if (!text) return;
    
    userText.innerText = `[USER_INPUT]: ${text}`;
    aiText.innerText = 'PROCESSING...';
    chatInput.value = '';
    
    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: text })
    }).catch(err => {
        console.error('Chat error:', err);
        addLogEntry('SYS_ERR', 'Command transmission failed.', 'err');
    });
}

// Telemetry Canvas (Sine Wave)
const tCanvas = document.getElementById('telemetry-canvas');
if(tCanvas) {
    const tCtx = tCanvas.getContext('2d');
    let tOffset = 0;

    function drawTelemetry() {
        requestAnimationFrame(drawTelemetry);
        
        if(tCanvas.width !== tCanvas.clientWidth) tCanvas.width = tCanvas.clientWidth;
        if(tCanvas.height !== tCanvas.clientHeight) tCanvas.height = tCanvas.clientHeight;
        
        tCtx.clearRect(0, 0, tCanvas.width, tCanvas.height);
        tCtx.strokeStyle = '#5b8cff';
        tCtx.lineWidth = 1.5;
        tCtx.beginPath();
        
        let isListening = document.querySelector('.rings-container').classList.contains('state-listening');
        let amplitude = isListening ? 6 : 2;
        let frequency = isListening ? 0.1 : 0.05;
        
        for (let x = 0; x < tCanvas.width; x++) {
            let spike = 0;
            if (!isListening && Math.abs(Math.sin(x * 0.02 + tOffset * 0.5)) > 0.98) {
                spike = Math.sin(x) * 8;
            }
            let y = (tCanvas.height / 2) + Math.sin(x * frequency + tOffset) * amplitude + spike;
            if (x === 0) tCtx.moveTo(x, y);
            else tCtx.lineTo(x, y);
        }
        tCtx.stroke();
        tOffset -= 0.1;
    }
    drawTelemetry();
}

// Particles Canvas
const pCanvas = document.getElementById('particles-canvas');
if(pCanvas) {
    const pCtx = pCanvas.getContext('2d');
    let particles = [];

    function initParticles() {
        pCanvas.width = window.innerWidth;
        pCanvas.height = window.innerHeight;
        particles = [];
        for (let i=0; i<40; i++) {
            particles.push({
                x: Math.random() * pCanvas.width,
                y: Math.random() * pCanvas.height,
                r: Math.random() * 1.5 + 0.5,
                dx: (Math.random() - 0.5) * 0.3,
                dy: (Math.random() - 0.5) * 0.3,
                a: Math.random() * 0.4 + 0.1
            });
        }
    }

    function animateParticles() {
        requestAnimationFrame(animateParticles);
        pCtx.clearRect(0, 0, pCanvas.width, pCanvas.height);
        pCtx.fillStyle = 'rgba(91, 140, 255, 0.8)'; // Primary Glow Color
        
        particles.forEach(p => {
            p.x += p.dx;
            p.y += p.dy;
            if (p.x < 0 || p.x > pCanvas.width) p.dx *= -1;
            if (p.y < 0 || p.y > pCanvas.height) p.dy *= -1;
            
            pCtx.beginPath();
            pCtx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            pCtx.globalAlpha = p.a;
            pCtx.fill();
        });
    }
    window.addEventListener('resize', initParticles);
    initParticles();
    animateParticles();
}
