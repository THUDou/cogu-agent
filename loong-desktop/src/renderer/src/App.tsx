import React from 'react';
import { useAppState, ViewType } from './hooks/useAppState';
import TitleBar from './components/TitleBar';
import Sidebar from './components/Sidebar';
import HomeView from './views/HomeView';
import ChatView from './views/ChatView';
import SkillsView from './views/SkillsView';
import SettingsView from './views/SettingsView';
import StudioView from './views/StudioView';
import ObserveView from './views/ObserveView';

export default function App() {
  const state = useAppState();

  const renderView = () => {
    switch (state.currentView) {
      case 'home': return <HomeView state={state} />;
      case 'chat': return <ChatView state={state} />;
      case 'skills': return <SkillsView />;
      case 'settings': return <SettingsView />;
      case 'studio': return <StudioView />;
      case 'observe': return <ObserveView />;
      default: return <HomeView state={state} />;
    }
  };

  return (
    <div className="h-screen flex flex-col bg-canvas text-white">
      <TitleBar version={state.appVersion} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          currentView={state.currentView}
          setCurrentView={state.setCurrentView}
          collapsed={state.sidebarCollapsed}
          setCollapsed={state.setSidebarCollapsed}
          onNewChat={state.newChat}
        />
        <main className="flex-1 flex flex-col overflow-hidden relative">
          {renderView()}
        </main>
      </div>
    </div>
  );
}