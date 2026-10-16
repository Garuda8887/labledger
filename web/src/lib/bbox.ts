/**
 * Map a stored result bbox onto the served page PNG, as fractions (0–1) of the displayed image.
 *
 * What the backend stores (api/app/extraction/*), as of 2026-10-15:
 *  - digital_pdf : PDF points (72/in). The served PNG is 150 DPI, so points × 150/72 = px.
 *  - scanned_pdf : OCR pixels at 200 DPI. px_png = px_ocr × 150/200.
 *  - image / multi_image: OCR pixels after preprocessing (upscaled so the long edge is >= 2000).
 *    The served file is the original, so scale = naturalLong / max(naturalLong, 2000).
 *    Perspective/deskew warps aren't invertible here, so the box is approximate.
 * Overrides:
 *  - bbox already in 0–1 → used as-is.
 *  - bbox with 6 values [x0,y0,x1,y1,pageW,pageH] → normalized by that page size (preferred, if B adds it).
 */
export interface Frac { left: number; top: number; width: number; height: number }

const PNG_DPI = 150;

export function bboxToFrac(bbox: number[] | null | undefined, sourceType: string, natW: number, natH: number): Frac | null {
  if (!bbox || bbox.length < 4 || bbox.slice(0, 4).some((n) => n == null || !Number.isFinite(n))) return null;
  let [x0, y0, x1, y1] = bbox as [number, number, number, number];
  if (x1 < x0) [x0, x1] = [x1, x0];
  if (y1 < y0) [y0, y1] = [y1, y0];

  let fx: number, fy: number;
  if (bbox.length >= 6 && bbox[4]! > 0 && bbox[5]! > 0) {
    fx = 1 / bbox[4]!; fy = 1 / bbox[5]!;
  } else if (Math.max(x0, y0, x1, y1) <= 1.0001) {
    fx = fy = 1;
  } else {
    if (!natW || !natH) return null;
    let s: number; // source coord → served PNG px
    if (sourceType === "digital_pdf") s = PNG_DPI / 72;
    else if (sourceType === "scanned_pdf") s = PNG_DPI / 200;
    else { const long = Math.max(natW, natH); s = long / Math.max(long, 2000); }
    fx = s / natW; fy = s / natH;
  }
  const pad = 0.004; // small breathing room around the text
  const f = {
    left: Math.max(0, x0 * fx - pad),
    top: Math.max(0, y0 * fy - pad),
    width: (x1 - x0) * fx + pad * 2,
    height: (y1 - y0) * fy + pad * 2,
  };
  // If it falls clearly outside the page, our coordinate guess is wrong. Hide it rather than mislead.
  if (f.left > 1 || f.top > 1 || f.left + f.width > 1.15 || f.top + f.height > 1.15) return null;
  f.width = Math.min(f.width, 1 - f.left); f.height = Math.min(f.height, 1 - f.top);
  return f;
}
