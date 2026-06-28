import React, { useState, useEffect } from 'react';
import { fetchTraces, fetchMetricsSummary, fetchModelMetrics, fetchPipelineStats, TraceSpan } from '../api';

export default function ObserveView() {
  const [traces, setTraces] = useState<TraceSpan[]>([]);
  const [metrics, setMetrics] = useState<any>({});
  const [modelMetrics, setModelMetrics] = useState<any>({});
  const [pipelineStats, setPipelineStats] = useState<any>({});
  const [activeTab, setActiveTab] = useState<'traces' | 'metrics' | 'pipeline'>('traces');
  const [selectedTrace, setSelectedTrace] = useState('');

  const refresh = async () => {
    try {
      const [t, m, mm, ps] = await Promise.all([
        fetchTraces(selectedTrace || undefined, 50).catch(() => []),
        fetchMetricsSummary(24).catch(() => ({})),
        fetchModelMetrics().catch(() => ({})),
        fetchPipelineStats().catch(() => ({})),
      ]);
      setTraces(t);
      setMetrics(m);
      setModelMetrics(mm);
      setPipelineStats(ps);
    } catch {}
  };

  useEffect(() => { refresh(); }, [selectedTrace]);

  const formatDuration = (us: number) => {
    if (us < 1000) return `${us}μs`;
    if (us < 1000000) return `${(us / 1000).toFixed(1)}ms`;
    return `${(us / 1000000).toFixed(2)}s`;
  };

  const spanTypeColors: Record<string, string> = {
    agent: 'bg-blue-500/30 text-blue-300',
    model: 'bg-green-500/30 text-green-300',
    tool: 'bg-yellow-500/30 text-yellow-300',
    workflow: 'bg-purple-500/30 text-purple-300',
    plugin: 'bg-pink-500/30 text-pink-300',
  };

  return (
    <div className="flex flex-col h-full p-4 overflow-y-auto">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-white/90">可观测性</h2>
        <button
          onClick={refresh}
          className="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-white/70 text-xs rounded-lg transition-colors"
        >
          刷新
        </button>
      </div>

      <div className="flex gap-2 mb-4">
        {(['traces', 'metrics', 'pipeline'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1.5 rounded text-sm transition-colors ${
              activeTab === tab ? 'bg-blue-600 text-white' : 'bg-white/5 text-white/60 hover:bg-white/10'
            }`}
          >
            {tab === 'traces' ? 'Trace' : tab === 'metrics' ? 'Metrics' : 'Pipeline'}
          </button>
        ))}
      </div>

      {activeTab === 'traces' && (
        <div>
          <div className="flex gap-2 mb-3">
            <input
              value={selectedTrace}
              onChange={e => setSelectedTrace(e.target.value)}
              placeholder="按 trace_id 过滤..."
              className="flex-1 bg-black/30 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white/80"
            />
          </div>
          {traces.length === 0 ? (
            <div className="text-center py-8 text-white/40">
              <p className="text-sm">暂无 Trace 数据</p>
              <p className="text-xs mt-1">Agent 运行时自动采集</p>
            </div>
          ) : (
            <div className="space-y-1">
              {traces.map(span => (
                <div key={span.span_id} className="bg-white/5 rounded px-3 py-2 flex items-center gap-3 text-xs">
                  <span className={`px-1.5 py-0.5 rounded ${spanTypeColors[span.span_type] || 'bg-white/10 text-white/50'}`}>
                    {span.span_type}
                  </span>
                  <span className="text-white/80 flex-1 truncate">{span.span_name}</span>
                  <span className="text-white/40">{formatDuration(span.duration)}</span>
                  <span className={`px-1.5 py-0.5 rounded ${span.status_code === 'ok' ? 'bg-green-500/20 text-green-300' : 'bg-red-500/20 text-red-300'}`}>
                    {span.status_code}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'metrics' && (
        <div className="space-y-4">
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-sm font-medium text-white/80 mb-3">模型指标</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-white/40">QPM</div>
                <div className="text-lg font-mono text-white/90">{(modelMetrics.qpm || 0).toFixed(1)}</div>
              </div>
              <div>
                <div className="text-xs text-white/40">成功率</div>
                <div className="text-lg font-mono text-white/90">{((modelMetrics.success_ratio || 0) * 100).toFixed(1)}%</div>
              </div>
              <div>
                <div className="text-xs text-white/40">平均延迟</div>
                <div className="text-lg font-mono text-white/90">{(modelMetrics.avg_latency_s || 0).toFixed(2)}s</div>
              </div>
              <div>
                <div className="text-xs text-white/40">TTFT</div>
                <div className="text-lg font-mono text-white/90">{(modelMetrics.ttft_avg_s || 0).toFixed(2)}s</div>
              </div>
            </div>
          </div>
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-sm font-medium text-white/80 mb-2">指标摘要 (24h)</h3>
            <pre className="text-xs text-white/60 font-mono overflow-auto max-h-48">
              {JSON.stringify(metrics.metrics || metrics, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {activeTab === 'pipeline' && (
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <h3 className="text-sm font-medium text-white/80 mb-3">Collector Pipeline</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs text-white/40">已接收</div>
              <div className="text-lg font-mono text-blue-300">{pipelineStats.received || 0}</div>
            </div>
            <div>
              <div className="text-xs text-white/40">已处理</div>
              <div className="text-lg font-mono text-green-300">{pipelineStats.processed || 0}</div>
            </div>
            <div>
              <div className="text-xs text-white/40">已导出</div>
              <div className="text-lg font-mono text-yellow-300">{pipelineStats.exported || 0}</div>
            </div>
            <div>
              <div className="text-xs text-white/40">错误</div>
              <div className="text-lg font-mono text-red-300">{pipelineStats.errors || 0}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}