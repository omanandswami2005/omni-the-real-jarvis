/**
 * Page: SettingsPage — Application settings (theme, audio, privacy, shortcuts, billing).
 */

import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { toast } from 'sonner';
import ThemeToggle from '@/components/layout/ThemeToggle';
import { useAuthStore } from '@/stores/authStore';
import { useAuth } from '@/hooks/useAuth';
import { api } from '@/lib/api';
import { auth } from '@/lib/firebase';
import { useVoice } from '@/hooks/useVoiceProvider';
import { usePersonaStore } from '@/stores/personaStore';
import { useBillingStore } from '@/stores/billingStore';

const TABS = ['General', 'Audio', 'Billing', 'Privacy', 'Shortcuts'];

// Gemini prebuilt voices (subset)
const AVAILABLE_VOICES = [
  { id: 'Aoede', label: 'Aoede', description: 'Warm and friendly' },
  { id: 'Charon', label: 'Charon', description: 'Deep and authoritative' },
  { id: 'Kore', label: 'Kore', description: 'Clear and analytical' },
  { id: 'Puck', label: 'Puck', description: 'Energetic and dynamic' },
  { id: 'Leda', label: 'Leda', description: 'Creative and expressive' },
  { id: 'Fenrir', label: 'Fenrir', description: 'Calm and composed' },
  { id: 'Orus', label: 'Orus', description: 'Steady and reliable' },
  { id: 'Zephyr', label: 'Zephyr', description: 'Light and airy' },
];

const SHORTCUTS = [
  { keys: 'Ctrl + K', action: 'Command palette' },
  { keys: 'Ctrl + /', action: 'Toggle sidebar' },
  { keys: 'Space', action: 'Push-to-talk (when not in input)' },
  { keys: 'Escape', action: 'Stop recording / close modal' },
];

export default function SettingsPage() {
  useDocumentTitle('Settings');
  const [searchParams] = useSearchParams();
  const initialTab = TABS.includes(searchParams.get('tab')) ? searchParams.get('tab') : 'General';
  const [tab, setTab] = useState(initialTab);
  const [signingOut, setSigningOut] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);
  const user = useAuthStore((s) => s.user);
  const { signOut } = useAuth();
  const navigate = useNavigate();
  const voice = useVoice();
  const activePersona = usePersonaStore((s) => s.activePersona);
  const personas = usePersonaStore((s) => s.personas);
  const setActivePersona = usePersonaStore((s) => s.setActivePersona);

  // Billing store
  const billing = useBillingStore();

  // Load billing data when billing tab is active
  useEffect(() => {
    if (tab === 'Billing') {
      billing.fetchBillingStatus();
      billing.fetchUsage();
    }
  }, [tab]);

  // Determine the current voice from the active persona
  const currentVoice = activePersona?.voice || 'Aoede';

  const handleVoiceChange = (voiceId) => {
    if (!activePersona) return;
    // Update the active persona's voice locally
    const updated = { ...activePersona, voice: voiceId };
    setActivePersona(updated);
    // Reconnect to apply the voice change
    voice.reconnect?.();
  };

  const handleSignOut = async () => {
    setSigningOut(true);
    try {
      await signOut();
      // Wait a bit for the auth state to propagate
      await new Promise(resolve => setTimeout(resolve, 500));
      // Force a full page reload with cache bypass to clear all state
      window.location.replace('/login?t=' + Date.now());
    } catch (error) {
      console.error('Sign out failed:', error);
      // Force navigation even if signOut fails
      window.location.replace('/login?t=' + Date.now());
    } finally {
      setSigningOut(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirmText !== 'DELETE') return;
    setDeleting(true);
    try {
      // Re-authenticate to get a fresh token (Firebase requires recent auth for destructive ops)
      const fbUser = auth.currentUser;
      if (fbUser) {
        const freshToken = await fbUser.getIdToken(true);
        await api.delete('/auth/account', { token: freshToken });
      }
      toast.success('Account deleted successfully');
      await signOut();
      window.location.replace('/login?t=' + Date.now());
    } catch (error) {
      console.error('Account deletion failed:', error);
      toast.error(error.message || 'Failed to delete account. Please try again.');
    } finally {
      setDeleting(false);
      setShowDeleteConfirm(false);
      setDeleteConfirmText('');
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      {/* Tab nav */}
      <nav className="flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${tab === t ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
          >
            {t}
          </button>
        ))}
      </nav>

      {/* General */}
      {tab === 'General' && (
        <div className="space-y-6">
          <section className="space-y-4">
            <h2 className="text-lg font-medium">Appearance</h2>
            <div className="flex items-center justify-between rounded-lg border border-border p-4">
              <span>Theme</span>
              <ThemeToggle />
            </div>
          </section>

          <section className="space-y-4">
            <h2 className="text-lg font-medium">Account</h2>
            <div className="rounded-lg border border-border p-4">
              {user ? (
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{user.displayName || user.email}</p>
                    <p className="text-sm text-muted-foreground">{user.email}</p>
                  </div>
                  <button onClick={handleSignOut} disabled={signingOut} className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted disabled:opacity-50">
                    {signingOut ? 'Signing out...' : 'Sign out'}
                  </button>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Not signed in</p>
              )}
            </div>
          </section>
        </div>
      )}

      {/* Audio */}
      {tab === 'Audio' && (
        <div className="space-y-4">
          <h2 className="text-lg font-medium">Audio Settings</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-lg border border-border p-4">
              <div>
                <p className="text-sm font-medium">Voice output</p>
                <p className="text-xs text-muted-foreground">
                  When enabled, the AI responds with voice. When disabled, only text responses are shown.
                </p>
              </div>
              <button
                onClick={() => voice.toggleVoice?.()}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors ${voice.voiceEnabled ? 'bg-primary' : 'bg-muted'}`}
              >
                <span className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${voice.voiceEnabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </button>
            </div>
            <div className="rounded-lg border border-border p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-sm font-medium">Voice</p>
                  <p className="text-xs text-muted-foreground">
                    Select the AI voice for audio responses. Changes take effect on next connection.
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {AVAILABLE_VOICES.map((v) => (
                  <button
                    key={v.id}
                    onClick={() => handleVoiceChange(v.id)}
                    className={`rounded-lg border p-3 text-left transition-colors ${currentVoice === v.id ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'border-border hover:bg-muted/50'}`}
                  >
                    <p className="text-sm font-medium">{v.label}</p>
                    <p className="text-xs text-muted-foreground">{v.description}</p>
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border p-4">
              <span className="text-sm">Input sample rate</span>
              <span className="text-sm text-muted-foreground">16 kHz (PCM16)</span>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border p-4">
              <span className="text-sm">Output sample rate</span>
              <span className="text-sm text-muted-foreground">24 kHz (PCM16)</span>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border p-4">
              <span className="text-sm">Audio capture</span>
              <span className="text-sm text-muted-foreground">AudioWorklet</span>
            </div>
          </div>
        </div>
      )}

      {/* Privacy */}
      {tab === 'Privacy' && (
        <div className="space-y-6">
          <div className="space-y-4">
            <h2 className="text-lg font-medium">Privacy</h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-lg border border-border p-4">
                <div>
                  <p className="text-sm font-medium">Data retention</p>
                  <p className="text-xs text-muted-foreground">Store conversation history in Firestore</p>
                </div>
                <span className="text-sm text-muted-foreground">Enabled</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border p-4">
                <div>
                  <p className="text-sm font-medium">Analytics</p>
                  <p className="text-xs text-muted-foreground">Help improve Omni with usage analytics</p>
                </div>
                <span className="text-sm text-muted-foreground">Disabled</span>
              </div>
            </div>
          </div>

          {/* Danger Zone */}
          <section className="space-y-4">
            <h2 className="text-lg font-medium text-destructive">Danger Zone</h2>
            <div className="rounded-lg border-2 border-destructive/30 p-4 space-y-4">
              <div>
                <p className="text-sm font-medium">Delete Account</p>
                <p className="text-xs text-muted-foreground">
                  Permanently delete your account and all associated data including sessions, personas, memories, and AI data. This action cannot be undone.
                </p>
              </div>

              {!showDeleteConfirm ? (
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  className="rounded-lg bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 transition-colors"
                >
                  Delete my account
                </button>
              ) : (
                <div className="space-y-3 rounded-lg bg-destructive/5 p-4">
                  <p className="text-sm font-medium text-destructive">
                    Are you absolutely sure? This will permanently delete:
                  </p>
                  <ul className="text-xs text-muted-foreground space-y-1 list-disc pl-4">
                    <li>All conversation sessions and chat history</li>
                    <li>All custom personas you created</li>
                    <li>All stored memories and AI-learned facts</li>
                    <li>Your Vertex AI data and agent engine sessions</li>
                    <li>Your Firebase authentication account</li>
                  </ul>
                  <div>
                    <label className="text-xs text-muted-foreground block mb-1">
                      Type <span className="font-mono font-bold text-destructive">DELETE</span> to confirm
                    </label>
                    <input
                      type="text"
                      value={deleteConfirmText}
                      onChange={(e) => setDeleteConfirmText(e.target.value)}
                      placeholder="DELETE"
                      className="w-48 rounded-md border border-destructive/50 bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-destructive"
                      autoComplete="off"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleDeleteAccount}
                      disabled={deleteConfirmText !== 'DELETE' || deleting}
                      className="rounded-lg bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {deleting ? 'Deleting...' : 'Permanently delete my account'}
                    </button>
                    <button
                      onClick={() => {
                        setShowDeleteConfirm(false);
                        setDeleteConfirmText('');
                      }}
                      className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          </section>
        </div>
      )}

      {/* Billing */}
      {tab === 'Billing' && (
        <BillingTab billing={billing} />
      )}

      {/* Shortcuts */}
      {tab === 'Shortcuts' && (
        <div className="space-y-4">
          <h2 className="text-lg font-medium">Keyboard Shortcuts</h2>
          <div className="rounded-lg border border-border">
            {SHORTCUTS.map((s, i) => (
              <div key={i} className={`flex items-center justify-between p-4 ${i > 0 ? 'border-t border-border' : ''}`}>
                <span className="text-sm">{s.action}</span>
                <kbd className="rounded bg-muted px-2 py-1 font-mono text-xs">{s.keys}</kbd>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


// ── Billing Tab Component ─────────────────────────────────────────────

const PLAN_LABELS = {
  free: { name: 'Free', price: '$0/mo', color: 'text-muted-foreground' },
  pro: { name: 'Pro', price: '$12/mo', color: 'text-blue-500' },
  ultra: { name: 'Ultra', price: '$29/mo', color: 'text-purple-500' },
  admin: { name: 'Admin', price: '∞', color: 'text-amber-500' },
  tester: { name: 'Tester', price: '∞', color: 'text-green-500' },
};

function BillingTab({ billing }) {
  const { plan, credits, features, plans, isOverride, cancelAtPeriodEnd, loading, usage } = billing;
  const creditsPercent = billing.creditsPercent();

  if (loading && !plan) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const planInfo = PLAN_LABELS[plan] || PLAN_LABELS.free;

  // Aggregate usage by action for the breakdown
  const usageByAction = {};
  (usage || []).forEach((u) => {
    usageByAction[u.action] = (usageByAction[u.action] || 0) + (u.credits || 0);
  });
  const totalUsed = Object.values(usageByAction).reduce((a, b) => a + b, 0);

  const ACTION_LABELS = {
    model_inference: 'Text / Voice',
    image_gen: 'Image Generation',
    mcp_call: 'Tool Calls',
    brave_search: 'Web Search',
    google_maps: 'Maps',
    sandbox_min: 'Code Sandbox',
  };

  return (
    <div className="space-y-6">
      {/* Current plan header */}
      <section className="space-y-4">
        <h2 className="text-lg font-medium">Subscription</h2>
        <div className="rounded-lg border border-border p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className={`text-xl font-bold ${planInfo.color}`}>{planInfo.name}</span>
                {isOverride && (
                  <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-500 font-medium">
                    Override
                  </span>
                )}
                {cancelAtPeriodEnd && (
                  <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-xs text-destructive font-medium">
                    Cancels at period end
                  </span>
                )}
              </div>
              <p className="text-sm text-muted-foreground mt-1">{planInfo.price}</p>
            </div>
            {!isOverride && plan !== 'free' && (
              <button
                onClick={() => billing.openPortal()}
                className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted transition-colors"
              >
                Manage Plan
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Credit bar */}
      <section className="space-y-4">
        <h2 className="text-lg font-medium">Credits</h2>
        <div className="rounded-lg border border-border p-4 space-y-3">
          {credits?.unlimited ? (
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-amber-500">∞</span>
              <span className="text-sm text-muted-foreground">Unlimited credits</span>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">
                  {credits?.balance?.toLocaleString() || 0} / {credits?.period_limit?.toLocaleString() || 0}
                </span>
                <span className="text-xs text-muted-foreground">{creditsPercent}% remaining</span>
              </div>
              <div className="h-3 w-full rounded-full bg-muted overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    creditsPercent > 50 ? 'bg-primary' : creditsPercent > 20 ? 'bg-amber-500' : 'bg-destructive'
                  }`}
                  style={{ width: `${Math.max(creditsPercent, 1)}%` }}
                />
              </div>
              {credits?.bonus_credits > 0 && (
                <p className="text-xs text-muted-foreground">
                  + {credits.bonus_credits.toLocaleString()} bonus credits
                </p>
              )}
            </>
          )}
        </div>
      </section>

      {/* Usage breakdown */}
      {totalUsed > 0 && (
        <section className="space-y-4">
          <h2 className="text-lg font-medium">Usage This Period</h2>
          <div className="rounded-lg border border-border">
            {Object.entries(usageByAction)
              .sort(([, a], [, b]) => b - a)
              .map(([action, credits], i) => (
                <div
                  key={action}
                  className={`flex items-center justify-between p-3 ${i > 0 ? 'border-t border-border' : ''}`}
                >
                  <span className="text-sm">{ACTION_LABELS[action] || action}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium">{credits.toLocaleString()}</span>
                    <span className="text-xs text-muted-foreground w-10 text-right">
                      {totalUsed > 0 ? Math.round((credits / totalUsed) * 100) : 0}%
                    </span>
                  </div>
                </div>
              ))}
          </div>
        </section>
      )}

      {/* Plan comparison / upgrade */}
      {!isOverride && plans && (
        <section className="space-y-4">
          <h2 className="text-lg font-medium">Plans</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {Object.entries(plans).map(([planKey, config]) => {
              const info = PLAN_LABELS[planKey] || {};
              const isCurrent = planKey === plan;
              return (
                <div
                  key={planKey}
                  className={`rounded-lg border p-4 space-y-3 ${
                    isCurrent ? 'border-primary ring-1 ring-primary' : 'border-border'
                  }`}
                >
                  <div>
                    <h3 className={`font-bold ${info.color || ''}`}>{info.name}</h3>
                    <p className="text-lg font-bold">{info.price}</p>
                  </div>
                  <ul className="text-xs text-muted-foreground space-y-1">
                    <li>{config.credits_monthly?.toLocaleString()} credits/mo</li>
                    <li>{config.max_personas === -1 ? 'Unlimited' : config.max_personas} persona(s)</li>
                    <li>{config.max_active_mcps === -1 ? 'Unlimited' : config.max_active_mcps} active plugins</li>
                    <li>{config.max_devices === -1 ? 'Unlimited' : config.max_devices} device(s)</li>
                    <li>{config.image_gen_daily_limit === -1 ? 'Unlimited' : config.image_gen_daily_limit} images/day</li>
                    <li>{config.sandbox_enabled ? '✓ Code sandbox' : '✗ Code sandbox'}</li>
                  </ul>
                  {isCurrent ? (
                    <div className="rounded bg-primary/10 text-center py-1.5 text-xs font-medium text-primary">
                      Current Plan
                    </div>
                  ) : planKey !== 'free' ? (
                    <button
                      onClick={() => billing.startCheckout(planKey)}
                      className="w-full rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                    >
                      Upgrade to {info.name}
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
