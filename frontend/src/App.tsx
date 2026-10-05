import React, { useState, useEffect } from 'react';
import { useStore } from './store';
import { Core3D } from './Core3D';

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

    if (isCompact) {
        return (
            <div style={{ width: '100vw', height: '100vh', overflow: 'hidden', position: 'relative', backgroundColor: '#010714' }}>
                <Core3D state={state} isVisible={isVisible} rms={rms} />
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
            <Core3D state={state} isVisible={isVisible} rms={rms} />

            {/* Top Left Glass Panel - Metrics (Mocked) */}
            <div className="glass-panel" style={{ position: 'absolute', top: '20px', left: '20px', width: '200px', zIndex: 10 }}>
                <div style={{ color: '#5b8cff', marginBottom: '5px', fontWeight: 'bold' }}>SYSTEM METRICS</div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>CPU</span><span>--%</span></div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>MEM</span><span>-- GB</span></div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>DSK</span><span>--%</span></div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>NET</span><span>-- ms</span></div>
            </div>

            {/* Top Right Glass Panel - Status */}
            <div className="glass-panel" style={{ position: 'absolute', top: '20px', right: '20px', width: '200px', zIndex: 10 }}>
                <div style={{ color: '#5b8cff', marginBottom: '5px', fontWeight: 'bold' }}>AONYX STATUS</div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>OLLAMA</span><span>OK</span></div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>MODEL</span><span>LLAMA3</span></div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>CORE</span><span style={{color: state==='ERROR'?'#ff3b4e':'#9db9ff'}}>{state}</span></div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>MEMORY</span><span style={{color: '#9db9ff'}}>{memoryCount > 0 ? `${memoryCount} ENTRIES` : 'EMPTY'}</span></div>
            </div>

            {/* Status Text Overlay near Core */}
            <div style={{
                position: 'absolute', top: '40%', left: '50%', transform: 'translate(-50%, -50%)',
                textAlign: 'center', pointerEvents: 'none', zIndex: 5, width: '100%'
            }}>
                <div style={{
                    color: state === 'ERROR' ? '#ff3b4e' : 'rgba(91, 140, 255, 0.4)', 
                    fontFamily: "'Orbitron', sans-serif", fontSize: '12px', letterSpacing: '4px',
                    fontWeight: 700, textTransform: 'uppercase'
                }}>
                    NEURAL CORE {state} // AWAITING DIRECTIVE
                </div>
            </div>

            {/* Tool Activity HUD */}
            {toolActivity && state === 'TOOL_EXECUTION' && (
                <div className="tool-activity">
                    <span className="tool-name">{toolActivity.name}</span>
                    <span className="tool-status">[{toolActivity.status}]</span>
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

            {/* Floating Chat */}
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
                    <div className="chat-message" style={{ color: '#ff3b4e', fontWeight: 'bold', display: 'flex', gap: '15px', alignItems: 'center' }}>
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

            {/* Slim Command Bar */}
            <form className="input-bar" onSubmit={handleSubmit} style={{ display: 'flex', alignItems: 'center' }}>
                <button type="button" onClick={() => (window as any).pywebview.api.toggle_listening()} style={{ background: 'none', border: 'none', cursor: 'pointer', color: state === 'LISTENING' ? '#ff3b4e' : '#5b8cff', padding: '0 10px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill={state === 'LISTENING' ? '#ff3b4e' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path>
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                        <line x1="12" y1="19" x2="12" y2="23"></line>
                        <line x1="8" y1="23" x2="16" y2="23"></line>
                    </svg>
                </button>
                <input 
                    type="text" 
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Enter directive or press Ctrl+Alt+Space to speak..."
                    disabled={state === 'THINKING' || state === 'SPEAKING' || state === 'LISTENING'}
                    style={{ flexGrow: 1 }}
                />
                <button type="submit" disabled={state === 'THINKING' || state === 'SPEAKING'}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="22" y1="2" x2="11" y2="13"></line>
                        <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                    </svg>
                </button>
            </form>
        </div>
    );
};

export default App;
