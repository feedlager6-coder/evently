import React, { useRef, useState, useEffect, useLayoutEffect, useCallback } from 'react';
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
  const indicatorWrapperRef = useRef<HTMLDivElement>(null);
  const indicatorInnerRef = useRef<HTMLDivElement>(null);

  const [isReady, setIsReady] = useState(false);
  const [layout, setLayout] = useState<{ top: number; height: number; left: number; width: number }>({
    top: 0,
    height: 0,
    left: 0,
    width: 0,
  });

  const isInitialMountRef = useRef(true);
  const currentLeftRef = useRef<number>(0);
  const currentWidthRef = useRef<number>(0);
  const velocityLeftRef = useRef<number>(0);
  const velocityWidthRef = useRef<number>(0);
  const rafIdRef = useRef<number | null>(null);

  // Gesture tracking refs
  const isDraggingRef = useRef(false);
  const startXRef = useRef(0);
  const startYRef = useRef(0);
  const hasMovedRef = useRef(false);
  const dragHoveredValRef = useRef<T>(value);

  // 60 FPS Physics Spring with Inertia Overshoot & Settle Recoil Wobble
  const animateSpringTo = useCallback((targetLeft: number, targetWidth: number, initialVelLeft = 0) => {
    if (rafIdRef.current) {
      cancelAnimationFrame(rafIdRef.current);
    }

    let lastTime = performance.now();
    let posLeft = currentLeftRef.current;
    let velLeft = initialVelLeft || velocityLeftRef.current;
    let posWidth = currentWidthRef.current;
    let velWidth = velocityWidthRef.current;

    const stiffness = 280;
    const damping = 22;
    let arrivalTime: number | null = null;

    const step = (now: number) => {
      const dt = Math.min((now - lastTime) / 1000, 0.032);
      lastTime = now;

      // Spring physics for position
      const distLeft = posLeft - targetLeft;
      const forceLeft = -stiffness * distLeft - damping * velLeft;
      velLeft += forceLeft * dt;
      posLeft += velLeft * dt;
      currentLeftRef.current = posLeft;
      velocityLeftRef.current = velLeft;

      // Spring physics for width
      const distWidth = posWidth - targetWidth;
      const forceWidth = -stiffness * distWidth - (damping + 4) * velWidth;
      velWidth += forceWidth * dt;
      posWidth += velWidth * dt;
      currentWidthRef.current = posWidth;
      velocityWidthRef.current = velWidth;

      // Detect arrival phase near target position
      if (arrivalTime === null && Math.abs(distLeft) < 6) {
        arrivalTime = now;
      }

      // Compute liquid inertia & settle recoil wobble ("потряхивание при торможении")
      let scaleX = 1;
      let scaleY = 1;

      if (arrivalTime !== null) {
        const elapsed = (now - arrivalTime) / 1000;
        // High-frequency damped settle ripple
        const ripple = Math.sin(elapsed * 28) * Math.exp(-elapsed * 8.5) * 0.045;
        scaleX = 1 + ripple;
        scaleY = 1 - ripple * 0.65;
      } else {
        // Fluid elongation in direction of travel
        const stretch = Math.min(0.06, Math.abs(velLeft) * 0.0008);
        scaleX = 1 + stretch;
        scaleY = 1 - stretch * 0.6;
      }

      // Direct GPU Compositor update at 60/120 FPS
      if (indicatorWrapperRef.current) {
        indicatorWrapperRef.current.style.transform = `translate3d(${posLeft.toFixed(2)}px, 0, 0)`;
        indicatorWrapperRef.current.style.width = `${Math.max(12, posWidth).toFixed(2)}px`;
      }
      if (indicatorInnerRef.current) {
        indicatorInnerRef.current.style.transform = `scale3d(${scaleX.toFixed(4)}, ${scaleY.toFixed(4)}, 1)`;
      }

      // Settle termination criteria
      const settled =
        Math.abs(distLeft) < 0.2 &&
        Math.abs(velLeft) < 1 &&
        Math.abs(distWidth) < 0.2 &&
        (arrivalTime === null || now - arrivalTime > 280);

      if (settled) {
        currentLeftRef.current = targetLeft;
        currentWidthRef.current = targetWidth;
        velocityLeftRef.current = 0;
        velocityWidthRef.current = 0;

        if (indicatorWrapperRef.current) {
          indicatorWrapperRef.current.style.transform = `translate3d(${targetLeft}px, 0, 0)`;
          indicatorWrapperRef.current.style.width = `${targetWidth}px`;
        }
        if (indicatorInnerRef.current) {
          indicatorInnerRef.current.style.transform = 'scale3d(1, 1, 1)';
        }
        rafIdRef.current = null;
        return;
      }

      rafIdRef.current = requestAnimationFrame(step);
    };

    rafIdRef.current = requestAnimationFrame(step);
  }, []);

  // Update layout and trigger animation
  useLayoutEffect(() => {
    const activeButton = buttonRefs.current.get(value);
    if (!activeButton) return;

    const left = activeButton.offsetLeft;
    const top = activeButton.offsetTop;
    const width = activeButton.offsetWidth;
    const height = activeButton.offsetHeight;

    if (isInitialMountRef.current) {
      isInitialMountRef.current = false;
      currentLeftRef.current = left;
      currentWidthRef.current = width;
      setLayout({ top, height, left, width });
      setIsReady(true);
      return;
    }

    setLayout((prev) => ({ ...prev, top, height }));

    // Launch 60 FPS physics spring if not currently user-dragging
    if (!isDraggingRef.current) {
      animateSpringTo(left, width);
    }

    if (scrollable) {
      activeButton.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
        inline: 'nearest',
      });
    }
  }, [value, items, scrollable, animateSpringTo]);

  // Handle window/container resize without spring lag
  useEffect(() => {
    const handleResize = () => {
      const activeButton = buttonRefs.current.get(value);
      if (!activeButton) return;

      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }

      const left = activeButton.offsetLeft;
      const top = activeButton.offsetTop;
      const width = activeButton.offsetWidth;
      const height = activeButton.offsetHeight;

      currentLeftRef.current = left;
      currentWidthRef.current = width;
      velocityLeftRef.current = 0;
      velocityWidthRef.current = 0;

      setLayout({ top, height, left, width });

      if (indicatorWrapperRef.current) {
        indicatorWrapperRef.current.style.transform = `translate3d(${left}px, 0, 0)`;
        indicatorWrapperRef.current.style.width = `${width}px`;
      }
      if (indicatorInnerRef.current) {
        indicatorInnerRef.current.style.transform = 'scale3d(1, 1, 1)';
      }
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
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, [value]);

  // Pointer drag gestures
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    const container = containerRef.current;
    if (!container) return;

    startXRef.current = e.clientX;
    startYRef.current = e.clientY;
    hasMovedRef.current = false;
    isDraggingRef.current = false;
    dragHoveredValRef.current = value;

    // Subtle tactile expansion on touch down
    if (indicatorInnerRef.current) {
      indicatorInnerRef.current.style.transform = 'scale3d(1.06, 1.05, 1)';
    }
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const container = containerRef.current;
    if (!container) return;

    const deltaX = Math.abs(e.clientX - startXRef.current);
    const deltaY = Math.abs(e.clientY - startYRef.current);

    // If moving more vertically before engaging drag, allow normal scroll
    if (!isDraggingRef.current && deltaY > deltaX && deltaY > 7) {
      if (!rafIdRef.current && indicatorInnerRef.current) {
        indicatorInnerRef.current.style.transform = 'scale3d(1, 1, 1)';
      }
      return;
    }

    // Engage horizontal drag gesture
    if (!isDraggingRef.current && deltaX > 6) {
      isDraggingRef.current = true;
      hasMovedRef.current = true;

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
    const relativeX = e.clientX - rect.left;

    // Find closest button/item to current pointer X
    let closestItem = items[0];
    let minDistance = Infinity;

    for (const item of items) {
      const btn = buttonRefs.current.get(item.value);
      if (!btn) continue;
      const btnCenter = btn.offsetLeft + btn.offsetWidth / 2;
      const dist = Math.abs(relativeX - btnCenter);
      if (dist < minDistance) {
        minDistance = dist;
        closestItem = item;
      }
    }

    const targetBtn = buttonRefs.current.get(closestItem.value);
    const targetWidth = targetBtn ? targetBtn.offsetWidth : currentWidthRef.current;

    // Fluid drag position clamped to container bounds
    const maxLeft = Math.max(0, container.clientWidth - targetWidth);
    const rawLeft = relativeX - targetWidth / 2;
    const dragLeft = Math.max(0, Math.min(maxLeft, rawLeft));

    currentLeftRef.current = dragLeft;
    currentWidthRef.current = targetWidth;

    if (indicatorWrapperRef.current) {
      indicatorWrapperRef.current.style.transform = `translate3d(${dragLeft.toFixed(2)}px, 0, 0)`;
      indicatorWrapperRef.current.style.width = `${targetWidth}px`;
    }
    if (indicatorInnerRef.current) {
      // Playful slightly enlarged lens during drag ("живая, играет")
      indicatorInnerRef.current.style.transform = 'scale3d(1.07, 1.05, 1)';
    }

    if (closestItem.value !== dragHoveredValRef.current) {
      dragHoveredValRef.current = closestItem.value;
      telegram.hapticSelection();
    }
  };

  const finishGesture = (e: React.PointerEvent<HTMLDivElement>) => {
    if (isDraggingRef.current) {
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {}

      isDraggingRef.current = false;

      const finalVal = dragHoveredValRef.current;
      const finalBtn = buttonRefs.current.get(finalVal);

      if (finalBtn) {
        // Spring smoothly into the slot from finger release position
        animateSpringTo(finalBtn.offsetLeft, finalBtn.offsetWidth);
      }

      if (finalVal !== value) {
        if (hapticFeedback) {
          telegram.hapticImpact('light');
        }
        onChange(finalVal);
      }
    } else {
      if (!rafIdRef.current && indicatorInnerRef.current) {
        indicatorInnerRef.current.style.transform = 'scale3d(1, 1, 1)';
      }
    }
  };

  const handleSelect = (itemValue: T) => {
    if (hasMovedRef.current) return;

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
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={finishGesture}
      onPointerCancel={finishGesture}
      className={`relative ${
        scrollable ? 'inline-flex min-w-full' : 'flex'
      } items-center rounded-full bg-[#141724]/70 p-1 border border-white/8 select-none touch-none ${
        scrollable ? '' : className
      }`}
    >
      {/* Sliding Active Pill Indicator (60 FPS Hardware Spring with Recoil Wobble) */}
      <div
        ref={indicatorWrapperRef}
        className={`absolute pointer-events-none will-change-transform ${
          isReady ? 'opacity-100' : 'opacity-0'
        }`}
        style={{
          top: `${layout.top}px`,
          height: `${layout.height}px`,
          left: 0,
          width: `${layout.width}px`,
          transform: `translate3d(${layout.left}px, 0, 0)`,
        }}
        aria-hidden="true"
      >
        <div
          ref={indicatorInnerRef}
          data-element="segmented-indicator"
          className="w-full h-full rounded-full will-change-transform"
        />
      </div>

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
            } transition-colors duration-150 outline-none focus-visible:ring-1 focus-visible:ring-indigo-400 select-none cursor-pointer ${
              isActive ? 'text-white' : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <span className={scrollable || !equalWidth ? 'whitespace-nowrap' : 'truncate'}>{item.label}</span>

            {/* Optional Ping Dot */}
            {item.badgePing && (
              <span className="w-2 h-2 rounded-full bg-red-500 absolute top-1.5 right-1.5 animate-ping" />
            )}

            {/* Optional Count Badge */}
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

export default AnimatedSegmentedControl;
