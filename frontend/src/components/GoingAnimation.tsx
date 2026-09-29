import React, { useEffect, useState } from 'react';
import { Ticket, Check, Loader2 } from 'lucide-react';

export type GoingAnimationState = 'idle' | 'loading' | 'animating' | 'success';

export interface GoingAnimationProps {
  state: GoingAnimationState;
  onAnimationEnd?: () => void;
  size?: number;
  className?: string;
}

/**
 * GoingAnimation — Micro-interaction icon for RSVP button.
 * Smoothly transitions from Ticket (idle) -> Loader (loading) -> Checkmark (animating/success)
 * without layout shifts or geometry jumps.
 */
export const GoingAnimation: React.FC<GoingAnimationProps> = ({
  state,
  onAnimationEnd,
  size = 18,
  className = '',
}) => {
  const [internalPhase, setInternalPhase] = useState<GoingAnimationState>(state);

  useEffect(() => {
    setInternalPhase(state);

    if (state === 'animating') {
      const timer = setTimeout(() => {
        setInternalPhase('success');
        if (onAnimationEnd) {
          onAnimationEnd();
        }
      }, 400);

      return () => clearTimeout(timer);
    }
  }, [state, onAnimationEnd]);

  if (internalPhase === 'loading') {
    return (
      <Loader2
        className={`animate-spin shrink-0 ${className}`}
        style={{ width: size, height: size }}
      />
    );
  }

  if (internalPhase === 'animating' || internalPhase === 'success') {
    return (
      <Check
        className={`stroke-[3] shrink-0 ${
          internalPhase === 'animating' ? 'animate-scale-pop text-emerald-400' : ''
        } ${className}`}
        style={{ width: size, height: size }}
      />
    );
  }

  // Default: Idle Ticket Icon
  return (
    <Ticket
      className={`shrink-0 ${className}`}
      style={{ width: size, height: size }}
    />
  );
};

