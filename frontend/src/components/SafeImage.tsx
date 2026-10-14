import React, { useState, useEffect } from 'react';
import { Compass } from 'lucide-react';

const DEFAULT_EVENT_FALLBACK =
  'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500"><defs><radialGradient id="g" cx="50%" cy="40%" r="60%"><stop offset="0%" stop-color="%231a2b22"/><stop offset="60%" stop-color="%23121516"/><stop offset="100%" stop-color="%230a0a0c"/></radialGradient><linearGradient id="star" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="%234edea3"/><stop offset="100%" stop-color="%2310b981"/></linearGradient></defs><rect width="800" height="500" fill="url(%23g)"/><g transform="translate(400, 220)"><path d="M0 -45 C0 -10 10 0 45 0 C10 0 0 10 0 45 C0 10 -10 0 -45 0 C-10 0 0 -10 0 -45 Z" fill="url(%23star)" opacity="0.85"/><circle cx="0" cy="0" r="12" fill="%23ffffff" opacity="0.25"/></g><text x="400" y="310" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="20" font-weight="700" fill="%23c4c7c8" text-anchor="middle" letter-spacing="1.5">IVENTLY</text></svg>';

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
  const [currentSrc, setCurrentSrc] = useState<string>(src || fallbackSrc);
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    setCurrentSrc(src && src.trim() ? src.trim() : fallbackSrc);
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
      <div className={`w-full h-full bg-[#1c1b1e] flex items-center justify-center text-zinc-600 ${className}`}>
        <Compass className="w-8 h-8 opacity-30 text-white" />
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
