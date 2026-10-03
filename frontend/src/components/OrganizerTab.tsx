import React, { useState } from 'react';
import type { EventSummary, OrganizationSummary, UserSubscriptionItem } from '../types';
import { EventCard } from './EventCard';
import { SafeAvatar } from './SafeAvatar';
import { formatFollowers } from './OrganizationModal';
import { telegram } from '../services/telegram';
import { AnimatedSegmentedControl } from './AnimatedSegmentedControl';
import {
  Building2,
  ChevronRight,
  ShieldCheck,
  Plus,
  Calendar,
} from 'lucide-react';


export type PersonalHubTab = 'attending' | 'interested' | 'subscriptions' | 'history';

interface OrganizerTabProps {
  attendingEvents: EventSummary[];
  isLoadingAttending: boolean;
  interestedEvents: EventSummary[];
  isLoadingInterested: boolean;
  subscriptions: UserSubscriptionItem[];
  isLoadingSubscriptions: boolean;
  // Organizer summary
  organizations?: OrganizationSummary[];
  myCreatedEvents?: EventSummary[];
  onOpenOrganizerWorkspace: () => void;
  onOpenCreateEvent?: () => void;
  onOpenCreateOrg: () => void;
  // Item actions
  onEventClick: (event: EventSummary) => void;
  onOrgClick: (orgId: string) => void;
  onExplore: () => void;
}

export const OrganizerTab: React.FC<OrganizerTabProps> = ({
  attendingEvents,
  isLoadingAttending,
  interestedEvents,
  isLoadingInterested,
  subscriptions,
  isLoadingSubscriptions,
  organizations = [],
  myCreatedEvents = [],
  onOpenOrganizerWorkspace,
  onOpenCreateEvent,
  onOpenCreateOrg,
  onEventClick,
  onOrgClick,
  onExplore,
}) => {
  const [activeTab, setActiveTab] = useState<PersonalHubTab>('attending');

  const now = new Date();
  const activeAttending = attendingEvents.filter((e) => new Date(e.start_at) >= now);
  const activeInterested = interestedEvents.filter((e) => new Date(e.start_at) >= now);

  const pastEventsMap = new Map<string, EventSummary>();
  attendingEvents
    .filter((e) => new Date(e.start_at) < now)
    .forEach((e) => pastEventsMap.set(e.id, { ...e, is_attending: true }));
  interestedEvents
    .filter((e) => new Date(e.start_at) < now)
    .forEach((e) => {
      if (!pastEventsMap.has(e.id)) {
        pastEventsMap.set(e.id, { ...e, current_user_interested: true });
      }
    });
  const pastEvents = Array.from(pastEventsMap.values()).sort(
    (a, b) => new Date(b.start_at).getTime() - new Date(a.start_at).getTime()
  );

  const isOrganizer = organizations.length > 0 || myCreatedEvents.length > 0;
  const totalFollowers = organizations.reduce((acc, o) => acc + (o.followers_count || 0), 0);
  const hasAnyPersonalActivity =
    attendingEvents.length > 0 || interestedEvents.length > 0 || subscriptions.length > 0;
  const isBusyLoading =
    isLoadingAttending || isLoadingInterested || isLoadingSubscriptions;

  const handleTabChange = (tab: PersonalHubTab) => {
    if (tab !== activeTab) {
      telegram.hapticImpact('light');
      setActiveTab(tab);
    }
  };

  return (
    <div className="space-y-4 px-4 py-2 pb-20">
      {/* 1. Organizer Entry Banner (Only if user has created org or event) */}
      {isOrganizer && (
        <div className="p-4 rounded-2xl bg-gradient-to-r from-indigo-950/60 via-purple-950/40 to-[#141724] border border-indigo-500/25 shadow-lg flex items-center justify-between gap-3">
          <div className="space-y-1 min-w-0">
            <div className="flex items-center space-x-1.5 text-indigo-400">
              <Building2 className="w-4 h-4 shrink-0" />
              <h3 className="font-bold text-xs text-white uppercase tracking-wider">
                Кабинет организатора
              </h3>
            </div>
            <p className="text-xs text-gray-300 truncate">
              {organizations.length} {organizations.length === 1 ? 'организация' : 'организаций'} •{' '}
              {myCreatedEvents.length}{' '}
              {myCreatedEvents.length === 1 ? 'событие' : 'событий'} •{' '}
              {totalFollowers} {formatFollowers(totalFollowers).split(' ')[1]}
            </p>
          </div>

          <button
            onClick={() => {
              telegram.hapticImpact('medium');
              onOpenOrganizerWorkspace();
            }}
            className="flex items-center space-x-1 px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow-md shadow-indigo-600/30 transition-all shrink-0 btn-press"
          >
            <span>Кабинет</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* 2. Page Title Header */}
      <div className="px-1 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-0.5">
          <h2 className="text-lg font-bold text-white tracking-tight">Мои события</h2>
          <p className="text-xs text-gray-400 leading-relaxed">Ваши планы, сохранённые мероприятия и подписки</p>
        </div>
        {onOpenCreateEvent && (
          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onOpenCreateEvent();
            }}
            className="self-start sm:self-auto px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-indigo-300 border border-white/10 text-xs font-semibold flex items-center space-x-1.5 btn-press shrink-0"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Создать событие</span>
          </button>
        )}
      </div>

      {/* 3. Empty State for new/unengaged users vs Active Tabs */}
      {!isBusyLoading && !hasAnyPersonalActivity && !isOrganizer ? (
        <div className="p-6 text-center rounded-3xl bg-[#141724] border border-white/5 space-y-4 my-2">
          <div className="w-14 h-14 rounded-2xl bg-indigo-600/15 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mx-auto">
            <Calendar className="w-7 h-7" />
          </div>

          <div className="space-y-1.5 max-w-xs mx-auto">
            <h3 className="text-base font-bold text-white tracking-tight">
              У вас пока нет мероприятий
            </h3>
            <p className="text-xs text-gray-400 leading-relaxed">
              Отмечайте события в афише («Я иду» или «Хочу пойти»), подписывайтесь на площадки или создайте собственное мероприятие.
            </p>
          </div>

          <div className="space-y-2 pt-2 max-w-xs mx-auto">
            {onOpenCreateEvent && (
              <button
                type="button"
                onClick={() => {
                  telegram.hapticImpact('medium');
                  onOpenCreateEvent();
                }}
                className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow-md shadow-indigo-600/30 transition-all btn-press flex items-center justify-center space-x-2"
              >
                <Plus className="w-4 h-4" />
                <span>Создать событие</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => {
                telegram.hapticImpact('light');
                onOpenCreateOrg();
              }}
              className="w-full py-2.5 px-4 rounded-xl bg-white/5 hover:bg-white/10 text-indigo-300 border border-white/10 font-semibold text-xs transition-colors btn-press flex items-center justify-center space-x-2"
            >
              <Building2 className="w-3.5 h-3.5" />
              <span>Создать профиль организации</span>
            </button>

            <button
              type="button"
              onClick={() => {
                telegram.hapticImpact('light');
                onExplore();
              }}
              className="w-full py-2 text-xs text-gray-400 hover:text-white transition-colors"
            >
              Смотреть афишу событий →
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* Segmented Tabs Switcher */}
          <AnimatedSegmentedControl
            items={[
              { value: 'attending', label: 'Я иду', count: activeAttending.length },
              { value: 'interested', label: 'Хочу пойти', count: activeInterested.length },
              { value: 'subscriptions', label: 'Подписки', count: subscriptions.length },
              { value: 'history', label: 'Прошедшие', count: pastEvents.length },
            ]}
            value={activeTab}
            onChange={(val) => handleTabChange(val as PersonalHubTab)}
            size="sm"
            equalWidth={false}
          />

          {/* 4. Tab Contents */}
          <div key={activeTab} className="animate-tab-enter">
      {/* TAB: ATTENDING */}
      {activeTab === 'attending' && (
        <div className="space-y-3">
          {isLoadingAttending ? (
            <div className="py-16 text-center text-xs text-gray-400">Загрузка ваших планов...</div>
          ) : activeAttending.length === 0 ? (
            <div className="py-14 px-4 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-3">
              <div className="w-12 h-12 rounded-full bg-indigo-500/10 text-indigo-400 flex items-center justify-center mx-auto text-xl">
                🎟
              </div>
              <div className="space-y-1">
                <div className="text-sm font-semibold text-white">Нет активных планов</div>
                <p className="text-xs text-gray-400 max-w-xs mx-auto">
                  Здесь появятся предстоящие события, на которые вы нажали «Я иду»
                </p>
              </div>
              <button
                onClick={onExplore}
                className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold shadow hover:bg-indigo-500 btn-press"
              >
                Найти событие
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {activeAttending.map((event) => (
                <EventCard
                  key={event.id}
                  event={event}
                  onClick={() => onEventClick(event)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB: INTERESTED */}
      {activeTab === 'interested' && (
        <div className="space-y-3">
          {isLoadingInterested ? (
            <div className="py-16 text-center text-xs text-gray-400">Загрузка сохранённых событий...</div>
          ) : activeInterested.length === 0 ? (
            <div className="py-14 px-4 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-3">
              <div className="w-12 h-12 rounded-full bg-pink-500/10 text-pink-400 flex items-center justify-center mx-auto text-xl">
                ❤️
              </div>
              <div className="space-y-1">
                <div className="text-sm font-semibold text-white">Нет сохранённых событий</div>
                <p className="text-xs text-gray-400 max-w-xs mx-auto">
                  Сохраняйте интересные предстоящие события, чтобы вернуться к ним позже
                </p>
              </div>
              <button
                onClick={onExplore}
                className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold shadow hover:bg-indigo-500 btn-press"
              >
                Смотреть афишу
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {activeInterested.map((event) => (
                <EventCard
                  key={event.id}
                  event={event}
                  onClick={() => onEventClick(event)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB: HISTORY */}
      {activeTab === 'history' && (
        <div className="space-y-3">
          {pastEvents.length === 0 ? (
            <div className="py-14 px-4 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-3">
              <div className="w-12 h-12 rounded-full bg-indigo-500/10 text-indigo-400 flex items-center justify-center mx-auto text-xl">
                ⏳
              </div>
              <div className="space-y-1">
                <div className="text-sm font-semibold text-white">Нет прошедших событий</div>
                <p className="text-xs text-gray-400 max-w-xs mx-auto">
                  Здесь сохраняется архив событий из ваших планов и закладок после их завершения
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="text-[11px] text-gray-400 px-1">
                Архив прошедших событий из ваших планов и закладок
              </div>
              {pastEvents.map((event) => (
                <div key={event.id} className="opacity-80 hover:opacity-100 transition-opacity">
                  <EventCard
                    event={event}
                    onClick={() => onEventClick(event)}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB: SUBSCRIPTIONS */}
      {activeTab === 'subscriptions' && (
        <div className="space-y-3">
          {isLoadingSubscriptions ? (
            <div className="py-16 text-center text-xs text-gray-400">Загрузка подписок...</div>
          ) : subscriptions.length === 0 ? (
            <div className="py-14 px-4 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-3">
              <div className="w-12 h-12 rounded-full bg-amber-500/10 text-amber-400 flex items-center justify-center mx-auto text-xl">
                🏛
              </div>
              <div className="space-y-1">
                <div className="text-sm font-semibold text-white">Нет активных подписок</div>
                <p className="text-xs text-gray-400 max-w-xs mx-auto">
                  Подписывайтесь на места и организаторов, чтобы не пропускать новые события
                </p>
              </div>
              <button
                onClick={onExplore}
                className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold shadow hover:bg-indigo-500 btn-press"
              >
                Найти места
              </button>
            </div>
          ) : (
            <div className="space-y-2.5">
              {subscriptions.map((sub) => {
                const org = sub.organization;
                return (
                  <div
                    key={sub.id}
                    onClick={() => onOrgClick(org.id)}
                    className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 hover:border-indigo-500/30 transition-all cursor-pointer flex items-center justify-between group card-press"
                  >
                    <div className="flex items-center space-x-3 min-w-0">
                      <div className="w-11 h-11 rounded-xl overflow-hidden border border-indigo-500/30 flex items-center justify-center shrink-0">
                        <SafeAvatar
                          src={org.avatar_url}
                          name={org.name}
                          className="w-full h-full object-cover"
                        />
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
                          <span>{formatFollowers(org.followers_count || 0)}</span>
                        </div>
                      </div>
                    </div>

                    <ChevronRight className="w-4 h-4 text-gray-500 group-hover:text-indigo-400 group-hover:translate-x-0.5 transition-all shrink-0" />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
      </div>

      {/* 5. Non-Organizer Subtle CTA Banner at Bottom */}
      {!isOrganizer && (
        <div className="pt-2">
          <div className="p-3.5 rounded-2xl bg-[#141724]/70 border border-white/5 flex items-center justify-between gap-3">
            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-gray-300">Организуете мероприятия?</div>
              <div className="text-[11px] text-gray-500">Создайте профиль заведения или клуба</div>
            </div>
            <button
              onClick={() => {
                telegram.hapticImpact('light');
                onOpenCreateOrg();
              }}
              className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-indigo-300 border border-white/10 text-xs font-medium shrink-0 btn-press"
            >
              Создать профиль
            </button>
          </div>
        </div>
      )}
        </>
      )}
    </div>
  );
};
