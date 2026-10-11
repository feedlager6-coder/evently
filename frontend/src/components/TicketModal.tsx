import React, { useState, useEffect } from 'react';
import type { EventResponse, EventSummary } from '../types';
import { telegram } from '../services/telegram';
import { ArrowLeft, Share2, Check, Copy } from 'lucide-react';
import { SafeImage } from './SafeImage';
import QRCode from 'qrcode';

interface TicketModalProps {
  isOpen: boolean;
  onClose: () => void;
  event: EventResponse | EventSummary | null;
  ticketNumber?: string;
  tierName?: string;
}

export const TicketModal: React.FC<TicketModalProps> = ({
  isOpen,
  onClose,
  event,
  ticketNumber,
  tierName = 'Входной билет',
}) => {
  const [copiedToast, setCopiedToast] = useState(false);
  const [qrDataUrl, setQrDataUrl] = useState<string>('');

  const generatedTicketNo = event
    ? ticketNumber || `IVN-${event.id.replace(/-/g, '').slice(0, 6).toUpperCase()}`
    : '';

  useEffect(() => {
    if (!event || !isOpen) return;

    const qrPayload = JSON.stringify({
      ticket_id: generatedTicketNo,
      event_id: event.id,
      title: event.title,
      start_at: event.start_at,
      venue: event.venue_name,
      platform: 'ivently_tma_v1',
    });

    QRCode.toDataURL(qrPayload, {
      width: 280,
      margin: 1,
      errorCorrectionLevel: 'M',
      color: {
        dark: '#000000',
        light: '#ffffff',
      },
    })
      .then((url) => setQrDataUrl(url))
      .catch((err) => console.error('Failed to generate ticket QR code:', err));
  }, [event, isOpen, generatedTicketNo]);

  if (!isOpen || !event) return null;

  const eventDate = new Date(event.start_at);
  const formattedDate = eventDate.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });

  const handleShareTelegram = () => {
    telegram.hapticImpact('medium');
    const shareText = `Мой электронный билет на «${event.title}» в Ivently!\n📅 Дата: ${formattedDate}\n📍 Место: ${event.venue_name || 'г. Махачкала'}\n🎟 Номер: ${generatedTicketNo}`;
    const directEventUrl = `https://t.me/share/url?url=${encodeURIComponent(`https://t.me/Ivently_bot?start=event_${event.id}`)}&text=${encodeURIComponent(shareText)}`;

    if (window.Telegram?.WebApp?.openTelegramLink) {
      window.Telegram.WebApp.openTelegramLink(directEventUrl);
    } else {
      window.open(directEventUrl, '_blank');
    }
  };

  const handleCopyTicketData = () => {
    telegram.hapticImpact('light');
    const shareText = `Электронный билет Ivently\nСобытие: «${event.title}»\nБилет №: ${generatedTicketNo}\nДата: ${formattedDate}\nЛокация: ${event.venue_name || 'г. Махачкала'}\nКатегория: ${tierName}`;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(shareText);
      setCopiedToast(true);
      telegram.hapticSuccess();
      setTimeout(() => setCopiedToast(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex flex-col bg-[#08080a] text-white overflow-y-auto custom-scrollbar select-none">
      {/* Top App Bar */}
      <header className="sticky top-0 z-30 pt-safe px-4 pb-3 flex items-center justify-between bg-[#0d0d0f]/90 backdrop-blur-2xl border-b border-white/8 shadow-[0_1px_12px_rgba(0,0,0,0.5)]">
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onClose();
            }}
            className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 active:scale-95 flex items-center justify-center transition-all border border-white/10 text-[#c4c7c8] hover:text-white"
            aria-label="Назад"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-base font-bold text-white tracking-tight">Электронный билет</h1>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleShareTelegram}
            className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 active:scale-95 flex items-center justify-center text-[#c4c7c8] hover:text-white transition-all border border-white/10"
            title="Отправить в Telegram"
            aria-label="Отправить в Telegram"
          >
            <Share2 className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Main Ticket Surface Container */}
      <main className="flex-1 max-w-[420px] w-full mx-auto p-4 flex flex-col justify-between space-y-5 pb-[calc(2.5rem+var(--safe-bottom,0px))]">
        {/* Ticket Card matching Stitch Obsidian Optical */}
        <div className="rounded-[28px] relative overflow-hidden flex flex-col bg-[#151518] border border-white/12 shadow-[0_20px_50px_rgba(0,0,0,0.85)]">
          {/* Perforation notches */}
          <div className="absolute w-6 h-6 rounded-full bg-[#08080a] border border-white/10 left-[-12px] top-[58%] -translate-y-1/2 z-20 pointer-events-none" />
          <div className="absolute w-6 h-6 rounded-full bg-[#08080a] border border-white/10 right-[-12px] top-[58%] -translate-y-1/2 z-20 pointer-events-none" />

          {/* Upper Ticket Part: Event Hero & Info */}
          <div className="p-5 pb-6 space-y-4">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-[#10b981]/15 text-[#4edea3] border border-[#10b981]/30">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse" />
                Билет действителен
              </span>
              <span className="text-xs text-[#8e9192] font-mono font-medium tracking-wider">
                № {generatedTicketNo}
              </span>
            </div>

            <div className="flex gap-3.5 items-center">
              <div className="w-16 h-16 rounded-2xl overflow-hidden shrink-0 border border-white/10 bg-[#1c1b1e]">
                <SafeImage
                  src={event.cover_image_url}
                  alt={event.title}
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-base font-bold text-white leading-tight line-clamp-2">
                  {event.title}
                </h2>
                <p className="text-xs text-[#8e9192] mt-1 truncate">
                  Организатор: {event.organization_name || 'Ivently Events'}
                </p>
              </div>
            </div>

            {/* Metadata Grid */}
            <div className="grid grid-cols-2 gap-3 pt-3 border-t border-white/8 text-xs">
              <div>
                <span className="text-[#8e9192] block text-[11px]">Дата и время</span>
                <span className="font-semibold text-white text-sm">{formattedDate}</span>
                <span className="text-[11px] text-[#8e9192] block">По местному времени</span>
              </div>
              <div>
                <span className="text-[#8e9192] block text-[11px]">Категория</span>
                <span className="font-semibold text-white text-sm">{tierName}</span>
                <span className="text-[11px] text-[#4edea3] block">
                  {event.is_free ? 'Бесплатный вход' : `${event.price_amount || 0} ₽`}
                </span>
              </div>
              <div className="col-span-2 pt-1">
                <span className="text-[#8e9192] block text-[11px]">Локация</span>
                <span className="font-semibold text-white text-sm">
                  {event.venue_name || 'Локация в приложении'}
                </span>
                <span className="text-[11px] text-[#8e9192] block truncate">
                  {event.address || (event.city_name ? `г. ${event.city_name}` : 'Махачкала')}
                </span>
              </div>
            </div>
          </div>

          {/* Dashed Perforation Line */}
          <div className="relative w-full px-5">
            <div className="w-full border-t-2 border-dashed border-white/15" />
          </div>

          {/* Lower Ticket Part: High-Contrast Scanning Surface for Bouncers */}
          <div className="p-6 bg-[#1a1a1e] flex flex-col items-center text-center space-y-3">
            <div className="w-52 h-52 bg-white rounded-2xl p-3 shadow-2xl flex flex-col items-center justify-center overflow-hidden">
              {qrDataUrl ? (
                <img
                  src={qrDataUrl}
                  alt={`QR код билета ${generatedTicketNo}`}
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-black/50 text-xs">
                  Генерация QR...
                </div>
              )}
            </div>
            <p className="text-[11px] text-[#8e9192] max-w-xs leading-relaxed">
              Покажите этот QR-код на входе организатору или контролёру мероприятия
            </p>
          </div>
        </div>

        {/* Bottom Actions */}
        <div className="space-y-2 pt-1">
          <button
            type="button"
            onClick={handleShareTelegram}
            className="w-full py-3.5 px-4 rounded-full bg-white text-black font-bold text-xs flex items-center justify-center gap-2 active:scale-98 transition-all shadow-lg hover:bg-zinc-200"
          >
            <Share2 className="w-4 h-4" />
            <span>Переслать билет в Telegram</span>
          </button>
          <button
            type="button"
            onClick={handleCopyTicketData}
            className="w-full py-3 px-4 rounded-full bg-white/5 hover:bg-white/10 text-white font-medium text-xs flex items-center justify-center gap-2 active:scale-98 transition-all border border-white/10"
          >
            {copiedToast ? <Check className="w-4 h-4 text-[#4edea3]" /> : <Copy className="w-4 h-4 text-[#8e9192]" />}
            <span>{copiedToast ? 'Данные билета скопированы!' : 'Скопировать номер и детали'}</span>
          </button>
        </div>
      </main>
    </div>
  );
};
