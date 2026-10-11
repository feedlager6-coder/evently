import React, { type ReactNode } from 'react';

export interface LiquidGlassLensProps {
  children?: ReactNode;
  className?: string;
  active?: boolean;
  radius?: number | string;
  elevation?: 'subtle' | 'standard' | 'high';
  onClick?: () => void;
  role?: string;
  'aria-label'?: string;
  'aria-selected'?: boolean;
}

/**
 * Optical Liquid Glass Lens Primitive
 *
 * Simulates physical polished glass lens with:
 * - Crisp specular top-edge lip (inset highlight)
 * - Soft contact bottom shadow
 * - 135-degree diagonal light sheen
 * - Translucent body tint with backdrop blur
 */
export const LiquidGlassLens: React.FC<LiquidGlassLensProps> = ({
  children,
  className = '',
  active = false,
  radius = 9999,
  onClick,
  role,
  'aria-label': ariaLabel,
  'aria-selected': ariaSelected,
}) => {

  const borderRadius = typeof radius === 'number' ? `${radius}px` : radius;

  return (
    <div
      role={role}
      aria-label={ariaLabel}
      aria-selected={ariaSelected}
      onClick={onClick}
      style={{
        borderRadius,
      }}
      className={`liquid-lens select-none flex items-center justify-center ${
        active ? 'opacity-100' : 'opacity-85'
      } ${className}`}
    >
      <div className="relative z-10 flex items-center justify-center w-full h-full">
        {children}
      </div>
    </div>
  );
};
