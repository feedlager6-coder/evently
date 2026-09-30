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
}

export function AnimatedSegmentedControl<T extends string>({
  items,
  value,
  onChange,
  className = '',
  size = 'md',
  hapticFeedback = true,
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
      const containerRect = container.getBoundingClientRect();
      const buttonRect = activeButton.getBoundingClientRect();

      setIndicator({
        left: buttonRect.left - containerRect.left,
        top: buttonRect.top - containerRect.top,
        width: buttonRect.width,
        height: buttonRect.height,
        ready: true,
      });
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

  return (
    <div
      ref={containerRef}
      role="tablist"
      className={`relative flex rounded-2xl bg-[#141724] p-1 border border-white/5 select-none ${className}`}
    >
      {/* Sliding Active Pill Indicator */}
      <div
        className={`absolute rounded-xl bg-indigo-600 shadow-md shadow-indigo-600/25 pointer-events-none ${
          indicator.ready
            ? 'transition-[transform,width,height] duration-200 ease-out'
            : 'opacity-0'
        }`}
        style={{
          transform: `translate3d(${indicator.left}px, ${indicator.top}px, 0)`,
          width: `${indicator.width}px`,
          height: `${indicator.height}px`,
          willChange: 'transform, width, height',
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
            className={`relative z-10 flex-1 min-w-0 ${
              isSmall ? 'py-1.5 px-2 text-[10.5px]' : 'py-2 px-1 text-xs'
            } font-semibold rounded-xl flex items-center justify-center space-x-1 sm:space-x-1.5 transition-colors duration-150 outline-none focus-visible:ring-1 focus-visible:ring-indigo-400 ${
              isActive ? 'text-white' : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <span className="truncate">{item.label}</span>

            {/* Optional Ping Dot */}
            {item.badgePing && (
              <span className="w-2 h-2 rounded-full bg-red-500 absolute top-1.5 right-1.5 animate-ping" />
            )}

            {/* Optional Count Badge */}
            {typeof item.count === 'number' && (
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded-full min-w-[18px] text-center font-bold shrink-0 transition-colors duration-150 ${
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
}
