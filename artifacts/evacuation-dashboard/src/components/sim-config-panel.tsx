import { useState } from 'react';
import {
  useListLayouts,
  useStartSimulation,
  useStepSimulation,
  useRunSimulationToCompletion,
  useResetSimulation,
} from '@workspace/api-client-react';
import { Play, StepForward, FastForward, RotateCcw, Cpu } from 'lucide-react';

interface SimStateCompact {
  alive_count: number;
  exited_count: number;
  time_s: number;
  step: number;
  done: boolean;
}

interface Props {
  runId: string | null;
  onRunId: (id: string | null) => void;
  onLayoutId: (id: string) => void;
  onPopulation: (n: number) => void;
  simState: SimStateCompact | null;
  population: number;
}

export function SimConfigPanel({ runId, onRunId, onLayoutId, onPopulation, simState, population }: Props) {
  const [layoutId, setLayoutId] = useState('sample_medium');
  const [pop, setPop] = useState(200);
  const [adherence, setAdherence] = useState(0.70);
  const [useML, setUseML] = useState(true);

  const { data: layouts } = useListLayouts();
  const startMut = useStartSimulation();
  const stepMut = useStepSimulation();
  const runMut = useRunSimulationToCompletion();
  const resetMut = useResetSimulation();

  const handleStart = async () => {
    if (runId) {
      await resetMut.mutateAsync({ runId });
      onRunId(null);
    }
    const res = await startMut.mutateAsync({
      data: { layout_id: layoutId, population: pop, adherence_rate: adherence, use_ml: useML },
    });
    onRunId(res.run_id);
    onLayoutId(layoutId);
    onPopulation(pop);
  };

  const handleStep = () => {
    if (!runId) return;
    stepMut.mutate({ runId, data: { steps: 10 } });
  };

  const handleRunToEnd = () => {
    if (!runId) return;
    runMut.mutate({ runId });
  };

  const handleReset = async () => {
    if (runId) await resetMut.mutateAsync({ runId });
    onRunId(null);
  };

  const busy = startMut.isPending || stepMut.isPending || runMut.isPending;
  const active = !!runId && !simState?.done;

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="px-4 py-3 border-b border-border/50">
        <p className="text-[10px] font-bold tracking-widest uppercase text-muted-foreground">
          Simulation Config
        </p>
      </div>

      <div className="flex-1 p-4 flex flex-col gap-5">
        {/* Layout */}
        <div className="flex flex-col gap-1.5">
          <label className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">
            Layout
          </label>
          <select
            className="bg-background border border-border rounded px-2.5 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            value={layoutId}
            onChange={e => { setLayoutId(e.target.value); onLayoutId(e.target.value); }}
            disabled={active}
          >
            {layouts?.map(l => (
              <option key={l.id} value={l.id}>{l.name}</option>
            ))}
          </select>
        </div>

        {/* Population */}
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between items-center">
            <label className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">Population</label>
            <span className="text-xs font-mono text-primary font-bold">{pop}</span>
          </div>
          <input
            type="range" min={20} max={2000} step={10}
            value={pop}
            onChange={e => { const v = +e.target.value; setPop(v); onPopulation(v); }}
            disabled={active}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-[9px] text-muted-foreground font-mono">
            <span>20</span><span>2000</span>
          </div>
        </div>

        {/* Adherence */}
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between items-center">
            <label className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">
              Guided Adherence ρ
            </label>
            <span className="text-xs font-mono text-primary font-bold">{adherence.toFixed(2)}</span>
          </div>
          <input
            type="range" min={0} max={1} step={0.05}
            value={adherence}
            onChange={e => setAdherence(+e.target.value)}
            disabled={active}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-[9px] text-muted-foreground font-mono">
            <span>0.00</span><span>1.00</span>
          </div>
        </div>

        {/* Use ML */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Cpu className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">
              ML-Guided Routing
            </span>
          </div>
          <button
            onClick={() => setUseML(v => !v)}
            disabled={active}
            className={`relative w-10 h-5 rounded-full transition-colors ${useML ? 'bg-primary' : 'bg-slate-700'} disabled:opacity-40`}
          >
            <span
              className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${useML ? 'translate-x-5' : 'translate-x-0.5'}`}
            />
          </button>
        </div>

        {/* Action buttons */}
        <div className="flex flex-col gap-2 pt-2 border-t border-border/50">
          <button
            onClick={handleStart}
            disabled={busy}
            className="flex items-center justify-center gap-2 w-full py-2 rounded bg-primary text-primary-foreground text-xs font-bold tracking-wide hover:bg-primary/90 disabled:opacity-40 transition-colors"
          >
            <Play className="w-3.5 h-3.5" />
            {runId ? 'Restart' : 'Start Simulation'}
          </button>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={handleStep}
              disabled={!active || busy}
              className="flex items-center justify-center gap-1.5 py-1.5 rounded bg-slate-700 text-foreground text-xs hover:bg-slate-600 disabled:opacity-30 transition-colors"
            >
              <StepForward className="w-3 h-3" /> Step ×10
            </button>
            <button
              onClick={handleRunToEnd}
              disabled={!active || busy}
              className="flex items-center justify-center gap-1.5 py-1.5 rounded bg-slate-700 text-foreground text-xs hover:bg-slate-600 disabled:opacity-30 transition-colors"
            >
              <FastForward className="w-3 h-3" /> Run End
            </button>
          </div>
          <button
            onClick={handleReset}
            disabled={!runId || busy}
            className="flex items-center justify-center gap-1.5 py-1.5 rounded border border-border text-muted-foreground text-xs hover:border-primary/50 hover:text-foreground disabled:opacity-30 transition-colors"
          >
            <RotateCcw className="w-3 h-3" /> Reset
          </button>
        </div>

        {/* Live counters */}
        {simState && (
          <div className="grid grid-cols-2 gap-2">
            {([
              ['Alive',    simState.alive_count],
              ['Exited',   simState.exited_count],
              ['Time (s)', simState.time_s.toFixed(1)],
              ['Step',     simState.step],
            ] as [string, string | number][]).map(([label, value]) => (
              <div key={label} className="bg-background rounded border border-border p-2 text-center">
                <div className="text-[9px] text-muted-foreground uppercase tracking-wider font-semibold">{label}</div>
                <div className="text-sm font-mono font-bold text-foreground mt-0.5">{value}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
