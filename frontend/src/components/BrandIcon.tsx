import React from 'react';
import { Compass } from 'lucide-react';

interface BrandIconProps {
  className?: string;
  iconClassName?: string;
  variant?: 'badge' | 'icon';
}

/**
 * BrandIcon — Unified source of truth for Ivently brand iconography (Compass).
 * Supports:
 * - 'badge': Signature Ivently gradient rounded squircle with crisp white Compass symbol.
 * - 'icon': Bare Compass icon with customizable size and color classes.
 */
export const BrandIcon: React.FC<BrandIconProps> = ({
  className = 'w-8 h-8',
  iconClassName = 'w-4 h-4 text-white',
  variant = 'badge',
}) => {
  if (variant === 'icon') {
    return <Compass className={iconClassName} />;
  }

  return (
    <div
      className={`rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/25 shrink-0 select-none ${className}`}
      aria-hidden="true"
    >
      <Compass className={iconClassName} />
    </div>
  );
};
