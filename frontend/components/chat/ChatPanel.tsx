'use client';
import { useEffect, useRef, useState } from 'react';
import { Send, Trash2, Bot, User, Loader2, ChevronDown, Info } from 'lucide-react';
import { chatApi } from '@/lib/api';
import type { ChatMessage, ChatSession, Mode } from '@/lib/types';

// ── Markdown-lite renderer ────────────────────────────────────────────────────
function renderMd(text: string) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code class="bg-[#1e1e35] px-1 rounded text-[#00d97e]">$1</code>')
    .replace(/^• /gm, '&bull; ')
    .replace(/\n/g, '<br/>');
}

function MessageBubble({
  msg, onDelete
}: {
  msg: ChatMessage;
  onDelete: (id: string) => void;
}) {
  const isUser = msg.role === 'user';
  const [showSources, setShowSources] = useState(false);
  const sources = msg.sources as { fetched?: string[] } | undefined;
  const fetched = sources?.fetched ?? [];

  return (
    <div className={`flex gap-3 group ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
        isUser ? 'bg-[rgba(59,130,246,0.15)] text-[#3b82f6]' : 'bg-[rgba(139,92,246,0.15)] text-[#8b5cf6]'
      }`}>
        {isUser ? <User size={15} /> : <Bot size={15} />}
      </div>

      <div className={`flex flex-col gap-1 max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
          isUser
            ? 'bg-[rgba(59,130,246,0.12)] text-[#e2e8f0] rounded-tr-sm border border-[rgba(59,130,246,0.2)]'
            : 'bg-[#0f0f1a] text-[#cbd5e1] rounded-tl-sm border border-[#1e1e35]'
        }`}
          dangerouslySetInnerHTML={{ __html: isUser ? msg.content : renderMd(msg.content) }}
        />

        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          {!isUser && fetched.length > 0 && (
            <button
              onClick={() => setShowSources(s => !s)}
              className="flex items-center gap-1 text-[10px] text-[#475569] hover:text-[#64748b]"
            >
              <Info size={10} /> {fetched.length} sources
              <ChevronDown size={10} className={showSources ? 'rotate-180' : ''} />
            </button>
          )}
          <button
            onClick={() => onDelete(msg.id)}
            className="text-[#334155] hover:text-[#ff3d57] transition-colors"
          >
            <Trash2 size={11} />
          </button>
          <span className="text-[10px] text-[#334155]">
            {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>

        {showSources && (
          <div className="text-[10px] text-[#475569] bg-[#08080f] border border-[#1e1e35] rounded-lg px-3 py-2 space-y-0.5">
            {fetched.map(f => <div key={f}>• {f}</div>)}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Suggestion chips ──────────────────────────────────────────────────────────
const INVESTOR_SUGGESTIONS = [
  'Should I hold or sell RELIANCE?',
  'Top large cap stocks to buy now?',
  'How is NIFTY IT performing this week?',
  'What is the market sentiment today?',
  'Best SIP strategy for 2025?',
];

const TRADER_SUGGESTIONS = [
  'What is NIFTY PCR today?',
  'BANKNIFTY options strategy for weekly expiry?',
  'Best CE strike to buy for NIFTY?',
  'Where is max pain for NIFTY this expiry?',
  'FII DII activity today?',
];

// ── Main component ────────────────────────────────────────────────────────────
export default function ChatPanel({
  session,
  mode,
}: {
  session: ChatSession;
  mode: Mode;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setFetching(true);
    chatApi.messages(session.id)
      .then(d => setMessages(d.messages))
      .finally(() => setFetching(false));
  }, [session.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || loading) return;
    setInput('');

    const optimistic: ChatMessage = {
      id: `tmp-${Date.now()}`,
      session_id: session.id,
      role: 'user',
      content: q,
      sources_json: '{}',
      created_at: new Date().toISOString(),
    };
    setMessages(m => [...m, optimistic]);
    setLoading(true);

    try {
      // The backend now ALWAYS saves both user + assistant message before returning,
      // even on errors — so we just reload from DB after every ask.
      await chatApi.ask(session.id, q, mode);
    } catch (e: unknown) {
      // Network/5xx error — backend may not have saved anything.
      // Show inline error without mutating DB state.
      const err = e as { response?: { data?: { detail?: string }; status?: number } };
      const detail = err?.response?.data?.detail ?? 'Request failed. Check backend is running.';
      const errMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        session_id: session.id,
        role: 'assistant',
        content: `⚠️ ${detail}`,
        sources_json: '{}',
        created_at: new Date().toISOString(),
      };
      // Remove optimistic user bubble, add inline error
      setMessages(m => [...m.filter(x => x.id !== optimistic.id), errMsg]);
      setLoading(false);
      inputRef.current?.focus();
      return;
    }
    // Always reload from DB — this gets real IDs and includes any
    // error messages the backend saved (key missing, model error, etc.)
    try {
      const fresh = await chatApi.messages(session.id);
      setMessages(fresh.messages);
    } catch {
      // If reload fails, keep current messages minus optimistic
      setMessages(m => m.filter(x => x.id !== optimistic.id));
    }
  }

  async function deleteMsg(id: string) {
    await chatApi.deleteMessage(session.id, id).catch(() => {});
    setMessages(m => m.filter(x => x.id !== id));
  }

  const suggestions = mode === 'trader' ? TRADER_SUGGESTIONS : INVESTOR_SUGGESTIONS;
  const isEmpty = !fetching && messages.length === 0;

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {fetching && (
          <div className="flex items-center justify-center h-32 text-[#475569]">
            <Loader2 size={20} className="animate-spin" />
          </div>
        )}

        {isEmpty && (
          <div className="flex flex-col items-center justify-center h-64 gap-6">
            <div className="text-center">
              <Bot size={36} className="mx-auto text-[#8b5cf6] mb-3" />
              <div className="text-sm font-semibold text-[#e2e8f0] mb-1">
                {mode === 'trader' ? 'Trader AI' : 'Investor AI'}
              </div>
              <div className="text-xs text-[#475569]">
                Ask anything about {mode === 'trader' ? 'F&O, technicals, intraday setups' : 'stocks, portfolio, markets'}
              </div>
            </div>
            <div className="flex flex-wrap gap-2 justify-center max-w-lg">
              {suggestions.map(s => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-xs px-3 py-1.5 rounded-full border border-[#1e1e35] text-[#64748b] hover:border-[#8b5cf6] hover:text-[#8b5cf6] transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <MessageBubble key={msg.id} msg={msg} onDelete={deleteMsg} />
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full flex items-center justify-center bg-[rgba(139,92,246,0.15)] text-[#8b5cf6] shrink-0">
              <Bot size={15} />
            </div>
            <div className="px-4 py-3 rounded-2xl rounded-tl-sm border border-[#1e1e35] bg-[#0f0f1a] flex items-center gap-2">
              <Loader2 size={14} className="animate-spin text-[#8b5cf6]" />
              <span className="text-xs text-[#475569]">Analysing market data…</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 pb-4 pt-2 border-t border-[#1e1e35]">
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder={mode === 'trader'
              ? 'Ask about options, futures, PCR, max pain…'
              : 'Ask about stocks, portfolio, market outlook…'
            }
            rows={1}
            style={{ resize: 'none', minHeight: 44, maxHeight: 120, overflowY: 'auto' }}
            className="flex-1 bg-[#0f0f1a] border border-[#1e1e35] rounded-xl px-4 py-2.5 text-sm text-[#e2e8f0] placeholder-[#334155] focus:border-[#8b5cf6] focus:outline-none transition-colors"
          />
          <button
            onClick={() => send()}
            disabled={!input.trim() || loading}
            className="w-11 h-11 rounded-xl flex items-center justify-center bg-[rgba(139,92,246,0.15)] text-[#8b5cf6] border border-[rgba(139,92,246,0.3)] hover:bg-[rgba(139,92,246,0.25)] disabled:opacity-40 transition-colors shrink-0"
          >
            <Send size={16} />
          </button>
        </div>
        <div className="text-[10px] text-[#334155] mt-1.5 text-center">
          Enter to send · Shift+Enter for new line · Hover messages to delete
        </div>
      </div>
    </div>
  );
}
