import React from 'react';
import { ViewType } from '../hooks/useAppState';

interface Props {
  currentView: ViewType;
  setCurrentView: (v: ViewType) => void;
  collapsed: boolean;
  setCollapsed: (v: boolean) => void;
  onNewChat: () => void;
}

const NAV_ITEMS: { view: ViewType; icon: string; label: string }[] = [
  { view: 'home', icon: '⌂', label: '首页' },
  { view: 'chat', icon: '💬', label: '对话' },
  { view: 'skills', icon: '⚡', label: '技能' },
  { view: 'settings', icon: '⚙', label: '设置' },
];

export default function Sidebar({ currentView, setCurrentView, collapsed, setCollapsed, onNewChat }: Props) {
  return (
    <div
      className={`bg-panel border-r border-white/[0.06] flex flex-col flex-shrink-0 transition-all duration-300 ${
        collapsed ? 'w-[60px]' : 'w-[260px]'
      }`}
    >
      <div className="p-3 flex items-center justify-between border-b border-white/[0.06]">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg overflow-hidden glow-accent">
              <img src="../../assets/logo.jpg" alt="" className="w-full h-full object-cover" />
            </div>
            <span className="text-[15px] font-bold tracking-tight">Loong</span>
            <span className="text-[9px] font-medium text-accent bg-accent-soft px-1.5 py-0.5 rounded">PRO</span>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-7 h-7 rounded-md border border-white/[0.06] text-white/40 flex items-center justify-center text-xs hover:bg-hover hover:text-white/60 transition-colors"
        >
          {collapsed ? '▶' : '◀'}
        </button>
      </div>

      {!collapsed && (
        <div className="px-3 py-2">
          <input
            type="text"
            placeholder="搜索会话、技能…"
            className="w-full bg-surface border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-accent transition-colors placeholder:text-white/20"
          />
        </div>
      )}

      <nav className="px-2 py-1 flex flex-col gap-0.5">
        {NAV_ITEMS.map(item => (
          <button
            key={item.view}
            onClick={() => setCurrentView(item.view)}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-all relative ${
              currentView === item.view
                ? 'bg-accent-soft text-accent'
                : 'text-white/50 hover:bg-hover hover:text-white/80'
            } ${collapsed ? 'justify-center px-0' : ''}`}
          >
            {currentView === item.view && (
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 bg-accent rounded-r" />
            )}
            <span className="text-base flex-shrink-0 w-5 text-center">{item.icon}</span>
            {!collapsed && <span>{item.label}</span>}
          </button>
        ))}
      </nav>

      {!collapsed && (
        <>
          <div className="px-4 pt-4 pb-1 text-[10px] font-semibold text-white/25 uppercase tracking-wider">
            会话历史
          </div>
          <div className="flex-1 overflow-y-auto px-2">
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-accent-soft cursor-pointer">
              <div className="w-1.5 h-1.5 rounded-full bg-accent" />
              <div className="min-w-0 flex-1">
                <div className="text-xs font-medium truncate">新对话</div>
                <div className="text-[10px] text-white/25">刚刚</div>
              </div>
            </div>
          </div>
        </>
      )}

      <div className="p-3 border-t border-white/[0.06] flex gap-2">
        <button
          onClick={onNewChat}
          className="flex-1 py-1.5 rounded-lg bg-surface border border-white/[0.06] text-white/50 text-[11px] font-medium hover:bg-hover hover:text-white/70 transition-colors"
        >
          + 新对话
        </button>
        {!collapsed && (
          <button
            onClick={() => setCurrentView('settings')}
            className="py-1.5 px-2 rounded-lg bg-surface border border-white/[0.06] text-white/50 text-[11px] hover:bg-hover transition-colors"
          >
            ⚙
          </button>
        )}
      </div>
    </div>
  );
}