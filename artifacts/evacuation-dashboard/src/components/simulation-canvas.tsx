import { useRef, useEffect, useCallback, useState } from 'react';
import type { SimState, GridData } from '@workspace/api-client-react';

const CELL_COLORS: Record<number, string> = {
  0: '#F0F0F0',
  1: '#2D3748',
  2: '#805AD5',
  3: '#38A169',
};

interface Props {
  gridData: GridData | null;
  simState: SimState | null;
  population: number;
}

// Draw a filled arrowhead pointing in direction (dx,dy) at position (x,y)
function drawArrow(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  dx: number,
  dy: number,
  size: number,
  color: string,
  alpha: number,
) {
  const angle = Math.atan2(dy, dx);
  const headLen = size * 1.4;
  const shaftLen = size * 0.85;

  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = Math.max(1, size * 0.18);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  // Subtle shadow for visibility without being heavy
  ctx.shadowColor = 'rgba(0,0,0,0.4)';
  ctx.shadowBlur = 2;

  // Shaft
  ctx.beginPath();
  ctx.moveTo(cx - Math.cos(angle) * shaftLen, cy - Math.sin(angle) * shaftLen);
  ctx.lineTo(cx + Math.cos(angle) * shaftLen * 0.35, cy + Math.sin(angle) * shaftLen * 0.35);
  ctx.stroke();

  // Arrowhead
  ctx.beginPath();
  ctx.moveTo(cx + Math.cos(angle) * headLen, cy + Math.sin(angle) * headLen);
  ctx.lineTo(
    cx + Math.cos(angle + 2.3) * headLen * 0.6,
    cy + Math.sin(angle + 2.3) * headLen * 0.6,
  );
  ctx.lineTo(
    cx + Math.cos(angle) * headLen * 0.25,
    cy + Math.sin(angle) * headLen * 0.25,
  );
  ctx.lineTo(
    cx + Math.cos(angle - 2.3) * headLen * 0.6,
    cy + Math.sin(angle - 2.3) * headLen * 0.6,
  );
  ctx.closePath();
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.restore();
}

// Compute direction from a region center toward nearest exit
function dirToNearestExit(
  row: number,
  col: number,
  exits: Array<{ row: number; col: number }>,
): [number, number] {
  if (!exits.length) return [0, -1];
  let bestDx = 0, bestDy = -1, bestDist = Infinity;
  for (const ex of exits) {
    const dy = ex.row - row;
    const dx = ex.col - col;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < bestDist) {
      bestDist = dist;
      const len = Math.max(1, dist);
      bestDx = dx / len;
      bestDy = dy / len;
    }
  }
  return [bestDx, bestDy];
}

// Find the best FREE cell (type 0) near (row,col) to place an arrow.
// Two-pass: first prefers cells whose 4 cardinal neighbours are all free
// (guarantees the glow circle can't bleed into adjacent obstacles).
// Falls back to any free cell if no "clean" cell is found.
function findFreeCell(
  cells: number[][],
  row: number,
  col: number,
  rows: number,
  cols: number,
  maxRadius: number = 6,
): [number, number] | null {
  const inBounds = (r: number, c: number) =>
    r >= 2 && r < rows - 2 && c >= 2 && c < cols - 2;

  // Pass 1: free cell with all 4 cardinal neighbours also free
  for (let d = 0; d <= maxRadius; d++) {
    for (let dr = -d; dr <= d; dr++) {
      for (let dc = -d; dc <= d; dc++) {
        if (d > 0 && Math.abs(dr) !== d && Math.abs(dc) !== d) continue; // outer ring only
        const nr = row + dr, nc = col + dc;
        if (!inBounds(nr, nc)) continue;
        if (cells[nr]?.[nc] !== 0) continue; // must be FREE
        // All 4 cardinal neighbours must also be FREE (type 0)
        if (
          (cells[nr - 1]?.[nc] ?? 1) === 0 &&
          (cells[nr + 1]?.[nc] ?? 1) === 0 &&
          (cells[nr]?.[nc - 1] ?? 1) === 0 &&
          (cells[nr]?.[nc + 1] ?? 1) === 0
        ) return [nr, nc];
      }
    }
  }

  // Pass 2: any free cell within range
  for (let d = 0; d <= maxRadius; d++) {
    for (let dr = -d; dr <= d; dr++) {
      for (let dc = -d; dc <= d; dc++) {
        if (d > 0 && Math.abs(dr) !== d && Math.abs(dc) !== d) continue;
        const nr = row + dr, nc = col + dc;
        if (!inBounds(nr, nc)) continue;
        if (cells[nr]?.[nc] === 0) return [nr, nc];
      }
    }
  }

  return null; // no free cell found
}

export function SimulationCanvas({ gridData, simState, population }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const drawInfoRef = useRef({ cellSize: 1, offsetX: 0, offsetY: 0, cols: 1, rows: 1 });
  const [showLegend, setShowLegend] = useState(true);
  const [showArrows, setShowArrows] = useState(true);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width: cW, height: cH } = container.getBoundingClientRect();
    if (cW === 0 || cH === 0) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = cW * dpr;
    canvas.height = cH * dpr;
    canvas.style.width = `${cW}px`;
    canvas.style.height = `${cH}px`;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, cW, cH);

    if (!gridData) {
      ctx.fillStyle = '#1E293B';
      ctx.fillRect(0, 0, cW, cH);
      ctx.fillStyle = '#475569';
      ctx.font = '13px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('SELECT A LAYOUT TO BEGIN', cW / 2, cH / 2);
      return;
    }

    const cols = gridData.width;
    const rows = gridData.height;
    const pad = 40;
    const cs = Math.max(1, Math.floor(Math.min((cW - pad * 2) / cols, (cH - pad * 2) / rows, 20)));
    const drawW = cs * cols;
    const drawH = cs * rows;
    const offX = Math.floor((cW - drawW) / 2);
    const offY = Math.floor((cH - drawH) / 2);
    drawInfoRef.current = { cellSize: cs, offsetX: offX, offsetY: offY, cols, rows };

    ctx.save();
    ctx.translate(offX, offY);

    // ── Layer 1: grid cells ─────────────────────────────────────────────────
    const gap = cs > 4 ? 1 : 0;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const val = gridData.cells[r]?.[c] ?? 0;
        ctx.fillStyle = CELL_COLORS[val] ?? CELL_COLORS[0];
        ctx.fillRect(c * cs, r * cs, cs - gap, cs - gap);
      }
    }

    // ── Layer 2: congestion heatmap overlay ─────────────────────────────────
    if (simState?.region_congestion && cs >= 2) {
      const regionSize = 8;
      for (const rc of simState.region_congestion) {
        if (rc.congestion < 0.05) continue;
        const r0 = rc.row - Math.floor(regionSize / 2);
        const c0 = rc.col - Math.floor(regionSize / 2);
        const rSize = Math.min(regionSize, rows - r0);
        const cSize = Math.min(regionSize, cols - c0);
        ctx.fillStyle = `rgba(239,68,68,${rc.congestion * 0.55})`;
        ctx.fillRect(
          Math.max(0, c0) * cs,
          Math.max(0, r0) * cs,
          cSize * cs,
          rSize * cs
        );
      }
    }

    // ── Layer 3: exit glow + EXIT label ────────────────────────────────────
    if (gridData.exits) {
      const pulse = 0.4 + 0.2 * Math.sin(Date.now() / 400);
      for (const ex of gridData.exits) {
        // Glow
        const grd = ctx.createRadialGradient(
          (ex.col + 0.5) * cs, (ex.row + 0.5) * cs, 0,
          (ex.col + 0.5) * cs, (ex.row + 0.5) * cs, cs * 3,
        );
        grd.addColorStop(0, `rgba(56,161,105,${pulse})`);
        grd.addColorStop(1, 'rgba(56,161,105,0)');
        ctx.fillStyle = grd;
        ctx.fillRect((ex.col - 3) * cs, (ex.row - 3) * cs, cs * 7, cs * 7);

        // EXIT label (only if cells are big enough)
        if (cs >= 6) {
          const lx = (ex.col + 0.5) * cs;
          const ly = (ex.row - 1.2) * cs;
          const fontSize = Math.max(7, Math.min(11, cs * 0.7));
          ctx.font = `bold ${fontSize}px 'Inter', sans-serif`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';

          // Label background pill
          const labelW = fontSize * 3.2;
          const labelH = fontSize + 4;
          ctx.fillStyle = 'rgba(20,83,45,0.92)';
          ctx.beginPath();
          const rx = lx - labelW / 2, ry = ly - labelH / 2;
          ctx.roundRect(rx, ry, labelW, labelH, 3);
          ctx.fill();

          ctx.strokeStyle = '#68D391';
          ctx.lineWidth = 0.8;
          ctx.stroke();

          ctx.fillStyle = '#68D391';
          ctx.fillText('EXIT', lx, ly);
        }
      }
    }

    // ── Layer 4: agents ───────────────────────────────────────────────────
    if (simState?.agents && cs >= 2) {
      const r = Math.max(1.5, cs * 0.35);
      ctx.fillStyle = 'rgba(251,191,36,0.88)';
      ctx.shadowColor = 'rgba(251,191,36,0.5)';
      ctx.shadowBlur = 3;
      for (const [ar, ac] of simState.agents) {
        ctx.beginPath();
        ctx.arc((ac + 0.5) * cs, (ar + 0.5) * cs, r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
    }

    // ── Layer 5: direction arrows (on top of agents) ───────────────────────
    if (showArrows && simState?.region_congestion && cs >= 4 && gridData.exits?.length) {
      const exits = gridData.exits;
      const exitById: Record<number, { row: number; col: number }> = {};
      exits.forEach((ex, idx) => { exitById[(ex as any).id ?? idx] = ex; });

      const pulse = 0.78 + 0.22 * Math.sin(Date.now() / 380);

      for (const rc of simState.region_congestion) {
        const hasPeople = ((rc as any).local_population ?? 0) > 0;
        if (!hasPeople && rc.congestion < 0.05) continue;

        // Clamp region center with 2-cell margin from every edge
        const clampedRow = Math.min(Math.max(rc.row, 2), rows - 3);
        const clampedCol = Math.min(Math.max(rc.col, 2), cols - 3);

        // Find best free cell — two-pass ensures glow can't bleed into obstacles
        const freeCell = findFreeCell(gridData.cells, clampedRow, clampedCol, rows, cols, 6);
        if (!freeCell) continue;

        const [arrowRow, arrowCol] = freeCell;
        // Pixel center of the free cell
        const cx = arrowCol * cs + cs * 0.5;
        const cy = arrowRow * cs + cs * 0.5;

        const isRerouted = rc.congestion > 0.35;
        const color     = isRerouted ? '#FF6B00' : '#00D4FF';
        const glowColor = isRerouted ? 'rgba(255,107,0,0.65)' : 'rgba(0,212,255,0.65)';
        const bgColor   = isRerouted ? 'rgba(255,107,0,0.20)' : 'rgba(0,212,255,0.20)';
        const baseAlpha = Math.min(0.95, 0.55 + rc.congestion * 0.4 + (hasPeople ? 0.15 : 0));
        const alpha     = baseAlpha * pulse;

        // Resolve target exit (direction computed from REGION center for stability)
        const recExitId = (rc as any).recommended_exit_id;
        let targetExit = exitById[recExitId];
        if (!targetExit) {
          let best = exits[0]; let bestD = Infinity;
          for (const ex of exits) {
            const d = Math.abs(ex.row - rc.row) + Math.abs(ex.col - rc.col);
            if (d < bestD) { bestD = d; best = ex; }
          }
          targetExit = best;
        }

        // Direction vector: from found free cell toward target exit
        const rawDx = targetExit.col - arrowCol;
        const rawDy = targetExit.row - arrowRow;
        const mag = Math.sqrt(rawDx * rawDx + rawDy * rawDy) || 1;
        const dx = rawDx / mag;
        const dy = rawDy / mag;

        const arrowSize = Math.max(cs * 1.05, 7);
        // Glow circle strictly < half a cell so it CANNOT reach adjacent cells
        const bgRadius = cs * 0.42;

        // Background glow circle
        ctx.save();
        ctx.globalAlpha = alpha * 0.88;
        ctx.shadowColor = glowColor;
        ctx.shadowBlur  = 5;
        ctx.fillStyle   = bgColor;
        ctx.beginPath();
        ctx.arc(cx, cy, bgRadius, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur  = 0;
        ctx.strokeStyle = color;
        ctx.lineWidth   = Math.max(0.5, cs * 0.07);
        ctx.globalAlpha = alpha * 0.45;
        ctx.stroke();
        ctx.restore();

        // Arrow on top
        drawArrow(ctx, cx, cy, dx, dy, arrowSize, color, alpha);
      }
    }

    // ── Layer 6: Free-space label watermark (when no agents) ────────────────
    if (!simState && gridData && cs >= 6) {
      // Draw small "FREE SPACE" text inside a representative free cell near center
      const midR = Math.floor(rows / 2);
      const midC = Math.floor(cols / 2);
      const val = gridData.cells[midR]?.[midC] ?? 0;
      if (val === 0) {
        const fontSize = Math.max(6, Math.min(9, cs * 0.55));
        ctx.font = `${fontSize}px 'Inter', monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = 'rgba(71,85,105,0.7)';
        ctx.fillText('FREE', (midC + 0.5) * cs, (midR + 0.5) * cs);
      }
    }

    ctx.restore();

    // ── Zone-count HUD overlay (drawn in screen space) ──────────────────────
    if (simState?.region_congestion) {
      const reroutedCount = simState.region_congestion.filter(r => r.congestion > 0.35).length;
      if (reroutedCount > 0) {
        const badgeText = `${reroutedCount} zone${reroutedCount > 1 ? 's' : ''} rerouted`;
        const bx = cW - 16;
        const by = 16;
        ctx.font = 'bold 9px Inter, sans-serif';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'top';
        const tw = ctx.measureText(badgeText).width + 16;
        ctx.fillStyle = 'rgba(251,146,60,0.9)';
        ctx.beginPath();
        ctx.roundRect(bx - tw, by, tw, 18, 4);
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.fillText(badgeText, bx - 8, by + 4.5);
      }
    }
  }, [gridData, simState, showArrows]);

  useEffect(() => { draw(); }, [draw]);

  // Animate exit glow when idle
  useEffect(() => {
    if (!gridData || simState) return;
    let raf: number;
    const loop = () => { draw(); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [gridData, simState, draw]);

  // Continuous animation loop while simulation is loaded (for arrow pulse + glow)
  useEffect(() => {
    if (!simState) return;
    let raf: number;
    const loop = () => { draw(); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [simState, draw]);

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const ro = new ResizeObserver(() => requestAnimationFrame(draw));
    ro.observe(container);
    return () => ro.disconnect();
  }, [draw]);

  const exited = simState?.exited_count ?? 0;
  const pct = population > 0 ? Math.round((exited / population) * 100) : 0;

  // Count rerouted zones for the React overlay
  const reroutedZones = simState?.region_congestion?.filter(r => r.congestion > 0.35).length ?? 0;

  return (
    <div className="flex-1 flex flex-col overflow-hidden relative bg-[#0a1120]">
      <div ref={containerRef} className="flex-1 relative overflow-hidden">
        <canvas ref={canvasRef} className="absolute inset-0" />

        {/* Empty state */}
        {!gridData && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 pointer-events-none">
            <div className="w-16 h-16 rounded-xl border-2 border-dashed border-slate-600 flex items-center justify-center">
              <div className="w-6 h-6 rounded bg-slate-700 opacity-50" />
            </div>
            <p className="text-slate-500 text-xs font-mono tracking-widest uppercase">
              Configure and start a run
            </p>
          </div>
        )}

        {/* Toolbar — top-left controls */}
        {gridData && (
          <div className="absolute top-3 left-3 flex gap-1.5 z-10">
            <button
              onClick={() => setShowArrows(v => !v)}
              title="Toggle direction arrows"
              className={`flex items-center gap-1 px-2 py-1 rounded text-[9px] font-bold tracking-wider uppercase border transition-all ${
                showArrows
                  ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300'
                  : 'bg-slate-800/80 border-slate-600 text-slate-500'
              }`}
            >
              <span className="text-[10px]">↗</span> Arrows
            </button>
            <button
              onClick={() => setShowLegend(v => !v)}
              title="Toggle legend"
              className={`flex items-center gap-1 px-2 py-1 rounded text-[9px] font-bold tracking-wider uppercase border transition-all ${
                showLegend
                  ? 'bg-slate-700/80 border-slate-500 text-slate-300'
                  : 'bg-slate-800/80 border-slate-600 text-slate-500'
              }`}
            >
              ☰ Legend
            </button>
          </div>
        )}

        {/* DYNAMIC REROUTING banner */}
        {reroutedZones > 0 && (
          <div className="absolute top-3 right-3 z-10 flex flex-col gap-1.5 items-end">
            <div className="flex items-center gap-2 bg-orange-500/15 border border-orange-500/40 rounded-lg px-3 py-1.5 backdrop-blur-sm">
              <span className="w-2 h-2 rounded-full bg-orange-400 animate-pulse shrink-0" />
              <span className="text-[10px] font-bold text-orange-300 tracking-wider uppercase">
                Dynamic Rerouting Active
              </span>
            </div>
            <div className="text-[9px] font-mono text-orange-400/70 pr-1">
              {reroutedZones} zone{reroutedZones > 1 ? 's' : ''} redirected
            </div>
          </div>
        )}

        {/* Legend overlay */}
        {showLegend && gridData && (
          <div className="absolute bottom-12 left-3 z-10 bg-slate-900/90 backdrop-blur border border-slate-700 rounded-lg p-3 flex flex-col gap-2 text-[10px] font-mono min-w-[140px]">
            <p className="text-[9px] font-bold tracking-widest uppercase text-slate-400 mb-0.5">Legend</p>
            {([
              { color: '#F0F0F0', label: 'Free Space',    ring: false },
              { color: '#2D3748', label: 'Wall',          ring: false },
              { color: '#805AD5', label: 'Obstacle',      ring: false },
              { color: '#38A169', label: 'Exit',          ring: true  },
              { color: '#FBBF24', label: 'Occupants',     ring: false },
              { color: 'rgba(239,68,68,0.6)', label: 'High Congestion', ring: false },
              { color: '#22D3EE', label: '→ Route (Normal)', ring: false },
              { color: '#FB923C', label: '→ Rerouted Zone', ring: false },
            ] as const).map(({ color, label, ring }) => (
              <div key={label} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-sm shrink-0 flex-none"
                  style={{ background: color, boxShadow: ring ? '0 0 4px rgba(56,161,105,0.7)' : undefined }}
                />
                <span className="text-slate-300">{label}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Progress bar */}
      <div className="flex-none h-8 bg-[#0d1929] border-t border-border flex items-center px-4 gap-3">
        <span className="text-[10px] font-mono text-slate-500 w-20 shrink-0">
          {simState?.done ? 'COMPLETE' : simState ? 'RUNNING' : 'IDLE'}
        </span>
        <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{
              width: `${pct}%`,
              background: simState?.done
                ? '#38A169'
                : 'linear-gradient(90deg,#3B82F6,#0EA5E9)',
            }}
          />
        </div>
        <span className="text-[10px] font-mono text-slate-400 w-16 text-right shrink-0">
          {exited}/{population} ({pct}%)
        </span>
      </div>
    </div>
  );
}
