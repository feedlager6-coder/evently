import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { telegram } from '../services/telegram';
import {
  QrCode,
  X,
  Camera,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Users,
  Sparkles,
  Loader2,
  Clock,
  ArrowRight
} from 'lucide-react';

interface CheckInScannerModalProps {
  isOpen: boolean;
  onClose: () => void;
  event: any;
}

interface ScanResultItem {
  code: string;
  time: string;
  status: 'success' | 'already_checked_in' | 'invalid';
  message: string;
  guestName?: string;
  isPaymentRequiredAtDoor?: boolean;
  doorPrice?: number;
}

export const CheckInScannerModal: React.FC<CheckInScannerModalProps> = ({
  isOpen,
  onClose,
  event,
}) => {
  const [manualCode, setManualCode] = useState('');
  const [isChecking, setIsChecking] = useState(false);
  const [isContinuousScan, setIsContinuousScan] = useState(true);
  const [scannerNotice, setScannerNotice] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<ScanResultItem | null>(null);
  const [checkInHistory, setCheckInHistory] = useState<ScanResultItem[]>([]);

  // Ref guards against 30fps camera scan flooding (P5)
  const isProcessingRef = React.useRef(false);
  const lastScannedCodeRef = React.useRef<string>('');
  const lastScannedTimeRef = React.useRef<number>(0);

  // Load check-in history from localStorage on open
  useEffect(() => {
    if (!isOpen || !event) return;
    try {
      const saved = localStorage.getItem(`ivently_checkin_history_${event.id}`);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          setCheckInHistory(parsed);
        }
      }
    } catch {
      // ignore
    }
  }, [isOpen, event]);

  if (!isOpen || !event) return null;

  const totalRegistered = event.attendee_count ?? event.ticketsSold ?? event.attendees_count ?? 0;
  const verifiedCount = checkInHistory.filter((c) => c.status === 'success').length;

  const handleProcessCode = async (rawCode: string) => {
    if (!rawCode || !rawCode.trim()) return;
    const clean = rawCode.trim();

    // Debounce guard: suppress duplicate scans of same code within 2.5 seconds
    const nowMs = Date.now();
    if (clean === lastScannedCodeRef.current && nowMs - lastScannedTimeRef.current < 2500) {
      return;
    }
    if (isProcessingRef.current) return;

    isProcessingRef.current = true;
    lastScannedCodeRef.current = clean;
    lastScannedTimeRef.current = nowMs;

    setIsChecking(true);
    setScannerNotice(null);

    try {
      const res = await api.checkInTicket(event.id, clean);
      const now = new Date().toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });

      const resultItem: ScanResultItem = {
        code: res.ticket_code || clean,
        time: res.checked_in_at || now,
        status: res.status,
        message: res.message,
        guestName: res.guest_name,
        isPaymentRequiredAtDoor: res.is_payment_required_at_door,
        doorPrice: res.price_amount,
      };

      setLastResult(resultItem);

      if (res.status === 'success') {
        if (res.is_payment_required_at_door) {
          telegram.hapticNotification('warning');
        } else {
          telegram.hapticNotification('success');
        }
        const updated = [resultItem, ...checkInHistory.filter((c) => c.code !== resultItem.code)];
        setCheckInHistory(updated);
        try {
          localStorage.setItem(`ivently_checkin_history_${event.id}`, JSON.stringify(updated.slice(0, 50)));
        } catch {}
      } else if (res.status === 'already_checked_in') {
        telegram.hapticNotification('warning');
      } else {
        telegram.hapticNotification('error');
      }
    } catch (err: any) {
      telegram.hapticNotification('error');
      setLastResult({
        code: clean,
        time: new Date().toLocaleTimeString('ru-RU'),
        status: 'invalid',
        message: err.message || 'Ошибка проверки билета',
      });
    } finally {
      setIsChecking(false);
      isProcessingRef.current = false;
      setManualCode('');
    }
  };

  const handleStartTelegramScanner = () => {
    telegram.hapticImpact('medium');
    setScannerNotice(null);

    if (telegram.isScanQrAvailable()) {
      telegram.showScanQrPopup(
        { text: `Сканируйте QR-код билета: ${event.title}` },
        (scannedText: string) => {
          handleProcessCode(scannedText);
          return !isContinuousScan; // false keeps popup camera open for stream scanning
        }
      );
    } else {
      setScannerNotice(
        'Камера сканирования доступна в мобильном клиенте Telegram. В браузере используйте ручной ввод номера билета или кнопку тестовой проверки.'
      );
    }
  };

  const handleTestScan = () => {
    telegram.hapticImpact('light');
    const sampleSuffix = Math.floor(1000 + Math.random() * 9000);
    const sampleEventPrefix = event.id.replace(/-/g, '').slice(0, 4).toUpperCase();
    const testCode = `IVN-${sampleEventPrefix}-${sampleSuffix}`;
    handleProcessCode(testCode);
  };

  return (
    <div className="fixed inset-0 z-[70] bg-black/90 backdrop-blur-xl flex flex-col animate-fade-in overflow-y-auto">
      {/* Top Header */}
      <header className="sticky top-0 z-20 bg-[#0d0d0f]/95 backdrop-blur-md px-4 py-3.5 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center space-x-2 text-white min-w-0">
          <QrCode className="w-5 h-5 text-emerald-400 shrink-0" />
          <div className="min-w-0">
            <h2 className="font-bold text-sm truncate">Контроль билетов</h2>
            <p className="text-[11px] text-neutral-400 truncate">{event.title}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            telegram.hapticImpact('light');
            onClose();
          }}
          className="min-w-[44px] min-h-[44px] flex items-center justify-center rounded-full bg-white/5 text-neutral-400 hover:text-white active:scale-95 transition"
          aria-label="Закрыть"
        >
          <X className="w-5 h-5" />
        </button>
      </header>

      <main className="flex-1 max-w-sm w-full mx-auto p-4 space-y-4">
        {/* Attendance Counter Card */}
        <div className="p-4 rounded-2xl bg-[#141417] border border-white/10 grid grid-cols-2 gap-3">
          <div className="space-y-0.5">
            <div className="text-[11px] text-neutral-400 font-medium">Зарегистрировано</div>
            <div className="text-xl font-bold text-white flex items-center gap-1.5">
              <Users className="w-4 h-4 text-neutral-400" />
              <span>{totalRegistered}</span>
            </div>
            <div className="text-[10px] text-neutral-500">в списке гостей</div>
          </div>

          <div className="space-y-0.5">
            <div className="text-[11px] text-emerald-400 font-medium">Проверено на входе</div>
            <div className="text-xl font-bold text-emerald-400 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>{verifiedCount}</span>
            </div>
            <div className="text-[10px] text-emerald-500/80">
              {totalRegistered > 0 ? `${Math.round((verifiedCount / totalRegistered) * 100)}% от общего числа` : 'на контроле'}
            </div>
          </div>
        </div>

        {/* Primary Action: Open Telegram Camera Scanner */}
        <div className="space-y-2">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleStartTelegramScanner}
              className="flex-1 py-4 px-4 rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-black font-extrabold text-sm shadow-[0_4px_24px_rgba(16,185,129,0.3)] active:scale-95 transition flex items-center justify-center gap-2"
            >
              <Camera className="w-5 h-5 stroke-[2.2]" />
              <span>Сканировать QR-код</span>
            </button>
            <button
              type="button"
              onClick={() => {
                telegram.hapticImpact('light');
                setIsContinuousScan((prev) => !prev);
              }}
              title="Потоковое сканирование очереди"
              className={`px-3 py-3 rounded-2xl border transition flex flex-col items-center justify-center gap-1 text-[10px] font-bold min-w-[64px] ${
                isContinuousScan
                  ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                  : 'bg-white/5 border-white/10 text-neutral-400 hover:text-white'
              }`}
            >
              <Sparkles className="w-4 h-4" />
              <span>{isContinuousScan ? 'Поток: ВКЛ' : 'Поток'}</span>
            </button>
          </div>

          {scannerNotice && (
            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs leading-relaxed animate-fade-in">
              {scannerNotice}
            </div>
          )}
        </div>

        {/* Manual Code Input Form */}
        <div className="p-4 rounded-2xl bg-[#141417] border border-white/8 space-y-3">
          <div className="flex items-center justify-between">
            <label htmlFor="ticket-code-input" className="text-xs font-bold text-neutral-300">
              Ручная проверка по номеру билета
            </label>
            <span className="text-[10px] text-neutral-500">Пример: IVN-9821</span>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleProcessCode(manualCode);
            }}
            className="flex gap-2"
          >
            <div className="relative flex-1">
              <input
                id="ticket-code-input"
                type="text"
                value={manualCode}
                onChange={(e) => setManualCode(e.target.value.toUpperCase())}
                placeholder="IVN-XXXXXX"
                disabled={isChecking}
                className="w-full bg-[#1c1c20] text-white text-xs px-3.5 py-2.5 rounded-xl border border-white/10 focus:border-emerald-500/50 focus:outline-none uppercase font-mono tracking-wider"
              />
            </div>
            <button
              type="submit"
              disabled={isChecking || !manualCode.trim()}
              className="px-4 py-2.5 rounded-xl bg-white text-black font-bold text-xs disabled:opacity-40 active:scale-95 transition shrink-0 flex items-center gap-1.5"
            >
              {isChecking ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <span>Проверить</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </form>

          {/* Instant Test Button */}
          <div className="pt-2 border-t border-white/5 flex items-center justify-between">
            <span className="text-[11px] text-neutral-400">Нужно протестировать?</span>
            <button
              type="button"
              onClick={handleTestScan}
              disabled={isChecking}
              className="text-xs text-emerald-400 hover:text-emerald-300 font-semibold flex items-center gap-1 active:scale-95 transition"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Тестовый билет гостя</span>
            </button>
          </div>
        </div>

        {/* Live Validation Result Feedback Card */}
        {lastResult && (
          <div
            className={`p-4 rounded-2xl border animate-scale-in transition-all ${
              lastResult.status === 'success'
                ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300 shadow-[0_0_24px_rgba(16,185,129,0.15)]'
                : lastResult.status === 'already_checked_in'
                ? 'bg-amber-500/15 border-amber-500/40 text-amber-300 shadow-[0_0_24px_rgba(245,158,11,0.15)]'
                : 'bg-rose-500/15 border-rose-500/40 text-rose-300 shadow-[0_0_24px_rgba(244,63,94,0.15)]'
            }`}
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5 shrink-0">
                {lastResult.status === 'success' && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
                {lastResult.status === 'already_checked_in' && <AlertTriangle className="w-5 h-5 text-amber-400" />}
                {lastResult.status === 'invalid' && <XCircle className="w-5 h-5 text-rose-400" />}
              </div>
              <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-center justify-between gap-1">
                  <span className="font-bold text-xs uppercase tracking-wide">
                    {lastResult.status === 'success'
                      ? 'Вход разрешен'
                      : lastResult.status === 'already_checked_in'
                      ? 'Повторный вход'
                      : 'Вход отклонен'}
                  </span>
                  <span className="text-[10px] opacity-75 font-mono">{lastResult.time}</span>
                </div>
                <p className="text-xs font-semibold leading-snug">{lastResult.message}</p>
                <div className="text-[11px] font-mono opacity-80 pt-0.5 truncate">
                  Билет: <span className="font-bold">{lastResult.code}</span>
                </div>

                {lastResult.isPaymentRequiredAtDoor && (
                  <div className="mt-2.5 p-2.5 rounded-xl bg-amber-500/25 border border-amber-400/50 text-amber-200 text-xs font-bold flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-300 shrink-0" />
                    <span>⚠️ ТРЕБУЕТСЯ ОПЛАТА НА ВХОДЕ: {lastResult.doorPrice ? `${lastResult.doorPrice} ₽` : 'по прайсу'}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Check-in Session History */}
        {checkInHistory.length > 0 && (
          <div className="space-y-2 pt-1">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-neutral-300 uppercase tracking-wider">
                История текущей смены ({checkInHistory.length})
              </h3>
              <button
                type="button"
                onClick={async () => {
                  const confirmed = await telegram.showConfirm('Очистить историю чек-ина этой смены?');
                  if (confirmed) {
                    setCheckInHistory([]);
                    localStorage.removeItem(`ivently_checkin_history_${event.id}`);
                    telegram.hapticImpact('light');
                  }
                }}
                className="text-[10px] text-neutral-500 hover:text-neutral-300"
              >
                Очистить
              </button>
            </div>

            <div className="space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar pr-1">
              {checkInHistory.map((item, index) => (
                <div
                  key={`${item.code}-${index}`}
                  className="p-2.5 rounded-xl bg-[#141417] border border-white/5 flex items-center justify-between text-xs"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span className="font-mono text-white text-[11px] truncate">{item.code}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-neutral-400 text-[10px] shrink-0 font-mono">
                    <Clock className="w-3 h-3 text-neutral-500" />
                    <span>{item.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
