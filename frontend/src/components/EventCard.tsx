import React from 'react';
import type { EventSummary } from '../types';
import { Calendar, MapPin, Users, Bookmark } from 'lucide-react';
import { SafeImage } from './SafeImage';
import { telegram } from '../services/telegram';

interface EventCardProps {
  event: EventSummary;
  onClick: () => void;
  isHero?: boolean;
  onToggleInterest?: (event: EventSummary) => void;
}

export const EventCard: React.FC<EventCardProps> = ({
  event,
  onClick,
  isHero = false,
  onToggleInterest,
}) => {
  // Format date nicely
  const eventDate = new Date(event.start_at);
  const formattedDate = eventDate.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: isHero ? 'long' : 'short',
    hour: '2-digit',
    minute: '2-digit',
  });

  const priceAmount = event.price_amount;
  const isFree = Boolean(event.is_free) || (priceAmount !== null && priceAmount !== undefined && Number(priceAmount) === 0);
  const priceLabel = isFree
    ? 'Бесплатно'
    : priceAmount !== null && priceAmount !== undefined
      ? `${Number(priceAmount) % 1 === 0 ? Number(priceAmount) : priceAmount} ₽`
      : 'Вход свободный';

  const isPast = eventDate < new Date();
  const isCancelled = event.status === 'cancelled';

  const handleBookmarkClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    telegram.hapticImpact('light');
    if (onToggleInterest) {
      onToggleInterest(event);
    }
  };

  // Hero Card Presentation (First item in feed matching Stitch)
  if (isHero) {
    return (
      <section
        onClick={onClick}
        className="relative w-full rounded-[28px] overflow-hidden bg-[#1c1b1e] border border-white/12 shadow-[0_16px_36px_rgba(0,0,0,0.65)] group cursor-pointer transition-all active:scale-[0.99]"
      >
        <div className="relative h-[360px] w-full flex flex-col justify-between p-4">
          {/* Background image & gradient ramp */}
          <div className="absolute inset-0 z-0">
            <SafeImage
              src={event.cover_image_url}
              alt={event.title}
              loading="eager"
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700 ease-[cubic-bezier(0.16,1,0.3,1)]"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[#08080a] via-[#08080a]/60 to-black/25 pointer-events-none" />
          </div>

          {/* Top Badges */}
          <div className="relative z-10 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="px-3 py-1.5 rounded-full bg-[#0e0e10]/80 backdrop-blur-md text-white font-medium text-xs border border-white/15 shadow-[inset_0_1px_1px_rgba(255,255,255,0.2)]">
                {event.category_name || 'Событие'}
              </span>
              {event.organization_is_verified && (
                <span className="px-2.5 py-1 rounded-full bg-emerald-500/20 backdrop-blur-md text-emerald-400 font-bold text-[10px] border border-emerald-500/30 shadow-sm flex items-center gap-0.5">
                  ✓ Проверено
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleBookmarkClick}
                aria-label={event.current_user_interested ? 'Удалить из закладок' : 'В закладки'}
                className="w-9 h-9 rounded-full bg-[#0e0e10]/80 backdrop-blur-md border border-white/15 flex items-center justify-center text-white/90 shadow-[inset_0_1px_1px_rgba(255,255,255,0.2)] active:scale-90 transition-transform btn-press"
              >
                <Bookmark className={`w-4 h-4 ${event.current_user_interested ? 'fill-white text-white' : 'text-white'}`} />
              </button>
            </div>
          </div>

          {/* Bottom Content Area */}
          <div className="relative z-10 flex flex-col gap-2 pt-4">
            <div className="flex items-center gap-2 text-[#ffb95f] font-semibold text-xs">
              <Calendar className="w-3.5 h-3.5 shrink-0" />
              <span>{formattedDate}</span>
            </div>

            <h2 className="font-extrabold text-xl text-white tracking-tight leading-snug line-clamp-2">
              {event.title}
            </h2>

            <div className="flex items-center justify-between pt-0.5">
              <div className="flex items-center gap-1.5 text-[#c4c7c8] text-xs min-w-0">
                <MapPin className="w-3.5 h-3.5 text-[#8e9192] shrink-0" />
                <span className="truncate">{event.venue_name} ({event.city_name})</span>
              </div>
              <div className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-white/10 backdrop-blur-md text-white text-[11px] font-bold shrink-0 border border-white/10">
                <Users className="w-3 h-3 text-[#4edea3]" />
                <span>{event.attendee_count} идут</span>
              </div>
            </div>

            {/* Action & Price Row */}
            <div className="flex items-center justify-between pt-2">
              <div className="flex flex-col">
                <span className="text-[10px] font-bold tracking-wider uppercase text-[#8e9192]">Билеты</span>
                <span className={`text-base font-extrabold ${isFree ? 'text-[#4edea3]' : 'text-white'}`}>
                  {priceLabel}
                </span>
              </div>
              <button
                type="button"
                className="px-5 py-2.5 rounded-full bg-white text-[#08080a] font-bold text-xs shadow-[0_4px_16px_rgba(255,255,255,0.25)] active:scale-95 transition-all hover:bg-zinc-100"
              >
                {isFree ? 'Подробнее' : 'Купить билет'}
              </button>
            </div>
          </div>
        </div>
      </section>
    );
  }

  // Standard Feed Card Presentation matching Stitch
  return (
    <article
      onClick={onClick}
      className={`group relative flex flex-col rounded-3xl overflow-hidden bg-[#141416] border border-white/10 shadow-[0_8px_24px_rgba(0,0,0,0.5)] transition-all card-press cursor-pointer hover:border-white/20 active:scale-[0.99] ${
        isPast ? 'opacity-85 hover:opacity-100' : ''
      }`}
    >
      {/* Cover Image Container */}
      <div className="relative h-[190px] w-full overflow-hidden bg-[#121215] p-3 flex flex-col justify-between">
        <div className="absolute inset-0 z-0">
          <SafeImage
            src={event.cover_image_url}
            alt={event.title}
            loading="eager"
            className="w-full h-full object-cover transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-105"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#141416] via-transparent to-black/35 pointer-events-none" />
        </div>

        {/* Top Badges */}
        <div className="relative z-10 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            {event.category_name && (
              <span className="px-2.5 py-1 rounded-full bg-[#08080a]/80 backdrop-blur-md text-white font-medium text-[11px] border border-white/15">
                {event.category_name}
              </span>
            )}
            {isFree && (
              <span className="px-2.5 py-1 rounded-full bg-[#10b981]/25 backdrop-blur-md text-[#4edea3] font-semibold text-[10px] border border-[#10b981]/40 shadow-[0_2px_8px_rgba(16,185,129,0.2)]">
                Бесплатно
              </span>
            )}

            {isPast && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/10 backdrop-blur-md text-gray-300 border border-white/10">
                Завершено
              </span>
            )}
            {isCancelled && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-950/80 backdrop-blur-md text-red-300 border border-red-500/30">
                Отменено
              </span>
            )}
          </div>

          {/* Bookmark icon */}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleBookmarkClick}
              aria-label={event.current_user_interested ? 'Удалить из закладок' : 'В закладки'}
              className="w-8 h-8 rounded-full bg-black/60 backdrop-blur-md border border-white/15 flex items-center justify-center text-white/80 shadow-sm active:scale-90 transition-transform btn-press"
            >
              <Bookmark className={`w-3.5 h-3.5 ${event.current_user_interested ? 'fill-white text-white' : 'text-white'}`} />
            </button>
          </div>
        </div>

        {/* Bottom tags on cover */}
        <div className="relative z-10 flex items-center gap-1.5">
          <span className="px-2.5 py-1 rounded-full bg-[#08080a]/85 backdrop-blur-md text-white font-bold text-[11px] border border-white/10 shadow-sm">
            {formattedDate}
          </span>
        </div>
      </div>

      {/* Card Body */}
      <div className="p-4 flex flex-col gap-2">
        <h3 className="font-bold text-[16px] text-white tracking-tight leading-snug line-clamp-2">
          {event.title}
        </h3>

        {event.source_type === 'external' ? (
          <div className="flex items-center gap-1.5 text-xs text-[#c4c7c8] line-clamp-1 leading-relaxed">
            <span className="truncate">{event.venue_name || 'Городская афиша'}</span>
          </div>
        ) : event.organization_name ? (
          <div className="flex items-center gap-1.5 text-xs text-[#c4c7c8] line-clamp-1 leading-relaxed">
            <span className="truncate">{event.organization_name}</span>
            {event.organization_is_verified && (
              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-bold text-[10px] border border-emerald-500/30 shrink-0">
                ✓ Проверено
              </span>
            )}
          </div>
        ) : null}

        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center gap-1.5 text-[#c4c7c8] text-xs min-w-0">
            <MapPin className="w-3.5 h-3.5 text-[#8e9192] shrink-0" />
            <span className="truncate">{event.venue_name}</span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {event.attendee_count > 0 && (
              <span className="text-[11px] text-[#8e9192] flex items-center gap-1">
                <Users className="w-3 h-3 text-[#4edea3]" />
                {event.attendee_count}
              </span>
            )}
            <span className={`text-sm font-bold ${isFree ? 'text-[#4edea3]' : 'text-white'}`}>
              {priceLabel}
            </span>
          </div>
        </div>
      </div>
    </article>
  );
};
