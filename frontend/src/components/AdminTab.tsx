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
} from 'lucide-react';
import { BrandIcon } from './BrandIcon';

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
    <div className="space-y-4 px-4 py-2">
      {/* Admin Header */}
      <div className="p-4 rounded-2xl bg-[#171A29] border border-indigo-500/30 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <BrandIcon className="w-8 h-8" iconClassName="w-4 h-4 text-white" />
          <div>
            <div className="flex items-center space-x-1.5">
              <h3 className="font-bold text-sm text-white">Панель администратора</h3>
              <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                Admin
              </span>
            </div>
            <p className="text-[11px] text-gray-400">Модерация событий и тестирование тарифов</p>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 flex items-center space-x-2 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Admin Section Switcher */}
      <div className="flex bg-[#141724] p-1 rounded-xl border border-white/5 text-xs">
        <button
          onClick={() => {
            telegram.hapticSelection();
            setAdminSection('events');
          }}
          className={`flex-1 py-1.5 font-medium rounded-lg transition-all pill-press flex items-center justify-center space-x-1.5 ${
            adminSection === 'events'
              ? 'bg-indigo-600 text-white shadow'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          <span>Модерация событий</span>
        </button>
        <button
          onClick={() => {
            telegram.hapticSelection();
            setAdminSection('organizations');
          }}
          className={`flex-1 py-1.5 font-medium rounded-lg transition-all pill-press flex items-center justify-center space-x-1.5 ${
            adminSection === 'organizations'
              ? 'bg-indigo-600 text-white shadow'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Организации и Pro</span>
        </button>
      </div>

      {/* SECTION 1: EVENTS MODERATION */}
      {adminSection === 'events' && (
        <div className="space-y-3">
          {/* Status Segmented Control */}
          <div className="flex bg-[#141724] p-1 rounded-xl border border-white/5 text-xs">
            <button
              onClick={() => {
                telegram.hapticSelection();
                onStatusChange('pending');
              }}
              className={`flex-1 py-1.5 font-medium rounded-lg transition-all pill-press ${
                activeStatus === 'pending'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              На проверке
            </button>
            <button
              onClick={() => {
                telegram.hapticSelection();
                onStatusChange('published');
              }}
              className={`flex-1 py-1.5 font-medium rounded-lg transition-all pill-press ${
                activeStatus === 'published'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Опубликованные
            </button>
            <button
              onClick={() => {
                telegram.hapticSelection();
                onStatusChange('rejected');
              }}
              className={`flex-1 py-1.5 font-medium rounded-lg transition-all pill-press ${
                activeStatus === 'rejected'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Отклонённые
            </button>
          </div>

          {/* Queue items */}
          <div className="space-y-3">
            {isLoading ? (
              <div className="py-12 text-center text-xs text-gray-400">Загрузка очереди...</div>
            ) : events.length === 0 ? (
              <div className="py-12 px-4 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-2.5">
                <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center mx-auto text-indigo-400">
                  <Compass className="w-5 h-5" />
                </div>
                <p className="text-xs text-gray-400">В этой категории нет событий</p>
              </div>
            ) : (
              events.map((ev) => {
                const isActing = actionLoadingId === ev.id;
                const isRejecting = rejectingId === ev.id;
                const dateStr = new Date(ev.start_at).toLocaleDateString('ru-RU', {
                  day: 'numeric',
                  month: 'short',
                  hour: '2-digit',
                  minute: '2-digit',
                });

                return (
                  <div
                    key={ev.id}
                    onClick={() => onEventClick(ev)}
                    className="p-4 rounded-2xl bg-[#141724] border border-white/8 hover:border-white/15 transition-all space-y-3 cursor-pointer"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="text-[10px] font-semibold text-indigo-400 uppercase tracking-wider">
                          {ev.category_name} · {ev.city_name}
                        </span>
                        <h4 className="font-bold text-sm text-white leading-tight mt-0.5">{ev.title}</h4>
                      </div>
                    </div>

                    <div className="flex items-center space-x-3 text-xs text-gray-400">
                      <div className="flex items-center space-x-1">
                        <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                        <span>{dateStr}</span>
                      </div>
                      <div className="flex items-center space-x-1 truncate">
                        <MapPin className="w-3.5 h-3.5 text-gray-500" />
                        <span className="truncate">{ev.venue_name}</span>
                      </div>
                    </div>

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
                          className="w-full px-2.5 py-1.5 rounded-lg bg-[#141724] border border-white/10 text-white"
                          required
                        />
                        <div className="flex space-x-2">
                          <button
                            type="submit"
                            disabled={isActing}
                            className="px-3 py-1 rounded-lg bg-red-600 text-white font-semibold btn-press"
                          >
                            Подтвердить отказ
                          </button>
                          <button
                            type="button"
                            onClick={() => setRejectingId(null)}
                            className="px-3 py-1 rounded-lg bg-white/10 text-gray-300 btn-press"
                          >
                            Отмена
                          </button>
                        </div>
                      </form>
                    ) : (
                      /* Action Buttons */
                      <div className="pt-2 border-t border-white/5 flex items-center justify-end space-x-2">
                        {ev.status === 'pending' && (
                          <>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setRejectingId(ev.id);
                              }}
                              disabled={isActing}
                              className="flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 font-semibold text-xs border border-red-500/20 transition-colors btn-press"
                            >
                              <X className="w-3.5 h-3.5" />
                              <span>Отклонить</span>
                            </button>
                            <button
                              onClick={(e) => handlePublish(e, ev.id)}
                              disabled={isActing}
                              className="flex items-center space-x-1 px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-md shadow-emerald-600/20 transition-all btn-press"
                            >
                              {isActing ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <>
                                  <Check className="w-3.5 h-3.5" />
                                  <span>Опубликовать</span>
                                </>
                              )}
                            </button>
                          </>
                        )}

                        {ev.status === 'published' && (
                          <button
                            onClick={(e) => handleCancel(e, ev.id)}
                            disabled={isActing}
                            className="flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white text-xs border border-white/5 transition-colors btn-press"
                          >
                            <Ban className="w-3.5 h-3.5" />
                            <span>Снять с публикации</span>
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* SECTION 2: ORGANIZATIONS & PRO TESTING */}
      {adminSection === 'organizations' && (
        <div className="space-y-3">
          <div className="p-3 rounded-xl bg-purple-500/10 border border-purple-500/20 text-xs space-y-1.5">
            <div className="flex items-center space-x-1.5 text-purple-300 font-semibold">
              <Sparkles className="w-4 h-4 text-purple-400 shrink-0" />
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
                className="w-full pl-8 pr-3 py-2 rounded-xl bg-[#141724] border border-white/10 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500/50"
              />
            </div>
            <button
              onClick={loadOrganizations}
              disabled={isLoadingOrgs}
              className="p-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 transition-all btn-press shrink-0"
              title="Обновить"
            >
              <RefreshCw className={`w-4 h-4 ${isLoadingOrgs ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* Organizations List */}
          <div className="space-y-2.5">
            {isLoadingOrgs ? (
              <div className="py-12 text-center text-xs text-gray-400 flex items-center justify-center space-x-2">
                <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                <span>Загрузка организаций...</span>
              </div>
            ) : filteredOrgs.length === 0 ? (
              <div className="py-12 px-4 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-2">
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
                    className="p-3.5 rounded-2xl bg-[#141724] border border-white/8 hover:border-white/15 transition-all space-y-2.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center space-x-2">
                          <h4 className="font-bold text-sm text-white truncate">{org.name}</h4>
                          <span
                            className={`text-[9.5px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider shrink-0 ${
                              isPro
                                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
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
                            : 'bg-purple-600 hover:bg-purple-500 text-white shadow-md shadow-purple-600/20'
                        }`}
                      >
                        {isToggling ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : isPro ? (
                          <span>Вернуть Free</span>
                        ) : (
                          <>
                            <Sparkles className="w-3.5 h-3.5" />
                            <span>Включить Pro</span>
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
