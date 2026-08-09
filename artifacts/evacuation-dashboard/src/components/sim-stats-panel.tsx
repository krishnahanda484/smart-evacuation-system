import { useMemo } from 'react';
import type { SimState, SimResults } from '@workspace/api-client-react';
import { CheckCircle, AlertTriangle } from 'lucide-react';

interface Props {
  simState:   SimState | null;
  results:    SimResults | null;
  population: number;
}

export function SimStatsPanel({ simState, results, population }: Props) {
  // Sparkline from results history
  const sparkData = useMemo(() => {
    if (results?.steps_history) {
      return results.steps_history
        .filter((_, i) => i % 5 === 0)
        .map(h => h.alive);
    }
    return [];
  }, [results]);

  const maxAlive = population;

  // Top 5 congested regions
  const topRegions = useMemo(() => {
    if (!simState?.region_congestion) return [];
    return [...simState.region_congestion]
      .sort((a, b) => b.congestion - a.congestion)
      .slice(0, 5);
  }, [simState?.region_congestion]);

  // Exit flows
  const exitFlows = useMemo(() => {
    const src = results?.exit_flows ?? simState?.exit_flows ?? {};
    return Object.entries(src).map(([k, v]) => ({ id: k, flow: v as number }));
  }, [results?.exit_flows, simState?.exit_flows]);

  const maxFlow = Math.max(1, ...exitFlows.map(e => e.flow));

  // Exit balance
  const exitBalance = useMemo(() => {
    if (exitFlows.length < 2) return null;
    const flows = exitFlows.map(e => e.flow);
    const mean  = flows.reduce((a, b) => a + b, 0) / flows.length;
    const std   = Math.sqrt(flows.reduce((a, b) => a + (b - mean) ** 2, 0) / flows.length);
    return std.toFixed(1);
  }, [exitFlows]);

  // Rerouting events — most recent 5, deduped
  const rerouteEvents: string[] = useMemo(() => {
    const evts: string[] = simState?.reroute_events ?? [];
    return evts.slice(0, 5);
  }, [simState?.reroute_events]);

  // Count currently rerouted zones
  const reroutedZones = (simState?.zone_directions ?? []).filter(z => z.is_rerouted).length;
  const totalZones    = (simState?.zone_directions ?? []).length;

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="px-4 py-3 border-b border-border/50">
        <p className="text-[10px] font-bold tracking-widest uppercase text-muted-foreground">
          Live Stats
        </p>
      </div>

      {!simState ? (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-[11px] text-muted-foreground font-mono">No active run</p>
        </div>
      ) : (
        <div className="flex-1 p-4 flex flex-col gap-5">

          {/* Done banner */}
          {simState.done && (
            <div className="rounded border border-green-500/30 bg-green-500/10 p-3 flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-green-400 shrink-0" />
              <div>
                <div className="text-xs font-bold text-green-300">EVACUATION COMPLETE</div>
                <div className="text-[10px] text-green-400/70 font-mono mt-0.5">
                  {results?.evacuation_time_s?.toFixed(1) ?? simState.time_s.toFixed(1)} s
                  {exitBalance && ` · Exit σ ${exitBalance}`}
                </div>
              </div>
            </div>
          )}

          {/* ── Rerouting alert panel ──────────────────────────────── */}
          {reroutedZones > 0 && (
            <div className="rounded border border-amber-500/40 bg-amber-900/20 p-3 flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                <span className="text-[10px] font-bold text-amber-300 uppercase tracking-wider">
                  Dynamic Rerouting Active
                </span>
                <span className="ml-auto text-[9px] font-mono text-amber-400/70 bg-amber-900/50 px-1.5 py-0.5 rounded">
                  {reroutedZones}/{totalZones} zones
                </span>
              </div>
              <div className="flex flex-col gap-1 max-h-28 overflow-y-auto">
                {rerouteEvents.map((msg, i) => (
                  <p key={i} className="text-[9px] font-mono text-amber-200/80 leading-relaxed border-l-2 border-amber-500/40 pl-2">
                    {msg}
                  </p>
                ))}
                {rerouteEvents.length === 0 && (
                  <p className="text-[9px] font-mono text-amber-300/60">
                    Congestion detected — rerouting occupants via ML guidance…
                  </p>
                )}
              </div>
            </div>
          )}

          {/* ML guidance status when zones are normal */}
          {totalZones > 0 && reroutedZones === 0 && !simState.done && (
            <div className="rounded border border-blue-500/30 bg-blue-900/10 px-3 py-2 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse shrink-0" />
              <span className="text-[9px] font-mono text-blue-300/80">
                ML guidance active — exits balanced, no congestion detected
              </span>
            </div>
          )}

          {/* Progress */}
          <div>
            <div className="flex justify-between text-[10px] font-mono text-muted-foreground mb-1.5">
              <span>Evacuation Progress</span>
              <span>{simState.exited_count}/{population}</span>
            </div>
            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-200"
                style={{
                  width: `${Math.round((simState.exited_count / Math.max(1, population)) * 100)}%`,
                  background: simState.done
                    ? '#38A169'
                    : 'linear-gradient(90deg,#3B82F6,#0EA5E9)',
                }}
              />
            </div>
          </div>

          {/* Exit flows */}
          {exitFlows.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground mb-2">
                Exit Flow
              </p>
              <div className="flex flex-col gap-1.5">
                {exitFlows.map(({ id, flow }) => (
                  <div key={id} className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-muted-foreground w-12 shrink-0">
                      Exit {id}
                    </span>
                    <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-green-500 transition-all duration-300"
                        style={{ width: `${(flow / maxFlow) * 100}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-foreground w-8 text-right">{flow}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top congested regions */}
          {topRegions.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground mb-2">
                Top Congestion
              </p>
              <div className="flex flex-col gap-1">
                {topRegions.map(r => (
                  <div key={r.region_id} className="flex items-center gap-2 rounded bg-background border border-border px-2 py-1">
                    <span className="text-[9px] font-mono text-muted-foreground w-20 shrink-0">
                      [{r.row},{r.col}]
                    </span>
                    <div className="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-200"
                        style={{
                          width: `${r.congestion * 100}%`,
                          background: r.congestion > 0.7 ? '#EF4444' : r.congestion > 0.4 ? '#F59E0B' : '#3B82F6',
                        }}
                      />
                    </div>
                    <span
                      className="text-[10px] font-mono w-10 text-right font-semibold"
                      style={{ color: r.congestion > 0.7 ? '#EF4444' : r.congestion > 0.4 ? '#F59E0B' : '#94A3B8' }}
                    >
                      {Math.round(r.congestion * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sparkline (when results available) */}
          {sparkData.length > 1 && (
            <div>
              <p className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground mb-2">
                Alive Over Time
              </p>
              <div className="h-14 flex items-end gap-px bg-background border border-border rounded p-1 overflow-hidden">
                {sparkData.map((v, i) => (
                  <div
                    key={i}
                    className="flex-1 rounded-sm bg-blue-500/70 min-w-px"
                    style={{ height: `${Math.max(2, ((v ?? 0) / maxAlive) * 100)}%` }}
                  />
                ))}
              </div>
              <div className="flex justify-between text-[9px] font-mono text-muted-foreground mt-1">
                <span>t=0</span>
                <span>Agents alive</span>
                <span>t={results?.evacuation_time_s?.toFixed(0)}s</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
