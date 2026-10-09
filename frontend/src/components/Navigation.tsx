import React, { useRef, useState } from 'react';
import { Compass, Calendar, Shield } from 'lucide-react';
import { telegram } from '../services/telegram';

export type TabType = 'feed' | 'my_events' | 'admin' | 'organizer';

interface NavigationProps {
  currentTab: TabType;
  onChangeTab: (tab: TabType) => void;
  isAdmin: boolean;
}

interface NavItem {
  id: TabType;
  label: string;
  icon: typeof Compass;
}

export const Navigation: React.FC<NavigationProps> = ({
  currentTab,
  onChangeTab,
  isAdmin,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // Map 'organizer' to 'my_events' in bottom bar
  const effectiveActiveTab: TabType =
    currentTab === 'organizer' || currentTab === 'my_events' ? 'my_events' : currentTab;

  const tabs: NavItem[] = [
    { id: 'feed', label: 'Афиша', icon: Compass },
    { id: 'my_events', label: 'Мои события', icon: Calendar },
    ...(isAdmin ? [{ id: 'admin' as TabType, label: 'Модерация', icon: Shield }] : []),
  ];

  const activeIndex = Math.max(
    0,
    tabs.findIndex((t) => t.id === effectiveActiveTab)
  );

  // Dragging gesture state
  const [isDragging, setIsDragging] = useState(false);
  const [dragSlotProgress, setDragSlotProgress] = useState<number>(activeIndex);

  const startXRef = useRef<number>(0);
  const isDraggingRef = useRef(false);
  const hasMovedRef = useRef(false);
  const dragHoveredTabRef = useRef<TabType>(effectiveActiveTab);

  // Compute equal slot width percentage: exactly 33.333% (if 3 tabs) or 50% (if 2 tabs)
  const slotWidthPercent = 100 / tabs.length;

  // Pointer drag gestures
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    const container = containerRef.current;
    if (!container) return;

    startXRef.current = e.clientX;
    hasMovedRef.current = false;
    isDraggingRef.current = false;
    dragHoveredTabRef.current = effectiveActiveTab;
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const container = containerRef.current;
    if (!container) return;

    const deltaX = Math.abs(e.clientX - startXRef.current);

    // Only engage continuous drag if the user actually moved their finger
    if (!isDraggingRef.current && deltaX > 6) {
      isDraggingRef.current = true;
      hasMovedRef.current = true;
      setIsDragging(true);
      try {
        e.currentTarget.setPointerCapture(e.pointerId);
      } catch {}
    }

    if (!isDraggingRef.current) return;

    const rect = container.getBoundingClientRect();
    const relativeX = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    const slotWidth = rect.width / tabs.length;
    const targetIndex = Math.min(tabs.length - 1, Math.floor(relativeX / slotWidth));

    // Continuous slot progress tracking finger
    const slotPos = Math.max(0, Math.min(tabs.length - 1, relativeX / slotWidth - 0.5));
    setDragSlotProgress(slotPos);

    const targetTab = tabs[targetIndex].id;
    if (targetTab !== dragHoveredTabRef.current) {
      dragHoveredTabRef.current = targetTab;
      // Telegram tactile feedback on passing into a new tab
      telegram.hapticSelection();
    }
  };

  const finishGesture = (e: React.PointerEvent<HTMLDivElement>) => {
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {}

    if (isDraggingRef.current) {
      isDraggingRef.current = false;
      setIsDragging(false);

      const finalTab = dragHoveredTabRef.current;
      if (finalTab !== effectiveActiveTab) {
        telegram.hapticImpact('light');
        onChangeTab(finalTab);
      }
    }
  };

  const handleTabClick = (tabId: TabType) => {
    if (tabId !== effectiveActiveTab) {
      telegram.hapticImpact('light');
      onChangeTab(tabId);
    }
  };

  // Determine indicator translation:
  // When dragging: follow continuous slot progress
  // When idle: exactly activeIndex * 100%
  const currentSlotTranslation = isDragging ? dragSlotProgress * 100 : activeIndex * 100;

  return (
    <nav
      data-element="navigation"
      className="fixed bottom-0 inset-x-0 z-40 bg-[#0E101A]/92 backdrop-blur-md border-t border-white/8 nav-safe-bottom px-4 select-none touch-none"
    >
      <div
        ref={containerRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={finishGesture}
        onPointerCancel={finishGesture}
        className="relative flex items-center max-w-lg mx-auto touch-none select-none h-12"
      >
        {/* Sliding Liquid Glass Slot Wrapper (100% Mathematically Centered) */}
        <div
          className={`absolute top-0 bottom-0 pointer-events-none flex items-center justify-center ${
            isDragging
              ? 'transition-none'
              : 'transition-transform duration-280 ease-[cubic-bezier(0.16,1,0.3,1)]'
          }`}
          style={{
            width: `${slotWidthPercent}%`,
            transform: `translate3d(${currentSlotTranslation}%, 0, 0)`,
            willChange: 'transform',
          }}
          aria-hidden="true"
        >
          {/* Liquid Glass Pill: Comfortably and fully covers the tab icon and label */}
          <div
            data-element="nav-sliding-lens"
            className="w-[calc(100%-8px)] h-[44px] rounded-full"
          />
        </div>

        {/* Tab Buttons (Equally partitioned slots) */}
        {tabs.map((tab) => {
          const isActive = tab.id === effectiveActiveTab;
          const Icon = tab.icon;

          return (
            <button
              key={tab.id}
              data-element={isActive ? 'nav-tab-active' : undefined}
              data-active={isActive ? 'true' : 'false'}
              onClick={() => handleTabClick(tab.id)}
              type="button"
              style={{ width: `${slotWidthPercent}%` }}
              className={`relative z-10 flex flex-col items-center justify-center py-1 rounded-full select-none cursor-pointer touch-none transition-colors duration-200 ${
                isActive
                  ? 'text-indigo-400 font-semibold'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
              aria-label={tab.label}
            >
              <Icon
                className={`w-5 h-5 mb-0.5 transition-colors duration-200 ${
                  isActive ? 'stroke-[2.25] text-indigo-400' : 'stroke-2 text-gray-400'
                }`}
              />
              <span
                className={`text-[10.5px] tracking-tight transition-colors duration-200 ${
                  isActive ? 'font-semibold text-white' : 'font-normal text-gray-400'
                }`}
              >
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};

export default Navigation;
