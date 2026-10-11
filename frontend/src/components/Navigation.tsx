import React from 'react';
import { Sparkles, Ticket, Search, Shield } from 'lucide-react';
import { telegram } from '../services/telegram';

export type TabType = 'feed' | 'my_events' | 'admin' | 'organizer';

interface NavigationProps {
  currentTab: TabType;
  onChangeTab: (tab: TabType) => void;
  isAdmin: boolean;
  onOpenSearch?: () => void;
}

export const Navigation: React.FC<NavigationProps> = ({
  currentTab,
  onChangeTab,
  isAdmin,
  onOpenSearch,
}) => {
  const handleTabClick = (tab: TabType) => {
    if (tab !== currentTab) {
      telegram.hapticImpact('light');
    }
    onChangeTab(tab);
  };

  const isFeedActive = currentTab === 'feed';
  const isMyEventsActive = currentTab === 'my_events' || currentTab === 'organizer';
  const isAdminActive = currentTab === 'admin';

  return (
    <nav className="fixed bottom-0 inset-x-0 z-50 pb-safe pointer-events-none">
      <div className="max-w-[480px] mx-auto px-4 pb-3 pt-1 flex justify-center">
        <div className="pointer-events-auto flex items-center p-1.5 h-16 w-full rounded-full bg-[#0e0e10]/90 backdrop-blur-2xl border border-white/12 shadow-[inset_0_1px_1px_0_rgba(255,255,255,0.15),0_12px_36px_rgba(0,0,0,0.75)]">
          {/* Feed Tab */}
          <button
            onClick={() => handleTabClick('feed')}
            className={`flex-1 h-full rounded-full flex flex-col items-center justify-center gap-0.5 transition-all duration-200 active:scale-95 min-h-[44px] ${
              isFeedActive
                ? 'text-white shadow-[inset_0_1px_2px_rgba(255,255,255,0.35),0_0_16px_rgba(255,255,255,0.12)] bg-[#39393b]/70 font-semibold'
                : 'text-[#c4c7c8] hover:text-white'
            }`}
            aria-label="Афиша"
            aria-current={isFeedActive ? 'page' : undefined}
          >
            <Sparkles className="w-5 h-5 mb-0.5" />
            <span className="text-[11px] font-bold tracking-[0.06em] leading-none">Афиша</span>
          </button>

          {/* My Events Tab (Personal Hub) */}
          <button
            onClick={() => handleTabClick('my_events')}
            className={`flex-1 h-full rounded-full flex flex-col items-center justify-center gap-0.5 transition-all duration-200 active:scale-95 min-h-[44px] ${
              isMyEventsActive
                ? 'text-white shadow-[inset_0_1px_2px_rgba(255,255,255,0.35),0_0_16px_rgba(255,255,255,0.12)] bg-[#39393b]/70 font-semibold'
                : 'text-[#c4c7c8] hover:text-white'
            }`}
            aria-label="Мои события"
            aria-current={isMyEventsActive ? 'page' : undefined}
          >
            <Ticket className="w-5 h-5 mb-0.5" />
            <span className="text-[11px] font-bold tracking-[0.06em] leading-none">Мои события</span>
          </button>

          {/* Search Action matching Stitch */}
          <button
            onClick={() => {
              telegram.hapticImpact('light');
              if (onOpenSearch) onOpenSearch();
            }}
            className="flex-1 h-full rounded-full flex flex-col items-center justify-center gap-0.5 transition-all duration-200 active:scale-95 min-h-[44px] text-[#c4c7c8] hover:text-white"
            aria-label="Поиск"
          >
            <Search className="w-5 h-5 mb-0.5" />
            <span className="text-[11px] font-bold tracking-[0.06em] leading-none">Поиск</span>
          </button>

          {/* Admin Tab (only if admin) */}
          {isAdmin && (
            <button
              onClick={() => handleTabClick('admin')}
              className={`flex-1 h-full rounded-full flex flex-col items-center justify-center gap-0.5 transition-all duration-200 active:scale-95 min-h-[44px] ${
                isAdminActive
                  ? 'text-white shadow-[inset_0_1px_2px_rgba(255,255,255,0.35),0_0_16px_rgba(255,255,255,0.12)] bg-[#39393b]/70 font-semibold'
                  : 'text-[#c4c7c8] hover:text-white'
              }`}
              aria-label="Модерация"
              aria-current={isAdminActive ? 'page' : undefined}
            >
              <Shield className="w-5 h-5 mb-0.5" />
              <span className="text-[11px] font-bold tracking-[0.06em] leading-none">Админ</span>
            </button>
          )}
        </div>
      </div>
    </nav>
  );
};
