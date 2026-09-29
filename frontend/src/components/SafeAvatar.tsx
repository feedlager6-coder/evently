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

export const SafeAvatar: React.FC<SafeAvatarProps> = ({
  src,
  name = '',
  alt,
  className = '',
  sizeClassName = 'w-full h-full',
  type = 'org',
}) => {
  const [imageState, setImageState] = useState<'loading' | 'loaded' | 'error'>('loading');

  // Reset state if src changes
  useEffect(() => {
    if (src && src.trim()) {
      setImageState('loading');
    } else {
      setImageState('error');
    }
  }, [src]);

  const initials = name.trim() ? name.trim().slice(0, 2).toUpperCase() : '';

  const renderFallback = () => {
    return (
      <div
        className={`w-full h-full bg-gradient-to-tr from-indigo-900 to-purple-900 flex items-center justify-center text-indigo-300 font-bold select-none ${className}`}
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

  if (!src || !src.trim() || imageState === 'error') {
    return renderFallback();
  }

  return (
    <div className={`relative overflow-hidden ${sizeClassName} ${className}`}>
      {/* Loading Skeleton / Gradient */}
      {imageState === 'loading' && (
        <div className="absolute inset-0 bg-[#171B29] animate-pulse flex items-center justify-center">
          <span className="text-gray-600 text-xs font-bold">{initials}</span>
        </div>
      )}

      <img
        src={src}
        alt={alt || name}
        loading="lazy"
        onLoad={() => setImageState('loaded')}
        onError={() => {
          console.warn('[Ivently Media] Avatar image failed to load, switching to graceful fallback:', src);
          setImageState('error');
        }}
        className={`w-full h-full object-cover transition-opacity duration-200 ${
          imageState === 'loaded' ? 'opacity-100' : 'opacity-0'
        }`}
      />
    </div>
  );
};
