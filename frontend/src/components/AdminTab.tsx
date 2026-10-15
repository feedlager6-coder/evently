import React, { useState, useEffect } from 'react';
import type { EventSummary, EventStatus, AdminOrganizationItem } from '../types';
import { api } from '../services/api';
import { telegram } from '../services/telegram';
import {
  Check,
  X,
  Ban,
  Calendar,
  MapPin,
  Loader2,
  AlertCircle,
  Compass,
  Building2,
  Sparkles,
  RefreshCw,
  Search,
  Clock,
  Eye,
  ShieldCheck,
  Globe,
} from 'lucide-react';
import { SafeImage } from './SafeImage';

interface AdminTabProps {
  events: EventSummary[];
  isLoading: boolean;
  activeStatus: EventStatus;
  onStatusChange: (status: EventStatus) => void;
  onRefresh: () => void;
  onEventClick: (event: EventSummary) => void;
}

type AdminSection = 'events' | 'organizations';

export const AdminTab: React.FC<AdminTabProps> = ({
  events,
  isLoading,
  activeStatus,
  onStatusChange,
  onRefresh,
  onEventClick,
}) => {
  const [adminSection, setAdminSection] = useState<AdminSection>('events');

  // Event Moderation state
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('Несоответствие правилам публикации событий');
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // External Events Sync state
  const [isSyncingExternal, setIsSyncingExternal] = useState(false);

  const handleSyncExternalEvents = async () => {
    try {
      setIsSyncingExternal(true);
      setError(null);
      telegram.hapticImpact('medium');
      const res = await api.adminSyncExternalEvents();
      telegram.hapticSuccess();
      await telegram.showAlert(
        `Синхронизация завершена!\nСоздано новых событий: ${res.created}\nОбновлено существующих: ${res.updated}\nОшибок: ${res.errors.length}`
      );
      onRefresh();
    } catch (err: any) {
      telegram.hapticNotification('error');
      setError(err.message || 'Ошибка синхронизации внешних событий');
    } finally {
      setIsSyncingExternal(false);
    }
  };

  // Organizations & Pro testing state
  const [organizations, setOrganizations] = useState<AdminOrganizationItem[]>([]);
  const [isLoadingOrgs, setIsLoadingOrgs] = useState(false);
  const [orgSearchQuery, setOrgSearchQuery] = useState('');
  const [togglingOrgId, setTogglingOrgId] = useState<string | null>(null);

  const loadOrganizations = async () => {
    try {
      setIsLoadingOrgs(true);
      setError(null);
      const data = await api.adminGetOrganizations();
      setOrganizations(data);
    } catch (err: any) {
      setError(err.message || 'Ошибка загрузки организаций');
    } finally {
      setIsLoadingOrgs(false);
    }
  };

  useEffect(() => {
    if (adminSection === 'organizations') {
      loadOrganizations();
    }
  }, [adminSection]);

  const handleToggleOrgPlan = async (org: AdminOrganizationItem) => {
    const newPlan = org.plan === 'pro' ? 'free' : 'pro';
    try {
      setTogglingOrgId(org.id);
      setError(null);
      telegram.hapticImpact('medium');
      await api.adminSetOrganizationPlan(org.id, newPlan);
      telegram.hapticSuccess();
      setOrganizations((prev) =>
        prev.map((o) => (o.id === org.id ? { ...o, plan: newPlan, plan_status: 'active' } : o))
      );
    } catch (err: any) {
      setError(err.message || 'Ошибка изменения тарифа');
    } finally {
      setTogglingOrgId(null);
    }
  };

  const handlePublish = async (e: React.MouseEvent, eventId: string) => {
    e.stopPropagation();
    try {
      setActionLoadingId(eventId);
      setError(null);
      await api.adminPublishEvent(eventId);
      telegram.hapticSuccess();
      onRefresh();
    } catch (err: any) {
      setError(err.message || 'Ошибка публикации события');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleConfirmReject = async (e: React.FormEvent, eventId: string) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      setActionLoadingId(eventId);
      setError(null);
      await api.adminRejectEvent(eventId, rejectReason);
      telegram.hapticSuccess();
      setRejectingId(null);
      onRefresh();
    } catch (err: any) {
      setError(err.message || 'Ошибка отклонения события');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleCancel = async (e: React.MouseEvent, eventId: string) => {
    e.stopPropagation();
    if (!confirm('Вы уверены, что хотите снять событие с публикации?')) return;
    try {
      setActionLoadingId(eventId);
      setError(null);
      await api.adminCancelEvent(eventId);
      telegram.hapticImpact('medium');
      onRefresh();
    } catch (err: any) {
      setError(err.message || 'Ошибка отмены публикации');
    } finally {
      setActionLoadingId(null);
    }
  };

  const filteredOrgs = organizations.filter((org) => {
    if (!orgSearchQuery.trim()) return true;
    const q = orgSearchQuery.toLowerCase();
    return (
      org.name.toLowerCase().includes(q) ||
      org.slug.toLowerCase().includes(q) ||
      org.category.toLowerCase().includes(q) ||
      org.city_id.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-4 px-4 py-2 pb-24 max-w-lg mx-auto">
      {/* Top Bar matching Stitch Obsidian Optical */}
      <div className="sticky top-0 z-20 bg-[#0e0e10]/85 backdrop-blur-xl border-b border-white/5 -mx-4 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#4edea3] animate-pulse" />
            <div>
              <div className="flex items-center gap-1.5">
                <h1 className="text-sm font-bold text-white tracking-tight">Панель администратора</h1>
                <span className="px-1.5 py-0.5 rounded-full bg-[#00a572]/20 border border-[#4edea3]/30 text-[#4edea3] text-[9.5px] font-bold tracking-wider leading-none">
                  ADMIN
                </span>
              </div>
              <p className="text-[11px] text-[#c4c7c8]">Модерация событий и управление тарифами</p>
            </div>
          </div>
          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onRefresh();
            }}
            disabled={isLoading}
            className="w-9 h-9 rounded-full bg-[#1c1b1e] border border-white/10 flex items-center justify-center text-gray-300 hover:text-white active:scale-95 transition-all btn-press shadow-sm"
            title="Обновить данные"
            aria-label="Обновить"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-[#4edea3]' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-300 flex items-center space-x-2 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Municipal / External Events Ingestion Trigger */}
      <button
        type="button"
        disabled={isSyncingExternal}
        onClick={handleSyncExternalEvents}
        className="w-full py-2.5 px-4 rounded-2xl bg-[#1c1b1e] hover:bg-[#252428] border border-emerald-500/30 text-emerald-400 flex items-center justify-between transition-all active:scale-[0.98] shadow-sm disabled:opacity-50"
      >
        <div className="flex items-center gap-2">
          <Globe className={`w-4 h-4 ${isSyncingExternal ? 'animate-spin' : ''}`} />
          <span className="text-xs font-bold text-white">
            {isSyncingExternal ? 'Синхронизация открытых событий...' : 'Синхронизировать внешние события'}
          </span>
        </div>
        <span className="text-[10px] text-emerald-400 font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
          KudaGo & Open API
        </span>
      </button>

      {/* Primary Segmented Switcher (Optical Glass Pill Tabs matching Stitch) */}
      <div className="p-1 rounded-2xl bg-[#1c1b1e] border border-white/10 flex items-center gap-1 shadow-inner text-xs">
        <button
          onClick={() => {
            telegram.hapticSelection();
            setAdminSection('events');
          }}
          className={`flex-1 h-9 rounded-xl flex items-center justify-center gap-1.5 transition-all pill-press font-semibold ${
            adminSection === 'events'
              ? 'bg-white !text-[#131315] font-bold shadow-md'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          <ShieldCheck className="w-4 h-4 text-[#4edea3]" />
          <span>Модерация событий</span>
        </button>
        <button
          onClick={() => {
            telegram.hapticSelection();
            setAdminSection('organizations');
          }}
          className={`flex-1 h-9 rounded-xl flex items-center justify-center gap-1.5 transition-all pill-press font-semibold ${
            adminSection === 'organizations'
              ? 'bg-white !text-[#131315] font-bold shadow-md'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          <Building2 className="w-4 h-4 text-[#ffb95f]" />
          <span>Организации и Pro</span>
        </button>
      </div>

      {/* SECTION 1: EVENTS MODERATION */}
      {adminSection === 'events' && (
        <div className="space-y-3.5">
          {/* Status Filter Pills */}
          <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-0.5">
            <button
              onClick={() => {
                telegram.hapticSelection();
                onStatusChange('pending');
              }}
              className={`shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold flex items-center gap-1.5 transition-all ${
                activeStatus === 'pending'
                  ? 'bg-white !text-[#131315] font-bold shadow-sm'
                  : 'bg-[#1c1b1e] text-gray-400 border border-white/5 hover:text-white'
              }`}
            >
              <span>На проверке</span>
              <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                activeStatus === 'pending' ? 'bg-[#131315] text-[#ffb95f]' : 'bg-white/10 text-gray-300'
              }`}>
                {events.filter((e) => e.status === 'pending').length || (activeStatus === 'pending' ? events.length : 0)}
              </span>
            </button>

            <button
              onClick={() => {
                telegram.hapticSelection();
                onStatusChange('published');
              }}
              className={`shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold flex items-center gap-1.5 transition-all ${
                activeStatus === 'published'
                  ? 'bg-white !text-[#131315] font-bold shadow-sm'
                  : 'bg-[#1c1b1e] text-gray-400 border border-white/5 hover:text-white'
              }`}
            >
              <span>Опубликованные</span>
            </button>

            <button
              onClick={() => {
                telegram.hapticSelection();
                onStatusChange('rejected');
              }}
              className={`shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold flex items-center gap-1.5 transition-all ${
                activeStatus === 'rejected'
                  ? 'bg-white !text-[#131315] font-bold shadow-sm'
                  : 'bg-[#1c1b1e] text-gray-400 border border-white/5 hover:text-white'
              }`}
            >
              <span>Отклонённые</span>
            </button>
          </div>

          {/* Quick Metrics Moderation Queue Bar matching Stitch */}
          <div className="rounded-xl bg-[#0e0e10]/80 border border-white/5 px-3 py-2 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#ffb95f]" />
              <span className="text-gray-300 font-medium">{events.length} в очереди</span>
            </div>
            <div className="flex items-center gap-1 text-gray-400 text-[11px]">
              <Clock className="w-3.5 h-3.5 text-gray-500" />
              <span>Ср. ответ ~18 мин</span>
            </div>
          </div>

          {/* Queue items */}
          <div className="space-y-3">
            {isLoading ? (
              <div className="py-12 text-center text-xs text-gray-400 flex items-center justify-center space-x-2">
                <Loader2 className="w-4 h-4 animate-spin text-[#4edea3]" />
                <span>Загрузка очереди...</span>
              </div>
            ) : events.length === 0 ? (
              <div className="py-12 px-4 text-center rounded-2xl bg-[#1c1b1e] border border-white/5 space-y-2.5">
                <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center mx-auto text-[#4edea3]">
                  <Compass className="w-5 h-5" />
                </div>
                <p className="text-xs text-gray-400">В этой категории нет событий</p>
              </div>
            ) : (
              events.map((ev) => {
                const isActing = actionLoadingId === ev.id;
                const isRejecting = rejectingId === ev.id;
                const dateObj = new Date(ev.start_at);
                const dayMonthStr = dateObj.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }).toUpperCase();
                const timeStr = dateObj.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

                return (
                  <article
                    key={ev.id}
                    onClick={() => onEventClick(ev)}
                    className="p-4 rounded-2xl bg-[#121215] border border-white/10 hover:border-white/20 transition-all space-y-3 cursor-pointer shadow-md card-press"
                  >
                    {/* Organizer Header & Status Badge */}
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="w-8 h-8 rounded-full bg-[#2a2a2c] border border-white/10 flex items-center justify-center font-bold text-white text-[11px] shrink-0">
                          {ev.organization_name ? ev.organization_name.slice(0, 2).toUpperCase() : 'ЛП'}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1">
                            <span className="text-xs font-bold text-white truncate">
                              {ev.organization_name || 'Личный профиль'}
                            </span>
                            <ShieldCheck className="w-3.5 h-3.5 text-[#4edea3] shrink-0" />
                          </div>
                          <span className="text-[10px] text-gray-400 block truncate">
                            {ev.city_name} · {ev.category_name}
                          </span>
                        </div>
                      </div>

                      {/* Status Badge */}
                      {ev.status === 'pending' && (
                        <span className="px-2.5 py-1 rounded-full bg-[#ffb95f]/10 border border-[#ffb95f]/30 text-[#ffb95f] text-[11px] font-semibold flex items-center gap-1 shrink-0">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#ffb95f] animate-pulse" />
                          <span>На проверке</span>
                        </span>
                      )}
                      {ev.status === 'published' && (
                        <span className="px-2.5 py-1 rounded-full bg-[#00a572]/15 border border-[#4edea3]/30 text-[#4edea3] text-[11px] font-semibold flex items-center gap-1 shrink-0">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#4edea3]" />
                          <span>Опубликовано</span>
                        </span>
                      )}
                      {ev.status === 'rejected' && (
                        <span className="px-2.5 py-1 rounded-full bg-red-500/10 border border-red-500/30 text-red-400 text-[11px] font-semibold flex items-center gap-1 shrink-0">
                          <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                          <span>Отклонено</span>
                        </span>
                      )}
                    </div>

                    {/* Hero Thumbnail & Details Split matching Stitch */}
                    <div className="flex gap-3 items-start">
                      <div className="w-20 h-20 rounded-xl overflow-hidden shrink-0 border border-white/10 relative bg-[#1c1b1e]">
                        <SafeImage
                          src={ev.cover_image_url}
                          alt={ev.title}
                          className="w-full h-full object-cover"
                        />
                        <div className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-black/75 backdrop-blur-md text-[9px] text-white font-bold">
                          {dayMonthStr}
                        </div>
                      </div>
                      <div className="flex-1 min-w-0 flex flex-col gap-1">
                        <span className="px-2 py-0.5 rounded-full bg-[#201f22] text-[#c4c7c8] text-[10px] font-medium self-start border border-white/5">
                          {ev.category_name}
                        </span>
                        <h4 className="text-sm font-bold text-white truncate leading-snug">{ev.title}</h4>
                        <div className="flex flex-col gap-0.5 text-[11px] text-gray-400">
                          <div className="flex items-center gap-1 truncate">
                            <Calendar className="w-3 h-3 text-gray-500" />
                            <span>{dayMonthStr}, {timeStr}</span>
                            <span className="text-gray-600">•</span>
                            <span>{ev.is_free ? 'Бесплатно' : `${ev.price_amount || 0} ₽`}</span>
                          </div>
                          <div className="flex items-center gap-1 truncate">
                            <MapPin className="w-3 h-3 text-gray-500" />
                            <span className="truncate">{ev.venue_name}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Description Snippet Quote */}
                    {ev.description && (
                      <p className="text-[11px] text-gray-300 bg-[#0e0e10]/80 rounded-xl p-2.5 border border-white/5 line-clamp-2 leading-relaxed">
                        «{ev.description}»
                      </p>
                    )}

                    {/* Reject Input Dialog */}
                    {isRejecting ? (
                      <form
                        onSubmit={(e) => handleConfirmReject(e, ev.id)}
                        onClick={(e) => e.stopPropagation()}
                        className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 space-y-2 text-xs"
                      >
                        <label className="font-semibold text-red-300">Причина отклонения:</label>
                        <input
                          type="text"
                          value={rejectReason}
                          onChange={(e) => setRejectReason(e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded-lg bg-[#201f22] border border-white/10 text-white focus:outline-none focus:border-red-400"
                          required
                        />
                        <div className="flex space-x-2">
                          <button
                            type="submit"
                            disabled={isActing}
                            className="px-3.5 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white font-semibold text-xs btn-press"
                          >
                            Подтвердить отказ
                          </button>
                          <button
                            type="button"
                            onClick={() => setRejectingId(null)}
                            className="px-3 py-1.5 rounded-lg bg-white/10 text-gray-300 hover:text-white text-xs btn-press"
                          >
                            Отмена
                          </button>
                        </div>
                      </form>
                    ) : (
                      /* Moderation Action Buttons matching Stitch */
                      <div className="pt-2 border-t border-white/5 flex items-center gap-2">
                        {ev.status === 'pending' && (
                          <>
                            <button
                              onClick={(e) => handlePublish(e, ev.id)}
                              disabled={isActing}
                              className="flex-1 h-9 rounded-full bg-[#00a572] hover:bg-[#4edea3] text-[#002113] font-bold text-xs flex items-center justify-center gap-1.5 active:scale-95 transition-all shadow-md btn-press disabled:opacity-50"
                            >
                              {isActing ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin text-[#002113]" />
                              ) : (
                                <>
                                  <Check className="w-3.5 h-3.5 stroke-[2.5]" />
                                  <span>Опубликовать</span>
                                </>
                              )}
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setRejectingId(ev.id);
                              }}
                              disabled={isActing}
                              className="h-9 px-3.5 rounded-full bg-transparent border border-red-500/40 text-red-400 font-semibold text-xs flex items-center justify-center gap-1 hover:bg-red-500/20 active:scale-95 transition-all btn-press"
                            >
                              <X className="w-3.5 h-3.5" />
                              <span>Отклонить</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => onEventClick(ev)}
                              className="w-9 h-9 rounded-full bg-[#1c1b1e] border border-white/10 flex items-center justify-center text-gray-300 hover:text-white active:scale-95 transition-all btn-press shrink-0"
                              title="Предпросмотр"
                              aria-label="Предпросмотр карточки"
                            >
                              <Eye className="w-4 h-4" />
                            </button>
                          </>
                        )}

                        {ev.status === 'published' && (
                          <div className="w-full flex items-center justify-between">
                            <button
                              onClick={(e) => handleCancel(e, ev.id)}
                              disabled={isActing}
                              className="flex items-center space-x-1 px-3.5 py-1.5 rounded-full bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white text-xs border border-white/5 transition-colors btn-press"
                            >
                              <Ban className="w-3.5 h-3.5" />
                              <span>Снять с публикации</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => onEventClick(ev)}
                              className="w-9 h-9 rounded-full bg-[#1c1b1e] border border-white/10 flex items-center justify-center text-gray-300 hover:text-white active:scale-95 transition-all btn-press shrink-0"
                              title="Открыть карточку"
                              aria-label="Открыть карточку"
                            >
                              <Eye className="w-4 h-4" />
                            </button>
                          </div>
                        )}

                        {ev.status === 'rejected' && (
                          <div className="w-full flex items-center justify-between">
                            <span className="text-[11px] text-red-400 truncate">
                              Причина: {ev.rejection_reason || 'Не указана'}
                            </span>
                            <button
                              type="button"
                              onClick={() => onEventClick(ev)}
                              className="w-9 h-9 rounded-full bg-[#1c1b1e] border border-white/10 flex items-center justify-center text-gray-300 hover:text-white active:scale-95 transition-all btn-press shrink-0"
                              title="Открыть карточку"
                              aria-label="Открыть карточку"
                            >
                              <Eye className="w-4 h-4" />
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </article>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* SECTION 2: ORGANIZATIONS & PRO TESTING */}
      {adminSection === 'organizations' && (
        <div className="space-y-3.5">
          <div className="p-3.5 rounded-2xl bg-[#ffb95f]/10 border border-[#ffb95f]/25 text-xs space-y-1.5">
            <div className="flex items-center space-x-1.5 text-[#ffb95f] font-semibold">
              <Sparkles className="w-4 h-4 text-[#ffb95f] shrink-0" />
              <span>Тестирование Pro-тарифов</span>
            </div>
            <p className="text-[11px] text-gray-300 leading-snug">
              Тариф Pro привязан к <strong>организации</strong>, а не к роли администратора. Здесь можно переключать тариф любой организации для проверки прав рассылок.
            </p>
          </div>

          {/* Search & Refresh */}
          <div className="flex items-center space-x-2">
            <div className="flex-1 relative">
              <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={orgSearchQuery}
                onChange={(e) => setOrgSearchQuery(e.target.value)}
                placeholder="Поиск по названию или категории..."
                className="w-full pl-8 pr-3 py-2 rounded-xl bg-[#201f22] border border-white/10 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-white/30"
              />
            </div>
            <button
              onClick={loadOrganizations}
              disabled={isLoadingOrgs}
              className="p-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 transition-all btn-press shrink-0"
              title="Обновить"
            >
              <RefreshCw className={`w-4 h-4 ${isLoadingOrgs ? 'animate-spin text-[#4edea3]' : ''}`} />
            </button>
          </div>

          {/* Organizations List */}
          <div className="space-y-2.5">
            {isLoadingOrgs ? (
              <div className="py-12 text-center text-xs text-gray-400 flex items-center justify-center space-x-2">
                <Loader2 className="w-4 h-4 animate-spin text-[#4edea3]" />
                <span>Загрузка организаций...</span>
              </div>
            ) : filteredOrgs.length === 0 ? (
              <div className="py-12 px-4 text-center rounded-2xl bg-[#1c1b1e] border border-white/5 space-y-2">
                <Building2 className="w-8 h-8 text-gray-500 mx-auto" />
                <p className="text-xs text-gray-400">
                  {orgSearchQuery.trim() ? 'Организации не найдены по запросу' : 'Список организаций пуст'}
                </p>
              </div>
            ) : (
              filteredOrgs.map((org) => {
                const isPro = org.plan === 'pro';
                const isToggling = togglingOrgId === org.id;

                return (
                  <div
                    key={org.id}
                    className="p-3.5 rounded-2xl bg-[#1c1b1e] border border-white/8 hover:border-white/15 transition-all space-y-2.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center space-x-2">
                          <h4 className="font-bold text-sm text-white truncate">{org.name}</h4>
                          <span
                            className={`text-[9.5px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider shrink-0 ${
                              isPro
                                ? 'bg-[#ffb95f]/15 text-[#ffb95f] border border-[#ffb95f]/30'
                                : 'bg-white/10 text-gray-400'
                            }`}
                          >
                            {isPro ? 'Pro' : 'Free'}
                          </span>
                        </div>
                        <p className="text-[11px] text-gray-400 mt-0.5 truncate">
                          {org.category} · {org.city_id} · Владелец ID: {org.owner_user_id}
                        </p>
                      </div>

                      <button
                        onClick={() => handleToggleOrgPlan(org)}
                        disabled={isToggling}
                        className={`px-3 py-1.5 rounded-xl font-semibold text-xs transition-all btn-press shrink-0 flex items-center space-x-1.5 ${
                          isPro
                            ? 'bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10'
                            : 'bg-white !text-[#131315] font-bold active:scale-95 shadow-md hover:bg-zinc-200'
                        }`}
                      >
                        {isToggling ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin !text-[#131315]" />
                        ) : isPro ? (
                          <span>Вернуть Free</span>
                        ) : (
                          <>
                            <Sparkles className="w-3.5 h-3.5 !text-[#131315]" />
                            <span className="!text-[#131315]">Включить Pro</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
