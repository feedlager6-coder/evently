/**
 * Safely parses date strings across all mobile WebKit and Chromium engines.
 * Replaces spaces with 'T' so iOS Safari never returns NaN for 'YYYY-MM-DD HH:mm:ss' dates.
 */
export function parseSafeDate(dateStr?: string | null): number {
  if (!dateStr) return 0;
  const clean = dateStr.trim();
  const normalized = clean.includes('T') ? clean : clean.replace(' ', 'T');
  const timestamp = new Date(normalized).getTime();
  return isNaN(timestamp) ? 0 : timestamp;
}

/**
 * Checks whether an event is finished / completed.
 * Logic:
 * 1. If end_at is specified, event is completed when now > end_at.
 * 2. If only start_at is specified:
 *    - If the start date is on a past calendar day (yesterday or earlier), it is completed.
 *    - If the start date is today, it is completed once 3 hours have passed since start_at.
 */
export function isEventCompleted(event: { start_at?: string; end_at?: string }): boolean {
  if (!event || !event.start_at) return false;
  const now = Date.now();

  if (event.end_at) {
    const endMs = parseSafeDate(event.end_at);
    if (endMs > 0) return now > endMs;
  }

  const startMs = parseSafeDate(event.start_at);
  if (startMs <= 0) return false;

  const startDate = new Date(startMs);
  const nowDate = new Date(now);

  const isSameDay =
    startDate.getFullYear() === nowDate.getFullYear() &&
    startDate.getMonth() === nowDate.getMonth() &&
    startDate.getDate() === nowDate.getDate();

  // If the event was on a previous calendar day and current time is past startMs -> completed!
  if (!isSameDay && now > startMs) {
    return true;
  }

  // If event is today -> completed once 3 hours have passed since the start time
  return now >= startMs + 3 * 3600 * 1000;
}
