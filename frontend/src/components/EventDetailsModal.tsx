import React, { useState } from 'react';
import type { EventResponse } from '../types';
import { telegram } from '../services/telegram';
import { api } from '../services/api';
import { 
  Calendar, 
  MapPin, 
  Users, 
  Check, 
  X, 
  Share2, 
  Ticket, 
  User as UserIcon,
  Loader2
} from 'lucide-react';

interface EventDetailsModalProps {
  event: EventResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onToggleRsvp: (eventId: string, currentStatus: boolean) => Promise<void>;
  isRsvpLoading: boolean;
}

export const EventDetailsModal: React.FC<EventDetailsModalProps> = ({
  event,
  isOpen,
  onClose,
  onToggleRsvp,
  isRsvpLoading,
}) => {
  const [copied, setCopied] = useState(false);
  const [shareToast, setShareToast] = useState<string | null>(null);

  if (!isOpen || !event) return null;

  const eventDate = new Date(event.start_at);
  const formattedFullDate = eventDate.toLocaleDateString('ru-RU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  const priceText = event.is_free
    ? 'Бесплатно'
    : `${event.price_amount} ${event.price_currency || 'RUB'}`;

  const handleShare = async () => {
    telegram.hapticImpact('light');
    const botUsername = api.getBotUsername();
    const shareUrl = `https://t.me/${botUsername}/app?startapp=event_${event.id}`;
    const shareTitle = `${event.title} — Ivently`;
    const shareText = `🎟️ ${event.title}\n📅 ${formattedFullDate}\n📍 ${event.venue_name}${event.city_name ? ` (${event.city_name})` : ''}\n\nСмотрите в Ivently:`;

    let shared = false;
    if (navigator.share) {
      try {
        await navigator.share({
          title: shareTitle,
          text: shareText,
          url: shareUrl,
        });
        shared = true;
      } catch (err: any) {
        if (err.name === 'AbortError') {
          return;
        }
      }
    }

    if (!shared) {
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(shareUrl);
        } else {
          const textArea = document.createElement('textarea');
          textArea.value = shareUrl;
          document.body.appendChild(textArea);
          textArea.select();
          document.execCommand('copy');
          document.body.removeChild(textArea);
        }
        setCopied(true);
        setShareToast('Ссылка скопирована!');
        telegram.hapticSuccess();
        setTimeout(() => {
          setCopied(false);
          setShareToast(null);
        }, 2500);
      } catch (copyErr) {
        console.warn('Clipboard copy failed:', copyErr);
      }
    }
  };


  const handleRsvpClick = async () => {
    if (isRsvpLoading) return;
    telegram.hapticSuccess();
    await onToggleRsvp(event.id, event.is_attending);
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end sm:justify-center items-center bg-black/80 backdrop-blur-sm animate-fade-in p-0 sm:p-4">
      {/* Bottom Sheet Modal Container */}
      <div 
        className="w-full max-w-lg bg-[#0F121C] sm:rounded-3xl rounded-t-3xl border border-white/10 overflow-hidden shadow-2xl flex flex-col max-h-[92vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Media / Hero */}
        <div className="relative aspect-[16/9] w-full bg-gray-900 shrink-0">
          <img
            src={event.cover_image_url || 'https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?w=800'}
            alt={event.title}
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#0F121C] via-transparent to-black/40" />

          {/* Action Buttons */}
          <div className="absolute top-4 inset-x-4 flex items-center justify-between">
            <button
              onClick={onClose}
              className="p-2 rounded-full bg-black/60 backdrop-blur-md text-white border border-white/10 hover:bg-black/80 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
            <button
              onClick={handleShare}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-black/60 backdrop-blur-md text-white border border-white/10 hover:bg-black/80 transition-colors text-xs font-medium"
            >
              <Share2 className="w-3.5 h-3.5" />
              <span>{copied ? 'Скопировано!' : 'Поделиться'}</span>
            </button>
          </div>

          {/* Toast Notification */}
          {shareToast && (
            <div className="absolute top-16 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-full bg-emerald-600/95 text-white text-xs font-semibold shadow-2xl backdrop-blur-md animate-fade-in flex items-center space-x-1.5 pointer-events-none">
              <Check className="w-3.5 h-3.5 stroke-[2.5]" />
              <span>{shareToast}</span>
            </div>
          )}


          {/* Badges on hero bottom */}
          <div className="absolute bottom-3 left-4 flex flex-wrap gap-2">
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-600/90 text-white backdrop-blur-md shadow-sm">
              {event.category_name}
            </span>
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-white/10 text-gray-200 border border-white/10 backdrop-blur-md">
              📍 {event.city_name}
            </span>
          </div>
        </div>

        {/* Scrollable Content Body */}
        <div className="p-5 overflow-y-auto space-y-5 no-scrollbar">
          {/* Title */}
          <h2 className="text-xl font-bold text-white tracking-tight leading-snug">
            {event.title}
          </h2>

          {/* Key Facts Cards */}
          <div className="grid grid-cols-2 gap-2.5">
            {/* Date */}
            <div className="p-3 rounded-2xl bg-[#171B29] border border-white/5 space-y-1">
              <div className="flex items-center space-x-1.5 text-indigo-400 text-xs font-medium">
                <Calendar className="w-4 h-4" />
                <span>Дата и время</span>
              </div>
              <div className="text-xs font-medium text-white capitalize leading-tight">
                {formattedFullDate}
              </div>
            </div>

            {/* Price */}
            <div className="p-3 rounded-2xl bg-[#171B29] border border-white/5 space-y-1">
              <div className="flex items-center space-x-1.5 text-emerald-400 text-xs font-medium">
                <Ticket className="w-4 h-4" />
                <span>Стоимость</span>
              </div>
              <div className="text-xs font-bold text-white leading-tight">
                {priceText}
              </div>
            </div>
          </div>

          {/* Location details */}
          <div className="p-3.5 rounded-2xl bg-[#171B29] border border-white/5 space-y-1">
            <div className="flex items-center space-x-1.5 text-indigo-400 text-xs font-medium">
              <MapPin className="w-4 h-4" />
              <span>Локация</span>
            </div>
            <div className="text-sm font-semibold text-white">{event.venue_name}</div>
            {event.address && (
              <div className="text-xs text-gray-400">{event.address}</div>
            )}
          </div>

          {/* Organizer info */}
          {event.organizer_name && (
            <div className="flex items-center space-x-3 p-3 rounded-2xl bg-[#171B29]/60 border border-white/5">
              <div className="w-8 h-8 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center shrink-0">
                <UserIcon className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <div className="text-gray-400">Организатор</div>
                <div className="font-medium text-white">@{event.organizer_name}</div>
              </div>
            </div>
          )}

          {/* Description */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-white">О мероприятии</h4>
            <p className="text-xs leading-relaxed text-gray-300 whitespace-pre-line">
              {event.description}
            </p>
          </div>

          {/* Attendees Summary */}
          <div className="flex items-center space-x-2 text-xs text-gray-400 py-1">
            <Users className="w-4 h-4 text-indigo-400" />
            <span>Уже идут: <strong className="text-white font-semibold">{event.attendee_count} человек</strong></span>
          </div>
        </div>

        {/* Sticky Bottom RSVP Action Bar */}
        <div className="modal-safe-bottom bg-[#141724] border-t border-white/8 shrink-0">
          <button
            onClick={handleRsvpClick}
            disabled={isRsvpLoading}
            className={`w-full py-3.5 px-6 rounded-2xl font-bold text-sm flex items-center justify-center space-x-2 transition-all duration-300 shadow-xl ${
              event.is_attending
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/30'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/30'
            } active:scale-[0.98] disabled:opacity-75`}
          >
            {isRsvpLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : event.is_attending ? (
              <>
                <Check className="w-5 h-5 stroke-[2.5]" />
                <span>✓ Вы идёте (нажмите, чтобы отменить)</span>
              </>
            ) : (
              <>
                <Ticket className="w-5 h-5" />
                <span>Я иду</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
