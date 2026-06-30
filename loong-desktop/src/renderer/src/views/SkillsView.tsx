import React, { useState, useEffect } from 'react';
import { fetchSkills, Skill } from '../api';

const SOURCES = [
  { id: 'all', label: '全部' },
  { id: 'office-claw', label: '办公自动化' },
  { id: 'workbuddy', label: 'WorkBuddy' },
  { id: 'doubao-local', label: '豆包本地' },
  { id: 'builtin', label: '内置' },
];

export default function SkillsView() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    fetchSkills().then(setSkills).catch(() => setSkills([]));
  }, []);

  const filtered = filter === 'all' ? skills : skills.filter(s => s.source === filter);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold">技能中心</h2>
        <span className="text-xs text-white/30">{skills.length} 项技能</span>
      </div>
      <div className="flex gap-1.5 mb-4 flex-wrap">
        {SOURCES.map(s => (
          <button
            key={s.id}
            onClick={() => setFilter(s.id)}
            className={`px-3 py-1.5 rounded-md text-[11px] font-medium transition-colors ${
              filter === s.id
                ? 'bg-accent-soft text-accent border border-accent/30'
                : 'bg-surface border border-white/[0.06] text-white/50 hover:border-white/[0.12] hover:text-white/70'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-2">
        {filtered.map(s => (
          <div
            key={s.name}
            className="bg-surface border border-white/[0.06] rounded-lg px-3.5 py-3 flex items-center gap-2 hover:border-white/[0.12] hover:bg-hover transition-colors cursor-pointer"
          >
            <span className="text-base">⚡</span>
            <span className="text-xs font-medium truncate">{s.name}</span>
            {s.source && <span className="text-[9px] text-white/20 ml-auto">{s.source}</span>}
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="col-span-full text-center py-16 text-white/20 text-sm">暂无技能数据</div>
        )}
      </div>
    </div>
  );
}