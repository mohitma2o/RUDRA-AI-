/**
 * RUDRA AI - Main React Application Component
 * Coordinates sidebar navigation, header, and active page views.
 */

import { useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import ChatPage from './pages/ChatPage';
import SystemMonitorPage from './pages/SystemMonitorPage';
import AutomationPage from './pages/AutomationPage';
import MemoryPage from './pages/MemoryPage';
import DocumentsPage from './pages/DocumentsPage';
import CodingPage from './pages/CodingPage';
import PluginsPage from './pages/PluginsPage';
import SettingsPage from './pages/SettingsPage';
import { useAppStore } from './stores/appStore';

export default function App() {
  const { currentPage, setPage, voiceEnabled } = useAppStore();

  useEffect(() => {
    const socket = new WebSocket('ws://127.0.0.1:8000/api/system/events');

    socket.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'WAKE_WORD_TRIGGERED') {
          setPage('chat');
          if (voiceEnabled && 'speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance('Rudra is listening. How can I help?');
            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(utterance);
          }
        }
      } catch {
        // ignore malformed events
      }
    });

    return () => socket.close();
  }, [setPage, voiceEnabled]);

  const renderPage = () => {
    switch (currentPage) {
      case 'chat': return <ChatPage />;
      case 'system': return <SystemMonitorPage />;
      case 'automation': return <AutomationPage />;
      case 'memory': return <MemoryPage />;
      case 'documents': return <DocumentsPage />;
      case 'coding': return <CodingPage />;
      case 'plugins': return <PluginsPage />;
      case 'settings': return <SettingsPage />;
      default: return <ChatPage />;
    }
  };

  return (
    <div className="app-layout" id="app-layout">
      <Sidebar />
      <main className="main-content">
        <Header />
        {renderPage()}
      </main>
    </div>
  );
}
