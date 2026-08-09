import { useState } from 'react';
import {
  useGetEvaluationStatus,
  useRunEvaluation,
  useGetEvaluationResults,
  useListLayouts,
  getGetEvaluationStatusQueryKey,
  getGetEvaluationResultsQueryKey,
  getListLayoutsQueryKey,
} from '@workspace/api-client-react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend,
  ReferenceLine, ComposedChart, Bar, CartesianGrid,
} from 'recharts';
import { BarChart2, Play, Loader2, Scale } from 'lucide-react';

function MetricCard({ label, value, sub, good }: { label: string; value: string; sub?: string; good?: boolean }) {
  return (
    <div className="bg-card border border-border rounded p-3 flex flex-col gap-1">
      <p className="text-[9px] font-semibold tracking-widest uppercase text-muted-foreground">{label}</p>
      <p className={`text-xl font-mono font-bold ${good === true ? 'text-green-400' : good === false ? 'text-red-400' : 'text-foreground'}`}>
        {value}
      </p>
      {sub && <p className="text-[9px] text-muted-foreground font-mono">{sub}</p>}
    </div>
  );
}

export function EvaluationPanel() {
  const [layoutId, setLayoutId] = useState('sample_medium');
  const [population, setPopulation] = useState(300);
  const [adherence, setAdherence] = useState(0.70);
  const [nRuns, setNRuns] = useState(20);

  const { data: layouts } = useListLayouts({ query: { queryKey: getListLayoutsQueryKey() } });
  const { data: evalStatus } = useGetEvaluationStatus({
    query: {
      queryKey: getGetEvaluationStatusQueryKey(),
      refetchInterval: (q) => q.state.data?.state === 'running' ? 1000 : false,
    },
  });
  const { data: results } = useGetEvaluationResults({
    query: {
      queryKey: getGetEvaluationResultsQueryKey(),
      enabled: evalStatus?.state === 'done',
    },
  });
  const runMut = useRunEvaluation();

  const isRunning = evalStatus?.state === 'running';

  const handleRun = () => {
    runMut.mutate({ data: { layout_id: layoutId, population, adherence_rate: adherence, n_runs: nRuns } });
  };

  // Congestion time series chart data (downsampled to max 200 pts)
  const rawCong = results?.congestion_time_series;
  const congData = rawCong?.time_axis
    ? rawCong.time_axis
        .map((t, i) => ({
          t: +t.toFixed(1),
          greedy: +((rawCong.greedy_mean?.[i] ?? 0)).toFixed(4),
          guided: +((rawCong.guided_mean?.[i] ?? 0)).toFixed(4),
        }))
        .filter((_, i, arr) => i % Math.max(1, Math.floor(arr.length / 200)) === 0)
    : [];

  // Per-run evacuation time bar data
  const greenyTimes = results?.greedy?.all_times ?? [];
  const guidedTimes = results?.guided?.all_times ?? [];
  const perRunData = Array.from(
    { length: Math.max(greenyTimes.length, guidedTimes.length) },
    (_, i) => ({
      run: i + 1,
      greedy: greenyTimes[i] ?? null,
      guided: guidedTimes[i] ?? null,
    })
  );

  const imp = results?.improvement_pct ?? 0;
  const greedyMean  = results?.greedy?.mean_evac_time_s ?? 0;
  const greedyStd   = results?.greedy?.std_evac_time_s ?? 0;
  const guidedMean  = results?.guided?.mean_evac_time_s ?? 0;
  const guidedStd   = results?.guided?.std_evac_time_s ?? 0;
  const greedyBal   = results?.greedy?.mean_exit_balance ?? 0;
  const guidedBal   = results?.guided?.mean_exit_balance ?? 0;
  const wallTime    = results?.wall_time_s ?? 0;
  const totalRuns   = results?.n_runs ?? 0;

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="px-4 py-3 border-b border-border/50">
        <p className="text-[10px] font-bold tracking-widest uppercase text-muted-foreground">
          A/B Evaluation — Greedy vs ML-Guided
        </p>
      </div>

      <div className="flex-1 p-4 flex flex-col gap-6">

        {/* Config row */}
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Layout</label>
            <select
              className="bg-background border border-border rounded px-2.5 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              value={layoutId} onChange={e => setLayoutId(e.target.value)} disabled={isRunning}
            >
              {layouts?.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Population</label>
            <input type="number" min={20} max={2000} value={population}
              onChange={e => setPopulation(+e.target.value)} disabled={isRunning}
              className="bg-background border border-border rounded px-2.5 py-1.5 text-xs text-foreground w-24 focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Adherence ρ</label>
            <input type="number" min={0} max={1} step={0.05} value={adherence}
              onChange={e => setAdherence(+e.target.value)} disabled={isRunning}
              className="bg-background border border-border rounded px-2.5 py-1.5 text-xs text-foreground w-20 focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Sims/side</label>
            <input type="number" min={5} max={50} value={nRuns}
              onChange={e => setNRuns(+e.target.value)} disabled={isRunning}
              className="bg-background border border-border rounded px-2.5 py-1.5 text-xs text-foreground w-20 focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <button
            onClick={handleRun}
            disabled={isRunning || runMut.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 disabled:opacity-40 transition-colors"
          >
            {isRunning
              ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Running…</>
              : <><Play className="w-3.5 h-3.5" /> Run Evaluation</>}
          </button>
        </div>

        {isRunning && (
          <div className="flex items-center gap-3 text-xs text-blue-300 font-mono bg-blue-900/20 border border-blue-700/30 rounded px-3 py-2">
            <Loader2 className="w-4 h-4 animate-spin shrink-0" />
            Running {nRuns} greedy + {nRuns} ML-guided simulations… This may take several minutes.
          </div>
        )}

        {evalStatus?.error && (
          <div className="text-xs text-red-400 font-mono bg-red-900/20 border border-red-700/30 rounded px-3 py-2">
            {evalStatus.error}
          </div>
        )}

        {results && (
          <>
            {/* Key metric cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <MetricCard label="Time Improvement" value={`${imp > 0 ? '+' : ''}${imp.toFixed(1)}%`} sub="ML-guided vs greedy" good={imp > 0} />
              <MetricCard label="Greedy Mean Time" value={`${greedyMean.toFixed(1)}s`} sub={`±${greedyStd.toFixed(1)}s`} />
              <MetricCard label="Guided Mean Time" value={`${guidedMean.toFixed(1)}s`} sub={`±${guidedStd.toFixed(1)}s`} good={guidedMean < greedyMean} />
              <MetricCard label="Wall Time" value={`${wallTime.toFixed(0)}s`} sub={`${totalRuns * 2} total runs`} />
            </div>

            {/* Exit balance */}
            <div className="flex items-center gap-6 bg-card border border-border rounded px-4 py-3">
              <Scale className="w-4 h-4 text-muted-foreground shrink-0" />
              <div className="flex-1 grid grid-cols-2 gap-4">
                <div>
                  <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">Greedy Exit Balance σ</p>
                  <p className="text-sm font-mono font-bold text-foreground mt-0.5">{greedyBal.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">ML-Guided Exit Balance σ</p>
                  <p className={`text-sm font-mono font-bold mt-0.5 ${guidedBal < greedyBal ? 'text-green-400' : 'text-red-400'}`}>
                    {guidedBal.toFixed(2)}
                  </p>
                </div>
              </div>
              <p className="text-[10px] text-muted-foreground hidden md:block">Lower σ = more balanced exit usage</p>
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              {congData.length > 1 && (
                <div className="bg-card border border-border rounded p-4">
                  <p className="text-[10px] font-bold tracking-widest uppercase text-muted-foreground mb-3">Mean Congestion Over Time</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={congData} margin={{ top: 4, right: 8, bottom: 16, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="t" tick={{ fontSize: 9, fill: '#94A3B8' }}
                        label={{ value: 'Sim. Time (s)', position: 'insideBottom', offset: -8, fontSize: 9, fill: '#64748B' }} />
                      <YAxis tick={{ fontSize: 9, fill: '#94A3B8' }} domain={[0, 1]} />
                      <Tooltip contentStyle={{ background: '#1E293B', border: '1px solid #334155', borderRadius: 4, fontSize: 10 }} labelStyle={{ color: '#94A3B8' }} />
                      <Legend wrapperStyle={{ fontSize: 10, paddingTop: 8 }} />
                      <ReferenceLine y={0.5} stroke="#F59E0B" strokeDasharray="4 4"
                        label={{ value: 'Critical', fontSize: 9, fill: '#F59E0B', position: 'right' }} />
                      <Line type="monotone" dataKey="greedy" stroke="#EF4444" strokeWidth={1.5} dot={false} name="Greedy" />
                      <Line type="monotone" dataKey="guided" stroke="#3B82F6" strokeWidth={1.5} dot={false} name="ML-Guided" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {perRunData.length > 0 && (
                <div className="bg-card border border-border rounded p-4">
                  <p className="text-[10px] font-bold tracking-widest uppercase text-muted-foreground mb-3">Per-Run Evacuation Times</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <ComposedChart data={perRunData} margin={{ top: 4, right: 8, bottom: 16, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="run" tick={{ fontSize: 9, fill: '#94A3B8' }}
                        label={{ value: 'Run #', position: 'insideBottom', offset: -8, fontSize: 9, fill: '#64748B' }} />
                      <YAxis tick={{ fontSize: 9, fill: '#94A3B8' }} />
                      <Tooltip contentStyle={{ background: '#1E293B', border: '1px solid #334155', borderRadius: 4, fontSize: 10 }} labelStyle={{ color: '#94A3B8' }} />
                      <Legend wrapperStyle={{ fontSize: 10, paddingTop: 8 }} />
                      <Bar dataKey="greedy" fill="#EF4444" fillOpacity={0.8} name="Greedy" radius={[2, 2, 0, 0]} />
                      <Bar dataKey="guided" fill="#3B82F6" fillOpacity={0.8} name="ML-Guided" radius={[2, 2, 0, 0]} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </>
        )}

        {!results && !isRunning && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center py-16">
            <BarChart2 className="w-10 h-10 text-slate-600" />
            <p className="text-xs text-slate-500 font-mono max-w-xs leading-relaxed">
              Configure parameters above and click Run Evaluation to compare greedy baseline against ML-guided routing.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
