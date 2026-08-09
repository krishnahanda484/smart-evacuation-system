import { useState } from 'react';
import {
  useGetDatasetStatus,
  useGenerateDataset,
  useGetMlStatus,
  useTrainModels,
  useGetMlMetrics,
  useGetMlWriteup,
  useReloadPredictor,
  getGetDatasetStatusQueryKey,
  getGetMlStatusQueryKey,
  getGetMlMetricsQueryKey,
  getGetMlWriteupQueryKey,
} from '@workspace/api-client-react';
import { Database, Brain, ChevronDown, ChevronRight, CheckCircle, AlertCircle, Loader2, RefreshCw } from 'lucide-react';

function StateBadge({ state }: { state: string }) {
  const map: Record<string, string> = {
    idle:    'bg-slate-700 text-slate-300',
    running: 'bg-blue-900/60 text-blue-300',
    done:    'bg-green-900/60 text-green-300',
    error:   'bg-red-900/60 text-red-300',
  };
  return (
    <span className={`text-[9px] font-bold tracking-widest uppercase px-2 py-0.5 rounded ${map[state] ?? map.idle}`}>
      {state}
    </span>
  );
}

type ModelKey = 'random_forest' | 'xgboost' | 'mlp';

function MetricsTable({
  data, label,
}: {
  data: Record<string, { rmse: number; mae: number; r2: number }> | undefined;
  label: string;
}) {
  if (!data) return null;
  const entries = Object.entries(data) as [ModelKey, { rmse: number; mae: number; r2: number }][];
  const bestKey = entries.reduce<string>((b, [k, v]) => (!b || v.rmse < (data[b]?.rmse ?? Infinity) ? k : b), '');
  const names: Record<string, string> = { random_forest: 'Random Forest', xgboost: 'XGBoost', mlp: 'MLP' };
  return (
    <div className="mt-3">
      <p className="text-[9px] font-bold tracking-widest uppercase text-muted-foreground mb-1.5">{label}</p>
      <table className="w-full text-[10px] font-mono">
        <thead>
          <tr className="text-muted-foreground">
            <th className="text-left pb-1 font-semibold">Model</th>
            <th className="text-right pb-1 font-semibold">RMSE</th>
            <th className="text-right pb-1 font-semibold">MAE</th>
            <th className="text-right pb-1 font-semibold">R²</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([k, m]) => (
            <tr key={k} className={`border-t border-border/40 ${k === bestKey ? 'text-primary' : 'text-foreground'}`}>
              <td className="py-1">
                <span className="flex items-center gap-1.5">
                  {k === bestKey && <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />}
                  {names[k] ?? k}
                </span>
              </td>
              <td className="text-right py-1">{m.rmse.toFixed(4)}</td>
              <td className="text-right py-1">{m.mae.toFixed(4)}</td>
              <td className="text-right py-1">{m.r2.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PipelinePanel() {
  const [writeupOpen, setWriteupOpen] = useState(false);

  const { data: dsStatus } = useGetDatasetStatus({
    query: {
      queryKey: getGetDatasetStatusQueryKey(),
      refetchInterval: (q) => q.state.data?.state === 'running' ? 2000 : false,
    },
  });
  const { data: mlStatus } = useGetMlStatus({
    query: {
      queryKey: getGetMlStatusQueryKey(),
      refetchInterval: (q) => q.state.data?.state === 'running' ? 2000 : false,
    },
  });
  const { data: metrics } = useGetMlMetrics({
    query: { queryKey: getGetMlMetricsQueryKey(), enabled: mlStatus?.models_exist ?? false },
  });
  const { data: writeup } = useGetMlWriteup({
    query: { queryKey: getGetMlWriteupQueryKey(), enabled: writeupOpen && (mlStatus?.models_exist ?? false) },
  });

  const genMut = useGenerateDataset();
  const trainMut = useTrainModels();
  const reloadMut = useReloadPredictor();

  const fmt = (n: number | undefined) => (n ?? 0).toLocaleString();
  const runsDone = dsStatus?.runs_done ?? 0;
  const runsTotal = dsStatus?.runs_total ?? 1;
  const dsPct = runsTotal > 0 ? Math.round((runsDone / runsTotal) * 100) : 0;

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="px-4 py-3 border-b border-border/50">
        <p className="text-[10px] font-bold tracking-widest uppercase text-muted-foreground">ML Pipeline</p>
      </div>

      <div className="flex-1 p-4 grid grid-cols-1 lg:grid-cols-2 gap-6 content-start">

        {/* ── Dataset column ─────────────────────────────────────────── */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-primary" />
            <h3 className="text-xs font-bold text-foreground">Dataset Generation</h3>
            {dsStatus && <StateBadge state={dsStatus.state} />}
          </div>

          <p className="text-[10px] text-muted-foreground leading-relaxed">
            Runs 300 agent simulations across 3 layouts, 5 population levels and 4 adherence rates
            to produce the ML training CSV (~500K rows).
          </p>

          {dsStatus?.state === 'running' && (
            <div className="flex flex-col gap-1">
              <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
                <span>Runs {runsDone} / {runsTotal}</span>
                <span>{dsPct}%</span>
              </div>
              <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: `${dsPct}%` }} />
              </div>
            </div>
          )}

          {(dsStatus?.rows_written ?? 0) > 0 && (
            <div className="flex items-center gap-2 text-[10px] font-mono">
              {dsStatus?.state === 'done'
                ? <CheckCircle className="w-3.5 h-3.5 text-green-400 shrink-0" />
                : <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin shrink-0" />}
              <span className={dsStatus?.state === 'done' ? 'text-green-300' : 'text-blue-300'}>
                {fmt(dsStatus?.rows_written)} rows written
              </span>
            </div>
          )}

          {dsStatus?.error && (
            <div className="flex items-center gap-2 text-[10px] text-red-400 font-mono">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />{dsStatus.error}
            </div>
          )}

          <button
            onClick={() => genMut.mutate()}
            disabled={genMut.isPending || dsStatus?.state === 'running'}
            className="mt-auto flex items-center justify-center gap-2 py-2 rounded bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 disabled:opacity-40 transition-colors"
          >
            {dsStatus?.state === 'running'
              ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Generating…</>
              : <><Database className="w-3.5 h-3.5" /> Generate Dataset</>}
          </button>
        </div>

        {/* ── ML Training column ─────────────────────────────────────── */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-primary" />
            <h3 className="text-xs font-bold text-foreground">Model Training</h3>
            {mlStatus && <StateBadge state={mlStatus.state} />}
          </div>

          <p className="text-[10px] text-muted-foreground leading-relaxed">
            Trains Random Forest, XGBoost, and MLP regressors. Selects the best model by test-set RMSE.
          </p>

          {mlStatus?.state === 'running' && (
            <div className="flex items-center gap-2 text-[10px] text-blue-300 font-mono">
              <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
              {mlStatus.message || 'Training…'}
            </div>
          )}

          {mlStatus?.predictor_loaded && (
            <div className="text-[10px] font-mono text-green-300 flex items-center gap-1.5">
              <CheckCircle className="w-3.5 h-3.5" />
              Predictor loaded: <strong className="text-green-200">{mlStatus.predictor_model}</strong>
            </div>
          )}

          {metrics && (
            <div className="bg-background border border-border rounded p-3 flex flex-col gap-1">
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-[9px] font-bold tracking-widest uppercase text-muted-foreground">Best:</span>
                <span className="text-[10px] font-bold text-primary">{(metrics.best_congestion ?? '').toUpperCase()}</span>
              </div>
              <MetricsTable data={metrics.congestion_model as Record<string, { rmse: number; mae: number; r2: number }>} label="Congestion in 30s" />
              <MetricsTable data={metrics.evactime_model as Record<string, { rmse: number; mae: number; r2: number }>} label="Evacuation Time" />
              <div className="text-[9px] text-muted-foreground font-mono mt-2 border-t border-border/40 pt-2">
                {fmt(metrics.train_rows)} train / {fmt(metrics.test_rows)} test rows
              </div>
            </div>
          )}

          <div className="flex gap-2">
            <button
              onClick={() => trainMut.mutate()}
              disabled={trainMut.isPending || mlStatus?.state === 'running' || !(mlStatus?.dataset_exists)}
              className="flex-1 flex items-center justify-center gap-2 py-2 rounded bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 disabled:opacity-40 transition-colors"
              title={!mlStatus?.dataset_exists ? 'Generate dataset first' : undefined}
            >
              {mlStatus?.state === 'running'
                ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Training…</>
                : <><Brain className="w-3.5 h-3.5" /> Train Models</>}
            </button>
            {mlStatus?.models_exist && (
              <button
                onClick={() => reloadMut.mutate()}
                disabled={reloadMut.isPending}
                className="px-3 py-2 rounded border border-border text-muted-foreground text-xs hover:border-primary/50 hover:text-foreground disabled:opacity-40 transition-colors"
                title="Reload predictor from disk"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {mlStatus?.models_exist && (
            <div className="border border-border rounded overflow-hidden">
              <button
                onClick={() => setWriteupOpen(v => !v)}
                className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-semibold text-muted-foreground hover:text-foreground hover:bg-background/50 transition-colors"
              >
                <span>Paper Writeup</span>
                {writeupOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              </button>
              {writeupOpen && writeup && (
                <div className="px-3 pb-3 text-[10px] font-mono text-slate-400 leading-relaxed border-t border-border/40 whitespace-pre-wrap">
                  {writeup.methodology_excerpt ?? writeup.comparison_table}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
