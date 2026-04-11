/**
 * Layout: AppShell — Main application shell with sidebar + content area.
 * Wraps all authenticated routes with the global VoiceProvider so voice
 * interaction persists across page navigations.
 */

import { Outlet } from 'react-router';
import Sidebar from '@/components/layout/Sidebar';
import TopBar from '@/components/layout/TopBar';
import MobileNav from '@/components/layout/MobileNav';
import FloatingVoiceBubble from '@/components/chat/FloatingVoiceBubble';
import MediaPreviewOverlay from '@/components/chat/MediaPreviewOverlay';
import PermissionErrorBanner from '@/components/chat/PermissionErrorBanner';
import SessionSuggestionBanner from '@/components/clients/SessionSuggestionBanner';
import CommandPalette from '@/components/layout/CommandPalette';
import { VoiceProvider, useVoice } from '@/hooks/useVoiceProvider';
import { useBootstrap } from '@/hooks/useBootstrap';
import { useEventSocket } from '@/hooks/useEventSocket';
import { useChatWebSocket } from '@/hooks/useChatWebSocket';
import { useIsMobile } from '@/hooks/useMediaQuery';
import { useBillingStore } from '@/stores/billingStore';

export function AppShell() {
  return (
    <VoiceProvider>
      <ShellLayout />
    </VoiceProvider>
  );
}

function ShellLayout() {
  const isMobile = useIsMobile();
  const voice = useVoice();
  useBootstrap();
  useEventSocket();
  useChatWebSocket();

  const { isLowCredits, isExhausted, credits, fetchBillingStatus } = useBillingStore();
  const low = isLowCredits();
  const exhausted = isExhausted();

  return (
    <div className="flex h-screen bg-background text-foreground">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar />
        {exhausted && (
          <div className="flex items-center justify-between bg-destructive/90 text-destructive-foreground px-4 py-2 text-sm font-medium">
            <span>Your credits are exhausted. Upgrade your plan to continue using Omni.</span>
            <a href="/settings?tab=Billing" className="underline font-semibold ml-2 whitespace-nowrap">Upgrade now</a>
          </div>
        )}
        {low && !exhausted && (
          <div className="flex items-center justify-between bg-yellow-500/90 text-yellow-950 px-4 py-2 text-sm font-medium">
            <span>You're running low on credits ({credits?.balance ?? 0} remaining).</span>
            <a href="/settings?tab=Billing" className="underline font-semibold ml-2 whitespace-nowrap">View plans</a>
          </div>
        )}
        <main className="flex-1 overflow-y-auto p-4 pb-20 md:pb-4">
          <Outlet />
        </main>
      </div>
      {isMobile && <MobileNav />}

      {/* Session continuity suggestion banner */}
      <SessionSuggestionBanner />

      {/* Permission denied / device busy / not-found toast */}
      <PermissionErrorBanner
        error={voice.permissionError}
        onDismiss={voice.clearPermissionError}
      />

      {/* Live camera / screen share PiP preview */}
      {voice.isVideoActive && (
        <MediaPreviewOverlay
          stream={voice.getPreviewStream()}
          source={voice.videoSource}
          onClose={voice.videoSource === 'screen' ? voice.toggleScreen : voice.toggleCamera}
          onFlipCamera={voice.videoSource === 'camera' ? voice.flipCamera : undefined}
        />
      )}

      {/* Global command palette (⌘K) */}
      <CommandPalette />

      {/* Global floating voice bubble — always visible */}
      <FloatingVoiceBubble
        isRecording={voice.isRecording}
        isMuted={voice.isMuted}
        isScreenSharing={voice.isScreenSharing}
        isCameraOn={voice.isCameraOn}
        isVideoActive={voice.isVideoActive}
        captureVolume={voice.captureVolume}
        playbackVolume={voice.playbackVolume}
        micBlocked={voice.micBlocked}
        onToggleRecording={voice.toggleRecording}
        onToggleMute={voice.toggleMute}
        onToggleScreen={voice.toggleScreen}
        onToggleCamera={voice.toggleCamera}
        isConnected={voice.isConnected}
      />
    </div>
  );
}

export default AppShell;
