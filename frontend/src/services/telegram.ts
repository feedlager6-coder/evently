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

  getStartParam(): string | null {
    // 1. Check Telegram's native initDataUnsafe.start_param
    const tgParam = window.Telegram?.WebApp?.initDataUnsafe?.start_param;
    if (tgParam && typeof tgParam === 'string' && tgParam.trim()) {
      return tgParam.trim();
    }

    // 2. Check window.Telegram?.WebApp?.initParams (used by certain Telegram client versions)
    try {
      const rawInitParams = (window.Telegram?.WebApp as any)?.initParams;
      if (rawInitParams) {
        const initParams = new URLSearchParams(typeof rawInitParams === 'string' ? rawInitParams : '');
        const p = initParams.get('start_param') || initParams.get('tgWebAppStartParam') || initParams.get('startapp');
        if (p && p.trim()) return p.trim();
      }
    } catch {
      // ignore
    }

    // 3. Check window.Telegram?.WebApp?.initData raw query string
    if (window.Telegram?.WebApp?.initData) {
      try {
        const initDataParams = new URLSearchParams(window.Telegram.WebApp.initData);
        const p = initDataParams.get('start_param') || initDataParams.get('tgWebAppStartParam') || initDataParams.get('startapp');
        if (p && p.trim()) return p.trim();
      } catch {
        // ignore parsing errors
      }
    }

    // 4. Check window.location.hash (Standard for Telegram Mobile Webview)
    // Telegram loads webviews with URL fragment:
    // #tgWebAppData=...&tgWebAppStartParam=event_123&tgWebAppVersion=...
    // or #/tgWebAppStartParam=... or #startapp=event_123
    if (typeof window !== 'undefined' && window.location.hash) {
      try {
        // Clean leading hash symbols and slashes: #, #/, #!/, #?
        const cleanHash = window.location.hash.replace(/^#[!/?]*/, '');
        const hashParams = new URLSearchParams(cleanHash);

        const startFromHash =
          hashParams.get('tgWebAppStartParam') ||
          hashParams.get('startapp') ||
          hashParams.get('start_param');
        if (startFromHash && startFromHash.trim()) {
          return startFromHash.trim();
        }

        // Check if start_param is encoded inside tgWebAppData parameter within hash
        const rawAppData = hashParams.get('tgWebAppData');
        if (rawAppData) {
          const appDataParams = new URLSearchParams(rawAppData);
          const p = appDataParams.get('start_param') || appDataParams.get('tgWebAppStartParam') || appDataParams.get('startapp');
          if (p && p.trim()) return p.trim();
        }
      } catch {
        // ignore parsing errors
      }
    }

    // 5. Check window.location.search (?startapp=... or ?tgWebAppStartParam=... or ?event_id=...)
    if (typeof window !== 'undefined' && window.location.search) {
      try {
        const cleanSearch = window.location.search.replace(/^\/[?]/, '?');
        const urlParams = new URLSearchParams(cleanSearch);
        const startAppParam =
          urlParams.get('tgWebAppStartParam') ||
          urlParams.get('startapp') ||
          urlParams.get('start_param');
        if (startAppParam && startAppParam.trim()) {
          return startAppParam.trim();
        }

        const eventIdParam = urlParams.get('event_id');
        if (eventIdParam && eventIdParam.trim()) {
          return `event_${eventIdParam.trim()}`;
        }
      } catch {
        // ignore parsing errors
      }
    }

    // 6. Direct Regex fallback on entire window.location.href (guards against non-standard WebView encoding)
    if (typeof window !== 'undefined' && window.location.href) {
      try {
        const match = /(?:tgWebAppStartParam|startapp|start_param)=([^&#?]+)/i.exec(window.location.href);
        if (match && match[1]) {
          const decoded = decodeURIComponent(match[1]).trim();
          if (decoded) return decoded;
        }
      } catch {
        // ignore regex/decoding errors
      }
    }

    return null;
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

