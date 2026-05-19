'use client';
import { useEffect, useState } from 'react';
import { RefreshCw, TrendingUp, TrendingDown, AlertCircle } from 'lucide-react';
import { foApi } from '@/lib/api';
import type { FutureContract, OptionChain } from '@/lib/types';

const fmt = (n: number) => n?.toLocaleString('en-IN', { maximumFractionDigits: 2 }) ?? '—';

// ── Option Chain ──────────────────────────────────────────────────────────────
function OptionChainCard({ symbol }: { symbol: string }) {
  const [data, setData] = useState<OptionChain | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true); setError('');
    try {
      const d = await foApi.optionChain(symbol);
      setData(d);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? 'NSE data unavailable — retrying next refresh');
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
          <h3 className="font-semibold text-sm text-[#e2e8f0]">{symbol} Options Chain</h3>
          {data && <div className="text-xs text-[#64748b]">Underlying ₹{fmt(data.underlying)}</div>}
        </div>
        <button onClick={load} className="p-1.5 hover:bg-[#1e1e35] rounded-lg transition-colors">
          <RefreshCw size={13} className={`text-[#64748b] ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && <div className="text-xs text-[#ff3d57] py-2">{error}</div>}

      {data && (
        <>
          {/* Summary row */}
          <div className="grid grid-cols-4 gap-3 mb-4">
            {[
              { label: 'PCR', value: data.pcr, color: pcrColor, sub: pcrLabel },
              { label: 'Max Pain', value: `₹${fmt(data.max_pain)}`, color: 'text-[#f59e0b]', sub: 'strike' },
              { label: 'Total CE OI', value: (data.total_ce_oi / 1e5).toFixed(1) + 'L', color: 'text-[#ff3d57]', sub: 'calls' },
              { label: 'Total PE OI', value: (data.total_pe_oi / 1e5).toFixed(1) + 'L', color: 'text-[#00d97e]', sub: 'puts' },
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

      {!loading && data && !data.total_ce_oi && !data.total_pe_oi && (
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
      <div className="grid grid-cols-3 gap-2">
        {data.map((f, i) => {
          const up = (f.change_pct ?? 0) >= 0;
          return (
            <div key={i} className="bg-[#08080f] border border-[#1e1e35] rounded-xl p-3">
              <div className="text-[10px] text-[#475569] mb-1">{labels[i] ?? `Month ${i + 1}`}</div>
              <div className="text-xs font-bold text-[#e2e8f0]">₹{fmt(f.ltp)}</div>
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
