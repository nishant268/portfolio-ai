'use client';
import { Fragment, useState } from 'react';
import { Brain, ShoppingCart, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { Position, QuickAnalysis } from '@/lib/types';
import AnalyseButton from '@/components/ui/AnalyseButton';

const fmt = (n: number, digits = 2) =>
  `₹${n.toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;

function SignalBadge({ signal }: { signal: string }) {
  const map: Record<string, string> = {
    STRONG_SELL: 'badge-sell', SELL: 'badge-sell', WEAK_SELL: 'badge-sell',
    HOLD: 'badge-hold',
    WEAK_BUY: 'badge-buy', BUY: 'badge-buy', STRONG_BUY: 'badge-buy',
  };
  return <span className={map[signal] ?? 'badge-hold'}>{signal.replace('_', ' ')}</span>;
}

function AnalysisRow({ ticker, onSell }: { ticker: string; onSell: (pos: Position) => void }) {
  const [data, setData] = useState<QuickAnalysis | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setData(await api.analysis.quick(ticker));
    } finally { setLoading(false); }
  }

  if (!data) {
    return (
      <tr className="border-t border-[#1e1e35]">
        <td colSpan={8} className="px-4 py-3 text-center">
          <button onClick={load} disabled={loading}
            className="text-xs text-[#3b82f6] hover:text-[#60a5fa] flex items-center gap-1 mx-auto">
            {loading ? <Loader2 size={12} className="animate-spin" /> : <Brain size={12} />}
            {loading ? 'Analysing...' : 'Run quick analysis'}
          </button>
        </td>
      </tr>
    );
  }

  const t = data.technicals;
  return (
    <tr className="border-t border-[#1e1e35] bg-[#0a0a14]">
      <td colSpan={8} className="px-4 py-3">
        <div className="flex flex-wrap gap-4 text-xs">
          <span className="text-[#64748b]">RSI <span className="text-[#e2e8f0] font-semibold">{String(t.rsi_14)}</span></span>
          <span className="text-[#64748b]">MACD <span className={`font-semibold ${Number(t.macd_histogram) >= 0 ? 'positive' : 'negative'}`}>{String(t.macd_histogram)}</span></span>
          <span className="text-[#64748b]">vs 50SMA <span className={`font-semibold ${Number(t.price_vs_sma50) >= 0 ? 'positive' : 'negative'}`}>{String(t.price_vs_sma50)}%</span></span>
          <span className="text-[#64748b]">Golden Cross <span className="text-[#e2e8f0] font-semibold">{String(t.golden_cross)}</span></span>
          <span className="text-[#64748b]">PE <span className="text-[#e2e8f0] font-semibold">{String((data.fundamentals as Record<string,unknown>).pe_ratio ?? '—')}</span></span>
          {data.recent_headlines[0] && (
            <span className="text-[#64748b] truncate max-w-xs">Latest: <span className="text-[#94a3b8]">{data.recent_headlines[0]}</span></span>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function PositionsTable({
  positions,
  onSell,
}: {
  positions: Position[];
  onSell: (pos: Position) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<keyof Position>('market_value');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  function toggleSort(key: keyof Position) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  }

  const sorted = [...positions].sort((a, b) => {
    const va = a[sortKey] as number, vb = b[sortKey] as number;
    return sortDir === 'asc' ? va - vb : vb - va;
  });

  function SortIcon({ col }: { col: keyof Position }) {
    if (sortKey !== col) return null;
    return sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />;
  }

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#1e1e35]">
        <h2 className="font-semibold text-sm text-[#e2e8f0]">Holdings</h2>
        <span className="text-xs text-[#64748b]">{positions.length} positions</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-[#64748b] uppercase tracking-wider border-b border-[#1e1e35]">
              {[
                { label: 'Stock', key: 'ticker' },
                { label: 'Qty', key: 'quantity' },
                { label: 'Avg Cost', key: 'avg_cost' },
                { label: 'LTP', key: 'current_price' },
                { label: 'Value', key: 'market_value' },
                { label: 'P&L', key: 'unrealized_pnl' },
                { label: '% P&L', key: 'unrealized_pnl_pct' },
                { label: 'Actions', key: null },
              ].map(({ label, key }) => (
                <th
                  key={label}
                  className={`px-4 py-2 text-left font-medium ${key ? 'cursor-pointer hover:text-[#e2e8f0]' : ''}`}
                  onClick={() => key && toggleSort(key as keyof Position)}
                >
                  <span className="flex items-center gap-1">
                    {label}
                    {key && <SortIcon col={key as keyof Position} />}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map(pos => {
              const up = pos.unrealized_pnl >= 0;
              const isExp = expanded === pos.ticker;
              return (
                <Fragment key={pos.ticker}>
                  <tr
                    className="border-b border-[#1e1e35] hover:bg-[#0f0f1a] transition-colors cursor-pointer"
                    onClick={() => setExpanded(isExp ? null : pos.ticker)}
                  >
                    <td className="px-4 py-3">
                      <div className="font-semibold text-[#e2e8f0]">{pos.ticker}</div>
                      <div className={`text-xs ${pos.day_change_pct >= 0 ? 'positive' : 'negative'}`}>
                        {pos.day_change_pct >= 0 ? '+' : ''}{pos.day_change_pct?.toFixed(2)}% today
                      </div>
                    </td>
                    <td className="px-4 py-3 text-[#94a3b8]">{pos.quantity}</td>
                    <td className="px-4 py-3 text-[#94a3b8]">{fmt(pos.avg_cost)}</td>
                    <td className="px-4 py-3 font-medium text-[#e2e8f0]">{fmt(pos.current_price)}</td>
                    <td className="px-4 py-3 font-medium text-[#e2e8f0]">{fmt(pos.market_value, 0)}</td>
                    <td className={`px-4 py-3 font-semibold ${up ? 'positive' : 'negative'}`}>
                      {up ? '+' : ''}{fmt(pos.unrealized_pnl, 0)}
                    </td>
                    <td className={`px-4 py-3 font-semibold ${up ? 'positive' : 'negative'}`}>
                      {up ? '+' : ''}{pos.unrealized_pnl_pct.toFixed(2)}%
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={e => { e.stopPropagation(); onSell(pos); }}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-[rgba(255,61,87,0.1)] text-[#ff3d57] border border-[rgba(255,61,87,0.3)] hover:bg-[rgba(255,61,87,0.2)] transition-colors"
                        >
                          <ShoppingCart size={11} /> Sell
                        </button>
                        <div onClick={e => e.stopPropagation()}>
                          <AnalyseButton ticker={pos.ticker} size="xs" label="Analyse" />
                        </div>
                      </div>
                    </td>
                  </tr>
                  {isExp && <AnalysisRow key={`${pos.ticker}-analysis`} ticker={pos.ticker} onSell={onSell} />}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
