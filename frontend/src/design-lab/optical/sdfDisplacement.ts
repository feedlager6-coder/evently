/**
 * Ivently Design Lab — Optical Lens SDF Displacement & Refraction Filter
 *
 * Adapted from Inigo Quilez 2D Signed Distance Function (SDF) and
 * kucukkanat/liquid-glass (MIT License).
 *
 * Generates an SVG feDisplacementMap + feColorMatrix chromatic aberration
 * filter calibrated for mobile GPU performance.
 */

export interface DisplacementOptions {
  width: number;
  height: number;
  radius: number;
  bevelDepth?: number;
  dpr?: number;
}

/**
 * 2D Signed distance to a rounded rectangle centered at origin.
 * Negative inside the box, positive outside.
 */
function sdRoundedBox(px: number, py: number, halfW: number, halfH: number, r: number): number {
  const qx = Math.abs(px) - halfW + r;
  const qy = Math.abs(py) - halfH + r;
  const outside = Math.hypot(Math.max(qx, 0), Math.max(qy, 0));
  const inside = Math.min(Math.max(qx, qy), 0);
  return inside + outside - r;
}

/**
 * Perlin smootherstep for optical bevel curvature: 6t^5 - 15t^4 + 10t^3
 */
function smootherstep(t: number): number {
  const clamped = Math.max(0, Math.min(1, t));
  return clamped * clamped * clamped * (clamped * (clamped * 6 - 15) + 10);
}

/**
 * Generates a PNG data URL displacement map encoding surface normals.
 * Red channel = X displacement (128 = 0 neutral)
 * Green channel = Y displacement (128 = 0 neutral)
 */
export function generateDisplacementMapDataUrl({
  width,
  height,
  radius,
  bevelDepth,
  dpr = 1,
}: DisplacementOptions): string {
  if (typeof document === 'undefined') return '';

  const w = Math.max(16, Math.round(width * dpr));
  const h = Math.max(16, Math.round(height * dpr));
  const r = Math.max(2, Math.round(radius * dpr));
  const bevel = Math.max(2, Math.round((bevelDepth ?? radius) * dpr));

  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';

  const img = ctx.createImageData(w, h);
  const data = img.data;

  const halfW = w / 2;
  const halfH = h / 2;
  const eps = 1.0;

  for (let y = 0; y < h; y++) {
    const py = y - halfH;
    for (let x = 0; x < w; x++) {
      const px = x - halfW;
      const idx = (y * w + x) * 4;

      const d = sdRoundedBox(px, py, halfW, halfH, r);

      if (d > 0) {
        // Outside the lens boundary -> neutral
        data[idx] = 128;
        data[idx + 1] = 128;
        data[idx + 2] = 128;
        data[idx + 3] = 0;
        continue;
      }

      // Inside bevel band (d between -bevel and 0)
      const distFromEdge = -d;
      if (distFromEdge < bevel) {
        // Optical lens normal gradient calculation
        const dx = (sdRoundedBox(px + eps, py, halfW, halfH, r) - sdRoundedBox(px - eps, py, halfW, halfH, r)) / (2 * eps);
        const dy = (sdRoundedBox(px, py + eps, halfW, halfH, r) - sdRoundedBox(px, py - eps, halfW, halfH, r)) / (2 * eps);
        const len = Math.hypot(dx, dy) || 1;

        // Inward pull factor
        const factor = smootherstep(1 - distFromEdge / bevel);

        // Normalize and map to 0..255 (128 neutral)
        const nx = (-dx / len) * factor;
        const ny = (-dy / len) * factor;

        data[idx] = Math.round(128 + nx * 127);
        data[idx + 1] = Math.round(128 + ny * 127);
        data[idx + 2] = 128;
        data[idx + 3] = 255;
      } else {
        // Center flat zone -> neutral (zero optical distortion of critical text)
        data[idx] = 128;
        data[idx + 1] = 128;
        data[idx + 2] = 128;
        data[idx + 3] = 255;
      }
    }
  }

  ctx.putImageData(img, 0, 0);
  return canvas.toDataURL('image/png');
}

/**
 * Creates an inline SVG filter string with chromatic aberration
 */
export function buildRefractionSvgFilter(
  filterId: string,
  mapDataUrl: string,
  scale = 28,
  aberration = 3.5
): string {
  return `
<svg style="position:absolute;width:0;height:0;pointer-events:none;" aria-hidden="true">
  <defs>
    <filter id="${filterId}" x="-20%" y="-20%" width="140%" height="140%" filterUnits="objectBoundingBox">
      <feImage href="${mapDataUrl}" result="map" preserveAspectRatio="none" />
      <!-- Red channel pass -->
      <feDisplacementMap in="SourceGraphic" in2="map" scale="${scale + aberration}" xChannelSelector="R" yChannelSelector="G" result="redDisplaced" />
      <feColorMatrix in="redDisplaced" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="redPass" />
      <!-- Green channel pass -->
      <feDisplacementMap in="SourceGraphic" in2="map" scale="${scale}" xChannelSelector="R" yChannelSelector="G" result="greenDisplaced" />
      <feColorMatrix in="greenDisplaced" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="greenPass" />
      <!-- Blue channel pass -->
      <feDisplacementMap in="SourceGraphic" in2="map" scale="${Math.max(0, scale - aberration)}" xChannelSelector="R" yChannelSelector="G" result="blueDisplaced" />
      <feColorMatrix in="blueDisplaced" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="bluePass" />
      <!-- Merge passes for chromatic fringe -->
      <feBlend in="redPass" in2="greenPass" mode="screen" result="rg" />
      <feBlend in="rg" in2="bluePass" mode="screen" />
    </filter>
  </defs>
</svg>`.trim();
}
