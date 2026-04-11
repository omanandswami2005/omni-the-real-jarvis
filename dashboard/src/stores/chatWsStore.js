/**
 * Bridge store — exposes the /ws/chat WebSocket sendText for typed messages.
 *
 * Typed text from the dashboard should go through /ws/chat (text model)
 * instead of /ws/live (audio model), so the backend can return formatted
 * text, code blocks, and GenUI.  Voice/audio continues on /ws/live.
 */

import { create } from 'zustand';

export const useChatWsStore = create((set) => ({
    /** The sendText function from useChatWebSocket (null until connected). */
    sendText: null,
    /** Whether the /ws/chat connection is open. */
    isConnected: false,

    setSendText: (fn) => set({ sendText: fn }),
    setIsConnected: (v) => set({ isConnected: v }),
}));
