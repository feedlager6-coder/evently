import React from 'react';

interface BrandIconProps {
  className?: string;
  iconClassName?: string;
  variant?: 'badge' | 'icon';
}

/**
 * BrandIcon — Unified source of truth for Ivently brand iconography.
 * Visual concept: Minimalist black circle with a single white star.
 * No gradients, no text, no unnecessary decorative elements.
 */
export const BrandIcon: React.FC<BrandIconProps> = ({
  className = 'w-8 h-8',
  iconClassName = 'w-4 h-4',
  variant = 'badge',
}) => {
  if (variant === 'icon') {
    return (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={iconClassName}
        aria-hidden="true"
      >
        <path
          d="M12 3L14.2 9.8L21 12L14.2 14.2L12 21L9.8 14.2L3 12L9.8 9.8L12 3Z"
          fill="currentColor"
        />
      </svg>
    );
  }

  return (
    <div
      className={`rounded-full bg-black border border-white/15 flex items-center justify-center shrink-0 select-none overflow-hidden shadow-sm ${className}`}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={iconClassName}
      >
        <path
          d="M12 3L14.2 9.8L21 12L14.2 14.2L12 21L9.8 14.2L3 12L9.8 9.8L12 3Z"
          fill="#FFFFFF"
        />
      </svg>
    </div>
  );
};
