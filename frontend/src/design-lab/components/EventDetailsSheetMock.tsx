import React, { useState } from 'react';
import { 
  MapPin, 
  Users, 
  Check, 
  X, 
  Share2, 
  Heart, 
  Sparkles, 
  ChevronRight, 
  Clock
} from 'lucide-react';

interface EventDetailsSheetMockProps {
  onClose?: () => void;
  onOpenCompanion?: () => void;
}

export const EventDetailsSheetMock: React.FC<EventDetailsSheetMockProps> = ({
  onClose,
  onOpenCompanion
}) => {
  const [isAttending, setIsAttending] = useState<boolean>(false);
  const [isInterested, setIsInterested] = useState<boolean>(false);
  const [isSubscribed, setIsSubscribed] = useState<boolean>(false);
  const [isDescExpanded, setIsDescExpanded] = useState<boolean>(false);
  const [attendeeCount, setAttendeeCount] = useState<number>(42);
  const [interestCount, setInterestCount] = useState<number>(88);

  const handleToggleRsvp = () => {
    if (!isAttending) {
      setIsAttending(true);
      setAttendeeCount((prev) => prev + 1);
      if (isInterested) {
        setIsInterested(false);
        setInterestCount((prev) => Math.max(0, prev - 1));
      }
    } else {
      setIsAttending(false);
      setAttendeeCount((prev) => Math.max(0, prev - 1));
    }
  };

  const handleToggleInterest = () => {
    if (!isInterested) {
      setIsInterested(true);
      setInterestCount((prev) => prev + 1);
      if (isAttending) {
        setIsAttending(false);
        setAttendeeCount((prev) => Math.max(0, prev - 1));
      }
    } else {
      setIsInterested(false);
      setInterestCount((prev) => Math.max(0, prev - 1));
    }
  };

  return (
    <div className="w-full max-w-[430px] rounded-t-[32px] bg-[#0E1015] border-t border-white/10 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
      {/* 1. Drag Handle & Sheet Header */}
      <div className="relative pt-3 pb-2 flex flex-col items-center justify-center shrink-0">
        <div className="w-10 h-1 rounded-full bg-white/20" />
        <div className="absolute top-2 right-3 flex items-center gap-1.5">
          <button
            type="button"
            className="w-8 h-8 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-gray-300 hover:text-white hover:bg-white/10 transition-colors"
            title="Поделиться"
          >
            <Share2 size={14} />
          </button>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-gray-300 hover:text-white hover:bg-white/10 transition-colors"
              title="Закрыть"
            >
              <X size={15} />
            </button>
          )}
        </div>
      </div>

      {/* 2. Scrollable Body */}
      <div className="overflow-y-auto px-4 pb-6 space-y-4 no-scrollbar">
        {/* Media Hero with Quad-Stop Scrim */}
        <div className="relative w-full h-56 rounded-2xl overflow-hidden border border-white/10 bg-gradient-to-br from-indigo-950/60 via-purple-950/40 to-emerald-950/40 shrink-0">
          <img
            src="https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=800"
            alt="Event Poster"
            className="w-full h-full object-cover"
            onError={(e) => {
              (e.target as HTMLElement).style.display = 'none';
            }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#0E1015] via-[#0E1015]/40 to-transparent" />
          
          <div className="absolute top-3 left-3 flex items-center gap-2">
            <span className="px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-md border border-white/15 text-[11px] font-semibold text-white">
              Концерты
            </span>
          </div>

          <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between">
            <span className="px-3 py-1 rounded-full bg-white/10 backdrop-blur-md border border-white/20 text-xs font-bold text-white shadow-lg">
              1 500 ₽
            </span>
            <div className="flex items-center gap-1.5 text-xs text-white/90 bg-black/60 backdrop-blur-md border border-white/10 px-2.5 py-1 rounded-full">
              <Users size={13} className="text-emerald-400" />
              <span>{attendeeCount} идут</span>
            </div>
          </div>
        </div>

        {/* Title & Timing */}
        <div className="space-y-1">
          <div className="text-xs font-medium text-emerald-400 flex items-center gap-1.5">
            <Clock size={13} />
            <span>Пятница, 10 октября • 19:26</span>
          </div>
          <h1 className="text-xl font-bold text-white tracking-tight leading-snug">
            Вечер джаза и неоклассики в оранжерее
          </h1>
        </div>

        {/* Organizer Card Chip */}
        <div className="p-3 rounded-2xl bg-white/[0.04] border border-white/8 flex items-center justify-between">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-amber-500 to-amber-300 p-0.5 shrink-0">
              <div className="w-full h-full rounded-full bg-black flex items-center justify-center font-bold text-xs text-amber-300">
                JD
              </div>
            </div>
            <div className="min-w-0">
              <div className="text-xs font-bold text-white truncate flex items-center gap-1">
                <span>Jazz & Dreams Moscow</span>
                <span className="text-[10px] text-emerald-400">✓</span>
              </div>
              <p className="text-[11px] text-gray-400 truncate">1 240 подписчиков</p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setIsSubscribed(!isSubscribed)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all shrink-0 ${
              isSubscribed
                ? 'bg-white/10 text-gray-300 border border-white/15'
                : 'bg-white text-black hover:bg-gray-100 font-bold shadow-md'
            }`}
          >
            {isSubscribed ? 'Вы подписаны' : 'Подписаться'}
          </button>
        </div>

        {/* Venue & Location Details */}
        <div className="p-3.5 rounded-2xl bg-white/[0.04] border border-white/8 space-y-2">
          <div className="flex items-start gap-2.5">
            <MapPin size={16} className="text-white/60 shrink-0 mt-0.5" />
            <div className="space-y-0.5 text-xs">
              <div className="font-semibold text-white">Ботаническая оранжерея</div>
              <div className="text-gray-400">г. Москва, ул. Проспект Мира, 26, стр. 1</div>
            </div>
          </div>
          <button
            type="button"
            className="w-full py-1.5 px-3 rounded-xl bg-white/5 hover:bg-white/10 text-white/80 hover:text-white text-xs font-medium flex items-center justify-center gap-1 border border-white/5 transition-colors"
          >
            <span>Показать на карте</span>
            <ChevronRight size={13} />
          </button>
        </div>

        {/* Companion Matching Pill Banner */}
        <div 
          onClick={onOpenCompanion}
          className="p-3.5 rounded-2xl bg-gradient-to-r from-emerald-950/40 via-white/[0.04] to-transparent border border-emerald-500/20 flex items-center justify-between cursor-pointer hover:border-emerald-500/35 transition-all"
        >
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Users size={16} />
            </div>
            <div>
              <div className="text-xs font-bold text-white">Найти компанию</div>
              <p className="text-[11px] text-gray-400">14 человек ищут компанию на этот вечер</p>
            </div>
          </div>
          <div className="flex items-center text-emerald-400 text-xs font-semibold gap-0.5">
            <span>Открыть</span>
            <ChevronRight size={14} />
          </div>
        </div>

        {/* Description Body */}
        <div className="space-y-1.5">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider">О событии</h3>
          <p className={`text-xs text-gray-300 leading-relaxed ${isDescExpanded ? '' : 'line-clamp-3'}`}>
            Уникальный акустический вечер джаза и неоклассических композиций в окружении тропических растений 
            исторической оранжереи. Камерная сцена, мягкий свет винтажных ламп и виртуозное исполнение лучших 
            солистов московской сцены. В программе: Gershwin, Einaudi, Richter, а также авторские импровизации.
          </p>
          <button
            type="button"
            onClick={() => setIsDescExpanded(!isDescExpanded)}
            className="text-xs text-white/60 hover:text-white font-medium flex items-center gap-1 pt-0.5"
          >
            <span>{isDescExpanded ? 'Свернуть' : 'Развернуть полностью'}</span>
          </button>
        </div>
      </div>

      {/* 3. Sticky Bottom Action Dock (Obsidian Liquid Glass) */}
      <div className="p-3 bg-[#0B0D13]/95 backdrop-blur-xl border-t border-white/10 shrink-0 flex flex-col gap-2">
        {/* Primary CTA: «Я иду» (RSVP) */}
        <button
          type="button"
          onClick={handleToggleRsvp}
          className={`w-full h-12 rounded-2xl font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 transition-all duration-300 ${
            isAttending
              ? 'bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 shadow-[0_0_20px_rgba(16,185,129,0.25)]'
              : 'bg-white text-black hover:bg-neutral-200 shadow-xl'
          }`}
        >
          {isAttending ? (
            <>
              <Check size={18} className="text-emerald-400 stroke-[2.5]" />
              <span>Вы идёте • Нажмите для отмены</span>
            </>
          ) : (
            <>
              <Sparkles size={16} />
              <span>Я иду на это событие</span>
            </>
          )}
        </button>

        {/* Secondary Action: «Хочу пойти» (Interest) */}
        <button
          type="button"
          onClick={handleToggleInterest}
          className={`w-full h-10 rounded-xl font-semibold text-xs flex items-center justify-center gap-2 border transition-all ${
            isInterested
              ? 'bg-pink-500/20 border-pink-500/40 text-pink-300 shadow-sm'
              : 'bg-white/5 border-white/10 text-gray-300 hover:text-white hover:bg-white/10'
          }`}
        >
          <Heart size={15} className={isInterested ? 'fill-pink-400 text-pink-400 scale-110' : 'text-gray-400'} />
          <span>{isInterested ? 'В списке желаний' : 'Хочу пойти'}</span>
          <span className="px-1.5 py-0.5 rounded-full bg-white/10 text-[10px] text-gray-300">
            {interestCount}
          </span>
        </button>
      </div>
    </div>
  );
};
