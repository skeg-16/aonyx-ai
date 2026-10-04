import { create } from 'zustand';

export type AppState = 'IDLE' | 'LISTENING' | 'THINKING' | 'TOOL_EXECUTION' | 'SPEAKING' | 'ERROR';

interface StoreState {
    state: AppState;
    message: string;
    errorText: string;
    isVisible: boolean;
    rms: number;
    setState: (state: AppState) => void;
    setMessage: (msg: string) => void;
    setError: (err: string) => void;
    setVisibility: (visible: boolean) => void;
    setRms: (rms: number) => void;
}

export const useStore = create<StoreState>((set) => ({
    state: 'IDLE',
    message: '',
    errorText: '',
    isVisible: true,
    rms: 0,
    setState: (state) => set({ state }),
    setMessage: (message) => set({ message }),
    setError: (errorText) => set({ errorText }),
    setVisibility: (isVisible) => set({ isVisible }),
    setRms: (rms) => set({ rms }),
}));

// Listen for events from Python backend
window.addEventListener('whis-state', (e: any) => {
    if (e.detail && e.detail.state) {
        useStore.getState().setState(e.detail.state);
    }
});

window.addEventListener('whis-message', (e: any) => {
    if (e.detail && e.detail.message !== undefined) {
        useStore.getState().setMessage(e.detail.message);
    }
});

window.addEventListener('whis-error', (e: any) => {
    if (e.detail && e.detail.errorText) {
        useStore.getState().setError(e.detail.errorText);
        useStore.getState().setState('ERROR');
    }
});

window.addEventListener('aonyx-visibility', (e: any) => {
    if (e.detail && e.detail.visible !== undefined) {
        useStore.getState().setVisibility(e.detail.visible);
    }
});

window.addEventListener('whis-rms', (e: any) => {
    if (e.detail && e.detail.rms !== undefined) {
        useStore.getState().setRms(e.detail.rms);
    }
});
