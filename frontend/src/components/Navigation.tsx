import React, { useRef, useState, useEffect, useLayoutEffect, useCallback } from 'react';
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
  const buttonRefs = useRef<Map<TabType, HTMLButtonElement>>(new Map());

  // Determine active primary tab ('organizer' maps to 'my_events' in bottom bar)
  const effectiveActiveTab: TabType =
    currentTab === 'organizer' || currentTab === 'my_events' ? 'my_events' : currentTab;

  const tabs: NavItem[] = [
    { id: 'feed', label: 'Афиша', icon: Compass },
    { id: 'my_events', label: 'Мои события', icon: Calendar },
    ...(isAdmin ? [{ id: 'admin' as TabType, label: 'Модерация', icon: Shield }] : []),
  ];

  // Indicator geometry
  const [lensStyle, setLensStyle] = useState<{
    left: number;
    width: number;
    ready: boolean;
  }>({ left: 0, width: 0, ready: false });

  // Drag interaction state
  const [isDragging, setIsDragging] = useState(false);
  const [dragHoveredTab, setDragHoveredTab] = useState<TabType | null>(null);
  const dragHoveredTabRef = useRef<TabType | null>(null);
  const isDraggingRef = useRef(false);

  // Measure tab button bounds
  const updateLensToTab = useCallback((tabId: TabType) => {
    const container = containerRef.current;
    const btn = buttonRefs.current.get(tabId);
    if (!container || !btn) return;

    const containerRect = container.getBoundingClientRect();
    const btnRect = btn.getBoundingClientRect();

    const left = btnRect.left - containerRect.left;
    const width = btnRect.width;

    setLensStyle({ left, width, ready: true });
  }, []);

  useLayoutEffect(() => {
    if (!isDraggingRef.current) {
      updateLensToTab(effectiveActiveTab);
    }
  }, [effectiveActiveTab, updateLensToTab, isAdmin]);

  useEffect(() => {
    const handleResize = () => {
      if (!isDraggingRef.current) {
        updateLensToTab(effectiveActiveTab);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [effectiveActiveTab, updateLensToTab]);

  // Find which tab button corresponds to an X coordinate
  const getTabAtX = useCallback(
    (clientX: number): TabType | null => {
      for (const tab of tabs) {
        const btn = buttonRefs.current.get(tab.id);
        if (btn) {
          const rect = btn.getBoundingClientRect();
          if (clientX >= rect.left && clientX <= rect.right) {
            return tab.id;
          }
        }
      }
      // Clamping fallback: if beyond leftmost or rightmost
      const firstBtn = buttonRefs.current.get(tabs[0].id);
      const lastBtn = buttonRefs.current.get(tabs[tabs.length - 1].id);
      if (firstBtn && clientX < firstBtn.getBoundingClientRect().left) {
        return tabs[0].id;
      }
      if (lastBtn && clientX > lastBtn.getBoundingClientRect().right) {
        return tabs[tabs.length - 1].id;
      }
      return null;
    },
    [tabs]
  );

  // Pointer drag gestures
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    const container = containerRef.current;
    if (!container) return;

    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {}

    isDraggingRef.current = true;
    setIsDragging(true);

    const targetTab = getTabAtX(e.clientX) || effectiveActiveTab;
    dragHoveredTabRef.current = targetTab;
    setDragHoveredTab(targetTab);

    // Position lens smoothly under finger
    const containerRect = container.getBoundingClientRect();
    const btn = buttonRefs.current.get(targetTab);
    const width = btn ? btn.offsetWidth : lensStyle.width;
    const left = Math.max(
      4,
      Math.min(containerRect.width - width - 4, e.clientX - containerRect.left - width / 2)
    );
    setLensStyle({ left, width, ready: true });
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDraggingRef.current) return;
    const container = containerRef.current;
    if (!container) return;

    const containerRect = container.getBoundingClientRect();
    const candidateTab = getTabAtX(e.clientX);

    if (candidateTab && candidateTab !== dragHoveredTabRef.current) {
      dragHoveredTabRef.current = candidateTab;
      setDragHoveredTab(candidateTab);
      // Tactile feedback on passing into a new tab in Telegram
      telegram.hapticSelection();
    }

    const currentTabToUse = candidateTab || dragHoveredTabRef.current || effectiveActiveTab;
    const btn = buttonRefs.current.get(currentTabToUse);
    const width = btn ? btn.offsetWidth : lensStyle.width;
    const left = Math.max(
      4,
      Math.min(containerRect.width - width - 4, e.clientX - containerRect.left - width / 2)
    );

    setLensStyle((prev) => ({ ...prev, left, width }));
  };

  const finishGesture = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDraggingRef.current) return;
    isDraggingRef.current = false;
    setIsDragging(false);

    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {}

    const finalTab = dragHoveredTabRef.current || effectiveActiveTab;
    setDragHoveredTab(null);
    dragHoveredTabRef.current = null;

    // Snap to the chosen tab
    updateLensToTab(finalTab);

    if (finalTab !== effectiveActiveTab) {
      telegram.hapticImpact('light');
      onChangeTab(finalTab);
    }
  };

  const handleTabClick = (tabId: TabType) => {
    if (tabId !== effectiveActiveTab) {
      telegram.hapticImpact('light');
      onChangeTab(tabId);
    }
    updateLensToTab(tabId);
  };

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
        className="relative flex items-center justify-around max-w-lg mx-auto touch-none select-none"
      >
        {/* Sliding Liquid Glass Lens */}
        <div
          data-element="nav-sliding-lens"
          className={`absolute top-0.5 bottom-0.5 rounded-full pointer-events-none ${
            isDragging
              ? 'transition-none scale-[1.03]'
              : 'transition-[transform,width] duration-250 ease-[cubic-bezier(0.16,1,0.3,1)]'
          } ${lensStyle.ready ? 'opacity-100' : 'opacity-0'}`}
          style={{
            width: `${lensStyle.width}px`,
            transform: `translate3d(${lensStyle.left}px, 0, 0)`,
            willChange: 'transform, width',
          }}
          aria-hidden="true"
        />

        {/* Tab Buttons */}
        {tabs.map((tab) => {
          const isActive = tab.id === effectiveActiveTab;
          const isHoveredDuringDrag = isDragging && tab.id === dragHoveredTab;
          const Icon = tab.icon;

          return (
            <button
              key={tab.id}
              ref={(el) => {
                if (el) buttonRefs.current.set(tab.id, el);
                else buttonRefs.current.delete(tab.id);
              }}
              data-element={isActive ? 'nav-tab-active' : undefined}
              data-active={isActive ? 'true' : 'false'}
              onClick={() => handleTabClick(tab.id)}
              type="button"
              className={`relative z-10 flex flex-col items-center py-1.5 px-5 rounded-full select-none cursor-pointer touch-none transition-colors duration-150 ${
                isActive
                  ? 'text-indigo-400 font-semibold'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
              aria-label={tab.label}
            >
              <Icon
                className={`w-5 h-5 mb-0.5 transition-transform duration-200 ease-[cubic-bezier(0.34,1.56,0.64,1)] ${
                  isHoveredDuringDrag
                    ? 'scale-[1.22] -translate-y-1 text-indigo-300'
                    : isActive
                    ? 'scale-105 stroke-[2.25]'
                    : 'scale-100 stroke-2'
                }`}
              />
              <span
                className={`text-[10px] tracking-tight transition-transform duration-150 ${
                  isHoveredDuringDrag ? 'scale-105 font-bold text-white' : ''
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
