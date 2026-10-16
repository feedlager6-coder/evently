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
  const [currentSrc, setCurrentSrc] = useState<string>(src && src.trim() ? src.trim() : fallbackSrc);
  const [isError, setIsError] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    // Immediately replace known 404 / dead Unsplash URLs to avoid waiting for SSL handshake timeout
    const clean = src && src.trim() ? src.trim() : '';
    if (!clean || clean.includes('photo-1520523839898-50712140e698')) {
      setCurrentSrc(fallbackSrc);
      setIsError(false);
      setIsLoaded(false);
      return;
    }
    setCurrentSrc(clean);
    setIsError(false);
    setIsLoaded(false);
  }, [src, fallbackSrc]);

  const handleError = () => {
    console.warn('[Ivently Media] Image failed to load:', currentSrc);
    if (currentSrc !== fallbackSrc) {
      setCurrentSrc(fallbackSrc);
      setIsLoaded(false);
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
    <div className="relative w-full h-full overflow-hidden bg-gradient-to-br from-[#1a1a1d] via-[#141416] to-[#0c0c0e]">
      <img
        src={currentSrc}
        alt={alt}
        loading={loading}
        onLoad={() => setIsLoaded(true)}
        onError={handleError}
        className={`${className} transition-opacity duration-300 ease-out ${
          isLoaded ? 'opacity-100' : 'opacity-0'
        }`}
      />
    </div>
  );
};
