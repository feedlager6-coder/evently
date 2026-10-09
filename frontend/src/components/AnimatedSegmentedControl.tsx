import React, { useRef, useState, useEffect, useLayoutEffect } from 'react';
import { telegram } from '../services/telegram';

export interface SegmentedControlItem<T extends string> {
  value: T;
  label: string;
  count?: number;
  badgePing?: boolean;
}

export interface AnimatedSegmentedControlProps<T extends string> {
  items: SegmentedControlItem<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
  size?: 'sm' | 'md';
  hapticFeedback?: boolean;
  scrollable?: boolean;
  equalWidth?: boolean;
}

export function AnimatedSegmentedControl<T extends string>({
  items,
  value,
  onChange,
  className = '',
  size = 'md',
  hapticFeedback = true,
  scrollable = false,
  equalWidth = true,
}: AnimatedSegmentedControlProps<T>): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRefs = useRef<Map<T, HTMLButtonElement>>(new Map());

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
    const activeButton = buttonRefs.current.get(value);

    if (container && activeButton) {
      // Use DOM layout offsets relative to offsetParent (immune to parent animations and transforms)
      const left = activeButton.offsetLeft;
      const top = activeButton.offsetTop;
      const width = activeButton.offsetWidth;
      const height = activeButton.offsetHeight;

      setIndicator({
        left,
        top,
        width,
        height,
        ready: true,
      });

      // If scrollable, ensure the active tab is scrolled into view smoothly
      if (scrollable) {
        activeButton.scrollIntoView({
          behavior: 'smooth',
          block: 'nearest',
          inline: 'nearest',
        });
      }
    }
  };

  useLayoutEffect(() => {
    updateIndicator();
  }, [value, items]);

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
  }, [value, items]);

  const handleSelect = (itemValue: T) => {
    if (itemValue !== value) {
      if (hapticFeedback) {
        telegram.hapticImpact('light');
      }
      onChange(itemValue);
    }
  };

  const isSmall = size === 'sm';

  const controlContent = (
    <div
      ref={containerRef}
      role="tablist"
      data-element="segmented-control"
      className={`relative ${
        scrollable ? 'inline-flex min-w-full' : 'flex'
      } items-center rounded-full bg-[#141724]/70 p-1 border border-white/8 select-none ${
        scrollable ? '' : className
      }`}
    >
      {/* Sliding Active Pill Indicator */}
      <div
        data-element="segmented-indicator"
        className={`absolute top-0 left-0 rounded-xl bg-indigo-600 shadow-md shadow-indigo-600/25 pointer-events-none ${
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

      {/* Segment Buttons */}
      {items.map((item) => {
        const isActive = item.value === value;

        return (
          <button
            key={item.value}
            ref={(el) => {
              if (el) {
                buttonRefs.current.set(item.value, el);
              } else {
                buttonRefs.current.delete(item.value);
              }
            }}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => handleSelect(item.value)}
            className={`relative z-10 ${
              scrollable
                ? 'shrink-0 px-3.5 sm:px-4'
                : equalWidth
                ? 'flex-1 min-w-0 px-0.5 xs:px-1'
                : 'flex-auto min-w-fit px-2.5 sm:px-4'
            } ${
              isSmall ? 'py-1.5 text-[10.5px] xs:text-[11px]' : 'py-2 text-xs'
            } font-semibold rounded-xl flex items-center justify-center ${
              isSmall ? 'space-x-0.5 xs:space-x-1' : 'space-x-1 sm:space-x-1.5'
            } transition-all duration-150 outline-none focus-visible:ring-1 focus-visible:ring-indigo-400 active:scale-[0.95] select-none cursor-pointer ${
              isActive ? 'text-white' : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <span className={scrollable || !equalWidth ? 'whitespace-nowrap' : 'truncate'}>{item.label}</span>

            {/* Optional Ping Dot */}
            {item.badgePing && (
              <span className="w-2 h-2 rounded-full bg-red-500 absolute top-1.5 right-1.5 animate-ping" />
            )}

            {/* Optional Count Badge (Only show if count > 0 to preserve compact geometry on mobile) */}
            {typeof item.count === 'number' && item.count > 0 && (
              <span
                className={`${
                  isSmall ? 'text-[9px] px-1 py-0.2 min-w-[14px]' : 'text-[10px] px-1.5 py-0.5 min-w-[18px]'
                } rounded-full text-center font-bold shrink-0 transition-colors duration-150 ${
                  isActive
                    ? 'bg-white/20 text-white'
                    : 'bg-white/5 text-gray-400'
                }`}
              >
                {item.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );

  if (scrollable) {
    return (
      <div className={`w-full overflow-x-auto no-scrollbar py-0.5 ${className}`}>
        {controlContent}
      </div>
    );
  }

  return controlContent;
}
