import React, { useState } from 'react';
import { Calendar, MapPin, Users, Heart, ArrowRight } from 'lucide-react';


export interface EditorialEventCardData {
  id: string;
  title: string;
  coverUrl: string;
  category: string;
  priceText: string;
  isFree?: boolean;
  dateText: string;
  venueText: string;
  cityText: string;
  attendeesCount: number;
  likesCount: number;
  initialInterested?: boolean;
}

export interface EditorialEventCardProps {
  event: EditorialEventCardData;
  onOpenDetails?: (id: string) => void;
  className?: string;
}

export const EditorialEventCard: React.FC<EditorialEventCardProps> = ({
  event,
  onOpenDetails,
  className = '',
}) => {
  const [isInterested, setIsInterested] = useState(event.initialInterested ?? false);
  const [likes, setLikes] = useState(event.likesCount);

  const handleToggleInterest = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsInterested((prev) => !prev);
    setLikes((prev) => (isInterested ? prev - 1 : prev + 1));
  };

  return (
    <article
      role="region"
      aria-label={`Карточка события: ${event.title}`}
      onClick={() => onOpenDetails?.(event.id)}
      className={`editorial-card rounded-[26px] overflow-hidden cursor-pointer select-none relative group ${className}`}
    >

      {/* 1. Cinematic Hero Image Area */}
      <div className="relative aspect-[16/11] w-full overflow-hidden bg-neutral-900">
        <img
          src={event.coverUrl}
          alt={event.title}
          loading="lazy"
          onError={(e) => {
            e.currentTarget.src = 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=900&auto=format&fit=crop&q=80';
          }}
          className="w-full h-full object-cover object-center transition-transform duration-700 ease-out group-hover:scale-105"
        />


        {/* Media Shadow Scrim */}
        <div className="card-media-scrim absolute inset-0 pointer-events-none" />

        {/* Top Floating Glass Badges */}
        <div className="absolute top-3.5 left-3.5 right-3.5 flex items-center justify-between pointer-events-none">
          {/* Category Pill */}
          <span className="glass-pill-badge px-3 py-1 rounded-full text-[11px] font-semibold text-white/90 tracking-wide uppercase shadow-sm">
            {event.category}
          </span>

          {/* Price Pill */}
          <span
            className={`px-3 py-1 rounded-full text-xs font-bold tracking-tight shadow-sm ${
              event.isFree
                ? 'glass-pill-emerald text-emerald-300'
                : 'glass-pill-badge text-white'
            }`}
          >
            {event.priceText}
          </span>
        </div>

        {/* Bottom CTA Overlay on Hero */}
        <div className="absolute bottom-3.5 right-3.5 flex items-center gap-2">
          <button
            onClick={handleToggleInterest}
            aria-label={isInterested ? 'Отменить отметку интереса' : 'Отметить интерес: Хочу пойти'}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold transition-all duration-300 cursor-pointer shadow-lg outline-none ${
              isInterested
                ? 'bg-white text-black shadow-white/20 scale-105'
                : 'glass-pill-badge text-white hover:bg-white/20 active:scale-95'
            }`}
          >
            <Heart
              size={14}
              className={`transition-colors ${isInterested ? 'fill-black text-black' : 'text-white'}`}
            />
            <span>{isInterested ? 'Вы идёте' : 'Хочу пойти'}</span>
          </button>
        </div>
      </div>

      {/* 2. Editorial Typography & Metadata Block */}
      <div className="p-4 pt-2 flex flex-col gap-2.5">
        {/* Title */}
        <h2 className="text-[17px] font-bold text-white tracking-[-0.015em] leading-[1.3] line-clamp-2 group-hover:text-neutral-200 transition-colors">
          {event.title}
        </h2>

        {/* Primary Metadata (Date & Venue) */}
        <div className="flex flex-col gap-1 text-[13px] text-neutral-400">
          <div className="flex items-center gap-2">
            <Calendar size={14} className="text-neutral-400 shrink-0" />
            <span className="font-medium text-neutral-300">{event.dateText}</span>
          </div>
          <div className="flex items-center gap-2">
            <MapPin size={14} className="text-neutral-400 shrink-0" />
            <span className="truncate text-neutral-400">{event.venueText}</span>
          </div>
        </div>

        {/* Divider */}
        <div className="h-[1px] w-full bg-white/[0.06] my-0.5" />

        {/* Social Proof & Navigation Link */}
        <div className="flex items-center justify-between text-xs text-neutral-400 pt-0.5">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 font-medium text-neutral-300">
              <Users size={14} className="text-neutral-400" />
              <span>{event.attendeesCount}</span>
            </div>
            <div className="flex items-center gap-1.5 text-neutral-400">
              <Heart size={14} className={isInterested ? 'fill-red-400 text-red-400' : 'text-neutral-400'} />
              <span>{likes}</span>
            </div>
          </div>

          <div className="flex items-center gap-1 font-semibold text-neutral-300 group-hover:text-white transition-colors">
            <span>Подробнее</span>
            <ArrowRight size={13} className="transition-transform group-hover:translate-x-0.5" />
          </div>
        </div>
      </div>
    </article>
  );
};
