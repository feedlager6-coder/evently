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
 * GoingAnimation — Flagship RSVP micro-animation component.
 * Decoupled from RSVP business logic: allows future plug-and-play replacement
 * with dotLottie/Rive character assets without rewriting the parent modal.
 */
export const GoingAnimation: React.FC<GoingAnimationProps> = ({
  state,
  onAnimationEnd,
  size = 20,
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
      }, 550);

      return () => clearTimeout(timer);
    }
  }, [state, onAnimationEnd]);

  if (internalPhase === 'loading') {
    return <Loader2 className={`animate-spin text-white shrink-0 ${className}`} style={{ width: size, height: size }} />;
  }

  if (internalPhase === 'success') {
    return <Check className={`stroke-[3] text-white shrink-0 animate-scale-pop ${className}`} style={{ width: size, height: size }} />;
  }

  if (internalPhase === 'animating') {
    return (
      <span
        className={`relative inline-flex items-center justify-center shrink-0 ${className}`}
        style={{ width: size + 4, height: size + 4 }}
        aria-hidden="true"
      >
        {/* Dynamic Urban Spark / Stride Silhouette (SVG Micro-Rig) */}
        <svg
          viewBox="0 0 28 28"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full animate-stride-burst"
        >
          {/* Ground motion line */}
          <line
            x1="2"
            y1="25"
            x2="26"
            y2="25"
            stroke="rgba(255,255,255,0.4)"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeDasharray="4 3"
            className="animate-dash"
          />

          {/* Ivi Minimalist Character Silhouette */}
          {/* Head: Soft diamond spark */}
          <path
            d="M14 3L17.5 7.5L14 12L10.5 7.5L14 3Z"
            fill="#A78BFA"
            className="animate-sparkle"
          />
          {/* Torso: Sleek urban jacket */}
          <path
            d="M11 12H17L18.5 19H9.5L11 12Z"
            fill="#FFFFFF"
            rx="1.5"
          />
          {/* Energetic Striding Legs */}
          <path
            d="M11.5 19L9 24.5M16.5 19L19.5 24"
            stroke="#FFFFFF"
            strokeWidth="2"
            strokeLinecap="round"
            className="animate-leg-stride"
          />
          {/* Forward ticket badge in hand */}
          <rect
            x="19"
            y="13"
            width="5"
            height="3.5"
            rx="0.8"
            fill="#34D399"
            className="animate-ticket-glow"
          />
        </svg>
      </span>
    );
  }

  // Default: Idle Ticket Icon
  return <Ticket className={`shrink-0 ${className}`} style={{ width: size, height: size }} />;
};
