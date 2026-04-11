import { create } from 'zustand';
import { api } from '@/lib/api';

export const useBillingStore = create((set, get) => ({
  // State
  plan: null,
  status: null,
  credits: null,
  features: null,
  plans: null,
  creditCosts: null,
  isOverride: false,
  cancelAtPeriodEnd: false,
  usage: [],
  loading: false,
  error: null,

  // Actions
  fetchBillingStatus: async () => {
    set({ loading: true, error: null });
    try {
      const data = await api.get('/billing/status');
      set({
        plan: data.plan,
        status: data.status,
        credits: data.credits,
        features: data.features,
        plans: data.plans,
        creditCosts: data.credit_costs,
        isOverride: data.is_override,
        cancelAtPeriodEnd: data.cancel_at_period_end,
        loading: false,
      });
    } catch (err) {
      set({ loading: false, error: err.message });
    }
  },

  fetchUsage: async () => {
    try {
      const data = await api.get('/billing/usage');
      set({ usage: data.usage || [] });
    } catch {
      // non-critical
    }
  },

  startCheckout: async (planName) => {
    try {
      const data = await api.post(`/billing/checkout?plan=${planName}`);
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch (err) {
      set({ error: err.message });
    }
  },

  openPortal: async () => {
    try {
      const data = await api.post('/billing/portal');
      if (data.portal_url) {
        window.location.href = data.portal_url;
      }
    } catch (err) {
      set({ error: err.message });
    }
  },

  // Computed helpers
  creditsPercent: () => {
    const { credits } = get();
    if (!credits || !credits.period_limit) return 100;
    if (credits.unlimited) return 100;
    return Math.round((credits.balance / credits.period_limit) * 100);
  },

  isLowCredits: () => {
    const { credits } = get();
    if (!credits || credits.unlimited) return false;
    return credits.balance < credits.period_limit * 0.2;
  },

  isExhausted: () => {
    const { credits } = get();
    if (!credits || credits.unlimited) return false;
    return (credits.balance + (credits.bonus_credits || 0)) <= 0;
  },
}));
