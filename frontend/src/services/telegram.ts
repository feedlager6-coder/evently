import type { TelegramWebAppUser } from '../types';

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string;
        initDataUnsafe: {
          query_id?: string;
          user?: TelegramWebAppUser;
          auth_date?: number;
          hash?: string;
          start_param?: string;
        };
        themeParams: {
          bg_color?: string;
          text_color?: string;
          hint_color?: string;
          link_color?: string;
          button_color?: string;
          button_text_color?: string;
          secondary_bg_color?: string;
        };
        isExpanded: boolean;
        viewportHeight: number;
        viewportStableHeight: number;
        headerColor: string;
        backgroundColor: string;
        BackButton: {
          isVisible: boolean;
          show: () => void;
          hide: () => void;
          onClick: (cb: () => void) => void;
          offClick: (cb: () => void) => void;
        };
        HapticFeedback: {
          impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
          notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
          selectionChanged: () => void;
        };
        ready: () => void;
        expand: () => void;
        close: () => void;
        openTelegramLink: (url: string) => void;
        openLink: (url: string) => void;
        onEvent?: (eventType: string, eventHandler: () => void) => void;
        offEvent?: (eventType: string, eventHandler: () => void) => void;
      };
    };
  }
}

export const telegram = {
  isAvailable(): boolean {
    return Boolean(window.Telegram?.WebApp && window.Telegram.WebApp.initData);
  },

  getInitData(): string {
    if (window.Telegram?.WebApp?.initData) {
      return window.Telegram.WebApp.initData;
    }
    // Return empty string or stored mock for local web testing
    return localStorage.getItem('evently_mock_init_data') || '';
  },

  setMockInitData(initData: string) {
    localStorage.setItem('evently_mock_init_data', initData);
  },

  getUser(): TelegramWebAppUser | null {
    if (window.Telegram?.WebApp?.initDataUnsafe?.user) {
      return window.Telegram.WebApp.initDataUnsafe.user;
    }
    return null;
  },

  getStartParam(force = false): string | null {
    let candidate: string | null = null;

    // 1. Check window.location.search (?startapp=... or ?tgWebAppStartParam=... or ?event_id=...)
    // Primary for native web_app buttons that launch Mini App directly with URL query params
    if (typeof window !== 'undefined' && window.location.search) {
      try {
        const cleanSearch = window.location.search.replace(/^\/[?]/, '?');
        const urlParams = new URLSearchParams(cleanSearch);
        const startAppParam =
          urlParams.get('tgWebAppStartParam') ||
          urlParams.get('startapp') ||
          urlParams.get('start_param');
        if (startAppParam && startAppParam.trim()) {
          candidate = startAppParam.trim();
        } else {
          const eventIdParam = urlParams.get('event_id');
          if (eventIdParam && eventIdParam.trim()) {
            candidate = `event_${eventIdParam.trim()}`;
          }
        }
      } catch {
        // ignore parsing errors
      }
    }

    // 2. Check window.location.hash (Primary for Telegram direct link launch and dynamic resumes)
    if (!candidate && typeof window !== 'undefined' && window.location.hash) {
      try {
        const cleanHash = window.location.hash.replace(/^#[!/?]*/, '');
        const hashParams = new URLSearchParams(cleanHash);

        const startFromHash =
          hashParams.get('tgWebAppStartParam') ||
          hashParams.get('startapp') ||
          hashParams.get('start_param');
        if (startFromHash && startFromHash.trim()) {
          candidate = startFromHash.trim();
        }

        // Check if start_param is encoded inside tgWebAppData parameter within hash
        if (!candidate) {
          const rawAppData = hashParams.get('tgWebAppData');
          if (rawAppData) {
            const appDataParams = new URLSearchParams(rawAppData);
            const p = appDataParams.get('start_param') || appDataParams.get('tgWebAppStartParam') || appDataParams.get('startapp');
            if (p && p.trim()) candidate = p.trim();
          }
        }
      } catch {
        // ignore parsing errors
      }
    }

    // 3. Direct Regex fallback on entire window.location.href (guards against non-standard WebView encoding)
    if (!candidate && typeof window !== 'undefined' && window.location.href) {
      try {
        const match = /(?:tgWebAppStartParam|startapp|start_param)=([^&#?]+)/i.exec(window.location.href);
        if (match && match[1]) {
          const decoded = decodeURIComponent(match[1]).trim();
          if (decoded) candidate = decoded;
        }
      } catch {
        // ignore regex/decoding errors
      }
    }

    // 4. Check Telegram's native initDataUnsafe.start_param (updated dynamically by Telegram on resume/launch)
    if (!candidate && typeof window !== 'undefined') {
      const tgParam = window.Telegram?.WebApp?.initDataUnsafe?.start_param;
      if (tgParam && typeof tgParam === 'string' && tgParam.trim()) {
        candidate = tgParam.trim();
      }

      // Check window.Telegram?.WebApp?.initParams
      if (!candidate) {
        try {
          const rawInitParams = (window.Telegram?.WebApp as any)?.initParams;
          if (rawInitParams) {
            const initParams = new URLSearchParams(typeof rawInitParams === 'string' ? rawInitParams : '');
            const p = initParams.get('start_param') || initParams.get('tgWebAppStartParam') || initParams.get('startapp');
            if (p && p.trim()) candidate = p.trim();
          }
        } catch {
          // ignore
        }
      }

      // Check window.Telegram?.WebApp?.initData raw query string
      if (!candidate && window.Telegram?.WebApp?.initData) {
        try {
          const initDataParams = new URLSearchParams(window.Telegram.WebApp.initData);
          const p = initDataParams.get('start_param') || initDataParams.get('tgWebAppStartParam') || initDataParams.get('startapp');
          if (p && p.trim()) candidate = p.trim();
        } catch {
          // ignore parsing errors
        }
      }
    }

    if (!candidate) return null;

    // VALUE-BASED CONSUMPTION GUARD:
    // If the candidate was already consumed and processed, return null to avoid duplicate actions.
    // If force is true, bypass consumption check (e.g. on external Telegram link activation).
    if (!force) {
      const lastConsumed = (typeof window !== 'undefined') ? (window as any).__evently_last_consumed_start_param : null;
      if (lastConsumed && lastConsumed === candidate) {
        return null;
      }
    }

    return candidate;
  },

  consumeStartParam(paramToConsume?: string): void {
    try {
      if (typeof window !== 'undefined') {
        // Record value-based consumption marker
        const resolved = paramToConsume || (window.Telegram?.WebApp?.initDataUnsafe?.start_param) || null;
        if (resolved) {
          (window as any).__evently_last_consumed_start_param = resolved;
        }

        // Clean live parameters from URL fragment without full page reload
        if (window.location.hash) {
          const cleanHash = window.location.hash.replace(/^#[!/?]*/, '');
          const hashParams = new URLSearchParams(cleanHash);
          let changed = false;
          ['tgWebAppStartParam', 'startapp', 'start_param', 'event_id'].forEach((k) => {
            if (hashParams.has(k)) {
              hashParams.delete(k);
              changed = true;
            }
          });
          if (changed) {
            const newHash = hashParams.toString() ? `#${hashParams.toString()}` : '';
            window.history.replaceState(null, '', window.location.pathname + window.location.search + newHash);
          }
        }

        // Clean live parameters from URL search query if present
        if (window.location.search) {
          const searchParams = new URLSearchParams(window.location.search);
          let changed = false;
          ['tgWebAppStartParam', 'startapp', 'start_param', 'event_id'].forEach((k) => {
            if (searchParams.has(k)) {
              searchParams.delete(k);
              changed = true;
            }
          });
          if (changed) {
            const newSearch = searchParams.toString() ? `?${searchParams.toString()}` : '';
            window.history.replaceState(null, '', window.location.pathname + newSearch + window.location.hash);
          }
        }
      }
    } catch {
      // ignore state replacement errors
    }
  },

  resetConsumedStartParam(): void {
    if (typeof window !== 'undefined') {
      (window as any).__evently_last_consumed_start_param = null;
    }
  },

  onActivated(callback: () => void): () => void {
    try {
      if (typeof window !== 'undefined' && window.Telegram?.WebApp?.onEvent) {
        const handler = () => {
          telegram.resetConsumedStartParam();
          callback();
        };
        window.Telegram.WebApp.onEvent('activated', handler);
        return () => {
          try {
            window.Telegram?.WebApp?.offEvent?.('activated', handler);
          } catch {
            // ignore
          }
        };
      }
    } catch {
      // ignore
    }
    return () => {};
  },

  ready() {
    try {
      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
      }
    } catch {
      // Ignored outside Telegram
    }
  },

  hapticSuccess() {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('success');
    } catch {
      // Ignored outside Telegram
    }
  },

  hapticError() {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('error');
    } catch {
      // Ignored outside Telegram
    }
  },

  hapticImpact(style: 'light' | 'medium' | 'heavy' = 'medium') {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred(style);
    } catch {
      // Ignored outside Telegram
    }
  },

  hapticSelection() {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.selectionChanged();
    } catch {
      // Ignored outside Telegram
    }
  },

  hapticNotification(type: 'error' | 'success' | 'warning' = 'success') {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred(type);
    } catch {
      // Ignored outside Telegram
    }
  },

  showBackButton(onClick: () => void) {
    try {
      if (window.Telegram?.WebApp?.BackButton) {
        window.Telegram.WebApp.BackButton.show();
        window.Telegram.WebApp.BackButton.onClick(onClick);
      }
    } catch {
      // Ignored outside Telegram
    }
  },

  hideBackButton() {
    try {
      if (window.Telegram?.WebApp?.BackButton) {
        window.Telegram.WebApp.BackButton.hide();
      }
    } catch {
      // Ignored outside Telegram
    }
  },

  openTelegramLink(url: string) {
    try {
      if (window.Telegram?.WebApp?.openTelegramLink) {
        window.Telegram.WebApp.openTelegramLink(url);
        return;
      }
    } catch {
      // Ignored outside Telegram
    }
    window.open(url, '_blank');
  },

  canShareMessage(): boolean {
    try {
      const wa = window.Telegram?.WebApp as any;
      return Boolean(
        wa &&
        typeof wa.isVersionAtLeast === 'function' &&
        wa.isVersionAtLeast('8.0') &&
        typeof wa.shareMessage === 'function'
      );
    } catch {
      return false;
    }
  },

  async sharePreparedMessage(preparedMessageId: string): Promise<boolean> {
    try {
      const wa = window.Telegram?.WebApp as any;
      if (!this.canShareMessage() || !wa) {
        return false;
      }

      return await new Promise<boolean>((resolve) => {
        let isResolved = false;

        const cleanupAndResolve = (result: boolean) => {
          if (!isResolved) {
            isResolved = true;
            if (typeof wa.offEvent === 'function') {
              wa.offEvent('shareMessageSent', onSent);
              wa.offEvent('shareMessageFailed', onFailed);
            }
            resolve(result);
          }
        };

        const onSent = () => {
          cleanupAndResolve(true);
        };

        const onFailed = (eventData?: any) => {
          console.log('Telegram shareMessage cancelled or failed:', eventData?.error);
          cleanupAndResolve(false);
        };

        if (typeof wa.onEvent === 'function') {
          wa.onEvent('shareMessageSent', onSent);
          wa.onEvent('shareMessageFailed', onFailed);
        }

        try {
          wa.shareMessage(preparedMessageId, (sent: boolean) => {
            cleanupAndResolve(Boolean(sent));
          });
        } catch (callErr) {
          console.warn('Telegram.WebApp.shareMessage invocation error:', callErr);
          cleanupAndResolve(false);
        }
      });
    } catch (err) {
      console.warn('sharePreparedMessage top-level exception:', err);
      return false;
    }
  },

  switchInlineQuery(query: string, chooseChatTypes?: ('users' | 'bots' | 'groups' | 'channels')[]): boolean {
    try {
      const wa = window.Telegram?.WebApp as any;
      if (wa && typeof wa.switchInlineQuery === 'function') {
        if (chooseChatTypes && chooseChatTypes.length > 0) {
          wa.switchInlineQuery(query, chooseChatTypes);
        } else {
          wa.switchInlineQuery(query);
        }
        return true;
      }
    } catch (e) {
      console.warn('Telegram.WebApp.switchInlineQuery warning:', e);
    }
    return false;
  },

  async requestWriteAccess(): Promise<boolean> {
    try {
      const wa = (window.Telegram?.WebApp as any);
      if (wa && typeof wa.requestWriteAccess === 'function') {
        return await new Promise<boolean>((resolve) => {
          try {
            wa.requestWriteAccess((allowed: boolean) => {
              resolve(Boolean(allowed));
            });
          } catch {
            resolve(false);
          }
        });
      }
    } catch {
      // Ignored outside Telegram
    }
    return false;
  },

  async requestLocation(): Promise<{ latitude: number; longitude: number } | null> {
    // 1. Try official Telegram WebApp LocationManager (Bot API 8.0+)
    const tgLocationManager = (window.Telegram?.WebApp as any)?.LocationManager;
    if (tgLocationManager) {
      try {
        const result = await new Promise<{ latitude: number; longitude: number } | null>((resolve) => {
          const fetchLoc = () => {
            try {
              tgLocationManager.getLocation((data: any) => {
                if (data && typeof data.latitude === 'number' && typeof data.longitude === 'number') {
                  resolve({ latitude: data.latitude, longitude: data.longitude });
                } else {
                  resolve(null);
                }
              });
            } catch {
              resolve(null);
            }
          };

          if (tgLocationManager.isInited) {
            fetchLoc();
          } else {
            tgLocationManager.init(() => {
              fetchLoc();
            });
          }
        });
        if (result) return result;
      } catch {
        // Fallback to standard navigator geolocation
      }
    }

    // 2. Fallback to standard browser geolocation
    if (typeof navigator !== 'undefined' && navigator.geolocation) {
      try {
        return await new Promise<{ latitude: number; longitude: number } | null>((resolve) => {
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              resolve({
                latitude: pos.coords.latitude,
                longitude: pos.coords.longitude,
              });
            },
            () => resolve(null),
            { timeout: 8000, enableHighAccuracy: false }
          );
        });
      } catch {
        return null;
      }
    }

    return null;
  }
};

