import React from 'react';
import type { EventSummary, OrganizationSummary } from '../types';
import { formatFollowers } from './OrganizationModal';
import {
  Plus,
  Calendar,
  MapPin,
  Clock,
  CheckCircle2,
  XCircle,
  Building2,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';

interface OrganizerTabProps {
  events: EventSummary[];
  isLoading: boolean;
  onOpenCreateModal: () => void;
  onEventClick: (event: EventSummary) => void;
  organizations?: OrganizationSummary[];
  isLoadingOrganizations?: boolean;
  onOpenCreateOrgModal?: () => void;
  onOrgClick?: (org: OrganizationSummary) => void;
}

export const OrganizerTab: React.FC<OrganizerTabProps> = ({
  events,
  isLoading,
  onOpenCreateModal,
  onEventClick,
  organizations = [],
  isLoadingOrganizations = false,
  onOpenCreateOrgModal,
  onOrgClick,
}) => {
  return (
    <div className="space-y-5 px-4 py-2">
      {/* Top Banner */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-indigo-900/40 via-purple-900/30 to-[#141724] border border-indigo-500/20 flex items-center justify-between shadow-lg">
        <div className="space-y-1">
          <h3 className="font-bold text-sm text-white">Кабинет организатора</h3>
          <p className="text-xs text-gray-400">Создавайте события и управляйте профилями организаций</p>
        </div>
        <button
          onClick={onOpenCreateModal}
          className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow-md shadow-indigo-600/30 transition-all shrink-0 btn-press"
        >
          <Plus className="w-4 h-4" />
          <span>Создать</span>
        </button>
      </div>

      {/* Organizations Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between px-1">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Мои организации ({organizations.length})
          </h4>
          <button
            onClick={onOpenCreateOrgModal}
            className="flex items-center space-x-1 text-xs text-indigo-400 hover:text-indigo-300 font-medium btn-press"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Создать профиль</span>
          </button>
        </div>

        {isLoadingOrganizations ? (
          <div className="py-6 text-center text-xs text-gray-400">Загрузка организаций...</div>
        ) : organizations.length === 0 ? (
          <div className="p-4 rounded-2xl bg-[#141724] border border-white/5 flex items-center justify-between gap-3">
            <div className="flex items-center space-x-3 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center shrink-0">
                <Building2 className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-white">Профиль площадки или клуба</div>
                <div className="text-[11px] text-gray-400">
                  Публикуйте анонсы от имени бренда и собирайте базу подписчиков
                </div>
              </div>
            </div>
            <button
              onClick={onOpenCreateOrgModal}
              className="px-3 py-1.5 rounded-xl bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-600/40 text-xs font-medium shrink-0 btn-press"
            >
              Создать
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-2.5">
            {organizations.map((org) => (
              <div
                key={org.id}
                onClick={() => onOrgClick?.(org)}
                className="p-3 rounded-2xl bg-[#141724] border border-white/5 hover:border-indigo-500/30 transition-all cursor-pointer flex items-center justify-between group card-press"
              >
                <div className="flex items-center space-x-3 min-w-0">
                  <div className="w-11 h-11 rounded-xl overflow-hidden bg-gradient-to-tr from-indigo-900 to-purple-900 border border-indigo-500/30 flex items-center justify-center shrink-0">
                    {org.avatar_url ? (
                      <img src={org.avatar_url} alt={org.name} className="w-full h-full object-cover" />
                    ) : (
                      <span className="text-sm font-bold text-indigo-300">
                        {org.name.slice(0, 2).toUpperCase()}
                      </span>
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center space-x-1.5">
                      <span className="font-semibold text-xs text-white group-hover:text-indigo-300 transition-colors truncate">
                        {org.name}
                      </span>
                      {org.is_verified && (
                        <ShieldCheck className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                      )}
                    </div>
                    <div className="flex items-center space-x-2 text-[11px] text-gray-400">
                      <span className="text-indigo-300">{org.category}</span>
                      <span>•</span>
                      <span>{formatFollowers(org.followers_count)}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-1 text-xs text-indigo-400 font-medium pl-2 shrink-0">
                  <span>Управлять</span>
                  <ChevronRight className="w-4 h-4 text-indigo-400 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Events List */}
      <div className="space-y-3">
        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-1">
          Мои мероприятия ({events.length})
        </h4>

        {isLoading ? (
          <div className="py-12 text-center text-xs text-gray-400">Загрузка ваших событий...</div>
        ) : events.length === 0 ? (
          <div className="p-8 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-3">
            <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mx-auto text-gray-400">
              <Calendar className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <div className="text-sm font-semibold text-white">У вас пока нет созданных событий</div>
              <p className="text-xs text-gray-400 max-w-xs mx-auto">
                Опубликуйте концерт, лекцию, вечеринку или митап для жителей города
              </p>
            </div>
            <button
              onClick={onOpenCreateModal}
              className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold shadow hover:bg-indigo-500 btn-press"
            >
              Создать первое событие
            </button>
          </div>
        ) : (
          events.map((ev) => {
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
                  <div className="font-semibold text-sm text-white line-clamp-1">{ev.title}</div>
                  {/* Status Pill */}
                  {ev.status === 'pending' && (
                    <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30 shrink-0">
                      <Clock className="w-3 h-3" />
                      <span>На проверке</span>
                    </span>
                  )}
                  {ev.status === 'published' && (
                    <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 shrink-0">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Опубликовано</span>
                    </span>
                  )}
                  {ev.status === 'rejected' && (
                    <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-500/10 text-red-400 border border-red-500/30 shrink-0">
                      <XCircle className="w-3 h-3" />
                      <span>Отклонено</span>
                    </span>
                  )}
                  {ev.status === 'cancelled' && (
                    <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-gray-500/10 text-gray-400 border border-gray-500/30 shrink-0">
                      Снято
                    </span>
                  )}
                </div>

                <div className="flex items-center space-x-3 text-xs text-gray-400">
                  <div className="flex items-center space-x-1">
                    <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                    <span>{dateStr}</span>
                  </div>
                  <div className="flex items-center space-x-1 truncate">
                    <MapPin className="w-3.5 h-3.5 text-gray-500" />
                    <span className="truncate">{ev.venue_name} ({ev.city_name})</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
