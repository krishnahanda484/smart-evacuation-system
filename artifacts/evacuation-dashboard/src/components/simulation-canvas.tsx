import { useRef, useEffect, useCallback } from 'react';
import type { SimState, GridData, ZoneDirection } from '@workspace/api-client-react';

const CELL_COLORS: Record<number, string> = {
  0: '#F0F0F0',
  1: '#2D3748',
  2: '#805AD5',
  3: '#38A169',
};

// Arrow direction from region centre toward recommended exit position
function drawArrow(
  ctx: CanvasRenderingContext2D,
  fromX: number, fromY: number,
  toX: number, toY: number,
  color: string,
  size: number,
) {
  const dx = toX - fromX;
  const dy = toY - fromY;
  const len = Math.sqrt(dx * dx + dy * dy);
  if (len < 1) return;
  const ux = dx / len, uy = dy / len;

  // Shaft
  const shaftLen = Math.min(len * 0.5, size * 3);
  const ex = fromX + ux * shaftLen;
  const ey = fromY + uy * shaftLen;

  ctx.beginPath();
  ctx.moveTo(fromX, fromY);
  ctx.lineTo(ex, ey);
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(1.5, size * 0.35);
  ctx.lineCap = 'round';
  ctx.stroke();

  // Arrowhead
  const hw = Math.max(2, size * 0.55);
  const hl = Math.max(3, size * 0.8);
  ctx.beginPath();
  ctx.moveTo(ex, ey);
  ctx.lineTo(ex - ux * hl + uy * hw, ey - uy * hl - ux * hw);
  ctx.lineTo(ex - ux * hl - uy * hw, ey - uy * hl + ux * hw);
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
}

interface Props {
  gridData: GridData | null;
  simState: SimState | null;
  population: number;
}

export function SimulationCanvas({ gridData, simState, population }: Props) {
  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const drawInfoRef  = useRef({ cellSize: 1, offsetX: 0, offsetY: 0, cols: 1, rows: 1 });

  const draw = useCallback(() => {
    const canvas    = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width: cW, height: cH } = container.getBoundingClientRect();
    if (cW === 0 || cH === 0) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width  = cW * dpr;
    canvas.height = cH * dpr;
    canvas.style.width  = `${cW}px`;
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
    const pad  = 32;
    const cs   = Math.max(1, Math.floor(Math.min((cW - pad * 2) / cols, (cH - pad * 2) / rows, 20)));
    const drawW = cs * cols;
    const drawH = cs * rows;
    const offX  = Math.floor((cW - drawW) / 2);
    const offY  = Math.floor((cH - drawH) / 2);
    drawInfoRef.current = { cellSize: cs, offsetX: offX, offsetY: offY, cols, rows };

    ctx.save();
    ctx.translate(offX, offY);

    // ── Layer 1: grid cells ───────────────────────────────────────────
    const gap = cs > 4 ? 1 : 0;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const val = gridData.cells[r]?.[c] ?? 0;
        ctx.fillStyle = CELL_COLORS[val] ?? CELL_COLORS[0];
        ctx.fillRect(c * cs, r * cs, cs - gap, cs - gap);
      }
    }

    // ── Layer 2: congestion heatmap ───────────────────────────────────
    if (simState?.region_congestion && cs >= 2) {
      const regionSize = 8;
      for (const rc of simState.region_congestion) {
        if (rc.congestion < 0.05) continue;
        const r0    = rc.row - Math.floor(regionSize / 2);
        const c0    = rc.col - Math.floor(regionSize / 2);
        const rSize = Math.min(regionSize, rows - r0);
        const cSize = Math.min(regionSize, cols - c0);
        ctx.fillStyle = `rgba(239,68,68,${rc.congestion * 0.55})`;
        ctx.fillRect(Math.max(0, c0) * cs, Math.max(0, r0) * cs, cSize * cs, rSize * cs);
      }
    }

    // ── Layer 3: exit glow ────────────────────────────────────────────
    if (gridData.exits) {
      for (const ex of gridData.exits) {
        const pulse = 0.4 + 0.2 * Math.sin(Date.now() / 400);
        const grd   = ctx.createRadialGradient(
          (ex.col + 0.5) * cs, (ex.row + 0.5) * cs, 0,
          (ex.col + 0.5) * cs, (ex.row + 0.5) * cs, cs * 2.5,
        );
        grd.addColorStop(0, `rgba(56,161,105,${pulse})`);
        grd.addColorStop(1, 'rgba(56,161,105,0)');
        ctx.fillStyle = grd;
        ctx.fillRect((ex.col - 2) * cs, (ex.row - 2) * cs, cs * 5, cs * 5);
      }
    }

    // ── Layer 4: zone direction arrows ───────────────────────────────
    // Only draw if ML is active (zone_directions populated) and cell size is large enough
    const zoneDirs: ZoneDirection[] = simState?.zone_directions ?? [];
    if (zoneDirs.length > 0 && cs >= 3 && gridData.exits) {
      for (const zd of zoneDirs) {
        const exitIdx = zd.recommended_exit;
        const exitPt  = gridData.exits[exitIdx];
        if (!exitPt) continue;

        const fromX = (zd.center_col + 0.5) * cs;
        const fromY = (zd.center_row + 0.5) * cs;
        const toX   = (exitPt.col + 0.5) * cs;
        const toY   = (exitPt.row + 0.5) * cs;

        // Rerouted zones: bright orange/amber; normal: soft cyan
        const color = zd.is_rerouted
          ? `rgba(251,191,36,0.95)`   // amber — rerouted
          : `rgba(99,179,237,0.60)`;  // soft blue — normal routing

        drawArrow(ctx, fromX, fromY, toX, toY, color, cs);
      }

      // Legend (top-left corner of the grid)
      if (cs >= 4) {
        ctx.font = `${Math.max(9, cs)}px monospace`;
        ctx.globalAlpha = 0.85;
        const legendY = 12;
        ctx.fillStyle = 'rgba(99,179,237,0.9)';
        ctx.fillText('▶ Guided', 4, legendY);
        ctx.fillStyle = 'rgba(251,191,36,0.95)';
        ctx.fillText('▶ Rerouted', 4, legendY + Math.max(10, cs + 2));
        ctx.globalAlpha = 1.0;
      }
    }

    // ── Layer 5: agents ───────────────────────────────────────────────
    if (simState?.agents && cs >= 2) {
      const r = Math.max(1.5, cs * 0.35);
      ctx.fillStyle   = 'rgba(251,191,36,0.88)';
      ctx.shadowColor = 'rgba(251,191,36,0.5)';
      ctx.shadowBlur  = 3;
      for (const [ar, ac] of simState.agents) {
        ctx.beginPath();
        ctx.arc((ac + 0.5) * cs, (ar + 0.5) * cs, r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
    }

    ctx.restore();
  }, [gridData, simState]);

  useEffect(() => { draw(); }, [draw]);

  // Pulse exits when idle
  useEffect(() => {
    if (!gridData || simState) return;
    let raf: number;
    const loop = () => { draw(); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [gridData, simState, draw]);

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const ro = new ResizeObserver(() => requestAnimationFrame(draw));
    ro.observe(container);
    return () => ro.disconnect();
  }, [draw]);

  const exited = simState?.exited_count ?? 0;
  const pct    = population > 0 ? Math.round((exited / population) * 100) : 0;

  // Count rerouted zones for legend badge
  const reroutedCount = (simState?.zone_directions ?? []).filter(z => z.is_rerouted).length;

  return (
    <div className="flex-1 flex flex-col overflow-hidden relative bg-[#0a1120]">
      <div ref={containerRef} className="flex-1 relative overflow-hidden">
        <canvas ref={canvasRef} className="absolute inset-0" />

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

        {/* Rerouting badge overlay */}
        {reroutedCount > 0 && (
          <div className="absolute top-2 right-2 flex items-center gap-1.5 bg-amber-900/80 border border-amber-500/50 text-amber-300 text-[10px] font-mono font-bold px-2 py-1 rounded backdrop-blur pointer-events-none">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            {reroutedCount} zone{reroutedCount !== 1 ? 's' : ''} rerouted
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
