import React, { useState, useEffect } from 'react';
import { Compass } from 'lucide-react';

const DEFAULT_EVENT_FALLBACK = '/covers/default_event.jpg';

interface SafeImageProps {
  src?: string | null;
  alt: string;
  fallbackSrc?: string;
  className?: string;
  loading?: 'lazy' | 'eager';
}

export const SafeImage: React.FC<SafeImageProps> = ({
  src,
  alt,
  fallbackSrc = DEFAULT_EVENT_FALLBACK,
  className = 'w-full h-full object-cover',
  loading = 'eager',
}) => {
  const [currentSrc, setCurrentSrc] = useState<string>(() => {
    const clean = src && src.trim() ? src.trim() : '';
    if (!clean || clean.includes('photo-1520523839898-50712140e698')) {
      return fallbackSrc;
    }
    return clean;
  });
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    const clean = src && src.trim() ? src.trim() : '';
    if (!clean || clean.includes('photo-1520523839898-50712140e698')) {
      setCurrentSrc(fallbackSrc);
      setIsError(false);
      return;
    }
    setCurrentSrc(clean);
    setIsError(false);
  }, [src, fallbackSrc]);

  const handleError = () => {
    console.warn('[Ivently Media] Image failed to load:', currentSrc);
    if (currentSrc !== fallbackSrc) {
      setCurrentSrc(fallbackSrc);
    } else {
      setIsError(true);
    }
  };

  if (isError) {
    return (
      <div className={`w-full h-full bg-[#1c1b1e] flex flex-col items-center justify-center text-zinc-500 select-none ${className}`}>
        <Compass className="w-8 h-8 opacity-40 text-emerald-400 mb-1" />
        <span className="text-[10px] uppercase font-mono tracking-wider opacity-40 text-neutral-400">Ivently</span>
      </div>
    );
  }

  return (
    <img
      src={currentSrc}
      alt={alt}
      loading={loading}
      onError={handleError}
      className={className}
    />
  );
};
