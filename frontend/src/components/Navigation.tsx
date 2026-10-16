import React from 'react';
import { Sparkles, Ticket, Shield } from 'lucide-react';
import { telegram } from '../services/telegram';

export type TabType = 'feed' | 'my_events' | 'admin' | 'organizer';

interface NavigationProps {
  currentTab: TabType;
  onChangeTab: (tab: TabType) => void;
  isAdmin: boolean;
}

export const Navigation: React.FC<NavigationProps> = ({
  currentTab,
  onChangeTab,
  isAdmin,
}) => {
  const lastTouchTimeRef = React.useRef<number>(0);

  const handleTouchStart = (_e: React.TouchEvent, tab: TabType) => {
    lastTouchTimeRef.current = Date.now();
    handleTabAction(tab);
  };

  const handleClick = (tab: TabType) => {
    if (Date.now() - lastTouchTimeRef.current < 500) return;
    handleTabAction(tab);
  };

  const handleTabAction = (tab: TabType) => {
    if (tab === 'feed' && currentTab === 'feed') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    if (tab !== currentTab) {
      telegram.hapticSelection();
      onChangeTab(tab);
    }
  };

  const isFeedActive = currentTab === 'feed';
  const isMyEventsActive = currentTab === 'my_events' || currentTab === 'organizer';
  const isAdminActive = currentTab === 'admin';

  // 0: feed, 1: my_events, 2: admin
  const activeIndex = isFeedActive ? 0 : isMyEventsActive ? 1 : isAdminActive ? 2 : 0;
  const totalTabs = isAdmin ? 3 : 2;

  const buttonStyle: React.CSSProperties = {
    touchAction: 'manipulation',
    userSelect: 'none',
    WebkitTapHighlightColor: 'transparent',
    cursor: 'pointer',
  };

  return (
    <nav className="fixed bottom-0 inset-x-0 z-50 pb-safe pointer-events-none">
      <div className="max-w-[480px] mx-auto px-4 pb-3 pt-1 flex justify-center">
        <div
          style={{ touchAction: 'manipulation' }}
          className={`pointer-events-auto relative flex items-center p-1.5 h-16 w-full ${
            isAdmin ? 'max-w-[380px]' : 'max-w-[280px]'
          } rounded-full bg-[#0e0e10]/90 backdrop-blur-2xl border border-white/12 shadow-[inset_0_1px_1px_0_rgba(255,255,255,0.15),0_12px_36px_rgba(0,0,0,0.75)]`}
        >
          {/* 60 FPS Hardware-Accelerated Sliding Optical Lens Indicator */}
          <div
            className="absolute top-1.5 bottom-1.5 left-1.5 rounded-full bg-[#39393b]/80 backdrop-blur-2xl border border-white/15 shadow-[inset_0_1px_2px_rgba(255,255,255,0.35),inset_0_-1px_1px_rgba(0,0,0,0.6),0_0_16px_rgba(255,255,255,0.1)] pointer-events-none"
            style={{
              width: `calc((100% - 12px) / ${totalTabs})`,
              transform: `translate3d(calc(${activeIndex} * 100%), 0, 0)`,
              transition: 'transform 300ms cubic-bezier(0.16, 1, 0.3, 1)',
              willChange: 'transform',
            }}
          />

          {/* Feed Tab */}
          <button
            style={buttonStyle}
            onTouchStart={(e) => handleTouchStart(e, 'feed')}
            onClick={() => handleClick('feed')}
            className={`relative z-10 flex-1 h-full rounded-full flex flex-col items-center justify-center gap-0.5 transition-colors duration-200 active:scale-95 min-h-[44px] cursor-pointer ${
              isFeedActive ? 'text-white font-semibold' : 'text-[#8e9192] hover:text-[#c4c7c8]'
            }`}
            aria-label="Афиша"
            aria-current={isFeedActive ? 'page' : undefined}
          >
            <Sparkles className={`w-5 h-5 mb-0.5 transition-transform duration-200 ${isFeedActive ? 'scale-105 text-[#4edea3]' : 'opacity-70'}`} />
            <span className="text-[11px] font-bold tracking-[0.06em] leading-none">Афиша</span>
          </button>

          {/* My Events Tab (Personal Hub) */}
          <button
            style={buttonStyle}
            onTouchStart={(e) => handleTouchStart(e, 'my_events')}
            onClick={() => handleClick('my_events')}
            className={`relative z-10 flex-1 h-full rounded-full flex flex-col items-center justify-center gap-0.5 transition-colors duration-200 active:scale-95 min-h-[44px] cursor-pointer ${
              isMyEventsActive ? 'text-white font-semibold' : 'text-[#8e9192] hover:text-[#c4c7c8]'
            }`}
            aria-label="Мои события"
            aria-current={isMyEventsActive ? 'page' : undefined}
          >
            <Ticket className={`w-5 h-5 mb-0.5 transition-transform duration-200 ${isMyEventsActive ? 'scale-105 text-[#4edea3]' : 'opacity-70'}`} />
            <span className="text-[11px] font-bold tracking-[0.06em] leading-none">Мои события</span>
          </button>

          {/* Admin Tab (only if admin) */}
          {isAdmin && (
            <button
              style={buttonStyle}
              onTouchStart={(e) => handleTouchStart(e, 'admin')}
              onClick={() => handleClick('admin')}
              className={`relative z-10 flex-1 h-full rounded-full flex flex-col items-center justify-center gap-0.5 transition-colors duration-200 active:scale-95 min-h-[44px] cursor-pointer ${
                isAdminActive ? 'text-white font-semibold' : 'text-[#8e9192] hover:text-[#c4c7c8]'
              }`}
              aria-label="Модерация"
              aria-current={isAdminActive ? 'page' : undefined}
            >
              <Shield className={`w-5 h-5 mb-0.5 transition-transform duration-200 ${isAdminActive ? 'scale-105 text-[#ffb95f]' : 'opacity-70'}`} />
              <span className="text-[11px] font-bold tracking-[0.06em] leading-none">Админ</span>
            </button>
          )}
        </div>
      </div>
    </nav>
  );
};
