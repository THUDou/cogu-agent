import React, { useState, useEffect } from 'react';
import { fetchNodeTypes, fetchPlugins, NodeTypeDef, Plugin } from '../api';

export default function StudioView() {
  const [nodeTypes, setNodeTypes] = useState<NodeTypeDef[]>([]);
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [activeTab, setActiveTab] = useState<'nodes' | 'plugins' | 'canvas'>('nodes');
  const [filterCategory, setFilterCategory] = useState('');
  const [canvasJson, setCanvasJson] = useState('');
  const [convertResult, setConvertResult] = useState<any>(null);

  useEffect(() => {
    fetchNodeTypes(filterCategory || undefined).then(setNodeTypes).catch(() => {});
    fetchPlugins().then(setPlugins).catch(() => {});
  }, [filterCategory]);

  const categories = [...new Set(nodeTypes.map(n => n.category))];

  const handleConvertCanvas = async () => {
    try {
      const data = JSON.parse(canvasJson);
      const { convertCanvas } = await import('../api');
      const result = await convertCanvas(data);
      setConvertResult(result);
    } catch (e: any) {
      setConvertResult({ error: e.message });
    }
  };

  return (
    <div className="flex flex-col h-full p-4 overflow-y-auto">
      <h2 className="text-lg font-bold mb-4 text-white/90">Agent Studio</h2>

      <div className="flex gap-2 mb-4">
        {(['nodes', 'plugins', 'canvas'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1.5 rounded text-sm transition-colors ${
              activeTab === tab ? 'bg-blue-600 text-white' : 'bg-white/5 text-white/60 hover:bg-white/10'
            }`}
          >
            {tab === 'nodes' ? '节点类型' : tab === 'plugins' ? '插件市场' : 'Canvas转换'}
          </button>
        ))}
      </div>

      {activeTab === 'nodes' && (
        <div>
          <div className="flex gap-2 mb-3 flex-wrap">
            <button
              onClick={() => setFilterCategory('')}
              className={`px-2 py-1 rounded text-xs ${!filterCategory ? 'bg-blue-500/30 text-blue-300' : 'bg-white/5 text-white/50'}`}
            >
              全部 ({nodeTypes.length})
            </button>
            {categories.map(cat => (
              <button
                key={cat}
                onClick={() => setFilterCategory(cat)}
                className={`px-2 py-1 rounded text-xs ${filterCategory === cat ? 'bg-blue-500/30 text-blue-300' : 'bg-white/5 text-white/50'}`}
              >
                {cat}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2">
            {nodeTypes.map(nt => (
              <div key={nt.type} className="bg-white/5 rounded-lg p-3 border border-white/10">
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: nt.color }} />
                  <span className="text-sm font-medium text-white/90">{nt.display_key}</span>
                  {nt.is_composite && (
                    <span className="text-[10px] bg-purple-500/30 text-purple-300 px-1.5 rounded">复合</span>
                  )}
                </div>
                <p className="text-xs text-white/50">{nt.description}</p>
                <div className="text-[10px] text-white/30 mt-1">{nt.type} · {nt.category}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'plugins' && (
        <div>
          {plugins.length === 0 ? (
            <div className="text-center py-8 text-white/40">
              <p className="text-sm">暂无已注册插件</p>
              <p className="text-xs mt-1">通过 API POST /api/plugins 注册 OpenAPI 插件</p>
            </div>
          ) : (
            <div className="space-y-2">
              {plugins.map(p => (
                <div key={p.plugin_id} className="bg-white/5 rounded-lg p-3 border border-white/10">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-white/90">{p.name}</span>
                    <span className="text-xs text-white/40">v{p.version}</span>
                  </div>
                  <p className="text-xs text-white/50 mt-1">{p.description}</p>
                  <div className="flex gap-2 mt-2">
                    <span className="text-[10px] bg-green-500/20 text-green-300 px-1.5 rounded">
                      {p.tool_count} 工具
                    </span>
                    {p.category && (
                      <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 rounded">
                        {p.category}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'canvas' && (
        <div>
          <textarea
            value={canvasJson}
            onChange={e => setCanvasJson(e.target.value)}
            placeholder='粘贴 Canvas JSON (nodes + edges)...'
            className="w-full h-48 bg-black/30 border border-white/10 rounded-lg p-3 text-xs text-white/80 font-mono resize-none"
          />
          <button
            onClick={handleConvertCanvas}
            className="mt-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
          >
            转换为 WorkflowSchema
          </button>
          {convertResult && (
            <pre className="mt-3 bg-black/30 border border-white/10 rounded-lg p-3 text-xs text-white/70 font-mono overflow-auto max-h-64">
              {JSON.stringify(convertResult, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}