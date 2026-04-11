/**
 * resetStores — Clears all user-specific data from Zustand stores on sign-out
 * or user switch. App-level settings (theme, UI state) are preserved.
 */

import { useChatStore } from '@/stores/chatStore';
import { useSessionStore } from '@/stores/sessionStore';
import { useClientStore } from '@/stores/clientStore';
import { usePersonaStore } from '@/stores/personaStore';
import { usePipelineStore } from '@/stores/pipelineStore';
import { useTaskStore } from '@/stores/taskStore';
import { useSessionSuggestionStore } from '@/stores/sessionSuggestionStore';

/**
 * Clear all user-scoped state from every store. Called on sign-out and when
 * the Firebase UID changes (account switch). Theme and UI layout are kept.
 */
export function resetAllUserStores() {
    // Chat — messages, transcripts, agent state, audio queue
    const chat = useChatStore.getState();
    chat.clearMessages();
    chat.clearAudioQueue();
    chat.setAgentState('idle');
    chat.cancelAllActions();

    // Sessions — list, active ID
    useSessionStore.setState({
        sessions: [],
        activeSessionId: null,
        loading: false,
        messagesLoading: false,
        error: null,
        wantsNewSession: false,
    });

    // Connected clients
    useClientStore.setState({
        clients: [],
        micFloorHolder: null,
    });

    // Personas — clear user-loaded list, keep defaults lazy
    usePersonaStore.setState({
        personas: [],
        activePersona: null,
        loading: false,
        error: null,
    });
    // Clear persisted persona from localStorage
    try { localStorage.removeItem('omni-persona'); } catch { /* noop */ }

    // Pipeline / task architect
    const pipe = usePipelineStore.getState();
    if (pipe.clearPipeline) pipe.clearPipeline();
    usePipelineStore.setState({ history: [] });

    // Background tasks / E2B desktop
    const tasks = useTaskStore.getState();
    if (tasks.clearTasks) tasks.clearTasks();
    useTaskStore.setState({ desktop: null, isAgentStreaming: false });

    // Session suggestion banner
    useSessionSuggestionStore.getState().dismiss?.();
}
