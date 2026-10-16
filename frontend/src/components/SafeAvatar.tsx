import React, { useState, useEffect } from 'react';
import { Building2, User } from 'lucide-react';

interface SafeAvatarProps {
  src?: string | null;
  name?: string;
  alt?: string;
  className?: string;
  sizeClassName?: string;
  type?: 'org' | 'user';
}

export function resolveAvatarUrl(url?: string | null): string | undefined {
  if (!url || typeof url !== 'string' || !url.trim()) return undefined;
  const clean = url.trim();
  if (clean.startsWith('http://') || clean.startsWith('https://') || clean.startsWith('data:')) {
    return clean;
  }
  if (clean.startsWith('/')) {
    const origin = (typeof window !== 'undefined' && window.location?.origin && window.location.origin.startsWith('http'))
      ? window.location.origin.replace(/\/+$/, '')
      : 'https://iventlyapp.ru';
    return `${origin}${clean}`;
  }
  return clean;
}

export const SafeAvatar: React.FC<SafeAvatarProps> = ({
  src,
  name = '',
  alt,
  className = '',
  sizeClassName = 'w-full h-full',
  type = 'org',
}) => {
  const resolvedSrc = resolveAvatarUrl(src);
  const [imageState, setImageState] = useState<'loading' | 'loaded' | 'error'>('loading');

  // Reset state if resolvedSrc changes
  useEffect(() => {
    if (resolvedSrc) {
      setImageState('loading');
    } else {
      setImageState('error');
    }
  }, [resolvedSrc]);

  const cleanName = name.trim();
  const nameParts = cleanName.split(/\s+/).filter(Boolean);
  const initials = nameParts.length >= 2
    ? (nameParts[0][0] + nameParts[1][0]).toUpperCase()
    : cleanName.slice(0, 2).toUpperCase();
  const hasExplicitSize = /\b(w-\d+|h-\d+|size-\d+|w-\[|h-\[)/.test(className);
  const effectiveSize = sizeClassName === 'w-full h-full' && hasExplicitSize ? '' : sizeClassName;

  const renderFallback = () => {
    return (
      <div
        className={`relative overflow-hidden shrink-0 flex items-center justify-center text-white font-bold select-none bg-gradient-to-tr bg-[#2a2a2c] ${effectiveSize} ${className}`}
      >
        {initials ? (
          <span className="leading-none text-xs sm:text-sm">{initials}</span>
        ) : type === 'org' ? (
          <Building2 className="w-1/2 h-1/2 opacity-75" />
        ) : (
          <User className="w-1/2 h-1/2 opacity-75" />
        )}
      </div>
    );
  };

  if (!resolvedSrc || imageState === 'error') {
    return renderFallback();
  }

  return (
    <div className={`relative overflow-hidden shrink-0 ${effectiveSize} ${className}`}>
      {/* Loading Skeleton / Gradient */}
      {imageState === 'loading' && (
        <div className="absolute inset-0 bg-[#201f22] animate-pulse flex items-center justify-center">
          <span className="text-gray-600 text-xs font-bold">{initials}</span>
        </div>
      )}

      <img
        src={resolvedSrc}
        alt={alt || name}
        loading="eager"
        referrerPolicy="no-referrer"
        onLoad={() => setImageState('loaded')}
        onError={() => {
          console.warn('[Ivently Media] Avatar image failed to load, switching to graceful fallback:', src);
          setImageState('error');
        }}
        className={`w-full h-full max-w-full max-h-full object-cover block transition-opacity duration-200 ${
          imageState === 'loaded' ? 'opacity-100' : 'opacity-0'
        }`}
      />
    </div>
  );
};
