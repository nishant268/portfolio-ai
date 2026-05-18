'use client';
import { MessageSquare, Plus, Trash2, TrendingUp, BarChart2 } from 'lucide-react';
import type { ChatSession, Mode } from '@/lib/types';

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function SessionSidebar({
  sessions,
  activeId,
  mode,
  onSelect,
  onNew,
  onDelete,
  onModeChange,
}: {
  sessions: ChatSession[];
  activeId: string | null;
  mode: Mode;
  onSelect: (s: ChatSession) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onModeChange: (m: Mode) => void;
}) {
  return (
    <div className="flex flex-col h-full w-64 border-r border-[#1e1e35] bg-[#09090f] shrink-0">
      {/* Mode toggle */}
      <div className="p-3 border-b border-[#1e1e35]">
        <div className="flex gap-1 p-1 bg-[#0f0f1a] rounded-xl border border-[#1e1e35]">
          <button
            onClick={() => onModeChange('investor')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              mode === 'investor'
                ? 'bg-[rgba(0,217,126,0.12)] text-[#00d97e] border border-[rgba(0,217,126,0.25)]'
                : 'text-[#475569] hover:text-[#64748b]'
            }`}
          >
            <TrendingUp size={12} /> Investor
          </button>
          <button
            onClick={() => onModeChange('trader')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              mode === 'trader'
                ? 'bg-[rgba(139,92,246,0.12)] text-[#8b5cf6] border border-[rgba(139,92,246,0.25)]'
                : 'text-[#475569] hover:text-[#64748b]'
            }`}
          >
            <BarChart2 size={12} /> Trader
          </button>
        </div>
      </div>

      {/* New chat button */}
      <div className="p-3">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-semibold bg-[rgba(139,92,246,0.1)] text-[#8b5cf6] border border-[rgba(139,92,246,0.25)] hover:bg-[rgba(139,92,246,0.18)] transition-colors"
        >
          <Plus size={15} /> New Chat
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-0.5">
        {sessions.length === 0 && (
          <div className="text-center text-[#334155] text-xs py-8 px-4">
            No chats yet. Start by asking a question.
          </div>
        )}
        {sessions.map(s => (
          <div
            key={s.id}
            onClick={() => onSelect(s)}
            className={`group flex items-start gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-colors ${
              activeId === s.id
                ? 'bg-[#0f0f1a] border border-[#1e1e35]'
                : 'hover:bg-[#0a0a12]'
            }`}
          >
            <MessageSquare size={13} className={`mt-0.5 shrink-0 ${
              s.mode === 'trader' ? 'text-[#8b5cf6]' : 'text-[#00d97e]'
            }`} />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-[#cbd5e1] truncate">{s.title}</div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className={`text-[9px] px-1.5 py-0.5 rounded font-semibold ${
                  s.mode === 'trader'
                    ? 'bg-[rgba(139,92,246,0.15)] text-[#8b5cf6]'
                    : 'bg-[rgba(0,217,126,0.1)] text-[#00d97e]'
                }`}>{s.mode}</span>
                <span className="text-[10px] text-[#334155]">{timeAgo(s.updated_at)}</span>
              </div>
            </div>
            <button
              onClick={e => { e.stopPropagation(); onDelete(s.id); }}
              className="opacity-0 group-hover:opacity-100 text-[#334155] hover:text-[#ff3d57] transition-all shrink-0 mt-0.5"
            >
              <Trash2 size={12} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
