'use client';
import { useEffect, useState } from 'react';
import { Activity, ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { chatApi, modeApi, api } from '@/lib/api';
import type { ChatSession, Mode } from '@/lib/types';
import ChatPanel from '@/components/chat/ChatPanel';
import SessionSidebar from '@/components/chat/SessionSidebar';

export default function ChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [active, setActive] = useState<ChatSession | null>(null);
  const [mode, setMode] = useState<Mode>('investor');

  useEffect(() => {
    // Load saved mode preference
    api.config.get().then(cfg => {
      setMode((cfg.mode as Mode) ?? 'investor');
    }).catch(() => {});

    chatApi.sessions().then(s => {
      setSessions(s);
      if (s.length > 0) setActive(s[0]);
    }).catch(() => {});
  }, []);

  async function newSession() {
    const s = await chatApi.newSession('New Chat', mode);
    setSessions(prev => [s, ...prev]);
    setActive(s);
  }

  async function deleteSession(id: string) {
    await chatApi.deleteSession(id);
    const updated = sessions.filter(s => s.id !== id);
    setSessions(updated);
    if (active?.id === id) setActive(updated[0] ?? null);
  }

  async function handleModeChange(m: Mode) {
    setMode(m);
    modeApi.save(m).catch(() => {});
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#08080f' }}>
      {/* Top bar */}
      <header className="glass sticky top-0 z-50 border-b border-[#1e1e35] px-4 py-2.5 flex items-center gap-3">
        <Link href="/dashboard" className="flex items-center gap-1.5 text-[#64748b] hover:text-[#94a3b8] transition-colors text-sm">
          <ArrowLeft size={15} /> Dashboard
        </Link>
        <div className="h-4 w-px bg-[#1e1e35]" />
        <div className="flex items-center gap-2">
          <Activity size={18} className="text-[#8b5cf6]" />
          <span className="font-semibold text-sm gradient-text">AI Analyst Chat</span>
        </div>
        <div className="ml-auto text-xs text-[#334155]">
          Ask anything about stocks, markets, F&amp;O
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden" style={{ height: 'calc(100vh - 49px)' }}>
        <SessionSidebar
          sessions={sessions}
          activeId={active?.id ?? null}
          mode={mode}
          onSelect={setActive}
          onNew={newSession}
          onDelete={deleteSession}
          onModeChange={handleModeChange}
        />

        {/* Chat area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {active ? (
            <ChatPanel key={active.id} session={active} mode={mode} />
          ) : (
            <div className="flex-1 flex items-center justify-center flex-col gap-4 text-center px-8">
              <Activity size={40} className="text-[#1e1e35]" />
              <div>
                <div className="text-sm font-semibold text-[#475569] mb-1">No conversation selected</div>
                <div className="text-xs text-[#334155]">Click &ldquo;New Chat&rdquo; in the sidebar to start asking questions</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
