import { useRef, useEffect, useState } from 'react';
import type { GridData } from '@workspace/api-client-react';

const CELL_COLORS: Record<number, string> = {
  0: '#F0F0F0', // FREE
  1: '#2D3748', // WALL
  2: '#805AD5', // OBSTACLE
  3: '#38A169', // EXIT
};

const CELL_NAMES: Record<number, string> = {
  0: 'FREE',
  1: 'WALL',
  2: 'OBSTACLE',
  3: 'EXIT',
};

interface HoverInfo {
  row: number;
  col: number;
  type: string;
  x: number;
  y: number;
}

export function GridCanvas({ gridData }: { gridData: GridData }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoverInfo, setHoverInfo] = useState<HoverInfo | null>(null);
  
  const drawInfo = useRef({ cellSize: 0, offsetX: 0, offsetY: 0 });

  useEffect(() => {
    if (!gridData || !canvasRef.current || !containerRef.current) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const container = containerRef.current;

    const draw = () => {
      const { width: cWidth, height: cHeight } = container.getBoundingClientRect();
      if (cWidth === 0 || cHeight === 0) return;
      
      const cols = gridData.width;
      const rows = gridData.height;

      const maxCellSize = 24; // Scale up to 24px per cell for visibility
      const padding = 48; // Padding on all sides to allow breathing room

      const cellW = (cWidth - padding * 2) / cols;
      const cellH = (cHeight - padding * 2) / rows;
      const cellSize = Math.min(cellW, cellH, maxCellSize);
      
      // Math.floor to avoid subpixel antialiasing gaps causing blurry lines
      const finalCellSize = Math.max(1, Math.floor(cellSize));

      const drawW = finalCellSize * cols;
      const drawH = finalCellSize * rows;

      const offsetX = Math.floor((cWidth - drawW) / 2);
      const offsetY = Math.floor((cHeight - drawH) / 2);

      drawInfo.current = { cellSize: finalCellSize, offsetX, offsetY };

      const dpr = window.devicePixelRatio || 1;
      canvas.width = cWidth * dpr;
      canvas.height = cHeight * dpr;
      canvas.style.width = `${cWidth}px`;
      canvas.style.height = `${cHeight}px`;

      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, cWidth, cHeight);

      // Translate to center the grid
      ctx.translate(offsetX, offsetY);

      // Optional grid background to frame it well
      ctx.fillStyle = 'rgba(15, 23, 42, 0.5)'; // subtle dark backdrop matching bg
      ctx.fillRect(0, 0, drawW, drawH);

      // Draw cells
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const val = gridData.cells[r]?.[c] ?? 0;
          ctx.fillStyle = CELL_COLORS[val] || CELL_COLORS[0];
          
          // Create a subtle grid line effect by subtracting 1px if cells are large enough
          const gap = finalCellSize > 6 ? 1 : 0;
          ctx.fillRect(
            c * finalCellSize, 
            r * finalCellSize, 
            finalCellSize - gap, 
            finalCellSize - gap
          );

          if (val === 3) {
            // Exit highlight/glow border
            ctx.strokeStyle = '#68D391'; // Lighter green
            ctx.lineWidth = finalCellSize > 12 ? 2 : 1;
            ctx.strokeRect(
              c * finalCellSize + (ctx.lineWidth / 2), 
              r * finalCellSize + (ctx.lineWidth / 2), 
              finalCellSize - gap - ctx.lineWidth, 
              finalCellSize - gap - ctx.lineWidth
            );
          }
        }
      }
      
      // Reset transform for absolute mouse coordinates
      ctx.setTransform(1, 0, 0, 1, 0, 0);
    };

    draw();

    // Handle resize observation
    const resizeObserver = new ResizeObserver(() => {
      requestAnimationFrame(draw);
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
    };
  }, [gridData]);

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!containerRef.current || !gridData) return;
    
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const { cellSize, offsetX, offsetY } = drawInfo.current;
    
    const col = Math.floor((x - offsetX) / cellSize);
    const row = Math.floor((y - offsetY) / cellSize);

    if (row >= 0 && row < gridData.height && col >= 0 && col < gridData.width) {
      const val = gridData.cells[row]?.[col] ?? 0;
      setHoverInfo({
        row,
        col,
        type: CELL_NAMES[val] || 'UNKNOWN',
        x: e.clientX,
        y: e.clientY
      });
    } else {
      setHoverInfo(null);
    }
  };

  const handleMouseLeave = () => {
    setHoverInfo(null);
  };

  // Safe window dimensions for tooltip clamp
  const maxW = typeof window !== 'undefined' ? window.innerWidth : 1000;
  const maxH = typeof window !== 'undefined' ? window.innerHeight : 1000;

  return (
    <div 
      ref={containerRef} 
      className="flex-1 w-full h-full relative cursor-crosshair overflow-hidden" 
      onMouseMove={handleMouseMove} 
      onMouseLeave={handleMouseLeave}
    >
      <canvas ref={canvasRef} className="absolute inset-0" />
      
      {hoverInfo && (
        <div 
          className="fixed pointer-events-none z-50 bg-popover text-popover-foreground text-xs px-3 py-2 rounded shadow-2xl font-mono border border-border" 
          style={{ 
            left: Math.min(hoverInfo.x + 16, maxW - 140), 
            top: Math.min(hoverInfo.y + 16, maxH - 100) 
          }}
        >
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center gap-4">
              <span className="font-semibold text-[10px] uppercase text-muted-foreground tracking-wider">Type</span>
              <span className="flex items-center gap-1.5 font-bold text-[11px]">
                <div 
                  className="w-2.5 h-2.5 rounded-[2px] shadow-[inset_0_0_0_1px_rgba(0,0,0,0.1)]" 
                  style={{ backgroundColor: CELL_COLORS[Object.keys(CELL_NAMES).find(k => CELL_NAMES[Number(k)] === hoverInfo.type) as any] || '#000' }}
                ></div>
                {hoverInfo.type}
              </span>
            </div>
            <div className="flex justify-between items-center gap-4 border-t border-border/50 pt-1.5">
              <span className="font-semibold text-[10px] uppercase text-muted-foreground tracking-wider">Coord</span>
              <span className="text-[11px]">[{hoverInfo.row}, {hoverInfo.col}]</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
