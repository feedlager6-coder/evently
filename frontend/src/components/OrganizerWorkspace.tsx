import React, { useState } from 'react';
import type { EventSummary, OrganizationSummary } from '../types';
import { SafeAvatar } from './SafeAvatar';
import { telegram } from '../services/telegram';
import {
  ArrowLeft,
  Plus,
  Building2,
  Calendar,
  Clock,
  CheckCircle2,
  XCircle,
  Users,
  Eye,
  Heart,
  TrendingUp,
  ChevronRight,
  ShieldCheck,
  AlertTriangle,
  Edit3,
  ExternalLink,
} from 'lucide-react';

export type WorkspaceTab = 'overview' | 'events' | 'organizations';
export type EventFilter = 'upcoming' | 'pending' | 'past';

interface OrganizerWorkspaceProps {
  onBack: () => void;
  organizations: OrganizationSummary[];
  events: EventSummary[];
  isLoading: boolean;
  onOpenCreateEvent: (orgId?: string) => void;
  onOpenCreateOrg: () => void;
  onEditOrg: (org: OrganizationSummary) => void;
  onOrgClick: (org: OrganizationSummary) => void;
  onEventClick: (event: EventSummary) => void;
}

export const OrganizerWorkspace: React.FC<OrganizerWorkspaceProps> = ({
  onBack,
  organizations,
  events,
  isLoading,
  onOpenCreateEvent,
  onOpenCreateOrg,
  onEditOrg,
  onOrgClick,
  onEventClick,
}) => {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('overview');
  const [eventFilter, setEventFilter] = useState<EventFilter>('upcoming');

  const now = new Date();

  // Segment events
  const upcomingEvents = events.filter(
    (e) => e.status === 'published' && new Date(e.start_at) >= now
  );
  const pendingEvents = events.filter(
    (e) => e.status === 'pending' || e.status === 'rejected'
  );
  const pastEvents = events.filter(
    (e) => e.status === 'published' && new Date(e.start_at) < now
  );

  // Aggregated overview metrics
  const totalFollowers = organizations.reduce((acc, o) => acc + (o.followers_count || 0), 0);
  const totalAttendees = events.reduce((acc, e) => acc + (e.attendee_count || 0), 0);
  const totalInterests = events.reduce((acc, e) => acc + (e.interest_count || 0), 0);
  const totalViews = events.reduce((acc, e) => acc + (e.views_count || 0), 0);

  // Conversion rates (Phase 10: safe formatting)
  const interestConversion = totalViews > 0 ? `${((totalInterests / totalViews) * 100).toFixed(1)}%` : '—';
  const rsvpConversion = totalViews > 0 ? `${((totalAttendees / totalViews) * 100).toFixed(1)}%` : '—';

  // Top upcoming 2 events
  const topUpcoming = upcomingEvents.slice(0, 2);

  // Events requiring attention (rejected or pending)
  const attentionEvents = pendingEvents;

  const handleTabChange = (tab: WorkspaceTab) => {
    if (tab !== activeTab) {
      telegram.hapticImpact('light');
      setActiveTab(tab);
    }
  };

  const handleFilterChange = (filter: EventFilter) => {
    if (filter !== eventFilter) {
      telegram.hapticImpact('light');
      setEventFilter(filter);
    }
  };

  const currentEventsList =
    eventFilter === 'upcoming'
      ? upcomingEvents
      : eventFilter === 'pending'
      ? pendingEvents
      : pastEvents;

  return (
    <div className="space-y-4 pb-20">
      {/* Workspace Header */}
      <div className="sticky top-0 z-20 bg-[#0B0D13]/90 backdrop-blur-md border-b border-white/5 px-4 py-3">
        <div className="flex items-center justify-between max-w-lg mx-auto">
          <div className="flex items-center space-x-2.5">
            <button
              onClick={() => {
                telegram.hapticImpact('light');
                onBack();
              }}
              className="p-1.5 -ml-1 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white transition-colors btn-press"
              aria-label="Назад"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-base font-bold text-white tracking-tight leading-tight">
                Кабинет организатора
              </h1>
              <p className="text-[11px] text-gray-400">Управление контентом и площадками</p>
            </div>
          </div>

          <button
            onClick={() => {
              telegram.hapticImpact('medium');
              onOpenCreateEvent();
            }}
            className="flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow-md shadow-indigo-600/30 transition-all btn-press shrink-0"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Создать</span>
          </button>
        </div>
      </div>

      <div className="px-4 space-y-4 max-w-lg mx-auto">
        {/* Navigation Tabs */}
        <div className="flex rounded-2xl bg-[#141724] p-1 border border-white/5">
          <button
            onClick={() => handleTabChange('overview')}
            className={`flex-1 py-2 text-xs font-semibold rounded-xl transition-all ${
              activeTab === 'overview'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            Обзор
          </button>
          <button
            onClick={() => handleTabChange('events')}
            className={`flex-1 py-2 text-xs font-semibold rounded-xl transition-all flex items-center justify-center space-x-1.5 ${
              activeTab === 'events'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <span>События</span>
            <span
              className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                activeTab === 'events' ? 'bg-white/20 text-white' : 'bg-white/5 text-gray-400'
              }`}
            >
              {events.length}
            </span>
          </button>
          <button
            onClick={() => handleTabChange('organizations')}
            className={`flex-1 py-2 text-xs font-semibold rounded-xl transition-all flex items-center justify-center space-x-1.5 ${
              activeTab === 'organizations'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <span>Организации</span>
            <span
              className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                activeTab === 'organizations' ? 'bg-white/20 text-white' : 'bg-white/5 text-gray-400'
              }`}
            >
              {organizations.length}
            </span>
          </button>
        </div>

        {/* TAB 1: OVERVIEW */}
        {activeTab === 'overview' && (
          <div className="space-y-4">
            {/* Stat Grid */}
            <div className="grid grid-cols-2 gap-2.5">
              <div className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 space-y-1">
                <div className="flex items-center space-x-2 text-indigo-400">
                  <Eye className="w-4 h-4" />
                  <span className="text-[11px] font-medium text-gray-400">Просмотры</span>
                </div>
                <div className="text-xl font-bold text-white tracking-tight">{totalViews}</div>
              </div>

              <div className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 space-y-1">
                <div className="flex items-center space-x-2 text-emerald-400">
                  <Users className="w-4 h-4" />
                  <span className="text-[11px] font-medium text-gray-400">Гости (RSVP)</span>
                </div>
                <div className="text-xl font-bold text-white tracking-tight">{totalAttendees}</div>
              </div>

              <div className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 space-y-1">
                <div className="flex items-center space-x-2 text-pink-400">
                  <Heart className="w-4 h-4" />
                  <span className="text-[11px] font-medium text-gray-400">Интерес</span>
                </div>
                <div className="text-xl font-bold text-white tracking-tight">{totalInterests}</div>
              </div>

              <div className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 space-y-1">
                <div className="flex items-center space-x-2 text-indigo-400">
                  <Building2 className="w-4 h-4" />
                  <span className="text-[11px] font-medium text-gray-400">Подписчики</span>
                </div>
                <div className="text-xl font-bold text-white tracking-tight">{totalFollowers}</div>
              </div>
            </div>

            {/* Conversion Indicators */}
            <div className="p-3 rounded-2xl bg-[#141724] border border-white/5 flex items-center justify-between text-xs text-gray-400">
              <div className="flex items-center space-x-1.5 text-indigo-400">
                <TrendingUp className="w-3.5 h-3.5" />
                <span className="text-[11px] font-medium text-gray-300">Конверсия</span>
              </div>
              <div className="flex items-center space-x-3 text-[11px]">
                <span>В интерес: <strong className="text-pink-400 font-semibold">{interestConversion}</strong></span>
                <span>•</span>
                <span>В гостей: <strong className="text-emerald-400 font-semibold">{rsvpConversion}</strong></span>
              </div>
            </div>

            {/* Quick Action Buttons */}
            <div className="grid grid-cols-2 gap-2.5">
              <button
                onClick={() => {
                  telegram.hapticImpact('light');
                  onOpenCreateEvent();
                }}
                className="p-3 rounded-2xl bg-indigo-600/15 border border-indigo-500/30 hover:bg-indigo-600/25 flex items-center justify-center space-x-2 text-xs font-semibold text-indigo-300 transition-all btn-press"
              >
                <Plus className="w-4 h-4" />
                <span>Новое событие</span>
              </button>

              <button
                onClick={() => {
                  telegram.hapticImpact('light');
                  onOpenCreateOrg();
                }}
                className="p-3 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 flex items-center justify-center space-x-2 text-xs font-semibold text-gray-200 transition-all btn-press"
              >
                <Building2 className="w-4 h-4 text-gray-400" />
                <span>+ Организация</span>
              </button>
            </div>

            {/* Requires Attention Section (if any pending/rejected) */}
            {attentionEvents.length > 0 && (
              <div className="space-y-2.5">
                <div className="flex items-center space-x-1.5 px-1">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <h3 className="text-xs font-semibold text-amber-300 uppercase tracking-wider">
                    Требует внимания ({attentionEvents.length})
                  </h3>
                </div>

                <div className="space-y-2">
                  {attentionEvents.map((ev) => (
                    <div
                      key={ev.id}
                      onClick={() => onEventClick(ev)}
                      className="p-3.5 rounded-2xl bg-[#141724] border border-amber-500/20 hover:border-amber-500/40 transition-all cursor-pointer space-y-2 card-press"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="font-semibold text-xs text-white line-clamp-1">{ev.title}</div>
                        {ev.status === 'pending' ? (
                          <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30 shrink-0">
                            <Clock className="w-3 h-3" />
                            <span>На проверке</span>
                          </span>
                        ) : (
                          <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-500/10 text-red-400 border border-red-500/30 shrink-0">
                            <XCircle className="w-3 h-3" />
                            <span>Отклонено</span>
                          </span>
                        )}
                      </div>

                      {ev.rejection_reason && (
                        <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-[11px] text-red-300 space-y-0.5">
                          <span className="font-semibold text-red-200">Причина модератора: </span>
                          <span>{ev.rejection_reason}</span>
                        </div>
                      )}

                      <div className="flex items-center justify-between text-[11px] text-gray-400 pt-1 border-t border-white/5">
                        <span>{ev.venue_name}</span>
                        <span className="text-indigo-400 font-medium flex items-center space-x-0.5">
                          <span>Открыть детали</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Upcoming Events Preview */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between px-1">
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Ближайшие события
                </h3>
                {upcomingEvents.length > 2 && (
                  <button
                    onClick={() => {
                      setActiveTab('events');
                      setEventFilter('upcoming');
                    }}
                    className="text-xs text-indigo-400 hover:text-indigo-300 font-medium btn-press"
                  >
                    Все ({upcomingEvents.length}) →
                  </button>
                )}
              </div>

              {topUpcoming.length === 0 ? (
                <div className="p-5 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-2">
                  <Calendar className="w-6 h-6 text-gray-500 mx-auto" />
                  <p className="text-xs text-gray-400">Нет опубликованных предстоящих событий</p>
                  <button
                    onClick={() => onOpenCreateEvent()}
                    className="px-3 py-1.5 rounded-xl bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-500 btn-press"
                  >
                    Опубликовать анонс
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  {topUpcoming.map((ev) => {
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
                        className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 hover:border-indigo-500/30 transition-all cursor-pointer space-y-2.5 card-press"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="font-semibold text-xs text-white line-clamp-1">
                            {ev.title}
                          </div>
                          <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 shrink-0">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Опубликовано</span>
                          </span>
                        </div>

                        <div className="flex items-center justify-between text-xs text-gray-400">
                          <div className="flex items-center space-x-1.5">
                            <Calendar className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                            <span>{dateStr}</span>
                          </div>
                          <div className="flex items-center space-x-2.5 text-[11px]">
                            <span className="flex items-center space-x-1 text-gray-400">
                              <Eye className="w-3 h-3 text-indigo-400" />
                              <span>{ev.views_count || 0}</span>
                            </span>
                            <span className="text-emerald-400 font-medium">
                              ● {ev.attendee_count} идут
                            </span>
                            <span className="text-pink-400 font-medium">
                              ● {ev.interest_count || 0} интерес
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: EVENTS */}
        {activeTab === 'events' && (
          <div className="space-y-3.5">
            {/* Sub-filter pills */}
            <div className="flex items-center space-x-2 overflow-x-auto no-scrollbar py-0.5">
              <button
                onClick={() => handleFilterChange('upcoming')}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                  eventFilter === 'upcoming'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-[#141724] text-gray-400 border border-white/5 hover:text-white'
                }`}
              >
                Предстоящие ({upcomingEvents.length})
              </button>
              <button
                onClick={() => handleFilterChange('pending')}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                  eventFilter === 'pending'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-[#141724] text-gray-400 border border-white/5 hover:text-white'
                }`}
              >
                На проверке ({pendingEvents.length})
              </button>
              <button
                onClick={() => handleFilterChange('past')}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                  eventFilter === 'past'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-[#141724] text-gray-400 border border-white/5 hover:text-white'
                }`}
              >
                Прошедшие ({pastEvents.length})
              </button>
            </div>

            {/* Event list */}
            {isLoading ? (
              <div className="py-12 text-center text-xs text-gray-400">Загрузка мероприятий...</div>
            ) : currentEventsList.length === 0 ? (
              <div className="py-12 px-4 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-2.5">
                <Calendar className="w-8 h-8 text-gray-500 mx-auto" />
                <div className="text-xs font-semibold text-white">
                  {eventFilter === 'upcoming'
                    ? 'Нет предстоящих событий'
                    : eventFilter === 'pending'
                    ? 'Нет событий на модерации'
                    : 'Нет прошедших событий'}
                </div>
                <p className="text-[11px] text-gray-400 max-w-xs mx-auto">
                  {eventFilter === 'upcoming'
                    ? 'Опубликуйте концерт, вечеринку или митап'
                    : 'Новые события попадают сюда до одобрения модератором'}
                </p>
                {eventFilter === 'upcoming' && (
                  <button
                    onClick={() => onOpenCreateEvent()}
                    className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-500 btn-press"
                  >
                    Создать событие
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-2.5">
                {currentEventsList.map((ev) => {
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
                      className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 hover:border-indigo-500/30 transition-all cursor-pointer space-y-2.5 card-press"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="font-semibold text-xs text-white truncate">{ev.title}</div>
                          <div className="text-[11px] text-gray-400 truncate">
                            {ev.organization_name ? ev.organization_name : 'Личный профиль'} • {ev.venue_name}
                          </div>
                        </div>

                        {/* Status Pill */}
                        {ev.status === 'pending' && (
                          <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30 shrink-0">
                            <Clock className="w-3 h-3" />
                            <span>На проверке</span>
                          </span>
                        )}
                        {ev.status === 'published' && (
                          <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 shrink-0">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Опубликовано</span>
                          </span>
                        )}
                        {ev.status === 'rejected' && (
                          <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-500/10 text-red-400 border border-red-500/30 shrink-0">
                            <XCircle className="w-3 h-3" />
                            <span>Отклонено</span>
                          </span>
                        )}
                        {ev.status === 'cancelled' && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-500/10 text-gray-400 border border-gray-500/30 shrink-0">
                            Снято
                          </span>
                        )}
                      </div>

                      {ev.status === 'rejected' && ev.rejection_reason && (
                        <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-[11px] text-red-300">
                          <span className="font-semibold text-red-200">Причина отказа: </span>
                          <span>{ev.rejection_reason}</span>
                        </div>
                      )}

                      <div className="flex items-center justify-between text-xs text-gray-400 pt-1 border-t border-white/5">
                        <div className="flex items-center space-x-1">
                          <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                          <span>{dateStr}</span>
                        </div>
                        <div className="flex items-center space-x-2.5 text-[11px]">
                          <span className="flex items-center space-x-1 text-gray-400">
                            <Eye className="w-3 h-3 text-indigo-400" />
                            <span>{ev.views_count || 0}</span>
                          </span>
                          <span className="text-emerald-400 font-medium">
                            ● {ev.attendee_count} идут
                          </span>
                          <span className="text-pink-400 font-medium">
                            ● {ev.interest_count || 0} интерес
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: ORGANIZATIONS */}
        {activeTab === 'organizations' && (
          <div className="space-y-3.5">
            <div className="flex items-center justify-between px-1">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Мои организации ({organizations.length})
              </h3>
              <button
                onClick={onOpenCreateOrg}
                className="flex items-center space-x-1 text-xs text-indigo-400 hover:text-indigo-300 font-medium btn-press"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Добавить</span>
              </button>
            </div>

            {organizations.length === 0 ? (
              <div className="p-6 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-3">
                <div className="w-12 h-12 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center mx-auto">
                  <Building2 className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <h4 className="text-xs font-bold text-white">Профиль площадки или заведения</h4>
                  <p className="text-[11px] text-gray-400 max-w-xs mx-auto">
                    Создайте профиль бара, клуба, лектория или комьюнити, чтобы собирать подписчиков
                  </p>
                </div>
                <button
                  onClick={onOpenCreateOrg}
                  className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold shadow hover:bg-indigo-500 btn-press"
                >
                  Создать организацию
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {organizations.map((org) => (
                  <div
                    key={org.id}
                    className="p-4 rounded-2xl bg-[#141724] border border-white/5 space-y-3"
                  >
                    {/* Header info */}
                    <div className="flex items-center space-x-3">
                      <div className="w-12 h-12 rounded-xl overflow-hidden border border-indigo-500/30 flex items-center justify-center shrink-0">
                        <SafeAvatar
                          src={org.avatar_url}
                          name={org.name}
                          className="w-full h-full object-cover"
                        />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center space-x-1.5">
                          <span className="font-semibold text-xs text-white truncate">
                            {org.name}
                          </span>
                          {org.is_verified && (
                            <ShieldCheck className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                          )}
                        </div>
                        <div className="flex items-center space-x-2 text-[11px] text-gray-400">
                          <span className="text-indigo-300">{org.category}</span>
                          <span>•</span>
                          <span>{org.city_name || 'Город'}</span>
                        </div>
                      </div>
                    </div>

                    {/* Stats pill */}
                    <div className="flex items-center justify-around py-2 px-3 rounded-xl bg-white/[0.03] border border-white/5 text-center">
                      <div>
                        <div className="text-xs font-bold text-white">{org.followers_count || 0}</div>
                        <div className="text-[10px] text-gray-400">подписчиков</div>
                      </div>
                      <div className="w-px h-6 bg-white/10" />
                      <div>
                        <div className="text-xs font-bold text-white">{org.events_count || 0}</div>
                        <div className="text-[10px] text-gray-400">мероприятий</div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="grid grid-cols-3 gap-2 pt-1">
                      <button
                        onClick={() => onEditOrg(org)}
                        className="py-2 px-1 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-[11px] font-medium text-gray-300 flex items-center justify-center space-x-1 btn-press"
                      >
                        <Edit3 className="w-3 h-3 text-gray-400" />
                        <span>Изменить</span>
                      </button>

                      <button
                        onClick={() => onOpenCreateEvent(org.id)}
                        className="py-2 px-1 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-[11px] font-medium text-indigo-300 flex items-center justify-center space-x-1 btn-press"
                      >
                        <Plus className="w-3 h-3 text-indigo-400" />
                        <span>Событие</span>
                      </button>

                      <button
                        onClick={() => onOrgClick(org)}
                        className="py-2 px-1 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-[11px] font-medium text-gray-300 flex items-center justify-center space-x-1 btn-press"
                      >
                        <ExternalLink className="w-3 h-3 text-gray-400" />
                        <span>Страница</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
