'use client';
import { useState } from 'react';
import { X, AlertTriangle, CheckCircle2, Loader2, Bot, ThumbsUp, ThumbsDown } from 'lucide-react';
import { api } from '@/lib/api';
import type { Position } from '@/lib/types';
import { useNotify } from '@/components/ui/Notifications';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

async function validateTrade(pos: Position, action: string, qty: number) {
  const r = await fetch(`${BASE}/api/analysis/validate-trade`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ticker: pos.ticker,
      action,
      quantity: qty,
      price: pos.current_price,
      rule_signal: pos.unrealized_pnl_pct > 20 ? 'TAKE_PROFIT' : pos.unrealized_pnl_pct < -8 ? 'STOP_LOSS' : 'SELL',
      rule_score: pos.unrealized_pnl_pct / 10,
      rule_reasoning: `P&L ${pos.unrealized_pnl_pct.toFixed(1)}%, current ₹${pos.current_price.toFixed(2)}, avg cost ₹${pos.avg_cost.toFixed(2)}`,
    }),
  });
  return r.json();
}

export default function OrderModal({
  position,
  onClose,
}: {
  position: Position;
  onClose: () => void;
}) {
  const { notify } = useNotify();
  const [qty, setQty] = useState(position.quantity);
  const [orderType, setOrderType] = useState<'market' | 'limit'>('market');
  const [limitPrice, setLimitPrice] = useState(position.current_price);
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ order_id: string; status: string } | null>(null);
  const [error, setError] = useState('');
  const [aiOpinion, setAiOpinion] = useState<{ verdict: string; opinion: string; cached?: boolean } | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  async function submit() {
    setSubmitting(true);
    setError('');
    try {
      const res = await api.portfolio.placeSell({
        ticker: position.ticker,
        quantity: qty,
        order_type: orderType,
        limit_price: orderType === 'limit' ? limitPrice : undefined,
        confirmed: true,
      });
      setResult(res);
      notify('sell', `SELL Order Placed — ${position.ticker}`,
        `${qty} shares @ ₹${position.current_price.toFixed(2)} · Order ID: ${res.order_id}`);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      const msg = err?.response?.data?.detail ?? 'Order failed';
      setError(msg);
      notify('error', 'Order Failed', msg);
    } finally { setSubmitting(false); }
  }

  const estimatedValue = qty * (orderType === 'limit' ? limitPrice : position.current_price);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div className="card w-full max-w-md mx-4 slide-up">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#1e1e35]">
          <h2 className="font-semibold text-[#e2e8f0]">Sell <span className="negative">{position.ticker}</span></h2>
          <button onClick={onClose} className="p-1.5 hover:bg-[#1e1e35] rounded-lg transition-colors">
            <X size={16} className="text-[#64748b]" />
          </button>
        </div>

        {result ? (
          <div className="px-5 py-6 text-center space-y-3">
            <CheckCircle2 size={40} className="mx-auto positive" />
            <div className="font-semibold text-[#e2e8f0]">Order Submitted!</div>
            <div className="text-sm text-[#64748b]">Order ID: <span className="text-[#94a3b8]">{result.order_id}</span></div>
            <div className="text-sm text-[#64748b]">Status: <span className="positive">{result.status}</span></div>
            <button onClick={onClose} className="mt-2 px-6 py-2 rounded-lg text-sm font-semibold bg-[rgba(0,217,126,0.1)] text-[#00d97e] border border-[rgba(0,217,126,0.3)] hover:bg-[rgba(0,217,126,0.2)] transition-colors">
              Done
            </button>
          </div>
        ) : (
          <div className="px-5 py-4 space-y-4">
            {/* Position info */}
            <div className="rounded-lg bg-[#08080f] border border-[#1e1e35] p-3 grid grid-cols-3 gap-3 text-xs">
              <div><div className="text-[#64748b]">LTP</div><div className="font-semibold text-[#e2e8f0]">₹{position.current_price.toLocaleString('en-IN')}</div></div>
              <div><div className="text-[#64748b]">Holdings</div><div className="font-semibold text-[#e2e8f0]">{position.quantity}</div></div>
              <div>
                <div className="text-[#64748b]">P&L</div>
                <div className={`font-semibold ${position.unrealized_pnl >= 0 ? 'positive' : 'negative'}`}>
                  {position.unrealized_pnl >= 0 ? '+' : ''}{position.unrealized_pnl_pct.toFixed(2)}%
                </div>
              </div>
            </div>

            {/* Qty */}
            <div>
              <label className="text-xs text-[#64748b] mb-1 block">Quantity</label>
              <input
                type="number"
                value={qty}
                min={1}
                max={position.quantity}
                onChange={e => setQty(Number(e.target.value))}
                className="w-full bg-[#08080f] border border-[#1e1e35] rounded-lg px-3 py-2 text-sm text-[#e2e8f0] focus:border-[#3b82f6] focus:outline-none"
              />
            </div>

            {/* Order type */}
            <div>
              <label className="text-xs text-[#64748b] mb-1 block">Order Type</label>
              <div className="flex gap-2">
                {(['market', 'limit'] as const).map(t => (
                  <button
                    key={t}
                    onClick={() => setOrderType(t)}
                    className={`flex-1 py-2 rounded-lg text-sm font-semibold capitalize transition-colors border ${
                      orderType === t
                        ? 'bg-[rgba(59,130,246,0.15)] text-[#3b82f6] border-[rgba(59,130,246,0.4)]'
                        : 'bg-[#08080f] text-[#64748b] border-[#1e1e35] hover:border-[#2a2a4a]'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* Limit price */}
            {orderType === 'limit' && (
              <div>
                <label className="text-xs text-[#64748b] mb-1 block">Limit Price (₹)</label>
                <input
                  type="number"
                  value={limitPrice}
                  step={0.05}
                  onChange={e => setLimitPrice(Number(e.target.value))}
                  className="w-full bg-[#08080f] border border-[#1e1e35] rounded-lg px-3 py-2 text-sm text-[#e2e8f0] focus:border-[#3b82f6] focus:outline-none"
                />
              </div>
            )}

            {/* Estimated value */}
            <div className="rounded-lg bg-[rgba(255,61,87,0.06)] border border-[rgba(255,61,87,0.2)] p-3 text-xs">
              <div className="flex justify-between">
                <span className="text-[#64748b]">Estimated proceeds</span>
                <span className="font-semibold text-[#e2e8f0]">₹{estimatedValue.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
              </div>
            </div>

            {/* Claude Opinion — on demand, one API call */}
            <div className="rounded-xl border border-[#1e1e35] overflow-hidden">
              <button
                onClick={async () => {
                  setAiLoading(true);
                  const res = await validateTrade(position, 'SELL', qty).catch(() => null);
                  setAiLoading(false);
                  if (res) setAiOpinion(res);
                }}
                disabled={aiLoading}
                className="w-full flex items-center justify-between px-3 py-2.5 bg-[#0f0f1a] hover:bg-[#141426] transition-colors"
              >
                <div className="flex items-center gap-2 text-xs font-semibold text-[#8b5cf6]">
                  <Bot size={13} />
                  {aiLoading ? 'Claude is thinking…' : aiOpinion ? 'Claude\'s opinion' : 'Get Claude\'s opinion (1 API call)'}
                </div>
                {aiLoading && <Loader2 size={12} className="animate-spin text-[#8b5cf6]" />}
                {aiOpinion && !aiLoading && (
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                    aiOpinion.verdict === 'CONFIRM' ? 'bg-[rgba(0,217,126,0.15)] text-[#00d97e]'
                    : aiOpinion.verdict === 'REJECT' ? 'bg-[rgba(255,61,87,0.15)] text-[#ff3d57]'
                    : 'bg-[rgba(245,158,11,0.15)] text-[#f59e0b]'
                  }`}>{aiOpinion.verdict} {aiOpinion.cached ? '(cached)' : ''}</span>
                )}
              </button>
              {aiOpinion && (
                <div className="px-3 py-2.5 text-xs text-[#94a3b8] leading-relaxed border-t border-[#1e1e35] bg-[#08080f]">
                  {aiOpinion.verdict === 'CONFIRM'
                    ? <ThumbsUp size={11} className="inline mr-1 text-[#00d97e]" />
                    : aiOpinion.verdict === 'REJECT'
                    ? <ThumbsDown size={11} className="inline mr-1 text-[#ff3d57]" />
                    : null}
                  {aiOpinion.opinion}
                  {aiOpinion.cached && <span className="text-[#334155] ml-1">(cached — no API call used)</span>}
                </div>
              )}
            </div>

            {/* Warning */}
            <div className="flex items-start gap-2 text-xs text-[#f59e0b]">
              <AlertTriangle size={13} className="shrink-0 mt-0.5" />
              <span>This will place a real sell order on your Zerodha account. Double-check before confirming.</span>
            </div>

            {error && (
              <div className="text-xs text-[#ff3d57] bg-[rgba(255,61,87,0.1)] border border-[rgba(255,61,87,0.3)] rounded-lg p-3">
                {error}
              </div>
            )}

            <button
              onClick={submit}
              disabled={submitting || qty <= 0 || qty > position.quantity}
              className="w-full py-3 rounded-xl font-semibold text-sm bg-[rgba(255,61,87,0.15)] text-[#ff3d57] border border-[rgba(255,61,87,0.4)] hover:bg-[rgba(255,61,87,0.25)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              {submitting ? 'Submitting...' : `Sell ${qty} × ${position.ticker}`}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
