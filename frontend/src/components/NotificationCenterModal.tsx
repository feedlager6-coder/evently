import React, { useState } from 'react';
import type { EventSummary } from '../types';
import { telegram } from '../services/telegram';
import {
  Bell,
  X,
  Sparkles,
  Clock,
  ArrowRight,
  ShieldCheck,
  Check,
} from 'lucide-react';

interface NotificationCenterModalProps {
  isOpen: boolean;
  onClose: () => void;
  attendingEvents?: EventSummary[];
  interestedEvents?: EventSummary[];
  organizerEvents?: EventSummary[];
  onEventClick?: (event: EventSummary) => void;
  onOpenOrganizerWorkspace?: () => void;
  onMarkAllRead?: () => void;
}

export const NotificationCenterModal: React.FC<NotificationCenterModalProps> = ({
  isOpen,
  onClose,
  attendingEvents = [],
  interestedEvents = [],
  organizerEvents = [],
  onEventClick,
  onOpenOrganizerWorkspace,
  onMarkAllRead,
}) => {
  const [filter, setFilter] = useState<'all' | 'events' | 'organizer'>('all');
  const [isMarkedRead, setIsMarkedRead] = useState(false);

  if (!isOpen) return null;

  const now = Date.now();
  const next48h = now + 48 * 60 * 60 * 1000;

  // 1. Upcoming RSVP/bookmark events within next 48 hours
  const upcomingAttending = attendingEvents.filter((e) => {
    const t = new Date(e.start_at).getTime();
    return t >= now && t <= next48h;
  });

  const upcomingInterested = interestedEvents.filter((e) => {
    const t = new Date(e.start_at).getTime();
    return t >= now && t <= next48h;
  });

  // 2. Organizer status updates (events published or pending)
  const pendingOrgEvents = organizerEvents.filter((e) => e.status === 'pending');
  const publishedOrgEvents = organizerEvents.filter((e) => e.status === 'published').slice(0, 3);

  const handleMarkAllRead = () => {
    telegram.hapticSuccess();
    try {
      localStorage.setItem('ivently_last_notifications_read_at', Date.now().toString());
    } catch {}
    setIsMarkedRead(true);
    onMarkAllRead?.();
  };

  const hasAnyItems =
    upcomingAttending.length > 0 ||
    upcomingInterested.length > 0 ||
    pendingOrgEvents.length > 0 ||
    publishedOrgEvents.length > 0;

  return (
    <div className="fixed inset-0 z-[70] bg-black/85 backdrop-blur-xl flex flex-col animate-fade-in overflow-hidden">
      {/* Header */}
      <header className="px-4 pt-4 pb-3 flex items-center justify-between border-b border-white/8 bg-[#0d0d10]/90 sticky top-0 z-20">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <Bell className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white tracking-tight leading-none">
              Центр уведомлений
            </h2>
            <span className="text-[11px] text-zinc-400">События и оперативный статус</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!isMarkedRead && hasAnyItems && (
            <button
              type="button"
              onClick={handleMarkAllRead}
              className="px-2.5 py-1 rounded-full bg-white/5 hover:bg-white/10 text-[11px] font-medium text-zinc-300 transition-colors"
            >
              Прочитано
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              telegram.hapticImpact('light');
              onClose();
            }}
            className="w-8 h-8 rounded-full bg-white/5 text-zinc-400 hover:text-white flex items-center justify-center transition-colors"
            aria-label="Закрыть"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Filter Tabs */}
      <div className="px-4 py-2 border-b border-white/5 bg-[#0a0a0c] flex items-center gap-1.5 shrink-0">
        <button
          type="button"
          onClick={() => {
            telegram.hapticImpact('light');
            setFilter('all');
          }}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-all ${
            filter === 'all'
              ? 'bg-white text-black'
              : 'bg-white/5 text-zinc-400 hover:text-zinc-200'
          }`}
        >
          Все
        </button>
        <button
          type="button"
          onClick={() => {
            telegram.hapticImpact('light');
            setFilter('events');
          }}
          className={`px-3 py-1 rounded-full text-xs font-semibold transition-all ${
            filter === 'events'
              ? 'bg-white text-black'
              : 'bg-white/5 text-zinc-400 hover:text-zinc-200'
          }`}
        >
          Мои события ({upcomingAttending.length + upcomingInterested.length})
        </button>
        {organizerEvents.length > 0 && (
          <button
            type="button"
            onClick={() => {
              telegram.hapticImpact('light');
              setFilter('organizer');
            }}
            className={`px-3 py-1 rounded-full text-xs font-semibold transition-all ${
              filter === 'organizer'
                ? 'bg-white text-black'
                : 'bg-white/5 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Организатор ({pendingOrgEvents.length + publishedOrgEvents.length})
          </button>
        )}
      </div>

      {/* Content List */}
      <main className="flex-1 overflow-y-auto px-4 py-3 space-y-3 pb-24">
        {/* 1. Upcoming RSVP Events (Starts soon) */}
        {(filter === 'all' || filter === 'events') &&
          upcomingAttending.map((ev) => {
            const dateObj = new Date(ev.start_at);
            const timeStr = dateObj.toLocaleTimeString('ru-RU', {
              hour: '2-digit',
              minute: '2-digit',
            });
            return (
              <div
                key={`attending-${ev.id}`}
                onClick={() => {
                  telegram.hapticImpact('light');
                  if (onEventClick) onEventClick(ev);
                  onClose();
                }}
                className="p-3.5 rounded-2xl bg-[#141418] border border-emerald-500/30 hover:border-emerald-500/50 cursor-pointer transition-all space-y-1.5"
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-1.5 text-emerald-400 font-bold">
                    <Clock className="w-3.5 h-3.5" />
                    Напоминание о событии
                  </span>
                  <span className="text-[11px] text-zinc-400 font-medium">
                    Сегодня в {timeStr}
                  </span>
                </div>
                <h3 className="text-sm font-semibold text-white truncate">{ev.title}</h3>
                <p className="text-xs text-zinc-400 truncate">
                  📍 {ev.venue_name || 'Локация в приложении'}
                </p>
                <div className="pt-1 flex items-center justify-between text-xs text-emerald-400 font-semibold">
                  <span>У вас есть билет / «Я иду»</span>
                  <span className="flex items-center gap-0.5 text-[11px]">
                    Открыть <ArrowRight className="w-3 h-3" />
                  </span>
                </div>
              </div>
            );
          })}

        {/* 2. Interested Bookmarks starting soon */}
        {(filter === 'all' || filter === 'events') &&
          upcomingInterested.map((ev) => {
            const dateObj = new Date(ev.start_at);
            const dateStr = dateObj.toLocaleDateString('ru-RU', {
              day: 'numeric',
              month: 'short',
              hour: '2-digit',
              minute: '2-digit',
            });
            return (
              <div
                key={`interested-${ev.id}`}
                onClick={() => {
                  telegram.hapticImpact('light');
                  if (onEventClick) onEventClick(ev);
                  onClose();
                }}
                className="p-3.5 rounded-2xl bg-[#141418] border border-white/8 hover:border-white/15 cursor-pointer transition-all space-y-1.5"
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-1.5 text-amber-400 font-semibold">
                    <Sparkles className="w-3.5 h-3.5" />
                    Событие из закладок
                  </span>
                  <span className="text-[11px] text-zinc-400 font-medium">{dateStr}</span>
                </div>
                <h3 className="text-sm font-semibold text-white truncate">{ev.title}</h3>
                <p className="text-xs text-zinc-400 truncate">
                  📍 {ev.venue_name || 'Локация в приложении'}
                </p>
                <div className="pt-1 flex items-center justify-between text-xs text-zinc-400">
                  <span>Вы отметили «Хочу пойти»</span>
                  <span className="text-emerald-400 flex items-center gap-0.5 text-[11px] font-semibold">
                    Детали <ArrowRight className="w-3 h-3" />
                  </span>
                </div>
              </div>
            );
          })}

        {/* 3. Pending Moderation Status */}
        {(filter === 'all' || filter === 'organizer') &&
          pendingOrgEvents.map((ev) => (
            <div
              key={`pending-${ev.id}`}
              onClick={() => {
                telegram.hapticImpact('light');
                if (onOpenOrganizerWorkspace) onOpenOrganizerWorkspace();
                onClose();
              }}
              className="p-3.5 rounded-2xl bg-[#141418] border border-amber-500/30 hover:border-amber-500/50 cursor-pointer transition-all space-y-1.5"
            >
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-amber-400 font-semibold">
                  <Clock className="w-3.5 h-3.5" />
                  На модерации
                </span>
                <span className="text-[11px] text-zinc-400">Проверка</span>
              </div>
              <h3 className="text-sm font-semibold text-white truncate">{ev.title}</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Заявка на публикацию отправлена администраторам. Скоро появится в афише!
              </p>
            </div>
          ))}

        {/* 4. Verified Platform Notice */}
        <div className="p-3.5 rounded-2xl bg-white/[0.03] border border-white/6 space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs text-zinc-300 font-semibold">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Ivently Bot в любых чатах</span>
          </div>
          <p className="text-xs text-zinc-400 leading-relaxed">
            Напишите <code className="text-emerald-400 font-mono">@ivently_bot</code> в любом диалоге Telegram для быстрого поиска и отправки карточек событий друзьям.
          </p>
        </div>

        {/* Empty State */}
        {!hasAnyItems && (
          <div className="py-12 text-center space-y-2">
            <div className="w-12 h-12 rounded-full bg-white/5 mx-auto flex items-center justify-center text-zinc-500">
              <Check className="w-6 h-6" />
            </div>
            <p className="text-sm font-bold text-white">Все уведомления прочитаны</p>
            <p className="text-xs text-zinc-400 max-w-xs mx-auto">
              Здесь будут появляться напоминания о предстоящих событиях, билетах и статусе ваших мероприятий.
            </p>
          </div>
        )}
      </main>
    </div>
  );
};
