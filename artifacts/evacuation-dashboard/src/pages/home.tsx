import { useState } from 'react';
import {
  useGetLayout,
  useGetSimulationState,
  useGetSimulationResults,
  getGetLayoutQueryKey,
  getGetSimulationStateQueryKey,
  getGetSimulationResultsQueryKey,
} from '@workspace/api-client-react';
import { Activity, Map, Play, Cpu, BarChart2 } from 'lucide-react';

import { LayoutSidebar } from '@/components/layout-sidebar';
import { GridCanvas } from '@/components/grid-canvas';
import { StatsPanel } from '@/components/stats-panel';
import { SimulationCanvas } from '@/components/simulation-canvas';
import { SimConfigPanel } from '@/components/sim-config-panel';
import { SimStatsPanel } from '@/components/sim-stats-panel';
import { PipelinePanel } from '@/components/pipeline-panel';
import { EvaluationPanel } from '@/components/evaluation-panel';

type Tab = 'grid' | 'simulation' | 'pipeline' | 'evaluation';

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'grid',       label: 'Grid Map',   icon: <Map className="w-3.5 h-3.5" /> },
  { id: 'simulation', label: 'Simulation', icon: <Play className="w-3.5 h-3.5" /> },
  { id: 'pipeline',   label: 'Pipeline',   icon: <Cpu className="w-3.5 h-3.5" /> },
  { id: 'evaluation', label: 'Evaluation', icon: <BarChart2 className="w-3.5 h-3.5" /> },
];

export default function Home() {
  const [tab, setTab] = useState<Tab>('grid');

  // ── Grid map ─────────────────────────────────────────────────────────────
  const [selectedLayoutId, setSelectedLayoutId] = useState<string | null>(null);
  const { data: layout, isLoading: layoutLoading } = useGetLayout(
    selectedLayoutId ?? '',
    { query: { enabled: !!selectedLayoutId, queryKey: selectedLayoutId ? getGetLayoutQueryKey(selectedLayoutId) : ['_empty_'] } }
  );

  // ── Simulation ───────────────────────────────────────────────────────────
  const [runId, setRunId]             = useState<string | null>(null);
  const [simLayoutId, setSimLayoutId] = useState('sample_medium');
  const [simPop, setSimPop]           = useState(200);

  const { data: simLayout } = useGetLayout(simLayoutId, {
    query: { queryKey: getGetLayoutQueryKey(simLayoutId) },
  });

  const { data: simState } = useGetSimulationState(runId ?? '', {
    query: {
      queryKey: getGetSimulationStateQueryKey(runId ?? ''),
      enabled: !!runId,
      refetchInterval: (q) => (q.state.data?.done ? false : 500),
    },
  });

  const { data: simResults } = useGetSimulationResults(runId ?? '', {
    query: {
      queryKey: getGetSimulationResultsQueryKey(runId ?? ''),
      enabled: !!runId && (simState?.done ?? false),
    },
  });

  return (
    <div className="flex flex-col h-[100dvh] bg-background text-foreground overflow-hidden font-sans">

      {/* Header */}
      <header className="flex-none h-12 border-b bg-card flex items-center px-4 justify-between z-20 shadow-sm">
        <div className="flex items-center gap-3 mr-6 shrink-0">
          <div className="w-7 h-7 rounded bg-primary flex items-center justify-center text-primary-foreground shadow-sm">
            <Activity className="w-4 h-4" />
          </div>
          <div className="hidden sm:block">
            <h1 className="text-xs font-bold leading-tight tracking-tight">Smart Evacuation System</h1>
            <p className="text-[9px] text-muted-foreground leading-tight tracking-widest uppercase font-semibold">
              Ibrahim et al., IEEE Access 2023
            </p>
          </div>
        </div>

        <nav className="flex items-center gap-0.5">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 px-3 h-8 rounded text-[11px] font-semibold transition-colors
                ${tab === t.id ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-background'}`}
            >
              {t.icon}
              <span className="hidden sm:inline">{t.label}</span>
            </button>
          ))}
        </nav>

        <div className="flex items-center ml-6 shrink-0">
          <div className="text-[9px] font-mono text-muted-foreground hidden sm:flex items-center gap-1.5 bg-background px-2 py-1 rounded border">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            SYSTEM ONLINE
          </div>
        </div>
      </header>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">

        {/* Tab 1: Grid Map */}
        {tab === 'grid' && (
          <div className="flex h-full">
            <aside className="w-72 flex-none border-r bg-card flex flex-col">
              <div className="px-4 py-2.5 border-b border-border/50">
                <p className="text-[10px] font-bold tracking-widest uppercase text-muted-foreground">Available Layouts</p>
              </div>
              <div className="flex-1 overflow-y-auto">
                <LayoutSidebar selectedId={selectedLayoutId} onSelect={setSelectedLayoutId} />
              </div>
            </aside>

            <main
              className="flex-1 relative flex bg-[#0a1120] overflow-hidden"
              style={{ backgroundImage: 'radial-gradient(circle, #1e293b 1px, transparent 1px)', backgroundSize: '20px 20px' }}
            >
              {selectedLayoutId ? (
                layoutLoading ? (
                  <div className="m-auto flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                    <p className="text-[10px] font-mono text-muted-foreground tracking-widest animate-pulse">Loading…</p>
                  </div>
                ) : layout ? (
                  <GridCanvas gridData={layout.grid} />
                ) : (
                  <p className="m-auto text-xs text-destructive font-mono">Failed to load layout</p>
                )
              ) : (
                <div className="m-auto flex flex-col items-center gap-4 text-center">
                  <div className="w-16 h-16 rounded-xl border-2 border-dashed border-slate-700 flex items-center justify-center">
                    <Map className="w-7 h-7 text-slate-600" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Awaiting Input</p>
                    <p className="text-[10px] text-slate-600 mt-1 max-w-48 leading-relaxed">Select a layout to visualize the cellular grid</p>
                  </div>
                </div>
              )}
              {selectedLayoutId && layout && !layoutLoading && (
                <div className="absolute bottom-3 left-3 bg-card/90 backdrop-blur border border-border rounded px-2.5 py-1.5 text-[10px] font-mono text-muted-foreground shadow flex items-center gap-1.5">
                  <span className="w-1 h-1 rounded-full bg-primary animate-pulse" />
                  {layout.grid.width} × {layout.grid.height} matrix
                </div>
              )}
            </main>

            <aside className="w-72 flex-none border-l bg-card flex flex-col">
              <div className="flex-1 overflow-y-auto">
                <StatsPanel layout={layout} isLoading={layoutLoading && !!selectedLayoutId} />
              </div>
            </aside>
          </div>
        )}

        {/* Tab 2: Simulation */}
        {tab === 'simulation' && (
          <div className="flex h-full">
            <aside className="w-64 flex-none border-r bg-card">
              <SimConfigPanel
                runId={runId}
                onRunId={setRunId}
                onLayoutId={setSimLayoutId}
                onPopulation={setSimPop}
                simState={simState ?? null}
                population={simPop}
              />
            </aside>

            <SimulationCanvas
              gridData={simLayout?.grid ?? null}
              simState={simState ?? null}
              population={simPop}
            />

            <aside className="w-64 flex-none border-l bg-card">
              <SimStatsPanel
                simState={simState ?? null}
                results={simResults ?? null}
                population={simPop}
              />
            </aside>
          </div>
        )}

        {/* Tab 3: Pipeline */}
        {tab === 'pipeline' && (
          <div className="h-full bg-background overflow-auto">
            <PipelinePanel />
          </div>
        )}

        {/* Tab 4: Evaluation */}
        {tab === 'evaluation' && (
          <div className="h-full bg-background overflow-auto">
            <EvaluationPanel />
          </div>
        )}
      </div>
    </div>
  );
}
