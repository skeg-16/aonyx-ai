import React, { useState, useEffect } from 'react';
import { useStore } from './store';
import { Core3D } from './Core3D';

const Waveform: React.FC<{rms: number, state: string}> = ({rms, state}) => {
    const bars = 40;
    const isVoiceActive = state === 'LISTENING' || state === 'SPEAKING';
    
    return (
        <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            height: '80px', width: '100%', position: 'relative',
            opacity: isVoiceActive ? 1 : (state === 'THINKING' ? 0.3 : 0),
            transition: 'opacity 0.5s ease-in-out'
        }}>
            {/* Soft background glow */}
            <div style={{
                position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
                width: '300px', height: '40px', background: state === 'LISTENING' ? '#ff3b4e' : '#5b8cff',
                filter: 'blur(30px)', opacity: isVoiceActive ? (rms / 200) + 0.1 : 0.05,
                borderRadius: '50%'
            }} />
            
            {/* Primary Waveform */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '3px', zIndex: 2 }}>
                {Array.from({ length: bars }).map((_, i) => {
                    const normalized = (i - bars/2) / (bars/2);
                    const bell = Math.exp(-0.5 * Math.pow(normalized / 0.4, 2));
                    const intensity = state === 'THINKING' ? 10 : rms;
                    const height = Math.max(2, (intensity * bell * (Math.random()*0.4 + 0.6)));
                    return (
                        <div key={i} style={{
                            width: '4px',
                            height: `${height}px`,
                            background: state === 'LISTENING' ? '#ff3b4e' : (state === 'ERROR' ? '#ff3b4e' : '#5b8cff'),
                            borderRadius: '2px',
                            transition: 'height 0.05s ease',
                            boxShadow: `0 0 10px ${state === 'LISTENING' ? '#ff3b4e' : '#5b8cff'}`
                        }} />
                    );
                })}
            </div>
            
            {/* Secondary Faint Waveform (Reflection) */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '3px', opacity: 0.3, transform: 'scaleY(-0.5)', marginTop: '2px' }}>
                {Array.from({ length: bars }).map((_, i) => {
                    const normalized = (i - bars/2) / (bars/2);
                    const bell = Math.exp(-0.5 * Math.pow(normalized / 0.4, 2));
                    const intensity = state === 'THINKING' ? 10 : rms;
                    const height = Math.max(2, (intensity * bell * (Math.random()*0.4 + 0.6)));
                    return (
                        <div key={`ref-${i}`} style={{
                            width: '4px',
                            height: `${height}px`,
                            background: state === 'LISTENING' ? '#ff3b4e' : '#5b8cff',
                            borderRadius: '2px',
                            transition: 'height 0.05s ease'
                        }} />
                    );
                })}
            </div>
        </div>
    );
};

const App: React.FC = () => {
    const { state, message, errorText, isVisible, rms, memoryCount } = useStore();
    const [input, setInput] = useState('');
    const [lastInput, setLastInput] = useState('');
    const [isCompact, setIsCompact] = useState(window.innerHeight < 300);
    const [toolActivity, setToolActivity] = useState<{name: string, status: string} | null>(null);
    const [confirmRequest, setConfirmRequest] = useState<{name: string, args: any} | null>(null);

    useEffect(() => {
        const handleTool = (e: any) => setToolActivity({name: e.detail.name, status: e.detail.status});
        const handleConfirm = (e: any) => setConfirmRequest({name: e.detail.name, args: JSON.parse(e.detail.args)});
        
        window.addEventListener('whis-tool', handleTool);
        window.addEventListener('whis-confirm', handleConfirm);
        
        return () => {
            window.removeEventListener('whis-tool', handleTool);
            window.removeEventListener('whis-confirm', handleConfirm);
        };
    }, []);

    const handleConfirmResponse = (approved: boolean) => {
        setConfirmRequest(null);
        if ((window as any).pywebview && (window as any).pywebview.api) {
            (window as any).pywebview.api.handle_confirm(approved);
        }
    };

    useEffect(() => {
        const handleResize = () => setIsCompact(window.innerHeight < 300);
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim()) return;
        
        setLastInput(input);
        if ((window as any).pywebview && (window as any).pywebview.api) {
            (window as any).pywebview.api.send_message(input);
        }
        
        setInput('');
    };

    const handleStop = () => {
        if ((window as any).pywebview && (window as any).pywebview.api) {
            (window as any).pywebview.api.stop_speaking();
        }
    };

    const handleCoreClick = () => {
        if (state === 'SPEAKING') {
            handleStop();
        } else {
            if ((window as any).pywebview && (window as any).pywebview.api) {
                (window as any).pywebview.api.toggle_listening();
            }
        }
    };

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                if (state === 'SPEAKING') {
                    handleStop();
                }
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [state]);

    if (isCompact) {
        return (
            <div style={{ width: '100vw', height: '100vh', overflow: 'hidden', position: 'relative', backgroundColor: '#010714' }}>
                <Core3D state={state} isVisible={isVisible} rms={rms} isCompact={true} onCoreClick={handleCoreClick} />
                <div style={{
                    position: 'absolute', bottom: '10px', width: '100%', textAlign: 'center',
                    color: state === 'ERROR' ? '#ff3b4e' : '#5b8cff', fontSize: '12px',
                    textShadow: '0 0 5px rgba(0,0,0,0.8)', zIndex: 10,
                    pointerEvents: 'none', fontWeight: 'bold', letterSpacing: '2px',
                    fontFamily: "'Rajdhani', sans-serif"
                }}>
                    {state}
                </div>
            </div>
        );
    }

    // Parse message
    let userText = '';
    let aonyxText = message;
    if (message.startsWith('User: ')) {
        const parts = message.split('\n\nAonyx: ');
        if (parts.length > 1) {
            userText = parts[0].replace('User: ', '');
            aonyxText = parts[1];
        } else {
            const fallbackParts = message.split('\n\n');
            if(fallbackParts.length > 1) {
                 userText = fallbackParts[0].replace('User: ', '');
                 aonyxText = fallbackParts[1];
            }
        }
    }

    return (
        <div style={{ width: '100vw', height: '100vh', overflow: 'hidden', position: 'relative' }}>
            {/* Background Effects */}
            <div className="vignette"></div>
            <div className="film-grain"></div>
            <div className="perspective-grid"></div>

            {/* 3D Core - Background */}
            <Core3D state={state} isVisible={isVisible} rms={rms} isCompact={false} onCoreClick={handleCoreClick} />

            {/* Top Left Glass Panel */}
            <div className={`glass-panel panel-left ${state === 'LISTENING' ? 'panel-listening' : ''}`}>
                <div className="panel-header">SYSTEM METRICS</div>
                <div className="panel-row"><span>CPU LOAD</span><span>--%</span></div>
                <div className="panel-row"><span>MEM USAGE</span><span>-- GB</span></div>
                <div className="panel-row"><span>DSK I/O</span><span>--%</span></div>
                <div className="panel-row"><span>NET PING</span><span>-- MS</span></div>
            </div>

            {/* Top Right Glass Panel */}
            <div className={`glass-panel panel-right ${state === 'LISTENING' ? 'panel-listening' : ''}`}>
                <div className="panel-header">AONYX STATUS</div>
                <div className="panel-row"><span>ORCHESTRATOR</span><span style={{color:'#5b8cff'}}>ONLINE</span></div>
                <div className="panel-row"><span>LLM_MODEL</span><span>LLAMA3</span></div>
                <div className="panel-row"><span>STATE</span><span style={{color: state==='ERROR'?'#ff3b4e':'#9db9ff'}}>{state}</span></div>
                <div className="panel-row"><span>MEMORY_DB</span><span style={{color: '#9db9ff'}}>{memoryCount > 0 ? `${memoryCount} ENTRIES` : 'EMPTY'}</span></div>
            </div>

            {/* Dynamic Status Indicator */}
            <div className="status-indicator">
                <span className="status-dot" style={{ backgroundColor: state === 'ERROR' ? '#ff3b4e' : (state === 'LISTENING' ? '#ff3b4e' : '#5b8cff') }}></span>
                NEURAL CORE // {state}
            </div>

            {/* Tool Activity HUD */}
            {toolActivity && state === 'TOOL_EXECUTION' && (
                <div className="tool-activity">
                    <div className="tool-spinner"></div>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '10px', color: '#5b8cff', letterSpacing: '2px' }}>EXECUTING DIRECTIVE</span>
                        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                            <span className="tool-name">{toolActivity.name}</span>
                            <span className="tool-status">[{toolActivity.status}]</span>
                        </div>
                    </div>
                </div>
            )}
            
            {/* Confirm Modal */}
            {confirmRequest && (
                <div className="confirm-modal">
                    <h3>Permission Required</h3>
                    <p>Tool: <strong>{confirmRequest.name}</strong></p>
                    <pre>{JSON.stringify(confirmRequest.args, null, 2)}</pre>
                    <div className="confirm-buttons">
                        <button className="btn-approve" onClick={() => handleConfirmResponse(true)}>Confirm</button>
                        <button className="btn-deny" onClick={() => handleConfirmResponse(false)}>Deny</button>
                    </div>
                </div>
            )}

            {/* Bottom Stack: Waveform -> Response -> Input Bar */}
            <div className="bottom-stack">
                <Waveform rms={rms} state={state} />
                
                <div className="chat-container">
                    {userText && (
                        <div className="chat-message chat-user">
                            "{userText}"
                        </div>
                    )}
                    {aonyxText && (
                        <div className="chat-message chat-aonyx">
                            {aonyxText}
                        </div>
                    )}
                    
                    {state === 'ERROR' && (
                        <div className="chat-message" style={{ color: '#ff3b4e', fontWeight: 'bold', display: 'flex', gap: '15px', alignItems: 'center', justifyContent: 'center' }}>
                            <span>ERROR: {errorText}</span>
                            {lastInput && (
                                <button 
                                    onClick={() => (window as any).pywebview.api.retry_last(lastInput)}
                                    style={{background: 'rgba(255, 59, 78, 0.2)', color: '#ff3b4e', border: '1px solid #ff3b4e', padding: '4px 10px', cursor: 'pointer', borderRadius: '4px', fontFamily: "'Rajdhani', sans-serif", fontWeight: 'bold', pointerEvents: 'auto'}}
                                >
                                    RETRY
                                </button>
                            )}
                        </div>
                    )}
                </div>

                <form className={`input-bar ${state === 'LISTENING' ? 'input-listening' : ''}`} onSubmit={handleSubmit}>
                    <button 
                        type="button" 
                        onClick={() => (window as any).pywebview.api.toggle_listening()} 
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: state === 'LISTENING' ? '#ff3b4e' : '#5b8cff', padding: '0 10px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                        title="START LISTENING"
                    >
                        <svg width="20" height="20" viewBox="0 0 24 24" fill={state === 'LISTENING' ? '#ff3b4e' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path>
                            <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                            <line x1="12" y1="19" x2="12" y2="23"></line>
                            <line x1="8" y1="23" x2="16" y2="23"></line>
                        </svg>
                    </button>
                    {state === 'SPEAKING' && (
                        <button 
                            type="button" 
                            onClick={handleStop} 
                            style={{ background: 'rgba(255, 59, 78, 0.1)', border: '1px solid #ff3b4e', borderRadius: '4px', cursor: 'pointer', color: '#ff3b4e', padding: '4px 10px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '10px' }}
                            title="STOP SPEAKING"
                        >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                            </svg>
                        </button>
                    )}
                    <input 
                        type="text" 
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder={state === 'SPEAKING' ? "Aonyx is speaking... (Esc to stop)" : "Enter directive or press Ctrl+Alt+Space to speak..."}
                        disabled={state === 'THINKING' || state === 'SPEAKING' || state === 'LISTENING'}
                    />
                    <button type="submit" disabled={state === 'THINKING' || state === 'SPEAKING'}>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13"></line>
                            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                        </svg>
                    </button>
                </form>
            </div>
        </div>
    );
};

export default App;
