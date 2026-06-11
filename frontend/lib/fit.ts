/* Accurate page-fill engine (pure, DOM-free).

   The /tailor live preview measures the REAL rendered height of every block, then
   uses this module to decide how many bullets (2-6) to show per project so the
   resume lands on a clean half-page boundary (1.0 / 1.5 / 2.0 / 2.5 / 3.0) with a
   well-filled last page, bounded to [1, 3] pages. Every experience keeps its fixed
   6 bullets; project bullets are the length lever. The math is isolated here so it
   can be reasoned about and checked without a DOM.

   Block meta: a trimmable project-bullet block carries { pi, rank } where `pi` is
   the project index and `rank` is the bullet's position (1-based; bullet 0 lives in
   the project's head block and is never trimmed). Everything else is `null`. */

export type FitMeta = { pi: number; rank: number } | null;

export interface FitResult {
  /* How many bullets to SHOW per project index. Projects with <=1 bullet (no
     trimmable blocks) are absent and render in full. */
  shownByProject: Record<number, number>;
  pages: number;
  lastFillPct: number;
}

const MIN_PROJECT_BULLETS = 2;

/* Pack block heights into pages, never splitting a block. Returns per-page used
   height (px). Mirrors the greedy packer in ResumePreview so the fitter's page
   count matches what actually renders. */
export function packPages(heights: number[], limit: number): number[] {
  const perPage: number[] = [];
  let h = 0;
  for (const bh of heights) {
    if (h > 0 && h + bh > limit) {
      perPage.push(h);
      h = 0;
    }
    h += bh;
  }
  if (h > 0 || perPage.length === 0) perPage.push(h);
  return perPage;
}

/* Score a configuration by how cleanly its last page lands on a boundary.
   A "full" last page (>=88%) scores highest (-> 1.0 / 2.0 / 3.0); a "half" last
   page (~50%) scores next (-> 1.5 / 2.5). Over 3 pages is excluded; fewer pages
   win ties. Higher is better. */
export function scoreConfig(perPage: number[], limit: number): number {
  const pages = perPage.length;
  if (pages < 1) return -Infinity;
  const lastFill = Math.min(1, perPage[pages - 1] / limit);
  let s: number;
  if (lastFill >= 0.88) {
    s = 100 - (1 - lastFill) * 100; // ~88..100, fuller is better
  } else if (lastFill >= 0.4 && lastFill <= 0.62) {
    s = 90 - Math.abs(0.51 - lastFill) * 100; // ~80..90, nearer half is better
  } else {
    const dFull = Math.abs(lastFill - 0.94);
    const dHalf = Math.abs(lastFill - 0.51);
    s = 55 - Math.min(dFull, dHalf) * 100; // off-boundary: penalise distance
  }
  if (pages > 3) s -= 1000; // hard ceiling: never prefer >3 pages
  s -= (pages - 1) * 1.5; // mild preference for fewer pages on ties
  return s;
}

function displayedHeights(heights: number[], meta: FitMeta[], shown: Record<number, number>): number[] {
  const out: number[] = [];
  for (let i = 0; i < heights.length; i++) {
    const m = meta[i];
    if (m && m.rank >= (shown[m.pi] ?? Infinity)) continue; // trimmed away
    out.push(heights[i]);
  }
  return out;
}

/* Choose how many bullets to show per project. Start every project at the minimum
   (2), then greedily add the next-ranked bullet to the project with the fewest
   shown, re-measuring analytically each step, never exceeding 3 pages. Keep the
   visited configuration with the best boundary score. */
export function fitProjects(heights: number[], meta: FitMeta[], limit: number): FitResult {
  // Capacity per project = (highest rank) + 1 = total authored bullets.
  const capacity: Record<number, number> = {};
  for (const m of meta) if (m) capacity[m.pi] = Math.max(capacity[m.pi] ?? 0, m.rank + 1);
  const pis = Object.keys(capacity).map(Number).sort((a, b) => a - b);

  const shown: Record<number, number> = {};
  for (const pi of pis) shown[pi] = Math.min(MIN_PROJECT_BULLETS, capacity[pi]);

  const evaluate = (cfg: Record<number, number>) => packPages(displayedHeights(heights, meta, cfg), limit);

  let bestShown = { ...shown };
  let bestPerPage = evaluate(shown);
  let bestScore = scoreConfig(bestPerPage, limit);

  // Greedy monotone climb: each step only adds height, so we visit configs from
  // shortest to tallest and keep the highest-scoring one.
  while (true) {
    const grow = pis
      .filter((pi) => shown[pi] < capacity[pi])
      .sort((a, b) => shown[a] - shown[b] || a - b)[0];
    if (grow === undefined) break;
    shown[grow] += 1;
    const perPage = evaluate(shown);
    if (perPage.length > 3) {
      shown[grow] -= 1; // adding this bullet spills past 3 pages: stop climbing
      break;
    }
    const score = scoreConfig(perPage, limit);
    if (score > bestScore) {
      bestScore = score;
      bestShown = { ...shown };
      bestPerPage = perPage;
    }
  }

  const pages = bestPerPage.length;
  const lastFillPct = pages ? Math.round(Math.min(1, bestPerPage[pages - 1] / limit) * 100) : 0;
  return { shownByProject: bestShown, pages, lastFillPct };
}
