'use client';
import { useEffect, useRef, useState } from 'react';
import { TrendingUp, TrendingDown, Activity, Wifi, WifiOff, MessageSquare, BarChart2, FlaskConical } from 'lucide-react';
import Link from 'next/link';
import { WS_URL, api } from '@/lib/api';
import type { MarketIndex, Mode } from '@/lib/types';

function IndexPill({ idx }: { idx: MarketIndex }) {
  const up = idx.percentChange >= 0;
  return (
    <div className="flex items-center gap-3 px-4 py-2 card rounded-lg shrink-0">
      <div>
        <div className="text-xs text-[#64748b] font-medium">{idx.indexSymbol}</div>
        <div className="text-sm font-bold text-[#e2e8f0]">
          {typeof idx.last === 'number' ? idx.last.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '-'}
        </div>
      </div>
      <div className={`flex items-center gap-1 text-xs font-semibold ${up ? 'positive' : 'negative'}`}>
        {up ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
        {up ? '+' : ''}{idx.percentChange?.toFixed(2)}%
      </div>
    </div>
  );
}

export default function MarketHeader({
  mode, onModeChange,
}: {
  mode?: Mode;
  onModeChange?: (m: Mode) => void;
}) {
  const [indices, setIndices] = useState<MarketIndex[]>([]);
  const [connected, setConnected] = useState(false);
  const [marketOpen, setMarketOpen] = useState<boolean | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  function loadIndices() {
    api.market.indices().then(setIndices).catch(() => {});
    api.market.status().then((d: { marketState?: Array<{ market: string; marketStatus: string }> }) => {
      // Use Capital Market status specifically
      const cap = d?.marketState?.find(s => s.market === 'Capital Market');
      const state = cap?.marketStatus ?? d?.marketState?.[0]?.marketStatus ?? '';
      setMarketOpen(state.toLowerCase().includes('open'));
    }).catch(() => {});
  }

  // Initial REST load + poll every 15s as WebSocket fallback
  useEffect(() => {
    loadIndices();
    const id = setInterval(() => {
      if (!connected) loadIndices();   // only poll when WS is down
    }, 15_000);
    return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected]);

  // Live WebSocket
  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'indices' && Array.isArray(msg.data)) {
          setIndices(msg.data);
        }
      } catch { /* ignore */ }
    };
    return () => ws.close();
  }, []);

  const priority = ['NIFTY 50', 'NIFTY BANK', 'NIFTY IT', 'INDIA VIX'];
  const sorted = [...indices].sort((a, b) => {
    const ai = priority.indexOf(a.indexSymbol), bi = priority.indexOf(b.indexSymbol);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  return (
    <header className="glass sticky top-0 z-50 border-b border-[#1e1e35] px-4 py-2">
      <div className="flex items-center gap-3 overflow-x-auto no-scrollbar">
        {/* Logo */}
        <div className="flex items-center gap-2 shrink-0 mr-2">
          <Activity size={20} className="text-[#00d97e]" />
          <span className="font-bold text-sm gradient-text whitespace-nowrap">Portfolio AI</span>
        </div>

        {/* Market status */}
        <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold shrink-0 ${
          marketOpen === true ? 'bg-[rgba(0,217,126,0.1)] text-[#00d97e]'
          : marketOpen === false ? 'bg-[rgba(255,61,87,0.1)] text-[#ff3d57]'
          : 'bg-[#1e1e35] text-[#64748b]'
        }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${marketOpen ? 'bg-[#00d97e] pulse-green' : 'bg-[#ff3d57]'}`} />
          {marketOpen === null ? 'Checking...' : marketOpen ? 'Market Open' : 'Market Closed'}
        </div>

        {/* Indices */}
        {sorted.slice(0, 4).map(idx => <IndexPill key={idx.indexSymbol} idx={idx} />)}

        <div className="ml-auto shrink-0 flex items-center gap-2">
          {/* Mode toggle */}
          {onModeChange && (
            <div className="flex gap-1 p-0.5 bg-[#0f0f1a] border border-[#1e1e35] rounded-lg">
              <button
                onClick={() => onModeChange('investor')}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-colors ${
                  mode === 'investor'
                    ? 'bg-[rgba(0,217,126,0.15)] text-[#00d97e]'
                    : 'text-[#475569] hover:text-[#64748b]'
                }`}
              >Investor</button>
              <button
                onClick={() => onModeChange('trader')}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold transition-colors ${
                  mode === 'trader'
                    ? 'bg-[rgba(139,92,246,0.15)] text-[#8b5cf6]'
                    : 'text-[#475569] hover:text-[#64748b]'
                }`}
              ><BarChart2 size={11} />Trader</button>
            </div>
          )}

          {/* Paper trading link */}
          <Link href="/paper"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[rgba(245,158,11,0.1)] text-[#f59e0b] border border-[rgba(245,158,11,0.25)] hover:bg-[rgba(245,158,11,0.18)] transition-colors">
            <FlaskConical size={12} /> Paper Trade
          </Link>

          {/* Chat link */}
          <Link href="/chat"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[rgba(139,92,246,0.1)] text-[#8b5cf6] border border-[rgba(139,92,246,0.25)] hover:bg-[rgba(139,92,246,0.18)] transition-colors">
            <MessageSquare size={12} /> Ask AI
          </Link>

          {/* WS status */}
          <div className="flex items-center gap-1 text-xs text-[#64748b]">
            {connected ? <Wifi size={12} className="text-[#00d97e]" /> : <WifiOff size={12} />}
            <span className="hidden sm:inline">{connected ? 'Live' : 'REST'}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
