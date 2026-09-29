import React, { useState, useEffect } from 'react';
import { Compass } from 'lucide-react';

const DEFAULT_EVENT_FALLBACK = 'https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?w=800';

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
  loading = 'lazy',
}) => {
  const [currentSrc, setCurrentSrc] = useState<string>(src || fallbackSrc);
  const [isLoaded, setIsLoaded] = useState(false);
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    setCurrentSrc(src && src.trim() ? src.trim() : fallbackSrc);
    setIsLoaded(false);
    setIsError(false);
  }, [src, fallbackSrc]);

  const handleError = () => {
    console.warn('[Ivently Media] Image failed to load:', currentSrc);
    if (currentSrc !== fallbackSrc) {
      // Try fallback source once
      setCurrentSrc(fallbackSrc);
    } else {
      setIsError(true);
    }
  };

  if (isError) {
    return (
      <div className={`w-full h-full bg-[#121624] flex items-center justify-center text-indigo-400/40 ${className}`}>
        <Compass className="w-10 h-10 opacity-30" />
      </div>
    );
  }

  return (
    <img
      src={currentSrc}
      alt={alt}
      loading={loading}
      onLoad={() => setIsLoaded(true)}
      onError={handleError}
      className={`${className} transition-opacity duration-300 ${isLoaded ? 'opacity-100' : 'opacity-60'}`}
    />
  );
};
