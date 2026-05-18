'use client';
/**
 * TradingAgents-style live agent pipeline UI.
 * Three panels:
 *   Top-left:  Progress (team → agent → status)
 *   Top-right: Messages & Tools (timestamp | type | content)
 *   Bottom:    Current Report (full text output of current agent)
 *   Footer:    Tool Calls | LLM Calls | Generated Reports
 */
import { useEffect, useRef, useState } from 'react';
import { X, Loader2 } from 'lucide-react';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface AgentState {
  team: string;
  agent: string;
  phase: string;
  status: 'pending' | 'in_progress' | 'completed' | 'skipped';
  score?: number;
}

interface Message {
  time: string;
  type: 'Reasoning' | 'Tool' | 'Status';
  agent: string;
  content: string;
}

interface Stats {
  tool_calls: number;
  llm_calls: number;
  reports: number;
}

const STATUS_COLOR: Record<string, string> = {
  pending:     '#475569',
  in_progress: '#f59e0b',
  completed:   '#00d97e',
  skipped:     '#334155',
};

const STATUS_DOT: Record<string, string> = {
  pending:     '○',
  in_progress: '◉',
  completed:   '●',
  skipped:     '–',
};

const MSG_COLOR: Record<string, string> = {
  Reasoning: '#00d97e',
  Tool:      '#3b82f6',
  Status:    '#8b5cf6',
};

export default function AgentPipeline({
  ticker, mode, onClose,
}: {
  ticker: string;
  mode: string;
  onClose: () => void;
}) {
  const [agents, setAgents] = useState<AgentState[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentReport, setCurrentReport] = useState('');
  const [currentReportTitle, setCurrentReportTitle] = useState('');
  const [stats, setStats] = useState<Stats>({ tool_calls: 0, llm_calls: 0, reports: 0 });
  const [done, setDone] = useState<Record<string, unknown> | null>(null);
  const [running, setRunning] = useState(true);
  const msgRef  = useRef<HTMLDivElement>(null);
  const esRef   = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource(`${BASE}/api/agent-stream/${ticker}?mode=${mode}`);
    esRef.current = es;

    es.onmessage = (e) => {
      const d = JSON.parse(e.data);

      if (d.type === 'init') {
        setAgents(d.agents);
      }

      if (d.type === 'agent_status') {
        setAgents(prev => prev.map(a =>
          a.agent === d.agent
            ? { ...a, status: d.status, score: d.score ?? a.score }
            : a
        ));
      }

      if (d.type === 'tool') {
        setMessages(prev => [...prev, {
          time: d.time, type: 'Tool', agent: 'System',
          content: d.status === 'running' ? `→ ${d.tool}` : `✓ ${d.tool} → ${d.result}`,
        }]);
      }

      if (d.type === 'message') {
        setMessages(prev => [...prev, {
          time: d.time, type: d.msg_type as 'Reasoning' | 'Tool',
          agent: d.agent, content: d.content,
        }]);
      }

      if (d.type === 'report') {
        setCurrentReportTitle(d.title);
        setCurrentReport(d.content);
      }

      if (d.type === 'stats') {
        setStats({ tool_calls: d.tool_calls, llm_calls: d.llm_calls, reports: d.reports });
      }

      if (d.type === 'done') {
        setDone(d);
        setRunning(false);
        es.close();
      }
    };

    es.onerror = () => { setRunning(false); es.close(); };

    return () => { es.close(); };
  }, [ticker, mode]);

  // Auto-scroll messages
  useEffect(() => {
    if (msgRef.current) {
      msgRef.current.scrollTop = msgRef.current.scrollHeight;
    }
  }, [messages]);

  // Group agents by team
  const teams: Record<string, AgentState[]> = {};
  for (const a of agents) {
    if (!teams[a.team]) teams[a.team] = [];
    teams[a.team].push(a);
  }

  const actionColor = done
    ? (done.action === 'BUY' ? '#00d97e' : done.action === 'SELL' ? '#ff3d57' : '#f59e0b')
    : '#f59e0b';

  return (
    <div
      className="fixed inset-0 z-[200] flex flex-col"
      style={{ background: '#080810', fontFamily: "'Courier New', 'JetBrains Mono', monospace" }}
    >
      {/* Title bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b"
        style={{ borderColor: '#1a2a1a', background: '#0a0f0a' }}>
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold" style={{ color: '#00d97e' }}>
            ◈ TradingAgents Pipeline
          </span>
          <span className="text-xs" style={{ color: '#475569' }}>—</span>
          <span className="text-xs font-bold" style={{ color: '#00d97e' }}>{ticker.toUpperCase()}</span>
          <span className="text-xs px-2 py-0.5 rounded" style={{ background: '#0f1f0f', color: '#00d97e', border: '1px solid #1a3a1a' }}>
            {mode.toUpperCase()}
          </span>
          {running && (
            <span className="flex items-center gap-1 text-xs" style={{ color: '#f59e0b' }}>
              <Loader2 size={11} className="animate-spin" /> Executing...
            </span>
          )}
          {done && (
            <span className="text-xs font-bold" style={{ color: actionColor }}>
              → {done.action as string} ({done.signal as string}) {((done.confidence as number) * 100).toFixed(0)}% confidence
            </span>
          )}
        </div>
        <button onClick={onClose} className="hover:opacity-70 transition-opacity">
          <X size={16} style={{ color: '#475569' }} />
        </button>
      </div>

      {/* Two top panels */}
      <div className="flex flex-1 overflow-hidden min-h-0" style={{ maxHeight: '60vh' }}>

        {/* LEFT: Progress */}
        <div className="flex flex-col border-r overflow-hidden"
          style={{ width: '38%', borderColor: '#1a2a1a' }}>
          <div className="px-3 py-1.5 border-b text-xs font-bold"
            style={{ borderColor: '#1a2a1a', color: '#00d97e', background: '#0a0f0a' }}>
            ── Progress
          </div>
          <div className="overflow-y-auto flex-1 px-3 py-2">
            {/* Header */}
            <div className="grid grid-cols-3 gap-2 text-xs mb-2 pb-1 border-b"
              style={{ color: '#00d97e', borderColor: '#1a2a1a' }}>
              <span>Team</span>
              <span>Agent</span>
              <span>Status</span>
            </div>
            {Object.entries(teams).map(([team, agts]) => (
              <div key={team} className="mb-1">
                {agts.map((a, i) => (
                  <div key={a.agent} className="grid grid-cols-3 gap-2 text-xs py-0.5"
                    style={{ color: '#cbd5e1' }}>
                    <span style={{ color: '#22d3ee' }}>{i === 0 ? team : ''}</span>
                    <span style={{ color: '#a78bfa' }}>{a.agent}</span>
                    <span className="flex items-center gap-1">
                      <span style={{ color: STATUS_COLOR[a.status] }}>
                        {STATUS_DOT[a.status]}
                      </span>
                      <span style={{ color: STATUS_COLOR[a.status] }}>{a.status}</span>
                      {a.score !== undefined && (
                        <span style={{ color: a.score >= 0 ? '#00d97e' : '#ff3d57', marginLeft: 4, fontSize: 10 }}>
                          {a.score >= 0 ? '+' : ''}{a.score}
                        </span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* RIGHT: Messages & Tools */}
        <div className="flex flex-col flex-1 overflow-hidden">
          <div className="px-3 py-1.5 border-b text-xs font-bold"
            style={{ borderColor: '#1a2a1a', color: '#00d97e', background: '#0a0f0a' }}>
            ── Messages &amp; Tools
          </div>
          {/* Column headers */}
          <div className="grid text-xs px-3 py-1 border-b"
            style={{ gridTemplateColumns: '70px 90px 1fr', borderColor: '#1a2a1a', color: '#00d97e', background: '#0a0a0f' }}>
            <span>Time</span>
            <span>Type</span>
            <span>Content</span>
          </div>
          <div ref={msgRef} className="overflow-y-auto flex-1 px-3 py-1">
            {messages.map((m, i) => (
              <div key={i} className="grid text-xs py-0.5 border-b"
                style={{ gridTemplateColumns: '70px 90px 1fr', borderColor: '#0f1f0f', minHeight: 20 }}>
                <span style={{ color: '#475569' }}>{m.time}</span>
                <span style={{ color: MSG_COLOR[m.type] ?? '#94a3b8' }}>{m.type}</span>
                <span style={{ color: '#94a3b8', wordBreak: 'break-all', lineHeight: 1.4 }}>{m.content}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom: Current Report */}
      <div className="flex flex-col border-t flex-1 overflow-hidden min-h-0"
        style={{ borderColor: '#1a2a1a', maxHeight: '35vh' }}>
        <div className="px-3 py-1.5 border-b text-xs font-bold"
          style={{ borderColor: '#1a2a1a', color: '#00d97e', background: '#0a0f0a' }}>
          ── Current Report
          {currentReportTitle && (
            <span className="ml-3 font-normal" style={{ color: '#a78bfa' }}>
              {currentReportTitle}
            </span>
          )}
        </div>
        <div className="overflow-y-auto flex-1 px-4 py-3">
          <pre className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: '#94a3b8', fontFamily: 'inherit' }}>
            {currentReport || (running ? '⟳ Waiting for first report...' : 'No report generated.')}
          </pre>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 py-1.5 border-t text-xs"
        style={{ borderColor: '#1a2a1a', background: '#0a0a0f', color: '#475569' }}>
        <div className="flex items-center gap-6">
          <span>Tool Calls: <span style={{ color: '#3b82f6' }}>{stats.tool_calls}</span></span>
          <span>LLM Calls: <span style={{ color: '#8b5cf6' }}>{stats.llm_calls}</span></span>
          <span>Generated Reports: <span style={{ color: '#00d97e' }}>{stats.reports}</span></span>
        </div>
        {done && (
          <span style={{ color: actionColor, fontWeight: 'bold' }}>
            ■ PIPELINE COMPLETE — {done.action as string} {ticker.toUpperCase()} @ ₹{(done.price as number)?.toFixed(2)}
            &nbsp;| Stop ₹{(done.stop_loss as number)?.toFixed(2)}
            &nbsp;| Target ₹{(done.take_profit as number)?.toFixed(2)}
          </span>
        )}
        {running && (
          <span style={{ color: '#f59e0b' }} className="flex items-center gap-1">
            <Loader2 size={10} className="animate-spin" /> Pipeline executing...
          </span>
        )}
      </div>
    </div>
  );
}
