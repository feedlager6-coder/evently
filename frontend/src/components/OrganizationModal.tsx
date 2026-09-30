import React, { useState, useEffect, useCallback } from 'react';
import type { OrganizationResponse, EventSummary } from '../types';
import { api } from '../services/api';
import { telegram } from '../services/telegram';
import {
  X,
  MapPin,
  Globe,
  Share2,
  Check,
  Plus,
  Edit3,
  Calendar,
  Users,
  ShieldCheck,
  Loader2,
  AlertCircle,
  ExternalLink
} from 'lucide-react';
import { AnimatedCounter } from './AnimatedCounter';
import { SafeAvatar } from './SafeAvatar';
import { SafeImage } from './SafeImage';

interface OrganizationModalProps {
  orgIdOrSlug: string | null;
  isOpen: boolean;
  onClose: () => void;
  onEventClick: (event: EventSummary) => void;
  onOpenCreateEvent?: (orgId: string) => void;
  onEditOrg?: (org: OrganizationResponse) => void;
  onSubscriptionChanged?: () => void;
}

export function getFollowersWord(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod100 >= 11 && mod100 <= 19) {
    return 'подписчиков';
  }
  if (mod10 === 1) {
    return 'подписчик';
  }
  if (mod10 >= 2 && mod10 <= 4) {
    return 'подписчика';
  }
  return 'подписчиков';
}

export function formatFollowers(count: number): string {
  return `${count} ${getFollowersWord(count)}`;
}

export const OrganizationModal: React.FC<OrganizationModalProps> = ({
  orgIdOrSlug,
  isOpen,
  onClose,
  onEventClick,
  onOpenCreateEvent,
  onEditOrg,
  onSubscriptionChanged,
}) => {
  const [org, setOrg] = useState<OrganizationResponse | null>(null);
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const loadData = useCallback(async () => {
    if (!orgIdOrSlug) return;
    try {
      setIsLoading(true);
      setError(null);
      const orgData = await api.getOrganization(orgIdOrSlug);
      setOrg(orgData);

      const eventsData = await api.getOrganizationEvents(orgData.id);
      setEvents(eventsData);
    } catch (err: any) {
      console.error('Failed to load organization:', err);
      setError(err.message || 'Не удалось загрузить данные организации');
    } finally {
      setIsLoading(false);
    }
  }, [orgIdOrSlug]);

  useEffect(() => {
    if (isOpen && orgIdOrSlug) {
      loadData();
    } else {
      setOrg(null);
      setEvents([]);
      setError(null);
    }
  }, [isOpen, orgIdOrSlug, loadData]);

  if (!isOpen) return null;

  const handleToggleSubscribe = async () => {
    if (!org || isSubscribing || org.is_owner) return;
    try {
      setIsSubscribing(true);
      telegram.hapticImpact('medium');

      if (org.is_subscribed) {
        const res = await api.unsubscribeOrganization(org.id);
        setOrg((prev) => prev ? {
          ...prev,
          is_subscribed: res.is_subscribed,
          followers_count: res.followers_count
        } : null);
        telegram.hapticImpact('light');
      } else {
        const res = await api.subscribeOrganization(org.id);
        setOrg((prev) => prev ? {
          ...prev,
          is_subscribed: res.is_subscribed,
          followers_count: res.followers_count
        } : null);
        telegram.hapticSuccess();
      }
      onSubscriptionChanged?.();
    } catch (err: any) {
      telegram.hapticError();
      alert(err.message || 'Ошибка обновления подписки');
    } finally {
      setIsSubscribing(false);
    }
  };

  const handleShare = async () => {
    if (!org) return;
    telegram.hapticImpact('light');
    const botUsername = api.getBotUsername();
    const shareUrl = `https://t.me/${botUsername}/app?startapp=org_${org.id}`;
    const shareText = `🏛️ ${org.name} (${org.category})\nПодписывайтесь на события в Ivently:`;

    let shared = false;
    if (navigator.share) {
      try {
        await navigator.share({
          title: `${org.name} — Ivently`,
          text: shareText,
          url: shareUrl,
        });
        shared = true;
      } catch (err: any) {
        if (err.name === 'AbortError') return;
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
        telegram.hapticSuccess();
        setTimeout(() => setCopied(false), 2500);
      } catch (copyErr) {
        console.warn('Clipboard copy failed:', copyErr);
      }
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex flex-col justify-end sm:justify-center items-center bg-black/80 backdrop-blur-sm backdrop-fade-in p-0 sm:p-4">
      <div
        className="w-full max-w-lg bg-[#0F121C] sm:rounded-3xl rounded-t-[28px] border border-white/10 overflow-hidden shadow-2xl flex flex-col max-h-[92vh] sheet-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Header Actions */}
        <div className="relative p-4 flex items-center justify-between border-b border-white/5 bg-[#141724]/70 backdrop-blur-md shrink-0">
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-white transition-colors btn-press"
          >
            <X className="w-5 h-5" />
          </button>
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Профиль организации
          </div>
          <button
            onClick={handleShare}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 text-white transition-colors text-xs font-medium btn-press"
          >
            <Share2 className="w-3.5 h-3.5" />
            <span>{copied ? 'Скопировано!' : 'Поделиться'}</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 overflow-y-auto space-y-5 no-scrollbar flex-1">
          {isLoading ? (
            <div className="py-20 flex flex-col items-center justify-center space-y-3 text-gray-400">
              <Loader2 className="w-7 h-7 animate-spin text-indigo-500" />
              <span className="text-xs">Загрузка организации...</span>
            </div>
          ) : error ? (
            <div className="p-6 text-center rounded-2xl bg-red-500/10 border border-red-500/20 text-red-300 space-y-2">
              <AlertCircle className="w-6 h-6 mx-auto" />
              <div className="text-sm font-semibold">{error}</div>
              <button
                onClick={loadData}
                className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-500 mt-2 btn-press"
              >
                Повторить попытку
              </button>
            </div>
          ) : org ? (
            <>
              {/* Profile Card */}
              <div className="flex flex-col items-center text-center space-y-3 pt-2">
                <div className="relative">
                  <div className="w-20 h-20 rounded-2xl overflow-hidden border-2 border-indigo-500/30 flex items-center justify-center shadow-xl">
                    <SafeAvatar
                      src={org.avatar_url}
                      name={org.name}
                      alt={org.name}
                      className="w-full h-full object-cover"
                    />
                  </div>
                  {org.is_verified && (
                    <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center shadow">
                      <ShieldCheck className="w-3.5 h-3.5" />
                    </div>
                  )}
                </div>

                <div className="space-y-1">
                  <h2 className="text-xl font-bold text-white tracking-tight flex items-center justify-center space-x-1.5">
                    <span>{org.name}</span>
                  </h2>
                  <div className="flex items-center justify-center space-x-2 text-xs text-gray-400">
                    <span className="px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-indigo-300 font-medium">
                      {org.category}
                    </span>
                    <span>•</span>
                    <AnimatedCounter
                      value={org.followers_count}
                      suffix={getFollowersWord(org.followers_count)}
                      className="text-indigo-400 font-semibold"
                    />
                  </div>
                </div>

                {/* Owner or Subscriber Action */}
                <div className="w-full pt-1">
                  {org.is_owner ? (
                    <div className="grid grid-cols-2 gap-2.5 w-full">
                      <button
                        onClick={() => onEditOrg?.(org)}
                        className="w-full min-h-[44px] py-2.5 px-2.5 rounded-xl bg-white/10 hover:bg-white/15 text-white font-semibold text-xs flex items-center justify-center gap-1.5 transition-colors border border-white/10 btn-press text-center leading-tight"
                      >
                        <Edit3 className="w-3.5 h-3.5 shrink-0" />
                        <span>Редактировать профиль</span>
                      </button>
                      <button
                        onClick={() => onOpenCreateEvent?.(org.id)}
                        className="w-full min-h-[44px] py-2.5 px-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs flex items-center justify-center gap-1.5 transition-colors shadow-md shadow-indigo-600/25 border border-indigo-500/30 btn-press text-center leading-tight"
                      >
                        <Plus className="w-3.5 h-3.5 shrink-0" />
                        <span>Создать событие</span>
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={handleToggleSubscribe}
                      disabled={isSubscribing}
                      className={`w-full py-3 px-6 rounded-2xl font-bold text-xs flex items-center justify-center space-x-2 transition-all duration-300 shadow-lg ${
                        org.is_subscribed
                          ? 'bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/40 shadow-emerald-500/10'
                          : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/30'
                      } btn-press disabled:opacity-75`}
                    >
                      {isSubscribing ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : org.is_subscribed ? (
                        <>
                          <Check className="w-4 h-4 stroke-[2.5]" />
                          <span>✓ Вы подписаны (уведомления включены)</span>
                        </>
                      ) : (
                        <>
                          <Users className="w-4 h-4" />
                          <span>Подписаться на новые события</span>
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>

              {/* Location & Links */}
              <div className="p-3.5 rounded-2xl bg-[#171B29] border border-white/5 space-y-2 text-xs">
                {(org.city_name || org.address) && (
                  <div className="flex items-start space-x-2 text-gray-300">
                    <MapPin className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                    <div>
                      {org.address && <div className="text-white font-medium">{org.address}</div>}
                      {org.city_name && <div className="text-gray-400">{org.city_name}</div>}
                    </div>
                  </div>
                )}

                {org.website && (
                  <a
                    href={org.website}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center space-x-2 text-indigo-400 hover:underline pt-1 border-t border-white/5"
                  >
                    <Globe className="w-4 h-4 shrink-0" />
                    <span className="truncate">{org.website.replace(/^https?:\/\//, '')}</span>
                    <ExternalLink className="w-3 h-3 shrink-0 ml-auto text-gray-500" />
                  </a>
                )}

                {org.social_link && (
                  <a
                    href={org.social_link.startsWith('http') ? org.social_link : `https://${org.social_link}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center space-x-2 text-indigo-400 hover:underline pt-1 border-t border-white/5"
                  >
                    <span className="w-4 h-4 text-center font-bold text-xs shrink-0">@</span>
                    <span className="truncate">Социальные сети / Канал</span>
                    <ExternalLink className="w-3 h-3 shrink-0 ml-auto text-gray-500" />
                  </a>
                )}
              </div>

              {/* Description */}
              {org.description && (
                <div className="space-y-1.5">
                  <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    О нас
                  </h4>
                  <p className="text-xs leading-relaxed text-gray-300 whitespace-pre-line p-3 rounded-2xl bg-[#171B29]/60 border border-white/5">
                    {org.description}
                  </p>
                </div>
              )}

              {/* Upcoming Events */}
              <div className="space-y-3 pt-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    События организации ({events.length})
                  </h4>
                </div>

                {events.length === 0 ? (
                  <div className="p-6 text-center rounded-2xl bg-[#171B29]/40 border border-white/5 space-y-2">
                    <Calendar className="w-6 h-6 text-gray-500 mx-auto" />
                    <div className="text-xs text-gray-400">
                      У организации пока нет предстоящих событий
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {events.map((ev) => {
                      const dateStr = new Date(ev.start_at).toLocaleDateString('ru-RU', {
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      });
                      const priceLabel = ev.is_free
                        ? 'Бесплатно'
                        : `${ev.price_amount} ${ev.price_currency || 'RUB'}`;

                      return (
                        <div
                          key={ev.id}
                          onClick={() => {
                            onClose();
                            onEventClick(ev);
                          }}
                          className="flex items-center space-x-3 p-3 rounded-2xl bg-[#171B29] border border-white/5 hover:border-indigo-500/40 transition-all cursor-pointer card-press"
                        >
                          <div className="w-14 h-14 rounded-xl overflow-hidden bg-gray-900 shrink-0">
                            <SafeImage
                              src={ev.cover_image_url}
                              alt={ev.title}
                              fallbackSrc="https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?w=400"
                              className="w-full h-full object-cover"
                            />
                          </div>
                          <div className="flex-1 min-w-0 space-y-1">
                            <div className="font-semibold text-xs text-white truncate">
                              {ev.title}
                            </div>
                            <div className="flex items-center space-x-2 text-[11px] text-gray-400">
                              <span className="text-indigo-400 font-medium">{dateStr}</span>
                              <span>•</span>
                              <span className="truncate">{ev.venue_name}</span>
                            </div>
                            <div className="text-[11px] font-semibold text-emerald-400">
                              {priceLabel}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
};
