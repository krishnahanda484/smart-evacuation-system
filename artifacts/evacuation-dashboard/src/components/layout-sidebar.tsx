import { useListLayouts } from '@workspace/api-client-react';
import { Layers, Box, DoorOpen } from 'lucide-react';

export function LayoutSidebar({ selectedId, onSelect }: { selectedId: string | null, onSelect: (id: string) => void }) {
  const { data: layouts, isLoading, error } = useListLayouts();

  if (isLoading) {
    return (
      <div className="p-4 flex flex-col gap-3">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-28 bg-card animate-pulse rounded border border-border"></div>
        ))}
      </div>
    );
  }

  if (error || !layouts) {
    return <div className="p-4 text-sm text-destructive font-mono">Failed to load layouts.</div>;
  }

  return (
    <div className="flex flex-col p-3 gap-2">
      {layouts.map(meta => (
        <button
          key={meta.id}
          onClick={() => onSelect(meta.id)}
          className={`flex flex-col p-3 border rounded text-left transition-all duration-200 ${
            selectedId === meta.id 
              ? 'bg-primary/10 border-primary shadow-[0_0_0_1px_hsl(var(--primary))]' 
              : 'bg-card border-border hover:border-muted-foreground/50 hover:bg-card/80'
          }`}
        >
          <div className="flex justify-between items-start w-full mb-3">
            <span className="font-semibold text-sm leading-tight pr-2">{meta.name}</span>
            {meta.is_sample && (
              <span className="text-[10px] bg-secondary px-1.5 py-0.5 rounded text-secondary-foreground font-medium uppercase tracking-wider shrink-0 shadow-sm border border-secondary-border">
                Sample
              </span>
            )}
          </div>
          
          <div className="grid grid-cols-2 gap-y-2 mt-auto w-full">
            <div className="text-[11px] text-muted-foreground font-mono flex items-center gap-1.5">
              <Box className="w-3.5 h-3.5 text-muted-foreground/80" />
              {meta.width}×{meta.height}
            </div>
            <div className="text-[11px] text-muted-foreground font-mono flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-muted-foreground/80" />
              {meta.physical_width_m}m × {meta.physical_height_m}m
            </div>
            <div className="text-[11px] font-mono flex items-center gap-1.5 col-span-2">
              <DoorOpen className="w-3.5 h-3.5 text-[#38A169] opacity-90" />
              <span className="text-muted-foreground">{meta.exit_count} Exits</span>
            </div>
          </div>
        </button>
      ))}
      {layouts.length === 0 && (
        <div className="text-sm text-muted-foreground text-center py-8 font-mono">No layouts available.</div>
      )}
    </div>
  );
}
