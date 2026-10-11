import React from 'react';
import type { City, TelegramWebAppUser } from '../types';
import { telegram } from '../services/telegram';
import {
  ArrowLeft,
  MapPin,
  Ticket,
  Bell,
  Globe,
  Store,
  ChevronRight,
  Shield,
  Heart,
  CheckCircle2,
} from 'lucide-react';
import { SafeAvatar } from './SafeAvatar';

interface UserProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  user?: TelegramWebAppUser | null;
  currentCity?: City;
  onOpenCityModal: () => void;
  attendingCount: number;
  interestedCount: number;
  subscriptionsCount: number;
  onNavigateToAttending: () => void;
  onNavigateToInterested: () => void;
  onOpenSubscriptions: () => void;
  onOpenOrganizerWorkspace: () => void;
  isAdmin: boolean;
  onOpenAdminPanel?: () => void;
}

export const UserProfileModal: React.FC<UserProfileModalProps> = ({
  isOpen,
  onClose,
  user,
  currentCity,
  onOpenCityModal,
  attendingCount,
  interestedCount,
  subscriptionsCount,
  onNavigateToAttending,
  onNavigateToInterested,
  onOpenSubscriptions,
  onOpenOrganizerWorkspace,
  isAdmin,
  onOpenAdminPanel,
}) => {
  if (!isOpen) return null;

  const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || 'Гость';
  const usernameLabel = user?.username ? `@${user.username}` : `ID: ${user?.id || '—'}`;
  const cityName = currentCity ? currentCity.name : 'Махачкала';

  return (
    <div className="fixed inset-0 z-[65] flex flex-col bg-[#0e0e10] text-[#e5e1e4] overflow-y-auto custom-scrollbar select-none">
      {/* Top App Bar */}
      <header className="sticky top-0 z-30 pt-safe px-4 pb-3 flex items-center justify-between bg-[#131315]/85 backdrop-blur-2xl border-b border-white/8 shadow-[0_1px_12px_rgba(0,0,0,0.5)]">
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onClose();
            }}
            className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 active:scale-95 flex items-center justify-center transition-all border border-white/10 text-[#c4c7c8] hover:text-white"
            aria-label="Назад"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-base font-bold text-white tracking-tight">Профиль</h1>
        </div>

        {isAdmin && (
          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#10b981]/20 text-[#4edea3] border border-[#10b981]/30">
            Admin
          </span>
        )}
      </header>

      {/* Main Profile Content */}
      <main className="flex-1 max-w-[440px] w-full mx-auto px-4 py-5 space-y-5 pb-20">
        {/* User Identity Section */}
        <section className="flex flex-col items-center text-center space-y-3 pt-2">
          {/* Avatar with luminous border */}
          <div className="relative">
            <div className="w-20 h-20 rounded-full overflow-hidden border-2 border-white/20 p-0.5 bg-[#1c1b1e] shadow-[0_0_24px_rgba(16,185,129,0.18)]">
              <SafeAvatar
                name={displayName}
                type="user"
                className="w-full h-full object-cover rounded-full"
              />
            </div>
            {isAdmin && (
              <div className="absolute bottom-0 right-0 w-6 h-6 rounded-full bg-[#10b981] text-black flex items-center justify-center shadow-md">
                <Shield className="w-3.5 h-3.5 fill-black" />
              </div>
            )}
          </div>

          <div>
            <h2 className="text-lg font-extrabold text-white tracking-tight">
              {displayName}
            </h2>
            <div className="flex items-center justify-center gap-2 pt-0.5">
              <span className="text-xs font-mono text-[#8e9192]">
                {usernameLabel}
              </span>
              {user?.id && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/5 border border-white/10 text-[#8e9192]">
                  TG #{user.id}
                </span>
              )}
            </div>
          </div>

          {/* City Capsule */}
          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onOpenCityModal();
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#201f22] hover:bg-[#2a2a2c] border border-white/10 text-xs font-medium text-[#c4c7c8] hover:text-white transition-all active:scale-95 shadow-sm"
          >
            <MapPin className="w-3.5 h-3.5 text-[#10b981]" />
            <span>г. {cityName}</span>
            <ChevronRight className="w-3 h-3 text-[#8e9192]" />
          </button>
        </section>

        {/* Stats Grid (3 Columns) */}
        <section className="grid grid-cols-3 gap-2.5">
          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onNavigateToAttending();
              onClose();
            }}
            className="p-3.5 rounded-2xl bg-[#1c1b1e] border border-white/8 hover:border-white/15 text-center transition-all active:scale-95 shadow-sm flex flex-col items-center justify-center gap-1 group"
          >
            <div className="flex items-center gap-1">
              <span className="text-lg font-black text-white group-hover:text-[#4edea3] transition-colors">
                {attendingCount}
              </span>
              <span className="w-1.5 h-1.5 rounded-full bg-[#10b981]" />
            </div>
            <span className="text-[11px] font-semibold text-[#8e9192] truncate w-full">
              Я иду
            </span>
          </button>

          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onNavigateToInterested();
              onClose();
            }}
            className="p-3.5 rounded-2xl bg-[#1c1b1e] border border-white/8 hover:border-white/15 text-center transition-all active:scale-95 shadow-sm flex flex-col items-center justify-center gap-1 group"
          >
            <div className="flex items-center gap-1">
              <span className="text-lg font-black text-white group-hover:text-[#ffb95f] transition-colors">
                {interestedCount}
              </span>
              <Heart className="w-3 h-3 text-[#ffb95f] fill-[#ffb95f]" />
            </div>
            <span className="text-[11px] font-semibold text-[#8e9192] truncate w-full">
              Хочу пойти
            </span>
          </button>

          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onOpenSubscriptions();
            }}
            className="p-3.5 rounded-2xl bg-[#1c1b1e] border border-white/8 hover:border-white/15 text-center transition-all active:scale-95 shadow-sm flex flex-col items-center justify-center gap-1 group"
          >
            <span className="text-lg font-black text-white group-hover:text-white transition-colors">
              {subscriptionsCount}
            </span>
            <span className="text-[11px] font-semibold text-[#8e9192] truncate w-full">
              Подписки
            </span>
          </button>
        </section>

        {/* Quick Actions & Sections (Grouped Glass List) */}
        <section className="rounded-3xl bg-[#1c1b1e] border border-white/8 overflow-hidden divide-y divide-white/5 shadow-md">
          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onNavigateToAttending();
              onClose();
            }}
            className="w-full p-4 flex items-center justify-between hover:bg-white/5 active:bg-white/10 transition-colors text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-[#4edea3]">
                <Ticket className="w-4 h-4" />
              </div>
              <div>
                <span className="font-semibold text-xs text-white block">Мои билеты</span>
                <span className="text-[10px] text-[#8e9192]">
                  {attendingCount > 0 ? `${attendingCount} активных билетов` : 'Билетов пока нет'}
                </span>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-[#8e9192]" />
          </button>

          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onOpenSubscriptions();
            }}
            className="w-full p-4 flex items-center justify-between hover:bg-white/5 active:bg-white/10 transition-colors text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-white">
                <Bell className="w-4 h-4" />
              </div>
              <div>
                <span className="font-semibold text-xs text-white block">Мои подписки</span>
                <span className="text-[10px] text-[#8e9192]">
                  {subscriptionsCount} организаторов и площадок
                </span>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-[#8e9192]" />
          </button>

          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onOpenCityModal();
            }}
            className="w-full p-4 flex items-center justify-between hover:bg-white/5 active:bg-white/10 transition-colors text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-[#ffb95f]">
                <Globe className="w-4 h-4" />
              </div>
              <div>
                <span className="font-semibold text-xs text-white block">Город афиши</span>
                <span className="text-[10px] text-[#8e9192]">
                  Текущий выбор: г. {cityName}
                </span>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-[#8e9192]" />
          </button>

          <div className="w-full p-4 flex items-center justify-between text-left">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-[#4edea3]">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <div>
                <span className="font-semibold text-xs text-white block">Уведомления в Telegram</span>
                <span className="text-[10px] text-[#8e9192]">
                  Активированы в @Ivently_bot
                </span>
              </div>
            </div>
            <span className="text-[11px] font-semibold text-[#4edea3]">Вкл</span>
          </div>

          {isAdmin && onOpenAdminPanel && (
            <button
              onClick={() => {
                telegram.hapticImpact('light');
                onOpenAdminPanel();
                onClose();
              }}
              className="w-full p-4 flex items-center justify-between hover:bg-white/5 active:bg-white/10 transition-colors text-left"
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-[#10b981]/20 border border-[#10b981]/30 flex items-center justify-center text-[#4edea3]">
                  <Shield className="w-4 h-4" />
                </div>
                <div>
                  <span className="font-semibold text-xs text-white block">Панель модератора</span>
                  <span className="text-[10px] text-[#4edea3]">Управление событиями платформы</span>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-[#8e9192]" />
            </button>
          )}
        </section>

        {/* Organizer Workspace Banner */}
        <section className="p-4 rounded-3xl bg-[#1c1b1e] border border-white/10 relative overflow-hidden shadow-lg space-y-3">
          <div className="flex items-center justify-between">
            <span className="px-2.5 py-0.5 rounded-full bg-white/10 text-white font-bold text-[10px] uppercase tracking-wider border border-white/10">
              ДЛЯ ОРГАНИЗАТОРОВ
            </span>
            <Store className="w-5 h-5 text-[#8e9192]" />
          </div>

          <div className="space-y-1">
            <h3 className="font-bold text-sm text-white">
              Организуете мероприятия?
            </h3>
            <p className="text-xs text-[#c4c7c8] leading-relaxed">
              Управляйте афишей, собирайте базу гостей и запускайте рассылки напрямую в Telegram.
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              telegram.hapticImpact('medium');
              onOpenOrganizerWorkspace();
              onClose();
            }}
            className="w-full py-2.5 px-4 rounded-full bg-white text-black font-semibold text-xs shadow-md transition-all active:scale-98 flex items-center justify-center gap-1.5"
          >
            <span>В кабинет организатора</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </section>
      </main>
    </div>
  );
};
