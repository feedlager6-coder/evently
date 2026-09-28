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
    // 1. Check Telegram's native start_param
    const tgParam = window.Telegram?.WebApp?.initDataUnsafe?.start_param;
    if (tgParam) return tgParam;

    // 2. Check URL search query (e.g. ?startapp=event_waw_01 or ?event_id=waw_01)
    const urlParams = new URLSearchParams(window.location.search);
    const startAppParam = urlParams.get('startapp') || urlParams.get('tgWebAppStartParam');
    if (startAppParam) return startAppParam;

    const eventIdParam = urlParams.get('event_id');
    if (eventIdParam) return `event_${eventIdParam}`;

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

  hapticImpact(style: 'light' | 'medium' | 'heavy' = 'medium') {
    try {
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred(style);
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
  }
};
