import type { Layout } from '@workspace/api-client-react';

export function StatsPanel({ layout, isLoading }: { layout?: Layout, isLoading: boolean }) {
  if (isLoading) {
    return (
      <div className="p-6">
        <div className="h-4 w-32 bg-card animate-pulse rounded mb-8"></div>
        <div className="flex flex-col gap-6">
          <div className="h-24 bg-card animate-pulse rounded border border-border"></div>
          <div className="h-32 bg-card animate-pulse rounded border border-border"></div>
        </div>
      </div>
    );
  }

  if (!layout) {
    return (
      <div className="p-6 text-sm text-muted-foreground italic text-center mt-10">
        No layout selected.
      </div>
    );
  }

  const { meta, grid } = layout;

  const StatBox = ({ label, count, color }: { label: string, count: number, color: string }) => (
    <div className="flex flex-col p-2.5 bg-background border rounded gap-1.5 shadow-sm">
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded-sm shadow-[inset_0_0_0_1px_rgba(0,0,0,0.1)]" style={{ backgroundColor: color }}></div>
        <span className="text-xs text-muted-foreground font-medium">{label}</span>
      </div>
      <span className="font-mono text-sm font-semibold">{count.toLocaleString()}</span>
    </div>
  );

  return (
    <div className="flex flex-col">
      <div className="p-5 border-b bg-card">
        <h2 className="font-semibold text-base mb-1.5 leading-tight">{meta.name}</h2>
        {meta.description && (
          <p className="text-xs text-muted-foreground leading-relaxed">{meta.description}</p>
        )}
      </div>

      <div className="p-5 border-b flex flex-col gap-3 bg-sidebar">
        <h3 className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Cell Breakdown</h3>
        <div className="grid grid-cols-2 gap-2.5">
          <StatBox label="Free Space" count={grid.cell_types.FREE || 0} color="#F0F0F0" />
          <StatBox label="Wall" count={grid.cell_types.WALL || 0} color="#2D3748" />
          <StatBox label="Obstacle" count={grid.cell_types.OBSTACLE || 0} color="#805AD5" />
          <StatBox label="Exit" count={grid.cell_types.EXIT || 0} color="#38A169" />
        </div>
        <div className="mt-1 bg-background border rounded p-3 flex justify-between items-center shadow-sm">
          <span className="text-xs font-medium text-muted-foreground">Total Matrix Cells</span>
          <span className="font-mono text-sm font-semibold">{meta.width * meta.height}</span>
        </div>
      </div>

      <div className="p-5 border-b flex flex-col gap-3 bg-sidebar">
        <h3 className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Physical Properties</h3>
        <div className="flex flex-col bg-background border rounded shadow-sm overflow-hidden text-sm">
          <div className="flex justify-between items-center p-3 border-b border-border/50">
            <span className="text-xs text-muted-foreground">Grid Resolution</span>
            <span className="font-mono text-xs">{meta.resolution_cm} cm/cell</span>
          </div>
          <div className="flex justify-between items-center p-3 border-b border-border/50">
            <span className="text-xs text-muted-foreground">Physical Size</span>
            <span className="font-mono text-xs">{meta.physical_width_m}m × {meta.physical_height_m}m</span>
          </div>
          <div className="flex justify-between items-center p-3">
            <span className="text-xs text-muted-foreground">Passable Area</span>
            <span className="font-mono text-xs text-primary font-medium">{(meta.passable_area_m2 || 0).toFixed(1)} m²</span>
          </div>
        </div>
      </div>

      <div className="p-5 flex flex-col gap-3 bg-sidebar pb-10">
        <h3 className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Exit Coordinates</h3>
        <div className="flex flex-col gap-2">
          {grid.exits.length === 0 ? (
            <div className="text-xs text-muted-foreground italic p-3 border rounded bg-background">No exits defined.</div>
          ) : (
            grid.exits.map(exit => (
              <div key={exit.id} className="flex justify-between items-center text-sm bg-background border px-3 py-2.5 rounded shadow-sm">
                <div className="flex items-center gap-2.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-[#38A169] shadow-[0_0_6px_rgba(56,161,105,0.8)]"></div>
                  <span className="text-xs font-medium">{exit.label || `Exit ${exit.id}`}</span>
                </div>
                <span className="font-mono text-muted-foreground text-[11px]">({exit.row}, {exit.col})</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
