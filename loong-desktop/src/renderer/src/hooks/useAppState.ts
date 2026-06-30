import { useState, useEffect, useCallback } from 'react';

declare global {
  interface Window {
    electronAPI?: {
      getApiPort: () => Promise<number>;
      getAppVersion: () => Promise<string>;
      isPackaged: () => Promise<boolean>;
      windowMinimize: () => void;
      windowMaximize: () => void;
      windowClose: () => void;
      onNewChat: (cb: () => void) => void;
    };
  }
}

export type ViewType = 'home' | 'chat' | 'skills' | 'settings' | 'studio' | 'observe';

export interface Message {
  role: 'user' | 'agent';
  content: string;
  id: string;
}

export function useAppState() {
  const [currentView, setCurrentView] = useState<ViewType>('home');
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [currentModel, setCurrentModel] = useState('deepseek-chat');
  const [isStreaming, setIsStreaming] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [appVersion, setAppVersion] = useState('1.4.0');

  useEffect(() => {
    window.electronAPI?.getAppVersion().then(v => setAppVersion(v)).catch(() => {});
  }, []);

  const newChat = useCallback(() => {
    setSessionId(crypto.randomUUID());
    setMessages([]);
    setCurrentView('chat');
  }, []);

  const addMessage = useCallback((role: 'user' | 'agent', content: string) => {
    const id = crypto.randomUUID();
    setMessages(prev => [...prev, { role, content, id }]);
    return id;
  }, []);

  const updateMessage = useCallback((id: string, content: string) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, content } : m));
  }, []);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return;
    addMessage('user', text);
    const agentId = addMessage('agent', '');
    setIsStreaming(true);

    try {
      const api = await import('../api');
      const stream = await api.streamChat(text, sessionId, currentModel);
      const reader = stream.getReader();
      const decoder = new TextDecoder();
      let fullText = '';
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'text.delta' || data.type === 'TEXT_DELTA') {
                fullText += data.content || '';
              } else if (data.type === 'run.completed' || data.type === 'RUN_COMPLETED') {
                if (data.reply) fullText = data.reply;
              }
              updateMessage(agentId, fullText);
            } catch {}
          }
        }
      }
    } catch (e: any) {
      updateMessage(agentId, `[错误] ${e.message}`);
    } finally {
      setIsStreaming(false);
    }
  }, [isStreaming, sessionId, currentModel, addMessage, updateMessage]);

  return {
    currentView, setCurrentView,
    messages, setMessages,
    sessionId,
    currentModel, setCurrentModel,
    isStreaming,
    sidebarCollapsed, setSidebarCollapsed,
    appVersion,
    newChat, addMessage, updateMessage, sendMessage,
  };
}