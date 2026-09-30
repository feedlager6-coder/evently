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
  ChevronRight,
  Heart
} from 'lucide-react';
import { formatFollowers } from './OrganizationModal';
import { GoingAnimation } from './GoingAnimation';
import type { GoingAnimationState } from './GoingAnimation';
import { AnimatedCounter } from './AnimatedCounter';
import { SafeImage } from './SafeImage';
import { SafeAvatar } from './SafeAvatar';

export function getAttendeesWord(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod100 >= 11 && mod100 <= 19) return 'человек идут';
  if (mod10 === 1) return 'человек идёт';
  if (mod10 >= 2 && mod10 <= 4) return 'человека идут';
  return 'человек идут';
}

export function getInterestedWord(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod100 >= 11 && mod100 <= 19) return 'хотят пойти';
  if (mod10 === 1) return 'хочет пойти';
  if (mod10 >= 2 && mod10 <= 4) return 'хотят пойти';
  return 'хотят пойти';
}

interface EventDetailsModalProps {
  event: EventResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onToggleRsvp: (eventId: string, currentStatus: boolean) => Promise<void>;
  isRsvpLoading: boolean;
  onToggleInterest?: (eventId: string, currentStatus: boolean) => Promise<void>;
  isInterestLoading?: boolean;
  onOpenOrgModal?: (orgId: string) => void;
}

export const EventDetailsModal: React.FC<EventDetailsModalProps> = ({
  event,
  isOpen,
  onClose,
  onToggleRsvp,
  isRsvpLoading,
  onToggleInterest,
  isInterestLoading = false,
  onOpenOrgModal,
}) => {
  const [copied, setCopied] = useState(false);
  const [shareToast, setShareToast] = useState<string | null>(null);
  const [rsvpAnimationPhase, setRsvpAnimationPhase] = useState<GoingAnimationState>('idle');

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
    const shareText = `🧭 ${event.title}\n📅 ${formattedFullDate}\n📍 ${event.venue_name}${event.city_name ? ` (${event.city_name})` : ''}\n\nСмотрите в Ivently:`;

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

    if (event.is_attending) {
      // Canceling attendance
      telegram.hapticImpact('light');
      setRsvpAnimationPhase('loading');
      try {
        await onToggleRsvp(event.id, true);
        setRsvpAnimationPhase('idle');
      } catch {
        setRsvpAnimationPhase('idle');
      }
    } else {
      // Joining event: Flagship RSVP Sequence
      telegram.hapticImpact('medium');
      setRsvpAnimationPhase('loading');
      try {
        await onToggleRsvp(event.id, false);
        // On successful HTTP confirmation, trigger the stride animation
        setRsvpAnimationPhase('animating');
        telegram.hapticSuccess();
      } catch {
        setRsvpAnimationPhase('idle');
        telegram.hapticError();
      }
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex flex-col justify-end sm:justify-center items-center bg-black/80 backdrop-fade-in p-0 sm:p-4">
      {/* Bottom Sheet Modal Container with physics slide up */}
      <div 
        className="w-full max-w-lg bg-[#0F121C] sm:rounded-3xl rounded-t-[28px] border border-white/10 overflow-hidden shadow-2xl flex flex-col max-h-[92vh] sheet-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Media / Hero */}
        <div className="relative aspect-[16/9] w-full bg-gray-900 shrink-0">
          <SafeImage
            src={event.cover_image_url}
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
            <div className="absolute top-16 left-1/2 -translate-x-1/2 z-[70] px-4 py-2 rounded-full bg-emerald-600/95 text-white text-xs font-semibold shadow-2xl backdrop-blur-md animate-fade-in flex items-center space-x-1.5 pointer-events-none">
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
          {event.organization_id ? (
            <div
              onClick={() => onOpenOrgModal?.(event.organization_id!)}
              className="flex items-center justify-between p-3.5 rounded-2xl bg-[#171B29] border border-white/5 hover:border-indigo-500/30 transition-all cursor-pointer group"
            >
              <div className="flex items-center space-x-3 min-w-0">
                <div className="w-10 h-10 rounded-xl overflow-hidden border border-indigo-500/30 flex items-center justify-center shrink-0">
                  <SafeAvatar
                    src={event.organization_avatar_url}
                    name={event.organization_name || 'Организация'}
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="min-w-0">
                  <div className="text-[11px] text-gray-400 font-medium">Организация</div>
                  <div className="text-xs font-bold text-white group-hover:text-indigo-300 transition-colors truncate">
                    {event.organization_name || 'Организатор'}
                  </div>
                  <div className="flex items-center space-x-1.5 text-[11px] text-gray-400">
                    {event.organization_category && <span>{event.organization_category}</span>}
                    {event.organization_followers_count !== undefined && (
                      <>
                        <span>•</span>
                        <span className="text-indigo-400 font-medium">
                          {formatFollowers(event.organization_followers_count)}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center space-x-1 text-xs text-indigo-400 font-medium pl-2 shrink-0">
                <span>Профиль</span>
                <ChevronRight className="w-4 h-4 text-indigo-400 group-hover:translate-x-0.5 transition-transform" />
              </div>
            </div>
          ) : event.organizer_name ? (
            <div className="flex items-center space-x-3 p-3 rounded-2xl bg-[#171B29]/60 border border-white/5">
              <div className="w-8 h-8 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center shrink-0">
                <UserIcon className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <div className="text-gray-400">Организатор</div>
                <div className="font-medium text-white">@{event.organizer_name}</div>
              </div>
            </div>
          ) : null}

          {/* Description */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-white">О мероприятии</h4>
            <p className="text-xs leading-relaxed text-gray-300 whitespace-pre-line">
              {event.description}
            </p>
          </div>

          {/* Attendees & Interested Summary */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-gray-400 py-1">
            <div className="flex items-center space-x-1.5">
              <Users className="w-4 h-4 text-indigo-400 shrink-0" />
              <span>
                Уже идут:{' '}
                <strong className="text-white font-semibold">
                  <AnimatedCounter
                    value={event.attendee_count}
                    suffix={getAttendeesWord(event.attendee_count)}
                  />
                </strong>
              </span>
            </div>
            {event.interest_count > 0 && (
              <div className="flex items-center space-x-1.5 text-purple-300">
                <Heart className="w-3.5 h-3.5 fill-purple-500/20 text-purple-400 shrink-0" />
                <span>
                  <strong className="text-white font-semibold">{event.interest_count}</strong> {getInterestedWord(event.interest_count)}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Sticky Bottom Action Bar */}
        <div className="modal-safe-bottom bg-[#131722] border-t border-white/8 shrink-0 px-4 py-3 space-y-2">
          {/* Primary CTA: «Я иду» */}
          <button
            onClick={handleRsvpClick}
            disabled={isRsvpLoading || isInterestLoading}
            title={event.is_attending ? 'Нажмите, чтобы отменить участие' : 'Подтвердить участие'}
            className={`w-full h-12 px-6 rounded-2xl font-semibold text-sm flex items-center justify-center space-x-2 transition-all duration-200 btn-press ${
              event.is_attending || rsvpAnimationPhase === 'animating'
                ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/25 shadow-sm'
                : 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white shadow-indigo-600/25 shadow-lg'
            } disabled:opacity-70`}
          >
            <GoingAnimation
              state={
                rsvpAnimationPhase === 'animating'
                  ? 'animating'
                  : isRsvpLoading
                  ? 'loading'
                  : event.is_attending
                  ? 'success'
                  : 'idle'
              }
              onAnimationEnd={() => setRsvpAnimationPhase('idle')}
              size={18}
            />
            <span>
              {isRsvpLoading && rsvpAnimationPhase === 'loading'
                ? 'Обновление...'
                : 'Я иду'}
            </span>
          </button>

          {/* Secondary Action: «Хочу пойти» */}
          {onToggleInterest && (
            <button
              onClick={() => {
                if (isInterestLoading || isRsvpLoading) return;
                telegram.hapticImpact('light');
                onToggleInterest(event.id, Boolean(event.current_user_interested));
              }}
              disabled={isInterestLoading || isRsvpLoading}
              title={event.current_user_interested ? 'Нажмите, чтобы отменить интерес' : 'Хочу пойти'}
              className={`w-full py-2.5 px-4 rounded-xl text-xs font-semibold flex items-center justify-center space-x-2 transition-all duration-200 btn-press ${
                event.current_user_interested
                  ? 'bg-purple-500/15 border border-purple-500/35 text-purple-200 hover:bg-purple-500/25'
                  : 'bg-[#181C2B] border border-white/8 text-gray-300 hover:text-white hover:border-white/20'
              } disabled:opacity-60`}
            >
              <Heart
                className={`w-3.5 h-3.5 transition-transform duration-200 ${
                  event.current_user_interested
                    ? 'fill-purple-400 text-purple-400 scale-110'
                    : 'text-gray-400'
                }`}
              />
              <span>
                {isInterestLoading
                  ? 'Обновление...'
                  : 'Хочу пойти'}
              </span>
              {event.interest_count > 0 && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ml-1 ${
                  event.current_user_interested
                    ? 'bg-purple-500/25 text-purple-200'
                    : 'bg-white/10 text-gray-400'
                }`}>
                  {event.interest_count}
                </span>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
