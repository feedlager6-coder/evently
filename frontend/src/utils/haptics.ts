import { telegram } from '../services/telegram';

/**
 * Unified Haptic Feedback utility for Telegram Mini App
 */
export const haptics = {
  selectionChanged(): void {
    telegram.hapticSelection();
  },
  impactLight(): void {
    telegram.hapticImpact('light');
  },
  impactMedium(): void {
    telegram.hapticImpact('medium');
  },
  notificationSuccess(): void {
    telegram.hapticNotification('success');
  },
  notificationError(): void {
    telegram.hapticNotification('error');
  },
};
