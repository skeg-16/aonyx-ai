import type { AppState } from './store';

/**
 * Mutable, non-React shared state. Everything that changes every frame lives here so that
 * animation code (R3F useFrame / canvas rAF) never triggers React re-renders.
 */

/** Raw audio level coming from the backend: microphone while LISTENING, Aonyx's own TTS while SPEAKING. */
export const audioBus = {
    raw: 0,                       // 0..1 (perceptual level, already RMS-derived on the backend)
    src: 'none' as 'mic' | 'tts' | 'none',
    at: 0,
};

/** Latest audible speech position reported by the audio engine (audio = timing source). */
export const speechClock = {
    uid: -1,
    idx: -1,
    pos: 0,           // seconds into the current segment at time `at`
    at: 0,            // performance.now() when pos was received
    playing: false,
};

/** Pointer / physical interaction state (written by DOM listeners, read by the render loop). */
export const interaction = {
    px: 0, py: 0,                 // cursor, normalised -1..1 (y up) relative to the core centre
    hoverT: 0, awareT: 0,         // targets
    pressing: false, dragging: false,
    dX: 0, dY: 0,                 // drag delta (px) accumulated since last frame
    rotX: 0, rotY: 0, velX: 0, velY: 0,
};

/** Smoothed drivers consumed by the core, the environment and the voice field. */
export const drive = {
    level: 0,                     // 0..1, smoothed audio level for the active source
    hover: 0, aware: 0, press: 0, drag: 0,
    listen: 0, think: 0, exec: 0, speak: 0, error: 0,
    web: 0, memory: 0, desktop: 0,
    chain: 0,                     // number of orbiting "chain" nodes (tools used this run)
    pulseAt: 0,                   // performance.now() of last speech pulse (real audio peak)
    pulseSeq: 0,
};

/** Live copy of app state for animation loops (updated from React once per state change). */
export const live = {
    state: 'IDLE' as AppState,
    kind: 'none' as ToolKind,
    toolCount: 0,
    visible: true,
};

export type ToolKind = 'none' | 'web' | 'memory' | 'desktop' | 'action';

const TOOL_META: Record<string, { kind: ToolKind; label: string }> = {
    SEARCH_WEB: { kind: 'web', label: 'SEARCHING WEB' },
    FETCH_WEBPAGE: { kind: 'web', label: 'READING WEB PAGE' },
    STORE_MEMORY: { kind: 'memory', label: 'STORING MEMORY' },
    RETRIEVE_MEMORY: { kind: 'memory', label: 'ACCESSING MEMORY' },
    UPDATE_MEMORY: { kind: 'memory', label: 'UPDATING MEMORY' },
    DELETE_MEMORY: { kind: 'memory', label: 'REMOVING MEMORY' },
    get_active_window: { kind: 'desktop', label: 'CHECKING ACTIVE WINDOW' },
    get_desktop_info: { kind: 'desktop', label: 'SCANNING SYSTEM' },
    system_information: { kind: 'desktop', label: 'CHECKING SYSTEM' },
    check_application: { kind: 'desktop', label: 'CHECKING APPLICATION' },
    focus_application: { kind: 'desktop', label: 'FOCUSING APPLICATION' },
    calculator: { kind: 'action', label: 'CALCULATING' },
    get_current_time: { kind: 'action', label: 'CHECKING TIME' },
    open_application: { kind: 'action', label: 'OPENING APPLICATION' },
    open_url: { kind: 'action', label: 'OPENING LINK' },
    read_file: { kind: 'action', label: 'READING FILE' },
    create_note: { kind: 'action', label: 'WRITING NOTE' },
    search_local_files: { kind: 'action', label: 'SEARCHING FILES' },
    set_aonyx_visibility: { kind: 'action', label: 'ADJUSTING INTERFACE' },
};

export function toolMeta(name: string): { kind: ToolKind; label: string } {
    return TOOL_META[name] ?? { kind: 'action', label: 'WORKING' };
}

export const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
/** Frame-rate independent exponential smoothing factor. */
export const damp = (k: number, dt: number) => 1 - Math.exp(-k * dt);

export function bindEvents() {
    window.addEventListener('whis-rms', (e: any) => {
        if (e.detail) {
            audioBus.raw = e.detail.rms / 100;
            audioBus.src = e.detail.src || 'none';
            audioBus.at = performance.now();
        }
    });

    window.addEventListener('whis-state', (e: any) => {
        if (e.detail && e.detail.state) {
            live.state = e.detail.state;
        }
    });

    window.addEventListener('whis-speech', (e: any) => {
        if (e.detail) {
            speechClock.uid = e.detail.uid;
            speechClock.idx = e.detail.idx;
            speechClock.pos = e.detail.pos;
            speechClock.at = performance.now();
            speechClock.playing = e.detail.playing;
        }
    });

    window.addEventListener('whis-seg-start', (e: any) => {
        if (e.detail && e.detail.words) {
            (window as any).currentSpeechWords = {
                uid: e.detail.uid,
                idx: e.detail.idx,
                words: e.detail.words
            };
        }
    });

    window.addEventListener('whis-tool', (e: any) => {
        if (e.detail) {
            live.kind = toolMeta(e.detail.name).kind;
            live.toolCount++;
        }
    });

    window.addEventListener('pointermove', (e) => {
        interaction.px = (e.clientX / window.innerWidth) * 2 - 1;
        interaction.py = -(e.clientY / window.innerHeight) * 2 + 1;
        interaction.velX = e.movementX;
        interaction.velY = e.movementY;
        if (interaction.dragging) {
            interaction.dX += e.movementX;
            interaction.dY += e.movementY;
        }
    });

    window.addEventListener('pointerdown', () => {
        interaction.pressing = true;
        if (interaction.hoverT > 0) {
            interaction.dragging = true;
        }
    });

    window.addEventListener('pointerup', () => {
        interaction.pressing = false;
        interaction.dragging = false;
    });
}

export function updateFrame(dt: number) {
    const k = damp(10, dt);
    
    // decay raw if too old (backend might have stopped sending without sending 0)
    if (performance.now() - audioBus.at > 200) {
        audioBus.raw = 0;
    }

    drive.level += (audioBus.raw - drive.level) * k;
    
    const st = live.state;
    drive.listen += ((st === 'LISTENING' ? 1 : 0) - drive.listen) * k;
    drive.think += ((st === 'THINKING' ? 1 : 0) - drive.think) * k;
    drive.exec += ((st === 'TOOL_EXECUTION' ? 1 : 0) - drive.exec) * k;
    drive.speak += ((st === 'SPEAKING' ? 1 : 0) - drive.speak) * k;
    drive.error += ((st === 'ERROR' ? 1 : 0) - drive.error) * k;

    interaction.velX *= 0.9;
    interaction.velY *= 0.9;
    
    drive.hover += (interaction.hoverT - drive.hover) * k;
    drive.press += ((interaction.pressing ? 1 : 0) - drive.press) * (interaction.pressing ? 1 : damp(5, dt));
}

// Bind events on module load
if (typeof window !== 'undefined') {
    bindEvents();
}
