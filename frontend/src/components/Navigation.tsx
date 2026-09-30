import React, { useRef, useState, useEffect, useLayoutEffect } from 'react';
import { Compass, Calendar, Shield } from 'lucide-react';
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
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

  const activeKey =
    currentTab === 'admin'
      ? 'admin'
      : currentTab === 'my_events' || currentTab === 'organizer'
      ? 'my_events'
      : 'feed';

  const [indicator, setIndicator] = useState<{
    left: number;
    top: number;
    width: number;
    height: number;
    ready: boolean;
  }>({
    left: 0,
    top: 0,
    width: 0,
    height: 0,
    ready: false,
  });

  const updateIndicator = () => {
    const container = containerRef.current;
    const activeButton = buttonRefs.current.get(activeKey);

    if (container && activeButton) {
      setIndicator({
        left: activeButton.offsetLeft,
        top: activeButton.offsetTop,
        width: activeButton.offsetWidth,
        height: activeButton.offsetHeight,
        ready: true,
      });
    }
  };

  useLayoutEffect(() => {
    updateIndicator();
  }, [activeKey, isAdmin]);

  useEffect(() => {
    const handleResize = () => {
      updateIndicator();
    };

    window.addEventListener('resize', handleResize);
    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined' && containerRef.current) {
      observer = new ResizeObserver(handleResize);
      observer.observe(containerRef.current);
    }

    return () => {
      window.removeEventListener('resize', handleResize);
      observer?.disconnect();
    };
  }, [activeKey, isAdmin]);

  const handleTabClick = (tab: TabType) => {
    if (tab !== currentTab) {
      telegram.hapticImpact('light');
    }
    onChangeTab(tab);
  };

  const isMyEventsActive = activeKey === 'my_events';

  return (
    <nav className="fixed bottom-0 inset-x-0 z-40 bg-[#0E101A]/92 backdrop-blur-md border-t border-white/8 nav-safe-bottom px-4">
      <div ref={containerRef} className="relative flex items-center justify-around max-w-lg mx-auto py-1">
        {/* Sliding Active Destination Capsule */}
        <div
          className={`absolute top-0 left-0 rounded-2xl bg-indigo-500/15 border border-indigo-500/25 pointer-events-none ${
            indicator.ready
              ? 'transition-[transform,width] duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] opacity-100'
              : 'opacity-0'
          }`}
          style={{
            top: `${indicator.top}px`,
            height: `${indicator.height}px`,
            width: `${indicator.width}px`,
            transform: `translate3d(${indicator.left}px, 0, 0)`,
            willChange: 'transform, width',
          }}
          aria-hidden="true"
        />

        {/* Feed Tab */}
        <button
          ref={(el) => {
            if (el) buttonRefs.current.set('feed', el);
            else buttonRefs.current.delete('feed');
          }}
          onClick={() => handleTabClick('feed')}
          className={`relative z-10 flex flex-col items-center py-1.5 px-4 rounded-xl btn-press transition-colors duration-150 ${
            currentTab === 'feed'
              ? 'text-indigo-400 font-semibold'
              : 'text-gray-400 hover:text-gray-200'
          }`}
          aria-label="Афиша"
        >
          <Compass
            className={`w-5 h-5 mb-0.5 transition-transform duration-150 ${
              currentTab === 'feed' ? 'scale-105 stroke-[2.25]' : 'stroke-2'
            }`}
          />
          <span className="text-[10px] tracking-tight">Афиша</span>
        </button>

        {/* My Events Tab (Personal Hub) */}
        <button
          ref={(el) => {
            if (el) buttonRefs.current.set('my_events', el);
            else buttonRefs.current.delete('my_events');
          }}
          onClick={() => handleTabClick('my_events')}
          className={`relative z-10 flex flex-col items-center py-1.5 px-4 rounded-xl btn-press transition-colors duration-150 ${
            isMyEventsActive
              ? 'text-indigo-400 font-semibold'
              : 'text-gray-400 hover:text-gray-200'
          }`}
          aria-label="Мои события"
        >
          <Calendar
            className={`w-5 h-5 mb-0.5 transition-transform duration-150 ${
              isMyEventsActive ? 'scale-105 stroke-[2.25]' : 'stroke-2'
            }`}
          />
          <span className="text-[10px] tracking-tight">Мои события</span>
        </button>

        {/* Admin Tab (only if admin) */}
        {isAdmin && (
          <button
            ref={(el) => {
              if (el) buttonRefs.current.set('admin', el);
              else buttonRefs.current.delete('admin');
            }}
            onClick={() => handleTabClick('admin')}
            className={`relative z-10 flex flex-col items-center py-1.5 px-4 rounded-xl btn-press transition-colors duration-150 ${
              currentTab === 'admin'
                ? 'text-indigo-400 font-semibold'
                : 'text-gray-400 hover:text-gray-200'
            }`}
            aria-label="Модерация"
          >
            <Shield
              className={`w-5 h-5 mb-0.5 transition-transform duration-150 ${
                currentTab === 'admin' ? 'scale-105 stroke-[2.25]' : 'stroke-2'
              }`}
            />
            <span className="text-[10px] tracking-tight">Модерация</span>
          </button>
        )}
      </div>
    </nav>
  );
};
