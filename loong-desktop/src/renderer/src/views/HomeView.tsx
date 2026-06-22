import React, { useState } from 'react';

interface Props {
  state: any;
}

const AGENT_CARDS = [
  { id: 'code', icon: '💻', color: 'blue', name: '代码开发', desc: '编程、调试、重构、代码审查', tags: ['Python', 'TypeScript', '代码审查'] },
  { id: 'office', icon: '📝', color: 'purple', name: '日常办公', desc: '文档撰写、数据分析、PPT生成', tags: ['Word', 'Excel', 'PPT'] },
  { id: 'research', icon: '🔬', color: 'green', name: '深度研究', desc: '多视角辩论、协同洞察、知识图谱', tags: ['辩论', '洞察', '图谱'] },
  { id: 'mission', icon: '🎯', color: 'amber', name: '任务执行', desc: 'PRD驱动、Checkpoint流转、多步骤编排', tags: ['PRD', '编排', '自动化'] },
];

const QUICK_PROMPTS = [
  '🐍 Python爬虫', '📊 代码分析', '📄 技术文档', '🧠 算法解释', '🔧 代码重构',
];

const HOT_SKILLS = [
  { name: '代码生成', source: 'builtin' },
  { name: '文件读写', source: 'builtin' },
  { name: '网页搜索', source: 'builtin' },
  { name: '文档撰写', source: 'office-claw' },
  { name: '数据分析', source: 'office-claw' },
  { name: 'PPT生成', source: 'office-claw' },
  { name: '邮件处理', source: 'workbuddy' },
  { name: '日程管理', source: 'workbuddy' },
  { name: '翻译助手', source: 'doubao-local' },
  { name: '思维导图', source: 'doubao-local' },
];

export default function HomeView({ state }: Props) {
  const [prompt, setPrompt] = useState('');

  const handleSend = () => {
    if (!prompt.trim()) return;
    state.setCurrentView('chat');
    setTimeout(() => state.sendMessage(prompt), 100);
    setPrompt('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-[800px] mx-auto text-center px-6 pt-16 pb-8">
        <div className="w-[72px] h-[72px] rounded-[20px] overflow-hidden mx-auto mb-6 glow-accent">
          <img src="../../assets/logo.jpg" alt="COGU Loong" className="w-full h-full object-cover" />
        </div>
        <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-white to-accent bg-clip-text text-transparent mb-2">
          COGU Loong
        </h1>
        <p className="text-[15px] text-white/40 max-w-[500px] mx-auto leading-relaxed">
          国产原创全栈 AI Agent 系统 · 三级模型策略 · 94项纯本地技能
        </p>

        <div className="mt-8 relative max-w-[680px] mx-auto">
          <textarea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的问题，按 Enter 发送…"
            rows={1}
            className="w-full bg-surface border border-white/[0.06] rounded-xl px-5 py-4 pr-14 text-sm text-white outline-none resize-none min-h-[56px] max-h-[160px] focus:border-accent focus:shadow-[0_0_0_3px_rgba(99,102,241,0.08)] transition-all placeholder:text-white/20"
          />
          <button
            onClick={handleSend}
            disabled={!prompt.trim()}
            className="absolute right-3 bottom-3 w-9 h-9 rounded-lg bg-accent text-white flex items-center justify-center hover:bg-accent-glow transition-all shadow-[0_0_16px_rgba(99,102,241,0.25)] disabled:opacity-30 disabled:cursor-default"
          >
            ↑
          </button>
        </div>

        <div className="mt-5 flex gap-2 justify-center flex-wrap">
          {QUICK_PROMPTS.map(p => (
            <button
              key={p}
              onClick={() => { setPrompt(p.replace(/^[^\s]+\s/, '')); }}
              className="px-3.5 py-1.5 bg-surface border border-white/[0.06] rounded-full text-xs text-white/50 hover:border-white/[0.12] hover:text-white/70 transition-colors"
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-[900px] mx-auto px-6 mt-8">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-[13px] font-semibold text-white/25 uppercase tracking-wider">智能体</span>
          <div className="flex-1 h-px bg-gradient-to-r from-white/[0.06] to-transparent" />
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-3">
          {AGENT_CARDS.map(card => (
            <button
              key={card.id}
              onClick={() => { state.setCurrentView('chat'); }}
              className="bg-surface border border-white/[0.06] rounded-xl p-5 text-left transition-all hover:border-white/[0.12] hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)] group relative overflow-hidden"
            >
              <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-accent to-purple-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg mb-3 ${
                card.color === 'blue' ? 'bg-accent/10' :
                card.color === 'purple' ? 'bg-purple-500/10' :
                card.color === 'green' ? 'bg-emerald-500/10' :
                'bg-amber-500/10'
              }`}>
                {card.icon}
              </div>
              <div className="text-sm font-semibold mb-1">{card.name}</div>
              <div className="text-xs text-white/40 leading-relaxed">{card.desc}</div>
              <div className="flex gap-1.5 mt-2.5 flex-wrap">
                {card.tags.map(t => (
                  <span key={t} className="text-[10px] px-2 py-0.5 rounded bg-white/[0.03] text-white/30 border border-white/[0.06]">{t}</span>
                ))}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-[900px] mx-auto px-6 mt-12 pb-10">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-[13px] font-semibold text-white/25 uppercase tracking-wider">热门技能</span>
          <div className="flex-1 h-px bg-gradient-to-r from-white/[0.06] to-transparent" />
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-2">
          {HOT_SKILLS.map(s => (
            <button
              key={s.name}
              onClick={() => { state.setCurrentView('chat'); }}
              className="bg-surface border border-white/[0.06] rounded-lg px-3.5 py-3 flex items-center gap-2 hover:border-white/[0.12] hover:bg-hover transition-colors"
            >
              <span className="text-base">⚡</span>
              <span className="text-xs font-medium">{s.name}</span>
              <span className="text-[9px] text-white/20 ml-auto">{s.source}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}