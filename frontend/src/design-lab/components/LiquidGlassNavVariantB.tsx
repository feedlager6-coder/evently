import React, { useRef, useEffect, useState } from 'react';
import { Compass, Calendar } from 'lucide-react';

export interface NavTabItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
}

export interface LiquidGlassNavProps {
  activeTab: string;
  onTabChange: (id: string) => void;
  className?: string;
}

const DEFAULT_TABS: NavTabItem[] = [
  { id: 'feed', label: 'Афиша', icon: Compass },
  { id: 'my_events', label: 'Мои события', icon: Calendar },
];

/**
 * VARIANT B: Floating Translucent Liquid Glass Dock
 *
 * Characteristics:
 * - Full translucent frosted liquid glass capsule (rgba(14, 16, 22, 0.65))
 * - Heavy backdrop blur (24px) with saturation boost (200%)
 * - Double specular highlight on dock perimeter
 * - Active tab: Secondary elevated optical glass lens inside the dock
 * - Creates a sophisticated "Lens-in-Glass" refraction depth hierarchy
 */
export const LiquidGlassNavVariantB: React.FC<LiquidGlassNavProps> = ({
  activeTab,
  onTabChange,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [lensStyle, setLensStyle] = useState({ left: 0, width: 0 });

  useEffect(() => {
    if (!containerRef.current) return;
    const activeEl = containerRef.current.querySelector(`[data-tab-id="${activeTab}"]`) as HTMLElement;
    if (activeEl) {
      setLensStyle({
        left: activeEl.offsetLeft,
        width: activeEl.offsetWidth,
      });
    }
  }, [activeTab]);

  return (
    <nav
      aria-label="Основная навигация (Вариант B: Парящее жидкое стекло)"
      className={`absolute bottom-0 left-0 right-0 z-40 pointer-events-none flex justify-center pb-6 px-4 ${className}`}
    >

      <div
        ref={containerRef}
        role="tablist"
        aria-orientation="horizontal"
        className="pointer-events-auto relative flex items-center p-1.5 rounded-full nav-dock-variant-b"
      >
        {/* Sliding Elevated Liquid Glass Lens */}
        <div
          className="dock-lens-indicator"
          style={{
            transform: `translateX(${lensStyle.left}px)`,
            width: `${lensStyle.width}px`,
          }}
          aria-hidden="true"
        />

        {/* Tab Buttons */}
        {DEFAULT_TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;

          return (
            <button
              key={tab.id}
              data-tab-id={tab.id}
              role="tab"
              aria-selected={isActive}
              aria-label={tab.label}
              onClick={() => onTabChange(tab.id)}
              className={`relative z-10 flex items-center justify-center gap-2.5 px-6 py-2.5 rounded-full text-xs font-semibold tracking-wide transition-colors duration-200 min-w-[130px] min-h-[44px] cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-white/40 ${
                isActive ? 'text-white' : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <Icon
                size={18}
                className={`transition-transform duration-300 ${
                  isActive ? 'scale-110 text-white drop-shadow-[0_2px_8px_rgba(255,255,255,0.5)]' : 'text-neutral-400'
                }`}
              />
              <span className="font-medium">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
