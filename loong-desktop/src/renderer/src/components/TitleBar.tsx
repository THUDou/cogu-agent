import React from 'react';

interface Props {
  version: string;
}

export default function TitleBar({ version }: Props) {
  return (
    <div className="h-9 bg-panel border-b border-white/[0.06] flex items-center px-4 titlebar-drag flex-shrink-0">
      <div className="w-5 h-5 rounded overflow-hidden flex-shrink-0">
        <img src="./logo.jpg" alt="" className="w-full h-full object-cover" />
      </div>
      <span className="text-[13px] font-semibold text-white ml-2 tracking-tight">COGU Loong</span>
      <span className="text-[10px] text-white/30 ml-1">v{version}</span>
      <div className="flex-1" />
      <div className="flex gap-2 titlebar-no-drag">
        <button
          onClick={() => window.electronAPI?.windowMinimize()}
          className="w-8 h-6 flex items-center justify-center text-white/40 hover:text-white/80 hover:bg-white/5 rounded transition-colors"
        >
          <svg width="10" height="1" viewBox="0 0 10 1"><rect width="10" height="1" fill="currentColor"/></svg>
        </button>
        <button
          onClick={() => window.electronAPI?.windowMaximize()}
          className="w-8 h-6 flex items-center justify-center text-white/40 hover:text-white/80 hover:bg-white/5 rounded transition-colors"
        >
          <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1"><rect x="0.5" y="0.5" width="7" height="7"/></svg>
        </button>
        <button
          onClick={() => window.electronAPI?.windowClose()}
          className="w-8 h-6 flex items-center justify-center text-white/40 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
        >
          <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1.2"><line x1="0" y1="0" x2="8" y2="8"/><line x1="8" y1="0" x2="0" y2="8"/></svg>
        </button>
      </div>
    </div>
  );
}