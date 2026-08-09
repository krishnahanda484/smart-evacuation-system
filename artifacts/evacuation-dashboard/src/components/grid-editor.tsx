import { useRef, useEffect, useState, useCallback } from 'react';
import type { GridData } from '@workspace/api-client-react';
import { useCreateLayout } from '@workspace/api-client-react';
import { useQueryClient } from '@tanstack/react-query';
import { getListLayoutsQueryKey } from '@workspace/api-client-react';

// ── Cell type constants ─────────────────────────────────────────────────────
const CELL_COLORS: Record<number, string> = {
  0: '#F0F0F0', // FREE
  1: '#2D3748', // WALL
  2: '#805AD5', // OBSTACLE
  3: '#38A169', // EXIT
};

const CELL_NAMES: Record<number, string> = {
  0: 'Free Space',
  1: 'Wall',
  2: 'Obstacle',
  3: 'Exit',
};

const PAINT_TOOLS = [
  { value: 0, label: 'Free', color: '#F0F0F0', desc: 'Open floor' },
  { value: 1, label: 'Wall', color: '#2D3748', desc: 'Solid wall' },
  { value: 2, label: 'Obstacle', color: '#805AD5', desc: 'Furniture' },
  { value: 3, label: 'Exit', color: '#38A169', desc: 'Exit door' },
] as const;

// ── Empty grid factory ──────────────────────────────────────────────────────
function makeEmptyGrid(cols: number, rows: number): number[][] {
  const grid: number[][] = [];
  for (let r = 0; r < rows; r++) {
    const row: number[] = [];
    for (let c = 0; c < cols; c++) {
      // Border = wall, interior = free
      const isEdge = r === 0 || r === rows - 1 || c === 0 || c === cols - 1;
      row.push(isEdge ? 1 : 0);
    }
    grid.push(row);
  }
  return grid;
}

// ── Count helpers ───────────────────────────────────────────────────────────
function countCell(cells: number[][], val: number): number {
  return cells.flat().filter(c => c === val).length;
}

// ── GridEditor ───────────────────────────────────────────────────────────────
interface Props {
  initialGrid?: GridData | null;
}

export function GridEditor({ initialGrid }: Props) {
  const queryClient = useQueryClient();
  const createMut = useCreateLayout();

  // Editor state
  const [cols, setCols] = useState(initialGrid?.width ?? 30);
  const [rows, setRows] = useState(initialGrid?.height ?? 20);
  const [cells, setCells] = useState<number[][]>(() =>
    initialGrid?.cells ?? makeEmptyGrid(cols, rows),
  );
  const [activeTool, setActiveTool] = useState<0 | 1 | 2 | 3>(0);
  const [isPainting, setIsPainting] = useState(false);
  const [layoutName, setLayoutName] = useState('My Custom Layout');
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  // Canvas refs
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const drawInfoRef = useRef({ cs: 1, offX: 0, offY: 0 });

  // ── Redraw ─────────────────────────────────────────────────────────────────
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width: cW, height: cH } = container.getBoundingClientRect();
    if (!cW || !cH) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = cW * dpr;
    canvas.height = cH * dpr;
    canvas.style.width = `${cW}px`;
    canvas.style.height = `${cH}px`;
    ctx.scale(dpr, dpr);

    const maxCS = 28;
    const pad = 16;
    const cs = Math.max(4, Math.min(maxCS, Math.floor(Math.min((cW - pad * 2) / cols, (cH - pad * 2) / rows))));
    const drawW = cs * cols;
    const drawH = cs * rows;
    const offX = Math.floor((cW - drawW) / 2);
    const offY = Math.floor((cH - drawH) / 2);
    drawInfoRef.current = { cs, offX, offY };

    ctx.clearRect(0, 0, cW, cH);
    ctx.save();
    ctx.translate(offX, offY);

    const gap = cs > 5 ? 1 : 0;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const val = cells[r]?.[c] ?? 0;
        ctx.fillStyle = CELL_COLORS[val] ?? CELL_COLORS[0];
        ctx.fillRect(c * cs, r * cs, cs - gap, cs - gap);

        if (val === 3 && cs >= 6) {
          ctx.strokeStyle = '#68D391';
          ctx.lineWidth = 1.5;
          ctx.strokeRect(c * cs + 0.75, r * cs + 0.75, cs - gap - 1.5, cs - gap - 1.5);
        }
      }
    }

    // Grid lines (subtle)
    if (cs >= 8) {
      ctx.strokeStyle = 'rgba(100,116,139,0.2)';
      ctx.lineWidth = 0.5;
      for (let r = 0; r <= rows; r++) {
        ctx.beginPath(); ctx.moveTo(0, r * cs); ctx.lineTo(drawW, r * cs); ctx.stroke();
      }
      for (let c = 0; c <= cols; c++) {
        ctx.beginPath(); ctx.moveTo(c * cs, 0); ctx.lineTo(c * cs, drawH); ctx.stroke();
      }
    }

    ctx.restore();
  }, [cells, cols, rows]);

  useEffect(() => { draw(); }, [draw]);

  useEffect(() => {
    const c = containerRef.current;
    if (!c) return;
    const ro = new ResizeObserver(() => requestAnimationFrame(draw));
    ro.observe(c);
    return () => ro.disconnect();
  }, [draw]);

  // ── Get cell from mouse event ───────────────────────────────────────────
  const cellFromEvent = useCallback((e: React.MouseEvent | MouseEvent): [number, number] | null => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return null;
    const { cs, offX, offY } = drawInfoRef.current;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const c = Math.floor((x - offX) / cs);
    const r = Math.floor((y - offY) / cs);
    if (r < 0 || r >= rows || c < 0 || c >= cols) return null;
    return [r, c];
  }, [rows, cols]);

  // ── Paint ─────────────────────────────────────────────────────────────────
  const paint = useCallback((e: React.MouseEvent | MouseEvent) => {
    const pos = cellFromEvent(e);
    if (!pos) return;
    const [r, c] = pos;
    setCells(prev => {
      if (prev[r]?.[c] === activeTool) return prev;
      const next = prev.map(row => [...row]);
      next[r][c] = activeTool;
      return next;
    });
  }, [cellFromEvent, activeTool]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    setIsPainting(true);
    paint(e);
  }, [paint]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (isPainting) paint(e);
  }, [isPainting, paint]);

  const onMouseUp = useCallback(() => setIsPainting(false), []);

  // ── New grid ──────────────────────────────────────────────────────────────
  const handleNewGrid = useCallback(() => {
    setCells(makeEmptyGrid(cols, rows));
    setSavedMsg(null);
  }, [cols, rows]);

  const handleResizeApply = useCallback((newCols: number, newRows: number) => {
    setCols(newCols);
    setRows(newRows);
    setCells(makeEmptyGrid(newCols, newRows));
    setSavedMsg(null);
  }, []);

  // ── Fill ──────────────────────────────────────────────────────────────────
  const handleFill = useCallback(() => {
    setCells(prev => prev.map(row => row.map(() => activeTool)));
    setSavedMsg(null);
  }, [activeTool]);

  // ── Save to backend ───────────────────────────────────────────────────────
  const handleSave = useCallback(async () => {
    const exitCount = countCell(cells, 3);
    if (exitCount < 1) {
      setSavedMsg('⚠ Add at least 1 EXIT cell before saving.');
      return;
    }
    setSavedMsg(null);

    const payload = {
      name: layoutName || 'Custom Layout',
      description: `Custom layout: ${cols}×${rows} grid with ${exitCount} exits`,
      width: cols,
      height: rows,
      resolution_cm: 30,
      cells,
    };

    createMut.mutate(payload as any, {
      onSuccess: () => {
        setSavedMsg('✓ Layout saved! Switch to Simulation to use it.');
        queryClient.invalidateQueries({ queryKey: getListLayoutsQueryKey() });
      },
      onError: (err: any) => {
        setSavedMsg(`✗ Save failed: ${err?.message ?? 'Unknown error'}`);
      },
    });
  }, [cells, cols, rows, layoutName, createMut, queryClient]);

  const exitCount = countCell(cells, 3);
  const freeCount = countCell(cells, 0);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div className="flex-none border-b border-border bg-card px-3 py-2 flex items-center gap-3 flex-wrap">
        {/* Paint tools */}
        <div className="flex items-center gap-1">
          {PAINT_TOOLS.map(tool => (
            <button
              key={tool.value}
              onClick={() => setActiveTool(tool.value as any)}
              title={`Paint: ${tool.desc}`}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[11px] font-semibold transition-all border ${
                activeTool === tool.value
                  ? 'border-primary shadow-[0_0_0_1px_hsl(var(--primary))] bg-primary/10 text-foreground'
                  : 'border-border text-muted-foreground hover:border-muted-foreground/50 hover:text-foreground'
              }`}
            >
              <span
                className="w-3 h-3 rounded-sm shrink-0"
                style={{ background: tool.color, boxShadow: tool.value === 3 ? '0 0 4px rgba(56,161,105,0.6)' : undefined }}
              />
              {tool.label}
            </button>
          ))}
        </div>

        <div className="h-5 w-px bg-border" />

        {/* Grid size */}
        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className="font-mono">Size:</span>
          <input
            type="number" min={5} max={120}
            value={cols}
            onChange={e => setCols(Number(e.target.value))}
            className="w-14 bg-background border border-border rounded px-1.5 py-0.5 text-[11px] font-mono text-foreground text-center"
          />
          <span>×</span>
          <input
            type="number" min={5} max={120}
            value={rows}
            onChange={e => setRows(Number(e.target.value))}
            className="w-14 bg-background border border-border rounded px-1.5 py-0.5 text-[11px] font-mono text-foreground text-center"
          />
          <button
            onClick={() => handleResizeApply(cols, rows)}
            className="px-2 py-0.5 rounded bg-slate-700 hover:bg-slate-600 text-[11px] text-slate-200 border border-slate-600 transition-colors"
          >
            Apply
          </button>
        </div>

        <div className="h-5 w-px bg-border" />

        <button
          onClick={handleNewGrid}
          className="px-2.5 py-1 rounded text-[11px] text-muted-foreground border border-border hover:border-muted-foreground/50 hover:text-foreground transition-colors"
        >
          Clear
        </button>
        <button
          onClick={handleFill}
          className="px-2.5 py-1 rounded text-[11px] text-muted-foreground border border-border hover:border-muted-foreground/50 hover:text-foreground transition-colors"
          title={`Fill entire grid with ${CELL_NAMES[activeTool]}`}
        >
          Fill All
        </button>

        <div className="flex-1" />

        {/* Stats */}
        <span className="text-[10px] font-mono text-muted-foreground">
          {cols}×{rows} · {freeCount} free · <span className={exitCount === 0 ? 'text-red-400' : 'text-green-400'}>{exitCount} exits</span>
        </span>

        <div className="h-5 w-px bg-border" />

        {/* Name + Save */}
        <input
          value={layoutName}
          onChange={e => setLayoutName(e.target.value)}
          placeholder="Layout name"
          className="w-36 bg-background border border-border rounded px-2 py-1 text-[11px] text-foreground placeholder:text-muted-foreground"
        />
        <button
          onClick={handleSave}
          disabled={createMut.isPending}
          className="px-3 py-1 rounded bg-primary text-primary-foreground text-[11px] font-bold hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {createMut.isPending ? 'Saving…' : 'Save Layout'}
        </button>
      </div>

      {/* ── Canvas ──────────────────────────────────────────────────────── */}
      <div
        ref={containerRef}
        className="flex-1 relative overflow-hidden cursor-crosshair select-none"
        style={{ background: 'radial-gradient(circle, #1e293b 1px, transparent 1px)', backgroundSize: '20px 20px', backgroundColor: '#0a1120' }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      >
        <canvas ref={canvasRef} className="absolute inset-0" />

        {/* Instruction hint */}
        {freeCount === cells.flat().length && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <p className="text-slate-500 text-[11px] font-mono tracking-widest uppercase">
              Click &amp; drag to paint cells
            </p>
          </div>
        )}
      </div>

      {/* ── Status bar ──────────────────────────────────────────────────── */}
      {savedMsg && (
        <div className={`flex-none px-4 py-2 text-[11px] font-mono border-t border-border ${
          savedMsg.startsWith('✓') ? 'text-green-400 bg-green-950/30' :
          savedMsg.startsWith('⚠') ? 'text-yellow-400 bg-yellow-950/20' :
          'text-red-400 bg-red-950/20'
        }`}>
          {savedMsg}
        </div>
      )}
    </div>
  );
}
