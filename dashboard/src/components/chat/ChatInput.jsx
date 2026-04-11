/**
 * Chat: ChatInput — Premium text input for voice interaction.
 * Includes a file upload button that uploads to the E2B sandbox when active.
 */

import { useState, useRef, useCallback } from 'react';
import { Send, Paperclip, CheckCircle, RefreshCw, Loader2, Square } from 'lucide-react';
import { useTaskStore } from '@/stores/taskStore';
import { useChatStore } from '@/stores/chatStore';
import { api } from '@/lib/api';

export default function ChatInput({ onSend, onStop, disabled = false, disconnected = false }) {
    const agentState = useChatStore((s) => s.agentState);
    const activeTools = useChatStore((s) => s.activeTools);
    const isGenerating = agentState === 'processing' || agentState === 'speaking' || activeTools.size > 0;
    const [text, setText] = useState('');
    const [uploadStatus, setUploadStatus] = useState(null); // null | 'uploading' | {name, path}
    const fileRef = useRef(null);
    const desktop = useTaskStore((s) => s.desktop);
    const isDesktopRunning = !!desktop?.status && !['destroyed', 'error', 'none'].includes(desktop.status);

    const handleSubmit = (e) => {
        e.preventDefault();
        if (text.trim() && onSend) {
            onSend(text.trim());
            setText('');
        }
    };

    const handleFileUpload = useCallback(async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setUploadStatus('uploading');
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('path', '/home/user');
            await api.postForm('/tasks/desktop/upload', formData);
            setUploadStatus({ name: file.name, path: `/home/user/${file.name}` });
            setTimeout(() => setUploadStatus(null), 4000);
        } catch (err) {
            setUploadStatus(null);
        } finally {
            if (fileRef.current) fileRef.current.value = '';
        }
    }, []);

    return (
        <form onSubmit={handleSubmit} className="flex flex-col gap-1">
            {disconnected && (
                <p className="text-xs text-amber-500/80 px-1">Chat disconnected — reconnecting…</p>
            )}
            {uploadStatus && uploadStatus !== 'uploading' && (
                <p className="flex items-center gap-1 text-xs text-emerald-400 px-1">
                    <CheckCircle size={12} />
                    {uploadStatus.name} → {uploadStatus.path}
                </p>
            )}
            {isGenerating && (
                <div className="flex items-center gap-2 px-1">
                    <Loader2 size={12} className="animate-spin text-blue-400" />
                    <span className="text-xs text-blue-400/80">
                        {activeTools.size > 0
                            ? `Running ${[...activeTools].join(', ')}…`
                            : 'Generating response…'}
                    </span>
                </div>
            )}
            <div className="flex items-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2 transition-colors focus-within:border-white/[0.15] focus-within:bg-white/[0.05]">
                <input
                    ref={fileRef}
                    type="file"
                    onChange={handleFileUpload}
                    className="hidden"
                />
                <button
                    type="button"
                    onClick={() => fileRef.current?.click()}
                    disabled={disabled || !isDesktopRunning || uploadStatus === 'uploading'}
                    className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
                    title={isDesktopRunning ? 'Upload file to sandbox' : 'Start a desktop sandbox to upload files'}
                >
                    {uploadStatus === 'uploading' ? <RefreshCw size={16} className="animate-spin" /> : <Paperclip size={16} />}
                </button>
                <input
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder={disconnected ? 'Reconnecting…' : isGenerating ? 'AI is thinking… press Stop to cancel' : 'Type a message...'}
                    disabled={disabled}
                    className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none"
                />
                {isGenerating ? (
                    <button
                        type="button"
                        onClick={onStop}
                        className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/90 text-white transition-all hover:bg-red-500 active:scale-95"
                        title="Stop generating"
                    >
                        <Square size={12} fill="currentColor" />
                    </button>
                ) : (
                    <button
                        type="submit"
                        disabled={disabled || !text.trim()}
                        className="flex h-8 w-8 items-center justify-center rounded-lg bg-foreground text-background transition-all hover:bg-foreground/90 disabled:opacity-30 disabled:hover:bg-foreground"
                    >
                        <Send size={14} />
                    </button>
                )}
            </div>
        </form>
    );
}
