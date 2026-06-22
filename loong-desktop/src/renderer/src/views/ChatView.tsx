import React, { useState, useRef, useEffect } from 'react';

interface Props {
  state: any;
}

const MODELS = [
  { id: 'deepseek-chat', label: 'DeepSeek-V4', local: false },
  { id: 'deepseek-reasoner', label: 'DeepSeek-R1', local: false },
  { id: 'qwen-max', label: '通义千问-Max', local: false },
  { id: 'glm-4', label: '智谱GLM-4', local: false },
  { id: 'qwen3.5-4.6b', label: 'Qwen3.5-4.6B (本地)', local: true },
];

function renderMarkdown(text: string): string {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="bg-canvas border border-white/[0.06] rounded-md p-3.5 my-2 font-mono text-xs leading-relaxed overflow-x-auto text-emerald-300/80"><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code class="font-mono text-xs bg-white/[0.06] px-1.5 py-0.5 rounded">$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br/>');
}

export default function ChatView({ state }: Props) {
  const [input, setInput] = useState('');
  const [modelOpen, setModelOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.messages]);

  const handleSend = () => {
    if (!input.trim() || state.isStreaming) return;
    state.sendMessage(input);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Top bar */}
      <div className="h-[52px] bg-panel border-b border-white/[0.06] flex items-center px-4 gap-3 flex-shrink-0">
        <span className="text-sm font-semibold">新对话</span>
        <div className="relative">
          <button
            onClick={() => setModelOpen(!modelOpen)}
            className="flex items-center gap-1 text-[11px] text-white/40 bg-surface border border-white/[0.06] px-2.5 py-1 rounded-md hover:border-white/[0.12] hover:text-white/60 transition-colors"
          >
            {MODELS.find(m => m.id === state.currentModel)?.label || state.currentModel}
            <span className="text-[8px]">▼</span>
          </button>
          {modelOpen && (
            <div className="absolute top-full right-0 mt-1 bg-panel border border-white/[0.06] rounded-lg p-1.5 min-w-[200px] z-50 shadow-[0_8px_30px_rgba(0,0,0,0.5)]">
              {MODELS.map(m => (
                <button
                  key={m.id}
                  onClick={() => { state.setCurrentModel(m.id); setModelOpen(false); }}
                  className={`w-full text-left px-3 py-2 rounded-md text-xs flex items-center gap-2 transition-colors ${
                    state.currentModel === m.id ? 'bg-accent-soft text-accent' : 'text-white/50 hover:bg-hover hover:text-white/80'
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${m.local ? 'bg-amber-400' : 'bg-emerald-400'}`} />
                  {m.label}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="flex-1" />
        <button onClick={state.newChat} className="w-8 h-8 rounded-md border border-white/[0.06] text-white/40 flex items-center justify-center text-sm hover:bg-hover hover:text-white/60 transition-colors">+</button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-6">
        <div className="max-w-[760px] mx-auto px-6 flex flex-col gap-5">
          {state.messages.length === 0 && (
            <div className="text-center py-20 text-white/20 text-sm">
              输入消息开始对话
            </div>
          )}
          {state.messages.map((msg: any) => (
            <div key={msg.id} className={`flex gap-3 msg-enter ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-semibold flex-shrink-0 mt-0.5 overflow-hidden ${
                msg.role === 'user' ? 'bg-accent text-white' : ''
              }`}>
                {msg.role === 'user' ? 'U' : (
                  <img src="../../assets/avatar.jpeg" alt="" className="w-full h-full object-cover rounded-lg" />
                )}
              </div>
              <div className={`max-w-[85%] px-4 py-3 rounded-xl text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-accent-soft text-accent rounded-br-sm'
                  : 'bg-surface border border-white/[0.06] text-white/90 rounded-bl-sm'
              }`}>
                {msg.content ? (
                  <span dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) + (msg.role === 'agent' && state.isStreaming && msg === state.messages[state.messages.length - 1] ? '<span class="streaming-cursor"></span>' : '') }} />
                ) : state.isStreaming && msg.role === 'agent' ? (
                  <span className="streaming-cursor" />
                ) : null}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="px-6 py-4 flex-shrink-0">
        <div className="max-w-[760px] mx-auto relative">
          <div className="bg-surface border border-white/[0.06] rounded-xl px-4 py-3 pr-12 focus-within:border-accent focus-within:shadow-[0_0_0_3px_rgba(99,102,241,0.08)] transition-all">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入消息… (Enter 发送，Shift+Enter 换行)"
              rows={1}
              className="w-full bg-transparent border-none text-sm text-white outline-none resize-none min-h-[24px] max-h-[160px] leading-relaxed placeholder:text-white/20"
            />
            <div className="flex items-center gap-1.5 mt-2">
              <button className="w-7 h-7 rounded-md border border-white/[0.06] text-white/30 flex items-center justify-center text-xs hover:bg-hover hover:text-white/50 transition-colors">⚡</button>
              <button className="w-7 h-7 rounded-md border border-white/[0.06] text-white/30 flex items-center justify-center text-xs hover:bg-hover hover:text-white/50 transition-colors">📎</button>
            </div>
          </div>
          <button
            onClick={handleSend}
            disabled={!input.trim() || state.isStreaming}
            className="absolute right-2 bottom-2 w-9 h-9 rounded-lg bg-accent text-white flex items-center justify-center hover:bg-accent-glow transition-all shadow-[0_0_16px_rgba(99,102,241,0.25)] disabled:opacity-30 disabled:cursor-default"
          >
            ↑
          </button>
        </div>
        <div className="text-center text-[11px] text-white/15 mt-2">
          COGU Loong 可能会产生不准确的信息，请注意甄别
        </div>
      </div>
    </div>
  );
}