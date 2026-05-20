'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  Activity, ArrowLeft, RotateCcw, Loader2, TrendingUp,
  TrendingDown, Target, Wallet, BarChart2, Award, AlertTriangle,
  CheckCircle2, Zap, Radio, Clock, ChevronDown, ChevronUp,
  TrendingUp as Bull, TrendingDown as Bear, Brain, Cpu, Search,
} from 'lucide-react';
import AnalyseButton from '@/components/ui/AnalyseButton';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine, AreaChart, Area,
} from 'recharts';
import axios from 'axios';
import type { Mode } from '@/lib/types';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const WS   = BASE.replace(/^http/, 'ws');
const http = axios.create({ baseURL: BASE, timeout: 30_000 });

const fmt    = (n: number) => `₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
const fmtPct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;

// ── Stat card ─────────────────────────────────────────────────────────────────
function Stat({ label, value, sub, color, icon: Icon }: {
  label: string; value: string; sub?: string; color: string; icon: React.ElementType;
}) {
  return (
    <div className="card p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-[#64748b] uppercase tracking-wide font-medium">{label}</span>
        <div className="p-1.5 rounded-lg" style={{ background: `${color}18` }}>
          <Icon size={14} style={{ color }} />
        </div>
      </div>
      <div className="text-xl font-bold text-[#e2e8f0]">{value}</div>
      {sub && <div className="text-xs text-[#64748b]">{sub}</div>}
    </div>
  );
}

// ── Trade entry in live feed ──────────────────────────────────────────────────
function TradePill({ t }: { t: Record<string, unknown> }) {
  const action  = t.action as string;
  const isEntry = action === 'BUY' || action === 'SHORT';
  const pnl     = (t.pnl as number) ?? 0;
  return (
    <div className={`flex items-center gap-3 px-3 py-2 rounded-xl border text-xs ${
      isEntry
        ? 'border-[rgba(59,130,246,0.25)] bg-[rgba(59,130,246,0.06)]'
        : pnl >= 0 ? 'border-[rgba(0,217,126,0.25)] bg-[rgba(0,217,126,0.06)]'
                   : 'border-[rgba(255,61,87,0.25)] bg-[rgba(255,61,87,0.06)]'
    }`}>
      <span className={`font-bold px-1.5 py-0.5 rounded text-[10px] ${
        isEntry ? 'bg-[rgba(59,130,246,0.2)] text-[#3b82f6]' : 'bg-[rgba(255,61,87,0.2)] text-[#ff3d57]'
      }`}>{action}</span>
      <span className="font-semibold text-[#e2e8f0]">{t.ticker as string}</span>
      <span className="text-[#64748b]">{t.qty as number} × ₹{(t.price as number)?.toFixed(2)}</span>
      {!isEntry && <span className={pnl >= 0 ? 'positive font-semibold ml-auto' : 'negative font-semibold ml-auto'}>
        {pnl >= 0 ? '+' : ''}₹{Math.abs(Math.round(pnl)).toLocaleString('en-IN')}
      </span>}
      <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
        (t.signal as string)?.includes('BUY') ? 'badge-buy' : 'badge-sell'
      }`}>{t.signal as string}</span>
    </div>
  );
}

// ── Ticker search bar ─────────────────────────────────────────────────────────
function TickerSearch({ mode }: { mode: string }) {
  const [input, setInput] = useState('');
  const POPULAR = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'SBIN', 'BAJFINANCE', 'AXISBANK', 'WIPRO', 'HCLTECH', 'MARUTI', 'SUNPHARMA', 'ITC', 'TITAN', 'ADANIENT'];
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Cpu size={14} className="text-[#8b5cf6]" />
        <h2 className="font-semibold text-sm text-[#e2e8f0]">Run Full Agent Pipeline on Any NSE Stock</h2>
        <span className="text-[10px] text-[#475569]">TradingAgents-style live analysis</span>
      </div>
      <div className="flex gap-2 mb-3">
        <input
          value={input}
          onChange={e => setInput(e.target.value.toUpperCase())}
          placeholder="Type NSE ticker e.g. RELIANCE, TCS..."
          className="flex-1 bg-[#08080f] border border-[#1e1e35] rounded-xl px-4 py-2 text-sm text-[#e2e8f0] placeholder-[#334155] focus:border-[#8b5cf6] focus:outline-none"
          onKeyDown={e => e.key === 'Enter' && input.trim() && (document.getElementById(`analyse-${input}`) as HTMLButtonElement)?.click()}
        />
        {input.trim() && (
          <div id={`analyse-${input}`}>
            <AnalyseButton ticker={input.trim()} mode={mode} label="Run Pipeline" />
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        <span className="text-[10px] text-[#475569]">Quick:</span>
        {POPULAR.map(t => (
          <AnalyseButton key={t} ticker={t} mode={mode} label={t} size="xs" />
        ))}
      </div>
    </div>
  );
}

// ── Analysis tab component ────────────────────────────────────────────────────
function AnalysisTab({ tradeId, mode }: { tradeId: string; mode: string }) {
  const [analysis, setAnalysis] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  async function load() {
    if (loaded) return;
    setLoading(true);
    try {
      const r = await fetch(`${BASE}/api/paper/analysis/${tradeId}`);
      const d = await r.json();
      setAnalysis(d.analysis);
    } catch { /* */ } finally {
      setLoading(false);
      setLoaded(true);
    }
  }

  const confColor = (c: string) =>
    c === 'high' ? '#00d97e' : c === 'low' ? '#ff3d57' : '#f59e0b';

  if (!loaded) {
    return (
      <button onClick={load} disabled={loading}
        className="w-full flex items-center justify-center gap-2 py-2.5 text-xs font-semibold text-[#8b5cf6] bg-[rgba(139,92,246,0.08)] border border-[rgba(139,92,246,0.2)] rounded-xl hover:bg-[rgba(139,92,246,0.14)] transition-colors">
        {loading ? <Loader2 size={12} className="animate-spin" /> : <Brain size={12} />}
        {loading ? 'Loading analysis…' : 'Load Bull/Bear/Researcher Analysis'}
      </button>
    );
  }

  if (!analysis) {
    return (
      <div className="text-xs text-[#475569] py-3 text-center">
        Analysis generating in background… check back in ~10 seconds.
        <button onClick={() => { setLoaded(false); }} className="ml-2 text-[#8b5cf6] underline">Retry</button>
      </div>
    );
  }

  const a = analysis as Record<string, unknown>;

  return (
    <div className="space-y-3 mt-2">
      {/* Technical snapshot */}
      {a.tech_summary
        ? (
        <div className="bg-[#08080f] border border-[#1e1e35] rounded-xl px-3 py-2">
          <div className="text-[10px] text-[#475569] font-semibold mb-1 uppercase">Technical Snapshot</div>
          <div className="text-[10px] text-[#64748b] font-mono leading-relaxed">{a.tech_summary as string}</div>
        </div>
        ) : null}

      {/* Bull Analyst */}
      <div className="rounded-xl border border-[rgba(0,217,126,0.2)] bg-[rgba(0,217,126,0.04)] p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-xs font-bold text-[#00d97e]">
            <Bull size={13} /> Bull Analyst
          </div>
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full border"
            style={{ color: confColor(a.bull_confidence as string), borderColor: confColor(a.bull_confidence as string) + '44' }}>
            {(a.bull_confidence as string)?.toUpperCase()} confidence
          </span>
        </div>
        <p className="text-xs text-[#94a3b8] leading-relaxed mb-2">{a.bull_thesis as string}</p>
        <div className="flex flex-wrap gap-1 mb-1">
          {(a.bull_catalysts as string[])?.map((c, i) => (
            <span key={i} className="text-[10px] bg-[rgba(0,217,126,0.1)] text-[#00d97e] px-2 py-0.5 rounded">📈 {c}</span>
          ))}
        </div>
        {(a.bull_target as number) > 0 && (
          <div className="text-[10px] text-[#64748b]">Price target: <span className="positive font-semibold">₹{(a.bull_target as number).toFixed(2)}</span></div>
        )}
      </div>

      {/* Bear Analyst */}
      <div className="rounded-xl border border-[rgba(255,61,87,0.2)] bg-[rgba(255,61,87,0.04)] p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-xs font-bold text-[#ff3d57]">
            <Bear size={13} /> Bear Analyst
          </div>
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full border"
            style={{ color: confColor(a.bear_confidence as string), borderColor: confColor(a.bear_confidence as string) + '44' }}>
            {(a.bear_confidence as string)?.toUpperCase()} confidence
          </span>
        </div>
        <p className="text-xs text-[#94a3b8] leading-relaxed mb-2">{a.bear_thesis as string}</p>
        <div className="flex flex-wrap gap-1 mb-1">
          {(a.bear_risks as string[])?.map((r, i) => (
            <span key={i} className="text-[10px] bg-[rgba(255,61,87,0.1)] text-[#ff3d57] px-2 py-0.5 rounded">⚠️ {r}</span>
          ))}
        </div>
        {(a.bear_stop as number) > 0 && (
          <div className="text-[10px] text-[#64748b]">Stop loss: <span className="negative font-semibold">₹{(a.bear_stop as number).toFixed(2)}</span></div>
        )}
      </div>

      {/* Researcher synthesis */}
      <div className="rounded-xl border border-[rgba(139,92,246,0.2)] bg-[rgba(139,92,246,0.06)] p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-xs font-bold text-[#8b5cf6]">
            <Brain size={13} /> Researcher Synthesis
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
              (a.researcher_verdict as string) === 'BUY' ? 'badge-buy' : 'badge-sell'
            }`}>{a.researcher_verdict as string}</span>
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full border"
              style={{ color: confColor(a.researcher_conviction as string), borderColor: confColor(a.researcher_conviction as string) + '44' }}>
              {(a.researcher_conviction as string)?.toUpperCase()} conviction
            </span>
          </div>
        </div>
        <p className="text-xs text-[#94a3b8] leading-relaxed mb-2">{a.researcher_reasoning as string}</p>
        {a.researcher_key_factor
          ? <div className="text-[10px] text-[#64748b]">🎯 Key factor: <span className="text-[#cbd5e1] font-medium">{a.researcher_key_factor as string}</span></div>
          : null}
      </div>
    </div>
  );
}

// ── Trade card with reasoning ─────────────────────────────────────────────────
function TradeCard({ trade, activeMode }: { trade: Record<string, unknown>; activeMode: string }) {
  const [tab, setTab] = useState<'rule' | 'analysis'>('rule');
  const [expanded, setExpanded] = useState(false);
  const action  = trade.action as string;
  const isEntry = action === 'BUY' || action === 'SHORT';
  const pnl     = (trade.pnl as number) ?? 0;

  return (
    <div className={`border rounded-xl overflow-hidden ${
      isEntry ? 'border-[rgba(59,130,246,0.2)]' : pnl >= 0 ? 'border-[rgba(0,217,126,0.2)]' : 'border-[rgba(255,61,87,0.2)]'
    }`}>
      {/* Header */}
      <div
        className={`flex items-center justify-between gap-3 px-3 py-2.5 cursor-pointer ${
          isEntry ? 'bg-[rgba(59,130,246,0.04)]' : pnl >= 0 ? 'bg-[rgba(0,217,126,0.04)]' : 'bg-[rgba(255,61,87,0.04)]'
        }`}
        onClick={() => setExpanded(e => !e)}
      >
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
            isEntry ? 'bg-[rgba(59,130,246,0.15)] text-[#3b82f6]' : pnl >= 0 ? 'badge-buy' : 'badge-sell'
          }`}>{action}</span>
          <span className="font-bold text-sm text-[#e2e8f0]">{trade.ticker as string}</span>
          <span className="text-xs text-[#64748b]">
            {trade.quantity as number} × ₹{(trade.price as number)?.toFixed(2)}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {!isEntry && (
            <span className={`text-sm font-bold ${pnl >= 0 ? 'positive' : 'negative'}`}>
              {pnl >= 0 ? '+' : ''}₹{Math.abs(Math.round(pnl)).toLocaleString('en-IN')}
            </span>
          )}
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
            (trade.signal as string)?.includes('BUY') ? 'badge-buy' :
            (trade.signal as string)?.includes('SELL') ? 'badge-sell' : 'badge-hold'
          }`}>{trade.signal as string}</span>
          <div onClick={e => e.stopPropagation()}>
            <AnalyseButton ticker={trade.ticker as string} mode={activeMode} label="Pipeline" size="xs" />
          </div>
          {expanded ? <ChevronUp size={13} className="text-[#475569]" /> : <ChevronDown size={13} className="text-[#475569]" />}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="bg-[#08080f] border-t border-[#1e1e35]">
          {/* Tab bar */}
          <div className="flex border-b border-[#1e1e35]">
            <button
              onClick={() => setTab('rule')}
              className={`px-4 py-2 text-xs font-semibold transition-colors ${
                tab === 'rule' ? 'text-[#e2e8f0] border-b-2 border-[#f59e0b]' : 'text-[#475569] hover:text-[#64748b]'
              }`}
            >📊 Rule Engine (5 Analysts)</button>
            <button
              onClick={() => setTab('analysis')}
              className={`px-4 py-2 text-xs font-semibold transition-colors flex items-center gap-1 ${
                tab === 'analysis' ? 'text-[#e2e8f0] border-b-2 border-[#8b5cf6]' : 'text-[#475569] hover:text-[#64748b]'
              }`}
            ><Brain size={11} /> Claude Analysis</button>
          </div>

          <div className="p-3">
            {tab === 'rule' && (
              <div className="space-y-2">
                <div className="text-xs text-[#94a3b8] leading-relaxed whitespace-pre-line">
                  {trade.reasoning as string}
                </div>
                {(()=>{const tech=trade.technicals as Record<string,unknown>|null;if(!tech||!Object.keys(tech).length)return null;return(<div className="flex flex-wrap gap-1 mt-2">{Object.entries(tech).map(([k,v])=>v!=null?(<span key={k} className="text-[10px] bg-[#0f0f1a] border border-[#1e1e35] px-1.5 py-0.5 rounded text-[#64748b]">{k}:<span className="text-[#94a3b8] ml-1">{String(v)}</span></span>):null)}</div>);})()}
                <div className="text-[10px] text-[#334155] mt-1">
                  {new Date(trade.executed_at as string).toLocaleString()}
                </div>
              </div>
            )}
            {tab === 'analysis' && (
              <AnalysisTab tradeId={trade.id as string} mode={activeMode} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function PaperTradingPage() {
  const [mode, setMode] = useState<Mode>('investor');
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [trades, setTrades] = useState<Record<string, unknown>[]>([]);
  const [atStatus, setAtStatus] = useState<Record<string, unknown>>({ running: true, status: 'starting', next_run_in: 60, market_open: false });
  const [loading, setLoading] = useState(false);
  const [sessionRunning, setSessionRunning] = useState(false);
  const [sessionMsg, setSessionMsg] = useState('');
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pRes, tRes] = await Promise.all([
        http.get(`/api/paper/portfolio/${mode}`),
        http.get(`/api/paper/trades/${mode}?limit=500`),
      ]);
      setData(pRes.data);
      setTrades(tRes.data.trades ?? []);
    } catch { /* silent */ } finally { setLoading(false); }
  }, [mode]);

  // Initial load + auto-reload every 30s (pulls fresh portfolio after auto-trades)
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [load]);

  // WebSocket: live auto-trader status feed
  useEffect(() => {
    const ws = new WebSocket(`${WS}/ws/auto-trader`);
    wsRef.current = ws;
    ws.onmessage = e => {
      try {
        const st = JSON.parse(e.data);
        setAtStatus(st);
        // Reload portfolio data when a new session completed
        if (st.has_new_trades) load();
      } catch { /* */ }
    };
    return () => ws.close();
  }, [load]);

  async function runSession() {
    if (sessionRunning) return;
    setSessionRunning(true);
    setSessionMsg('Starting session…');
    try {
      await http.post(`/api/paper/run/${mode}`);
      setSessionMsg('Analysing stocks & executing trades…');
      // Poll session-status every 3s until done or error
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const r = await http.get(`/api/paper/session-status/${mode}`);
          const st = r.data.status as string;
          if (st === 'done') {
            setSessionMsg(`✓ Session complete — ${r.data.trades_count ?? 0} trade(s) executed`);
            setSessionRunning(false);
            if (pollRef.current) clearInterval(pollRef.current);
            await load();
          } else if (st === 'error') {
            setSessionMsg(`✗ ${r.data.error ?? 'Session failed'}`);
            setSessionRunning(false);
            if (pollRef.current) clearInterval(pollRef.current);
          } else {
            setSessionMsg('Analysing stocks & executing trades…');
          }
        } catch { /* silent */ }
      }, 3000);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSessionMsg(msg ?? 'Failed to start session');
      setSessionRunning(false);
    }
  }

  async function reset() {
    if (!confirm(`Reset ${mode} paper portfolio? All trades will be cleared.`)) return;
    await http.post(`/api/paper/reset/${mode}`);
    await load();
  }

  async function changeMode(m: Mode) {
    setMode(m);
    // Switch auto-trader mode
    await http.post(`/api/auto-trader/start?mode=${m}&interval=60`).catch(() => {});
  }

  const portfolio  = data?.portfolio as Record<string, unknown> | undefined;
  const positions  = (data?.positions  as Record<string, unknown>[]) ?? [];
  const snapshots  = (data?.snapshots  as Record<string, unknown>[]) ?? [];
  const stats      = data?.stats as Record<string, unknown> | undefined;
  const recentTrades = (atStatus.recent_trades as Record<string, unknown>[]) ?? [];

  const cash         = (portfolio?.cash as number) ?? (portfolio?.initial_capital as number) ?? 1_000_000;
  const initCapital  = (portfolio?.initial_capital as number) ?? 1_000_000;
  // portfolio_contribution is signed: positive for long (asset), negative for short (liability)
  const posValue     = positions.reduce((s, p) => {
    const contrib = (p.portfolio_contribution as number);
    if (contrib !== undefined && contrib !== null) return s + contrib;
    const mv = (p.market_value as number) || (p.avg_entry_price as number) * (p.quantity as number) || 0;
    return s + ((p.direction as string) === 'short' ? -mv : mv);
  }, 0);
  const totalValue   = cash + posValue;
  const totalPnl     = totalValue - initCapital;
  const totalPct     = initCapital > 0 ? (totalPnl / initCapital * 100) : 0;
  const daysRunning  = (stats?.days_running as number) ?? 0;
  const annReturn    = daysRunning > 0 ? (Math.pow(1 + totalPct / 100, 365 / daysRunning) - 1) * 100 : 0;

  // Chart data
  const chartData = snapshots.map((s, i) => ({
    day: `D${i + 1}`, value: s.portfolio_value as number,
    pnl_pct: s.total_pnl_pct as number, daily_pnl: s.daily_pnl as number,
    nifty: s.nifty_value as number,
  }));
  const niftyBase = chartData[0]?.nifty || 1;
  const chartNorm = chartData.map(d => ({
    ...d, nifty_pct: niftyBase > 0 ? ((d.nifty - niftyBase) / niftyBase) * 100 : 0,
  }));

  const isRunning   = atStatus.running as boolean;
  const marketOpen  = atStatus.market_open as boolean;
  const nextRunIn   = atStatus.next_run_in as number ?? 0;
  const runCount    = atStatus.run_count as number ?? 0;
  const lastRunAt   = atStatus.last_run_at as string | null;

  return (
    <div className="min-h-screen" style={{ background: '#08080f' }}>
      {/* Header */}
      <header className="glass sticky top-0 z-50 border-b border-[#1e1e35] px-4 py-2.5">
        <div className="flex items-center gap-3 flex-wrap">
          <Link href="/dashboard" className="flex items-center gap-1.5 text-[#64748b] hover:text-[#94a3b8] text-sm">
            <ArrowLeft size={15} /> Dashboard
          </Link>
          <div className="h-4 w-px bg-[#1e1e35]" />
          <Activity size={18} className="text-[#f59e0b]" />
          <span className="font-semibold text-sm text-[#e2e8f0]">Paper Trading</span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[rgba(245,158,11,0.1)] text-[#f59e0b] border border-[rgba(245,158,11,0.2)] font-semibold">15-DAY AI CHALLENGE</span>

          {/* Auto-trader status pill */}
          <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
            marketOpen ? 'bg-[rgba(0,217,126,0.1)] text-[#00d97e] border border-[rgba(0,217,126,0.25)]'
            : 'bg-[#0f0f1a] text-[#475569] border border-[#1e1e35]'
          }`}>
            <Radio size={11} className={marketOpen ? 'pulse-green' : ''} />
            {marketOpen
              ? `Live · Run #${runCount} · Next in ${nextRunIn}s`
              : `Auto-paused (market closed) · ${runCount} runs done`
            }
          </div>

          <div className="ml-auto flex items-center gap-2">
            <div className="flex gap-1 p-0.5 bg-[#0f0f1a] border border-[#1e1e35] rounded-lg">
              {(['investor', 'trader'] as Mode[]).map(m => (
                <button key={m} onClick={() => changeMode(m)}
                  className={`px-3 py-1 rounded-md text-xs font-semibold capitalize transition-colors ${
                    mode === m ? 'bg-[rgba(245,158,11,0.15)] text-[#f59e0b]' : 'text-[#475569] hover:text-[#64748b]'
                  }`}>{m}</button>
              ))}
            </div>
            <button
              onClick={runSession}
              disabled={sessionRunning}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[rgba(0,217,126,0.1)] text-[#00d97e] border border-[rgba(0,217,126,0.3)] hover:bg-[rgba(0,217,126,0.18)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {sessionRunning
                ? <><Loader2 size={11} className="animate-spin" /> Running…</>
                : <><Zap size={11} /> Run Session Now</>
              }
            </button>
            <button onClick={reset}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-[#64748b] border border-[#1e1e35] hover:border-[#2a2a4a]">
              <RotateCcw size={11} /> Reset
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-screen-2xl mx-auto px-4 py-4 space-y-4">

        {/* Session status bar */}
        {sessionMsg && (
          <div className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-medium border ${
            sessionMsg.startsWith('✓')
              ? 'bg-[rgba(0,217,126,0.06)] border-[rgba(0,217,126,0.2)] text-[#00d97e]'
              : sessionMsg.startsWith('✗')
              ? 'bg-[rgba(255,61,87,0.06)] border-[rgba(255,61,87,0.2)] text-[#ff3d57]'
              : 'bg-[rgba(245,158,11,0.06)] border-[rgba(245,158,11,0.2)] text-[#f59e0b]'
          }`}>
            {sessionRunning && <Loader2 size={12} className="animate-spin shrink-0" />}
            {sessionMsg}
            {!sessionRunning && (
              <button onClick={() => setSessionMsg('')} className="ml-auto text-[#475569] hover:text-[#64748b]">✕</button>
            )}
          </div>
        )}

        {/* How it works banner */}
        <div className="rounded-xl border border-[rgba(245,158,11,0.2)] bg-[rgba(245,158,11,0.05)] p-4">
          <div className="flex items-start gap-3 flex-wrap">
            <Zap size={16} className="text-[#f59e0b] shrink-0 mt-0.5" />
            <div className="text-xs text-[#94a3b8] leading-relaxed">
              <span className="font-semibold text-[#f59e0b]">Fully automated 5-analyst rule engine</span> —
              runs every <strong>60 seconds during market hours (9:15–15:30 IST, Mon–Fri)</strong> with
              zero LLM/Claude API calls. Analyses {mode === 'trader' ? 15 : 20} NSE stocks using
              RSI · MACD · Bollinger Bands · SMA crossover · PE · ROE · news sentiment · VIX.
              Claude is only called when you confirm a <em>real</em> order.
              {!marketOpen && <span className="text-[#64748b]"> Auto-trading pauses when market closes and resumes at 9:15 IST.</span>}
            </div>
          </div>
        </div>

        {/* Analyse any stock */}
        <TickerSearch mode={mode} />

        {/* Live trade feed */}
        {recentTrades.length > 0 && (
          <div className="card p-4">
            <div className="flex items-center gap-2 mb-3">
              <Radio size={13} className="text-[#00d97e] pulse-green" />
              <h2 className="font-semibold text-sm text-[#e2e8f0]">Live Trade Feed</h2>
              <span className="text-xs text-[#475569]">auto-updated · last {runCount} sessions</span>
            </div>
            <div className="space-y-1.5 max-h-40 overflow-y-auto">
              {[...recentTrades].reverse().map((t, i) => (
                <TradePill key={i} t={t} />
              ))}
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <Stat label="Portfolio Value" value={totalValue > 0 ? fmt(totalValue) : fmt(initCapital)} icon={Wallet} color="#3b82f6"
            sub={positions.length > 0 ? `${positions.length} positions` : 'All cash'} />
          <Stat label="Total P&L" value={`${totalPnl >= 0 ? '+' : ''}${fmt(totalPnl)}`} sub={fmtPct(totalPct)}
            icon={totalPnl >= 0 ? TrendingUp : TrendingDown} color={totalPnl >= 0 ? '#00d97e' : '#ff3d57'} />
          <Stat label="Cash" value={fmt(cash)} sub={`${((cash / initCapital) * 100).toFixed(0)}% of capital`} icon={Wallet} color="#8b5cf6" />
          <Stat label="Annualised" value={`${annReturn >= 0 ? '+' : ''}${annReturn.toFixed(1)}%`}
            sub={`${daysRunning} day${daysRunning !== 1 ? 's' : ''} tracked`} icon={Target} color="#f59e0b" />
          <Stat label="Win Rate" value={`${stats?.win_rate ?? 0}%`} sub={`${stats?.wins ?? 0}W / ${stats?.losses ?? 0}L`} icon={Award} color="#00d97e" />
          <Stat label="Sessions Run" value={String(runCount)} sub={`${stats?.total_trades ?? 0} total trades`} icon={BarChart2} color="#64748b" />
        </div>

        {/* Performance chart */}
        {chartNorm.length > 0 && (
          <div className="card p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-sm text-[#e2e8f0]">Performance vs NIFTY 50</h2>
              <div className="flex items-center gap-4 text-xs text-[#64748b]">
                <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#f59e0b] inline-block"/>AI Portfolio</span>
                <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#475569] inline-block"/>NIFTY 50</span>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartNorm} margin={{ left: 0, right: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e1e35"/>
                <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#475569' }} axisLine={false} tickLine={false}/>
                <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 10, fill: '#475569' }} axisLine={false} tickLine={false}/>
                <Tooltip contentStyle={{ background: '#0f0f1a', border: '1px solid #1e1e35', borderRadius: 8, fontSize: 12 }}
                  formatter={(v, n) => [`${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(2)}%`, String(n)]}/>
                <ReferenceLine y={0} stroke="#334155" strokeDasharray="3 3"/>
                <Line type="monotone" dataKey="pnl_pct" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3, fill: '#f59e0b' }} name="AI Portfolio"/>
                <Line type="monotone" dataKey="nifty_pct" stroke="#475569" strokeWidth={1.5} dot={false} name="NIFTY 50" strokeDasharray="4 2"/>
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Active positions */}
        {positions.length > 0 && (
          <div className="card overflow-hidden">
            <div className="px-4 py-3 border-b border-[#1e1e35] flex items-center justify-between">
              <h2 className="font-semibold text-sm text-[#e2e8f0]">Active Virtual Positions</h2>
              <span className="text-xs text-[#64748b]">{positions.length} open</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[#475569] border-b border-[#1e1e35] uppercase tracking-wide">
                    {['Ticker', 'Dir', 'Qty', 'Entry', 'Current', 'Value', 'P&L', 'P&L %', 'Stop', 'Target'].map(h => (
                      <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p: Record<string, unknown>) => {
                    const pnl = p.unrealized_pnl as number;
                    const up = pnl >= 0;
                    return (
                      <tr key={p.id as string} className="border-b border-[#0f0f1a] hover:bg-[#0a0a12]">
                        <td className="px-3 py-2 font-bold text-[#e2e8f0]">{p.ticker as string}</td>
                        <td className="px-3 py-2"><span className={p.direction === 'long' ? 'badge-buy' : 'badge-sell'}>{(p.direction as string).toUpperCase()}</span></td>
                        <td className="px-3 py-2 text-[#94a3b8]">{Math.floor(p.quantity as number)}</td>
                        <td className="px-3 py-2 text-[#94a3b8]">₹{(p.avg_entry_price as number).toFixed(2)}</td>
                        <td className="px-3 py-2 font-medium text-[#e2e8f0]">₹{(p.current_price as number).toFixed(2)}</td>
                        <td className="px-3 py-2 text-[#e2e8f0]">₹{Math.round(p.market_value as number).toLocaleString('en-IN')}</td>
                        <td className={`px-3 py-2 font-semibold ${up ? 'positive' : 'negative'}`}>{up ? '+' : ''}₹{Math.abs(Math.round(pnl)).toLocaleString('en-IN')}</td>
                        <td className={`px-3 py-2 font-semibold ${up ? 'positive' : 'negative'}`}>{fmtPct(p.unrealized_pnl_pct as number)}</td>
                        <td className="px-3 py-2 text-[#ff3d57]">₹{(p.stop_loss as number).toFixed(2)}</td>
                        <td className="px-3 py-2 text-[#00d97e]">₹{(p.take_profit as number).toFixed(2)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Daily P&L */}
        {chartData.length > 0 && (
          <div className="card p-4">
            <h2 className="font-semibold text-sm text-[#e2e8f0] mb-4">Daily P&L</h2>
            <ResponsiveContainer width="100%" height={120}>
              <AreaChart data={chartData}>
                <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#475569' }} axisLine={false} tickLine={false}/>
                <YAxis tickFormatter={v => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`} tick={{ fontSize: 10, fill: '#475569' }} axisLine={false} tickLine={false}/>
                <Tooltip contentStyle={{ background: '#0f0f1a', border: '1px solid #1e1e35', borderRadius: 8, fontSize: 12 }}
                  formatter={(v) => [`${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(2)}%`, 'Daily P&L']}/>
                <ReferenceLine y={0} stroke="#334155"/>
                <Area type="monotone" dataKey="daily_pnl_pct" stroke="#8b5cf6" fill="rgba(139,92,246,0.1)" strokeWidth={2}/>
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Full trade history */}
        <div className="card">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#1e1e35]">
            <h2 className="font-semibold text-sm text-[#e2e8f0]">Full Trade History — With 5-Analyst Reasoning</h2>
            <div className="flex items-center gap-3 text-xs text-[#64748b]">
              <span className="positive">Best: {fmt((stats?.best_trade as number) ?? 0)}</span>
              <span className="negative">Worst: -{fmt(Math.abs((stats?.worst_trade as number) ?? 0))}</span>
              <span>{trades.length} trades</span>
            </div>
          </div>
          <div className="p-3 space-y-2 max-h-[600px] overflow-y-auto">
            {trades.length === 0 && (
              <div className="text-center text-sm py-12 space-y-4">
                <Clock size={28} className="mx-auto text-[#1e1e35]" />
                <div>
                  <div className="font-medium text-[#475569] mb-1">No trades yet</div>
                  <div className="text-xs text-[#334155]">
                    Auto-trader runs every 60 s during NSE hours (Mon–Fri, 9:15 AM – 3:30 PM IST).<br/>
                    Outside market hours, use the button below to force a session.
                  </div>
                </div>
                <button
                  onClick={runSession}
                  disabled={sessionRunning}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold bg-[rgba(0,217,126,0.12)] text-[#00d97e] border border-[rgba(0,217,126,0.3)] hover:bg-[rgba(0,217,126,0.2)] disabled:opacity-50 transition-colors"
                >
                  {sessionRunning
                    ? <><Loader2 size={13} className="animate-spin" /> Running session…</>
                    : <><Zap size={13} /> Run Trading Session Now</>
                  }
                </button>
              </div>
            )}
            {trades.map(t => <TradeCard key={t.id as string} trade={t} activeMode={mode} />)}
          </div>
        </div>

        {/* 15-day report */}
        {daysRunning > 0 && (
          <div className="card p-4 border border-[rgba(245,158,11,0.2)]">
            <h2 className="font-semibold text-sm text-[#f59e0b] mb-3 flex items-center gap-2">
              <Target size={15}/> {daysRunning}-Day Report — If This Were Real Money
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              {[
                { label: 'Starting Capital', value: fmt(initCapital) },
                { label: 'Current Value',    value: fmt(totalValue), color: totalPnl >= 0 ? '#00d97e' : '#ff3d57' },
                { label: `${daysRunning}-Day Return`, value: fmtPct(totalPct), color: totalPct >= 0 ? '#00d97e' : '#ff3d57' },
                { label: 'Annualised (proj)', value: `${annReturn >= 0 ? '+' : ''}${annReturn.toFixed(1)}% p.a.`, color: annReturn >= 0 ? '#00d97e' : '#ff3d57' },
                { label: 'Total Trades',  value: String(stats?.total_trades ?? 0) },
                { label: 'Win Rate',      value: `${stats?.win_rate ?? 0}%` },
                { label: 'Avg Win',       value: fmt((stats?.avg_win as number) ?? 0), color: '#00d97e' },
                { label: 'Avg Loss',      value: fmt(Math.abs((stats?.avg_loss as number) ?? 0)), color: '#ff3d57' },
              ].map(item => (
                <div key={item.label}>
                  <div className="text-xs text-[#64748b] mb-0.5">{item.label}</div>
                  <div className="font-bold" style={{ color: item.color ?? '#e2e8f0' }}>{item.value}</div>
                </div>
              ))}
            </div>
            <p className="text-xs text-[#334155] mt-3">
              * Paper trading results ≠ real performance. Slippage, liquidity, and execution risk not modelled.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
