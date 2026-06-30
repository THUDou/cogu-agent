import React, { useState, useEffect } from 'react';
import { fetchSettings, saveSettings, fetchPanguStatus, PanguStatus } from '../api';

export default function SettingsView() {
  const [provider, setProvider] = useState('deepseek');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [model, setModel] = useState('deepseek-chat');
  const [panguStatus, setPanguStatus] = useState<PanguStatus | null>(null);
  const [showPangu, setShowPangu] = useState(false);
  const [clickCount, setClickCount] = useState(0);

  useEffect(() => {
    fetchSettings().then(s => {
      setProvider(s.provider || 'deepseek');
      setBaseUrl(s.api_base_url || '');
      setModel(s.model || 'deepseek-chat');
    }).catch(() => {});
    fetchPanguStatus().then(setPanguStatus).catch(() => {});
  }, []);

  useEffect(() => {
    if (clickCount >= 3) {
      setShowPangu(true);
      setClickCount(0);
    }
    const t = setTimeout(() => setClickCount(0), 600);
    return () => clearTimeout(t);
  }, [clickCount]);

  const handleSave = async () => {
    if (apiKey) {
      const api = await import('../api');
      await api.setApiKey(provider, apiKey, baseUrl || undefined, model || undefined);
    }
    await saveSettings({ api_base_url: baseUrl, model, pangu_mini_enabled: showPangu });
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-[640px] mx-auto">
        <h2 className="text-lg font-semibold mb-6">设置</h2>

        <div className="mb-6">
          <div className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3 pb-2 border-b border-white/[0.06]">
            AI 服务配置
          </div>
          <div className="space-y-0">
            <div className="flex items-center justify-between py-3 border-b border-white/[0.06]">
              <div><div className="text-[13px] font-medium">AI 服务商</div><div className="text-[11px] text-white/25">选择 AI 服务提供商</div></div>
              <select value={provider} onChange={e => setProvider(e.target.value)} className="bg-input border border-white/[0.06] rounded-md px-3 py-2 text-xs text-white outline-none focus:border-accent w-[180px]">
                <option value="deepseek">DeepSeek</option>
                <option value="huawei_cloud">华为云 MaaS</option>
                <option value="tencent_cloud">腾讯云</option>
                <option value="openai">OpenAI</option>
                <option value="claude">Anthropic Claude</option>
                <option value="zhipu">智谱 GLM</option>
                <option value="qwen">通义千问</option>
                <option value="moonshot">Moonshot</option>
                <option value="doubao">豆包</option>
                <option value="ollama">Ollama (本地)</option>
                <option value="custom">自定义</option>
              </select>
            </div>
            <div className="flex items-center justify-between py-3 border-b border-white/[0.06]">
              <div><div className="text-[13px] font-medium">API 令牌</div><div className="text-[11px] text-white/25">服务商 API Key</div></div>
              <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="sk-..." className="bg-input border border-white/[0.06] rounded-md px-3 py-2 text-xs text-white outline-none focus:border-accent w-[260px]" />
            </div>
            <div className="flex items-center justify-between py-3 border-b border-white/[0.06]">
              <div><div className="text-[13px] font-medium">API 地址</div><div className="text-[11px] text-white/25">留空使用默认地址</div></div>
              <input type="text" value={baseUrl} onChange={e => setBaseUrl(e.target.value)} placeholder="https://api.example.com/v1" className="bg-input border border-white/[0.06] rounded-md px-3 py-2 text-xs text-white outline-none focus:border-accent w-[260px]" />
            </div>
            <div className="flex items-center justify-between py-3">
              <div><div className="text-[13px] font-medium">默认模型</div><div className="text-[11px] text-white/25">对话使用的模型名称</div></div>
              <input type="text" value={model} onChange={e => setModel(e.target.value)} placeholder="deepseek-chat" className="bg-input border border-white/[0.06] rounded-md px-3 py-2 text-xs text-white outline-none focus:border-accent w-[260px]" />
            </div>
          </div>
          <div className="mt-4 flex gap-2">
            <button onClick={handleSave} className="px-4 py-2 rounded-md bg-accent text-white text-xs font-medium hover:bg-accent-glow transition-colors shadow-[0_0_16px_rgba(99,102,241,0.2)]">保存设置</button>
          </div>
        </div>

        <div className="mb-6">
          <div className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3 pb-2 border-b border-white/[0.06]">
            本地模型
          </div>
          <div className="flex items-center justify-between py-3 border-b border-white/[0.06]">
            <div>
              <div className="text-[13px] font-medium">Qwen3.5-4.6B (GGUF)</div>
              <div className="text-[11px] text-white/25">{panguStatus?.backends?.gguf ? 'GGUF模型已就绪' : '未检测到GGUF模型文件'}</div>
            </div>
            <span className="text-[11px]">{panguStatus?.server_running ? '● 运行中' : '○ 已停止'}</span>
          </div>
        </div>

        {showPangu && (
          <div className="mb-6 opacity-50">
            <div className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3 pb-2 border-b border-white/[0.06]">
              盘古 Mini (实验性 - 隐藏)
            </div>
            <div className="flex items-center justify-between py-3">
              <div>
                <div className="text-[13px] font-medium">盘古-1.39B (Transformers)</div>
                <div className="text-[11px] text-white/25">{panguStatus?.backends?.transformers ? '模型已就绪' : '模型未就绪'}</div>
              </div>
              <span className="text-[11px]">{panguStatus?.server_running ? '● 运行中' : '○ 已停止'}</span>
            </div>
          </div>
        )}

        <div className="mb-6">
          <div className="text-[11px] font-semibold text-white/25 uppercase tracking-wider mb-3 pb-2 border-b border-white/[0.06]">
            关于
          </div>
          <div className="flex items-center justify-between py-3 border-b border-white/[0.06]">
            <div className="text-[13px] font-medium">版本</div>
            <span className="text-xs text-white/40 font-mono">v1.4.0</span>
          </div>
          <div className="flex items-center justify-between py-3 border-b border-white/[0.06]">
            <div className="text-[13px] font-medium">技能数量</div>
            <span className="text-xs text-white/40">94</span>
          </div>
          <div className="flex items-center justify-between py-3">
            <div className="text-[13px] font-medium">模型策略</div>
            <span className="text-xs text-white/40">云端 → Ollama → 本地MINI</span>
          </div>
        </div>

        <div className="text-center pt-4">
          <button
            onClick={() => setClickCount(c => c + 1)}
            className="text-[10px] text-white/10 cursor-default"
          >
            COGU Loong v1.4.0
          </button>
        </div>
      </div>
    </div>
  );
}
