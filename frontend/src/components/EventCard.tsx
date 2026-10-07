import React from 'react';
import type { EventSummary } from '../types';
import { Calendar, MapPin, Users, Check, Heart } from 'lucide-react';
import { SafeImage } from './SafeImage';

interface EventCardProps {
  event: EventSummary;
  onClick: () => void;
}

export const EventCard: React.FC<EventCardProps> = ({ event, onClick }) => {
  // Format date nicely
  const eventDate = new Date(event.start_at);
  const formattedDate = eventDate.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });

  const priceLabel = event.is_free
    ? 'Бесплатно'
    : `${event.price_amount} ${event.price_currency || 'RUB'}`;

  const isPast = eventDate < new Date();
  const isCancelled = event.status === 'cancelled';

  return (
    <div
      onClick={onClick}
      className={`group relative rounded-[20px] overflow-hidden bg-[#131722] border border-white/8 hover:border-indigo-500/40 card-press cursor-pointer shadow-lg hover:shadow-indigo-500/10 ${
        isPast ? 'opacity-85 hover:opacity-100' : ''
      }`}
    >
      {/* Cover Image Container */}
      <div className="relative aspect-[16/9] w-full overflow-hidden bg-gray-900">
        <SafeImage
          src={event.cover_image_url}
          alt={event.title}
          loading="lazy"
          className="w-full h-full object-cover transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-105"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-[#131722] via-transparent to-black/35" />

        {/* Top Badges (Frosted Glass) */}
        <div className="absolute top-2.5 inset-x-2.5 flex items-center justify-between pointer-events-none">
          <div className="flex items-center space-x-1.5">
            <span className="px-2.5 py-1 rounded-full text-[11px] font-semibold tracking-wide bg-black/65 backdrop-blur-md text-white border border-white/10 shadow-sm">
              {event.category_name}
            </span>
            {isPast && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/10 backdrop-blur-md text-gray-300 border border-white/10 shadow-sm">
                Завершено
              </span>
            )}
            {isCancelled && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-950/80 backdrop-blur-md text-red-300 border border-red-500/30 shadow-sm">
                Отменено
              </span>
            )}
          </div>
          <span
            className={`px-2.5 py-1 rounded-full text-[11px] font-bold backdrop-blur-md border shadow-sm ${
              isPast
                ? 'bg-white/10 border-white/10 text-gray-300'
                : event.is_free
                ? 'bg-emerald-500/85 border-emerald-400/40 text-white'
                : 'bg-indigo-600/85 border-indigo-400/40 text-white'
            }`}
          >
            {priceLabel}
          </span>
        </div>

        {/* Attending or Interested badge */}
        {!isPast ? (
          event.is_attending ? (
            <div className="absolute bottom-2.5 right-2.5 flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500 text-white shadow-lg animate-scale-pop">
              <Check className="w-3.5 h-3.5 stroke-[3]" />
              <span>Вы идёте</span>
            </div>
          ) : event.current_user_interested ? (
            <div className="absolute bottom-2.5 right-2.5 flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-600/90 text-white shadow-lg shadow-purple-600/20 backdrop-blur-sm animate-scale-pop">
              <Heart className="w-3 h-3 fill-white" />
              <span>Хочу пойти</span>
            </div>
          ) : null
        ) : (event.is_attending || event.current_user_interested || event.is_creator) ? (
          <div className="absolute bottom-2.5 right-2.5 flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-black/75 text-gray-300 border border-white/10 backdrop-blur-sm">
            <span>{event.is_creator ? 'Создано вами' : event.is_attending ? 'Вы были' : 'Было в закладках'}</span>
          </div>
        ) : null}
      </div>

      {/* Card Body */}
      <div className="p-4 space-y-2.5">
        <h3 className="font-semibold text-base text-white group-hover:text-indigo-300 transition-colors line-clamp-2 leading-snug">
          {event.title}
        </h3>

        <div className="space-y-1.5 text-xs text-gray-300">
          <div className="flex items-center space-x-2 text-indigo-300 font-medium">
            <Calendar className="w-3.5 h-3.5 shrink-0" />
            <span>{formattedDate}</span>
          </div>
          <div className="flex items-center space-x-2 text-gray-400">
            <MapPin className="w-3.5 h-3.5 shrink-0 text-gray-500" />
            <span className="truncate">{event.venue_name} ({event.city_name})</span>
          </div>
        </div>

        {/* Bottom stats */}
        <div className="pt-2 border-t border-white/5 flex items-center justify-between text-xs text-gray-400">
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-1.5">
              <Users className="w-3.5 h-3.5 text-indigo-400" />
              <span>{event.attendee_count}</span>
            </div>
            {event.interest_count > 0 && (
              <div className="flex items-center space-x-1 text-purple-300/90">
                <Heart className="w-3.5 h-3.5 fill-purple-500/20 text-purple-400" />
                <span>{event.interest_count}</span>
              </div>
            )}
          </div>
          <span className="text-indigo-400 font-medium group-hover:translate-x-0.5 transition-transform">
            Подробнее →
          </span>
        </div>
      </div>
    </div>
  );
};
