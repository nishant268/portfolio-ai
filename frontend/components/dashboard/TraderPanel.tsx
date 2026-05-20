'use client';
import { useEffect, useState } from 'react';
import { RefreshCw, TrendingUp, TrendingDown, AlertCircle, ExternalLink, Key, CheckCircle2, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { foApi, api } from '@/lib/api';
import type { FutureContract, OptionChain } from '@/lib/types';

const fmt = (n: number) => n?.toLocaleString('en-IN', { maximumFractionDigits: 2 }) ?? '—';

// ── Kiteconnect inline reconnect ──────────────────────────────────────────────
function KiteReconnect({ onSuccess }: { onSuccess: () => void }) {
  const [open, setOpen]               = useState(false);
  const [loginUrl, setLoginUrl]       = useState('');
  const [requestToken, setRequestToken] = useState('');
  const [loading, setLoading]         = useState(false);
  const [done, setDone]               = useState(false);
  const [error, setError]             = useState('');

  async function getUrl() {
    setLoading(true); setError('');
    try {
      const { login_url } = await api.config.loginUrl();
      setLoginUrl(login_url);
      window.open(login_url, '_blank', 'noopener,noreferrer');
    } catch {
      setError('Failed — make sure API Key + Secret are saved in Setup first.');
    } finally { setLoading(false); }
  }

  async function exchange() {
    if (!requestToken.trim()) return;
    setLoading(true); setError('');
    try {
      await api.config.generateToken(requestToken.trim());
      setDone(true);
      setTimeout(() => { setOpen(false); onSuccess(); }, 800);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? 'Token exchange failed — check your request_token.');
    } finally { setLoading(false); }
  }

  return (
    <div className="border border-[rgba(245,158,11,0.25)] rounded-xl bg-[rgba(245,158,11,0.04)] overflow-hidden mb-3">
      {/* Header row — always visible */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left"
      >
        <AlertCircle size={12} className="text-[#f59e0b] shrink-0" />
        <div className="flex-1 min-w-0">
          <span className="text-[11px] font-semibold text-[#f59e0b]">Live CE/PE OI unavailable</span>
          <span className="text-[10px] text-[#64748b] ml-2">
            Kiteconnect needs NSE + NFO exchange permissions
          </span>
        </div>
        {open ? <ChevronUp size={12} className="text-[#475569] shrink-0" /> : <ChevronDown size={12} className="text-[#475569] shrink-0" />}
      </button>

      {/* Expandable instructions + OAuth flow */}
      {open && (
        <div className="border-t border-[rgba(245,158,11,0.15)] px-3 pb-3 pt-2 space-y-3">

          {/* Step 1 — Enable permissions on developers.kite.trade */}
          <div className="bg-[#08080f] border border-[#1e1e35] rounded-lg p-3 space-y-1.5">
            <div className="text-[11px] font-semibold text-[#e2e8f0]">Step 1 — Enable NSE &amp; NFO in your API app</div>
            <ol className="text-[10px] text-[#64748b] space-y-1 list-decimal list-inside leading-relaxed">
              <li>Open <a href="https://developers.kite.trade" target="_blank" rel="noopener noreferrer" className="text-[#3b82f6] underline inline-flex items-center gap-0.5">developers.kite.trade <ExternalLink size={9}/></a></li>
              <li>Click your app → <strong className="text-[#94a3b8]">Edit</strong></li>
              <li>Under <strong className="text-[#94a3b8]">Exchange permissions</strong> tick <strong className="text-[#f59e0b]">NSE</strong>, <strong className="text-[#f59e0b]">NFO</strong>, and <strong className="text-[#f59e0b]">BSE</strong></li>
              <li>Save — then continue to Step 2 below</li>
            </ol>
          </div>

          {/* Step 2 — Re-login */}
          <div className="bg-[#08080f] border border-[#1e1e35] rounded-lg p-3 space-y-2">
            <div className="text-[11px] font-semibold text-[#e2e8f0]">Step 2 — Refresh your access token</div>

            {!loginUrl ? (
              <button
                onClick={getUrl}
                disabled={loading}
                className="w-full py-2 rounded-lg text-[11px] font-semibold flex items-center justify-center gap-1.5 bg-[rgba(59,130,246,0.1)] text-[#3b82f6] border border-[rgba(59,130,246,0.3)] hover:bg-[rgba(59,130,246,0.18)] disabled:opacity-50 transition-colors"
              >
                {loading ? <Loader2 size={11} className="animate-spin" /> : <ExternalLink size={11} />}
                Open Kiteconnect Login
              </button>
            ) : (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <a
                    href={loginUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 py-2 rounded-lg text-[11px] font-semibold flex items-center justify-center gap-1.5 bg-[rgba(59,130,246,0.1)] text-[#3b82f6] border border-[rgba(59,130,246,0.3)] hover:bg-[rgba(59,130,246,0.18)] transition-colors"
                  >
                    <ExternalLink size={11} /> Re-open Login Page
                  </a>
                </div>
                <p className="text-[10px] text-[#475569] leading-relaxed">
                  After logging in, Kiteconnect redirects to your app URL with{' '}
                  <code className="bg-[#1a1a2e] px-1 rounded text-[#94a3b8]">?request_token=…</code>{' '}
                  in the address bar. Copy that value and paste below.
                </p>
                <input
                  value={requestToken}
                  onChange={e => setRequestToken(e.target.value)}
                  placeholder="Paste request_token here"
                  className="w-full bg-[#0a0a14] border border-[#1e1e35] rounded-lg px-3 py-2 text-[11px] text-[#e2e8f0] placeholder-[#334155] focus:border-[#3b82f6] focus:outline-none"
                />
                <button
                  onClick={exchange}
                  disabled={loading || !requestToken.trim() || done}
                  className="w-full py-2 rounded-lg text-[11px] font-semibold flex items-center justify-center gap-1.5 bg-[rgba(0,217,126,0.1)] text-[#00d97e] border border-[rgba(0,217,126,0.3)] hover:bg-[rgba(0,217,126,0.18)] disabled:opacity-50 transition-colors"
                >
                  {loading ? <Loader2 size={11} className="animate-spin" />
                   : done   ? <CheckCircle2 size={11} />
                   :          <Key size={11} />}
                  {done ? 'Token saved — refreshing…' : 'Generate & Save Token'}
                </button>
              </div>
            )}

            {error && (
              <div className="text-[10px] text-[#ff3d57] bg-[rgba(255,61,87,0.08)] border border-[rgba(255,61,87,0.2)] rounded-lg px-2.5 py-1.5">{error}</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Option Chain ──────────────────────────────────────────────────────────────
function OptionChainCard({ symbol }: { symbol: string }) {
  const [data, setData] = useState<OptionChain | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function load(isRetry = false) {
    setLoading(true);
    if (!isRetry) setError('');
    try {
      const d = await foApi.optionChain(symbol);
      setData(d);
      setError('');
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      if (!isRetry) {
        // Auto-retry once after 3 s (NSE session may need a moment to prime)
        setTimeout(() => load(true), 3000);
      } else {
        setError(msg ?? 'NSE option chain unavailable — NSE may be blocking this server\'s IP. Works on local/Indian deployments.');
      }
    } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [symbol]);

  const pcr = data?.pcr ?? 0;
  const pcrColor = pcr > 1.2 ? 'text-[#00d97e]' : pcr < 0.8 ? 'text-[#ff3d57]' : 'text-[#f59e0b]';
  const pcrLabel = pcr > 1.2 ? 'Bullish' : pcr < 0.8 ? 'Bearish' : 'Neutral';

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-sm text-[#e2e8f0]">{symbol} Options Chain</h3>
            {data?.is_theoretical && (
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[rgba(245,158,11,0.15)] text-[#f59e0b] border border-[rgba(245,158,11,0.3)]">
                THEORETICAL · B-S
              </span>
            )}
          </div>
          {data && (
            <div className="text-xs text-[#64748b] flex items-center gap-2">
              <span>Underlying ₹{fmt(data.underlying)}</span>
              {data.vix ? <span>· VIX {data.vix}</span> : null}
              {data.dte !== undefined ? <span>· {data.dte}d to expiry</span> : null}
            </div>
          )}
        </div>
        <button onClick={() => load()} className="p-1.5 hover:bg-[#1e1e35] rounded-lg transition-colors">
          <RefreshCw size={13} className={`text-[#64748b] ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && <div className="text-xs text-[#ff3d57] py-2">{error}</div>}

      {data && (
        <>
          {/* OI unavailable — show inline reconnect */}
          {!data.total_ce_oi && !data.total_pe_oi && (
            <KiteReconnect onSuccess={() => load()} />
          )}

          {/* Summary row */}
          <div className="grid grid-cols-4 gap-3 mb-4">
            {[
              { label: 'PCR', value: data.pcr ? String(data.pcr) : '—', color: pcrColor, sub: pcrLabel },
              { label: 'Max Pain', value: data.max_pain ? `₹${fmt(data.max_pain)}` : '—', color: 'text-[#f59e0b]', sub: 'strike' },
              { label: 'Total CE OI', value: data.total_ce_oi ? (data.total_ce_oi / 1e5).toFixed(1) + 'L' : '—', color: 'text-[#ff3d57]', sub: 'calls' },
              { label: 'Total PE OI', value: data.total_pe_oi ? (data.total_pe_oi / 1e5).toFixed(1) + 'L' : '—', color: 'text-[#00d97e]', sub: 'puts' },
            ].map(item => (
              <div key={item.label} className="bg-[#08080f] border border-[#1e1e35] rounded-lg p-2.5 text-center">
                <div className="text-[10px] text-[#475569] mb-1">{item.label}</div>
                <div className={`text-sm font-bold ${item.color}`}>{item.value}</div>
                <div className="text-[10px] text-[#334155]">{item.sub}</div>
              </div>
            ))}
          </div>

          {/* Strikes table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[#475569] border-b border-[#1e1e35]">
                  <th className="py-1.5 text-right pr-3 text-[#ff3d57]">CE OI</th>
                  <th className="py-1.5 text-right pr-3 text-[#ff3d57]">CE LTP</th>
                  <th className="py-1.5 text-center font-bold text-[#e2e8f0]">STRIKE</th>
                  <th className="py-1.5 text-left pl-3 text-[#00d97e]">PE LTP</th>
                  <th className="py-1.5 text-left pl-3 text-[#00d97e]">PE OI</th>
                </tr>
              </thead>
              <tbody>
                {data.top_strikes
                  .sort((a, b) => a.strike - b.strike)
                  .map(row => {
                    const atm = Math.abs(row.strike - data.underlying) < 200;
                    return (
                      <tr key={row.strike} className={`border-b border-[#0f0f1a] ${atm ? 'bg-[rgba(245,158,11,0.05)]' : ''}`}>
                        <td className="py-1 text-right pr-3 text-[#ff3d57]">{(row.ce_oi / 1e5).toFixed(1)}L</td>
                        <td className="py-1 text-right pr-3 text-[#94a3b8]">₹{row.ce_ltp}</td>
                        <td className={`py-1 text-center font-bold ${atm ? 'text-[#f59e0b]' : 'text-[#e2e8f0]'}`}>
                          {row.strike} {atm && <span className="text-[9px]">ATM</span>}
                        </td>
                        <td className="py-1 text-left pl-3 text-[#94a3b8]">₹{row.pe_ltp}</td>
                        <td className="py-1 text-left pl-3 text-[#00d97e]">{(row.pe_oi / 1e5).toFixed(1)}L</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {loading && !data && (
        <div className="text-center text-[#475569] text-xs py-6">Loading options chain…</div>
      )}

      {!loading && data && !data.top_strikes?.length && (
        <div className="flex items-center gap-2 text-xs text-[#64748b] bg-[#08080f] border border-[#1e1e35] rounded-xl p-4">
          <AlertCircle size={14} className="shrink-0 text-[#f59e0b]" />
          <div className="flex-1">
            <div className="font-semibold text-[#f59e0b]">No Live Data</div>
            <div className="text-[#475569] mt-0.5">
              Options data is live during market hours (Mon–Fri, 9:15 AM – 3:30 PM IST).
              Outside hours NSE may return empty OI — <button onClick={load} className="text-[#8b5cf6] underline hover:text-[#a78bfa]">refresh</button> to retry.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Futures Strip ─────────────────────────────────────────────────────────────
function FuturesCard({ symbol }: { symbol: string }) {
  const [data, setData] = useState<FutureContract[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    foApi.futures(symbol).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, [symbol]);

  const labels = ['Near Month', 'Mid Month', 'Far Month'];

  return (
    <div className="card p-4">
      <h3 className="font-semibold text-sm text-[#e2e8f0] mb-3">{symbol} Futures</h3>
      {loading && <div className="text-xs text-[#475569] py-3 text-center">Loading…</div>}
      {!loading && !data.length && (
        <div className="flex items-center gap-2 text-xs text-[#64748b] bg-[#08080f] border border-[#1e1e35] rounded-xl p-3">
          <AlertCircle size={13} className="text-[#f59e0b]" />
          Futures data available during market hours: Mon–Fri, 9:15 AM – 3:30 PM IST
        </div>
      )}
      {data.some(f => f.ltp === 0) && (
        <div className="flex items-center gap-1.5 text-[10px] text-[#475569] mb-2">
          <AlertCircle size={10} className="text-[#f59e0b]" />
          Futures LTP unavailable — showing approximate spot price. Enable NSE permissions in Kiteconnect for live futures prices.
        </div>
      )}
      <div className="grid grid-cols-3 gap-2">
        {data.map((f, i) => {
          const up = (f.change_pct ?? 0) >= 0;
          return (
            <div key={i} className="bg-[#08080f] border border-[#1e1e35] rounded-xl p-3">
              <div className="text-[10px] text-[#475569] mb-1">{labels[i] ?? `Month ${i + 1}`}</div>
              <div className="text-xs font-bold text-[#e2e8f0]">{f.ltp ? `₹${fmt(f.ltp)}` : '—'}</div>
              <div className={`text-[11px] font-semibold flex items-center gap-0.5 ${up ? 'positive' : 'negative'}`}>
                {up ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                {up ? '+' : ''}{f.change_pct?.toFixed(2) ?? '0.00'}%
              </div>
              <div className="text-[10px] text-[#334155] mt-0.5 truncate">{f.expiry}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function TraderPanel() {
  const [foSymbol, setFoSymbol] = useState('NIFTY');
  const symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY'];

  return (
    <div className="space-y-4">
      {/* Symbol selector */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-[#64748b] font-medium">F&O Symbol:</span>
        {symbols.map(s => (
          <button
            key={s}
            onClick={() => setFoSymbol(s)}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors border ${
              foSymbol === s
                ? 'bg-[rgba(139,92,246,0.15)] text-[#8b5cf6] border-[rgba(139,92,246,0.3)]'
                : 'text-[#64748b] border-[#1e1e35] hover:border-[#2a2a4a]'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <OptionChainCard symbol={foSymbol} />
        <FuturesCard symbol={foSymbol} />
      </div>
    </div>
  );
}
