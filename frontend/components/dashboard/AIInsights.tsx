'use client';
import { useState } from 'react';
import { Brain, Loader2, ChevronDown, ChevronUp, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { Position, DeepAnalysis } from '@/lib/types';

function SignalBadge({ signal }: { signal: string }) {
  const sell = signal.includes('SELL');
  const buy = signal.includes('BUY');
  return (
    <span className={sell ? 'badge-sell' : buy ? 'badge-buy' : 'badge-hold'}>
      {signal.replace('_', ' ')}
    </span>
  );
}

function TickerCard({ pos, onSell }: { pos: Position; onSell: (pos: Position) => void }) {
  const [analysis, setAnalysis] = useState<DeepAnalysis | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  async function runDeep() {
    setLoading(true);
    try {
      await api.analysis.startDeep(pos.ticker);
      // Poll until done
      for (let i = 0; i < 60; i++) {
        await new Promise(r => setTimeout(r, 3000));
        const result = await api.analysis.getDeep(pos.ticker);
        setAnalysis(result);
        if (result.status === 'done' || result.status === 'error') break;
      }
    } finally { setLoading(false); }
  }

  const isSell = analysis?.signal?.includes('SELL');

  return (
    <div className="border border-[#1e1e35] rounded-xl overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-[#0f0f1a] transition-colors"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-3">
          <div>
            <div className="text-sm font-semibold text-[#e2e8f0]">{pos.ticker}</div>
            <div className={`text-xs font-medium ${pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}`}>
              {pos.unrealized_pnl >= 0 ? '+' : ''}{pos.unrealized_pnl_pct.toFixed(2)}%
            </div>
          </div>
          {analysis?.signal && <SignalBadge signal={analysis.signal} />}
        </div>
        <div className="flex items-center gap-2">
          {!analysis && !loading && (
            <button
              onClick={e => { e.stopPropagation(); runDeep(); }}
              className="flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-semibold bg-[rgba(59,130,246,0.1)] text-[#3b82f6] border border-[rgba(59,130,246,0.3)] hover:bg-[rgba(59,130,246,0.2)] transition-colors"
            >
              <Brain size={11} /> Analyse
            </button>
          )}
          {loading && <Loader2 size={14} className="animate-spin text-[#64748b]" />}
          {open ? <ChevronUp size={14} className="text-[#64748b]" /> : <ChevronDown size={14} className="text-[#64748b]" />}
        </div>
      </div>

      {/* Expanded content */}
      {open && analysis && (
        <div className="px-4 pb-4 space-y-3 border-t border-[#1e1e35]">
          {analysis.status === 'running' && (
            <div className="flex items-center gap-2 py-3 text-sm text-[#64748b]">
              <Loader2 size={14} className="animate-spin" /> AI agents are debating...
            </div>
          )}
          {analysis.status === 'error' && (
            <div className="flex items-center gap-2 py-3 text-sm text-[#ff3d57]">
              <AlertTriangle size={14} /> {analysis.error}
            </div>
          )}
          {analysis.status === 'done' && (
            <>
              <div className="flex items-center justify-between pt-3">
                <div className="flex items-center gap-2">
                  <SignalBadge signal={analysis.signal!} />
                  <span className="text-xs text-[#64748b]">
                    Confidence: <span className="text-[#e2e8f0] font-semibold">{((analysis.confidence ?? 0) * 100).toFixed(0)}%</span>
                  </span>
                </div>
                {isSell && (
                  <button
                    onClick={() => onSell(pos)}
                    className="flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-semibold bg-[rgba(255,61,87,0.15)] text-[#ff3d57] border border-[rgba(255,61,87,0.4)] hover:bg-[rgba(255,61,87,0.25)] transition-colors"
                  >
                    Create Sell Order
                  </button>
                )}
              </div>

              <p className="text-xs text-[#94a3b8] leading-relaxed">{analysis.analyst_summary}</p>

              {(analysis.target_price || analysis.stop_loss) && (
                <div className="flex gap-4 text-xs">
                  {analysis.target_price && (
                    <span className="text-[#64748b]">Target: <span className="positive font-semibold">₹{analysis.target_price}</span></span>
                  )}
                  {analysis.stop_loss && (
                    <span className="text-[#64748b]">Stop Loss: <span className="negative font-semibold">₹{analysis.stop_loss}</span></span>
                  )}
                </div>
              )}

              {analysis.reasoning && (
                <details className="text-xs">
                  <summary className="text-[#64748b] cursor-pointer hover:text-[#94a3b8]">Agent reasoning →</summary>
                  <div className="mt-2 space-y-2">
                    {Object.entries(analysis.reasoning).map(([k, v]) => (
                      <div key={k} className="border-l-2 border-[#1e1e35] pl-3">
                        <div className="text-[#475569] uppercase text-[10px] font-semibold mb-0.5">{k}</div>
                        <div className="text-[#64748b] leading-relaxed">{v}</div>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function AIInsights({ positions, onSell }: {
  positions: Position[];
  onSell: (pos: Position) => void;
}) {
  return (
    <div className="card flex flex-col" style={{ maxHeight: 520 }}>
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#1e1e35] shrink-0">
        <Brain size={15} className="text-[#8b5cf6]" />
        <h2 className="font-semibold text-sm text-[#e2e8f0]">AI Analyst</h2>
        <span className="text-xs text-[#64748b] ml-1">7-agent LangGraph pipeline</span>
      </div>
      <div className="overflow-y-auto flex-1 p-3 space-y-2">
        {positions.map(pos => (
          <TickerCard key={pos.ticker} pos={pos} onSell={onSell} />
        ))}
        {!positions.length && (
          <div className="text-center text-[#64748b] text-sm py-8">No positions loaded.</div>
        )}
      </div>
    </div>
  );
}
