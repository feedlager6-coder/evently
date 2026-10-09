import React, { useRef, useEffect, useCallback } from 'react';
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
  const lensWrapperRef = useRef<HTMLDivElement>(null);
  const lensInnerRef = useRef<HTMLDivElement>(null);

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

  // Equal slot width percentage: 50% (2 tabs) or 33.333% (3 tabs)
  const slotWidthPercent = 100 / tabs.length;

  // 60 FPS Physics Spring State Refs
  const currentPosRef = useRef<number>(activeIndex);
  const velocityRef = useRef<number>(0);
  const rafIdRef = useRef<number | null>(null);

  // Pointer gesture tracking
  const startXRef = useRef<number>(0);
  const isDraggingRef = useRef(false);
  const hasMovedRef = useRef(false);
  const dragHoveredTabRef = useRef<TabType>(effectiveActiveTab);

  // Spring physics animation with inertia overshoot & settle recoil ("потряхивание при торможении")
  const animateSpringTo = useCallback((target: number, initialVelocity = 0) => {
    if (rafIdRef.current) {
      cancelAnimationFrame(rafIdRef.current);
    }

    let lastTime = performance.now();
    let pos = currentPosRef.current;
    let vel = initialVelocity;
    const stiffness = 280;
    const damping = 22;
    let arrivalTime: number | null = null;

    const step = (now: number) => {
      const dt = Math.min((now - lastTime) / 1000, 0.032);
      lastTime = now;

      const dist = pos - target;
      const force = -stiffness * dist - damping * vel;
      vel += force * dt;
      pos += vel * dt;
      currentPosRef.current = pos;
      velocityRef.current = vel;

      // Detect arrival phase near target
      if (arrivalTime === null && Math.abs(dist) < 0.14) {
        arrivalTime = now;
      }

      // 60 FPS Inertia & Settle Recoil Wobble
      let scaleX = 1;
      let scaleY = 1;

      if (arrivalTime !== null) {
        const elapsed = (now - arrivalTime) / 1000;
        // Elastic damped harmonic recoil ripple (decaying sine wave)
        const ripple = Math.sin(elapsed * 28) * Math.exp(-elapsed * 8.5) * 0.045;
        scaleX = 1 + ripple;
        scaleY = 1 - ripple * 0.65;
      } else {
        // Fluid elongation along travel direction
        const stretch = Math.min(0.06, Math.abs(vel) * 0.012);
        scaleX = 1 + stretch;
        scaleY = 1 - stretch * 0.6;
      }

      // GPU Compositor transforms (no React render cycle overhead)
      if (lensWrapperRef.current) {
        lensWrapperRef.current.style.transform = `translate3d(${pos * 100}%, 0, 0)`;
      }
      if (lensInnerRef.current) {
        lensInnerRef.current.style.transform = `scale3d(${scaleX.toFixed(4)}, ${scaleY.toFixed(4)}, 1)`;
      }

      // Settle termination criteria
      const isSettled =
        Math.abs(dist) < 0.001 &&
        Math.abs(vel) < 0.01 &&
        (arrivalTime === null || now - arrivalTime > 280);

      if (isSettled) {
        currentPosRef.current = target;
        velocityRef.current = 0;
        if (lensWrapperRef.current) {
          lensWrapperRef.current.style.transform = `translate3d(${target * 100}%, 0, 0)`;
        }
        if (lensInnerRef.current) {
          lensInnerRef.current.style.transform = 'scale3d(1, 1, 1)';
        }
        rafIdRef.current = null;
        return;
      }

      rafIdRef.current = requestAnimationFrame(step);
    };

    rafIdRef.current = requestAnimationFrame(step);
  }, []);

  // Launch spring transition when activeIndex changes
  useEffect(() => {
    if (!isDraggingRef.current) {
      animateSpringTo(activeIndex);
    }
  }, [activeIndex, animateSpringTo]);

  // Clean up RAF on unmount
  useEffect(() => {
    return () => {
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, []);

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

      // Cancel any ongoing spring animation during active drag
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }

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
    currentPosRef.current = slotPos;

    if (lensWrapperRef.current) {
      lensWrapperRef.current.style.transform = `translate3d(${slotPos * 100}%, 0, 0)`;
    }
    if (lensInnerRef.current) {
      lensInnerRef.current.style.transform = 'scale3d(1.03, 0.97, 1)';
    }

    const targetTab = tabs[targetIndex].id;
    if (targetTab !== dragHoveredTabRef.current) {
      dragHoveredTabRef.current = targetTab;
      telegram.hapticSelection();
    }
  };

  const finishGesture = (e: React.PointerEvent<HTMLDivElement>) => {
    if (isDraggingRef.current) {
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {}

      isDraggingRef.current = false;

      const finalTab = dragHoveredTabRef.current;
      const targetIndex = tabs.findIndex((t) => t.id === finalTab);
      const validTarget = targetIndex >= 0 ? targetIndex : activeIndex;

      // Spring-recoil smoothly from finger release point into the slot
      animateSpringTo(validTarget);

      if (finalTab !== effectiveActiveTab) {
        telegram.hapticImpact('light');
        onChangeTab(finalTab);
      }
    }
  };

  const handleTabClick = (tabId: TabType) => {
    if (hasMovedRef.current) return;

    if (tabId !== effectiveActiveTab) {
      telegram.hapticImpact('light');
      onChangeTab(tabId);
    }
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
        className="relative flex items-center max-w-lg mx-auto touch-none select-none h-14"
      >
        {/* Sliding Liquid Glass Slot Wrapper (60 FPS GPU-Accelerated Hardware Spring) */}
        <div
          ref={lensWrapperRef}
          className="absolute top-0 bottom-0 pointer-events-none flex items-center justify-center will-change-transform"
          style={{
            width: `${slotWidthPercent}%`,
            transform: `translate3d(${activeIndex * 100}%, 0, 0)`,
          }}
          aria-hidden="true"
        >
          {/* Liquid Glass Pill: Softly rounded squircle with inertia settle recoil */}
          <div
            ref={lensInnerRef}
            data-element="nav-sliding-lens"
            className="w-[calc(100%-10px)] h-[48px] rounded-[22px] will-change-transform"
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
              className={`relative z-10 flex flex-col items-center justify-center py-1.5 rounded-full select-none cursor-pointer touch-none transition-colors duration-200 ${
                isActive
                  ? 'text-indigo-400 font-semibold'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
              aria-label={tab.label}
            >
              <Icon
                className={`w-5 h-5 mb-1 transition-colors duration-200 ${
                  isActive ? 'stroke-[2.25] text-indigo-400' : 'stroke-2 text-gray-400'
                }`}
              />
              <span
                className={`text-[11px] font-medium tracking-tight transition-colors duration-200 ${
                  isActive ? 'text-white' : 'text-gray-400'
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
