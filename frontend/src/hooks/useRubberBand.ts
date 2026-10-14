import React, { useRef, useState, useCallback } from 'react';
import { telegram } from '../services/telegram';

interface UseRubberBandOptions {
  maxDrag?: number;
  onRefresh?: () => Promise<void> | void;
}

export function useRubberBand({ maxDrag = 75, onRefresh }: UseRubberBandOptions = {}) {
  const [pullDistance, setPullDistance] = useState(0);
  const [isPulling, setIsPulling] = useState(false);
  const startYRef = useRef(0);
  const isDraggingRef = useRef(false);
  const hasTriggeredHapticRef = useRef(false);

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    const scrollY = window.scrollY || document.documentElement.scrollTop || 0;
    if (scrollY <= 0) {
      startYRef.current = e.touches[0].clientY;
      isDraggingRef.current = true;
      hasTriggeredHapticRef.current = false;
    } else {
      isDraggingRef.current = false;
    }
  }, []);

  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (!isDraggingRef.current) return;
    const currentY = e.touches[0].clientY;
    const rawDelta = currentY - startYRef.current;

    const scrollY = window.scrollY || document.documentElement.scrollTop || 0;
    if (scrollY > 0) {
      isDraggingRef.current = false;
      setPullDistance(0);
      setIsPulling(false);
      return;
    }

    if (rawDelta > 0) {
      // Elastic resistance curve (iOS standard exponential decay)
      const damped = Math.min(maxDrag, Math.pow(rawDelta, 0.72) * 2.2);
      setPullDistance(damped);
      setIsPulling(true);

      if (damped > 45 && !hasTriggeredHapticRef.current) {
        telegram.hapticImpact('light');
        hasTriggeredHapticRef.current = true;
      }
    } else {
      setPullDistance(0);
      setIsPulling(false);
    }
  }, [maxDrag]);

  const onTouchEnd = useCallback(() => {
    if (!isDraggingRef.current) return;
    isDraggingRef.current = false;
    setIsPulling(false);

    if (pullDistance > 50 && onRefresh) {
      telegram.hapticImpact('medium');
      onRefresh();
    }

    setPullDistance(0);
    hasTriggeredHapticRef.current = false;
  }, [pullDistance, onRefresh]);

  const style: React.CSSProperties = {
    transform: pullDistance > 0 ? `translate3d(0, ${pullDistance}px, 0)` : 'none',
    transition: isPulling ? 'none' : 'transform 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
    willChange: isPulling ? 'transform' : 'auto',
  };

  return {
    pullDistance,
    isPulling,
    containerProps: {
      onTouchStart,
      onTouchMove,
      onTouchEnd,
    },
    style,
  };
}
