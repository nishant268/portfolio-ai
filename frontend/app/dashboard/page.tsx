'use client';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { RefreshCw, Settings, AlertTriangle, Loader2 } from 'lucide-react';
import { api, modeApi } from '@/lib/api';
import type { Mode, Portfolio, Position } from '@/lib/types';

import MarketHeader from '@/components/dashboard/MarketHeader';
import PortfolioSummary from '@/components/dashboard/PortfolioSummary';
import PositionsTable from '@/components/dashboard/PositionsTable';
import AllocationChart from '@/components/dashboard/AllocationChart';
import SectorChart from '@/components/dashboard/SectorChart';
import NewsFeed from '@/components/dashboard/NewsFeed';
import AIInsights from '@/components/dashboard/AIInsights';
import OrderModal from '@/components/dashboard/OrderModal';
import TraderPanel from '@/components/dashboard/TraderPanel';

export default function Dashboard() {
  const router = useRouter();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [score, setScore] = useState<{
    target_return: number;
    current_return_pct: number;
    on_target: boolean;
    stop_loss_alerts: string[];
    take_profit_alerts: string[];
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sellTarget, setSellTarget] = useState<Position | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [mode, setMode] = useState<Mode>('investor');

  // Load saved mode
  useEffect(() => {
    api.config.get()
      .then(cfg => setMode((cfg.mode as Mode) ?? 'investor'))
      .catch(() => {});
  }, []);

  const loadPortfolio = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const p = await api.portfolio.get();
      setPortfolio(p);
      setLastRefresh(new Date());
      const sc = await api.analysis.portfolioScore(p).catch(() => null);
      if (sc) setScore(sc);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string }; status?: number } };
      if (err?.response?.status === 401) {
        setError('Zerodha not configured — run setup first.');
      } else {
        setError(err?.response?.data?.detail ?? 'Failed to load portfolio');
      }
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadPortfolio(); }, [loadPortfolio]);

  useEffect(() => {
    const id = setInterval(loadPortfolio, 15_000);
    return () => clearInterval(id);
  }, [loadPortfolio]);

  function handleModeChange(m: Mode) {
    setMode(m);
    modeApi.save(m).catch(() => {});
  }

  return (
    <div className="min-h-screen" style={{ background: '#08080f' }}>
      <MarketHeader mode={mode} onModeChange={handleModeChange} />

      <main className="max-w-screen-2xl mx-auto px-4 py-4 space-y-4">
        {/* Toolbar */}
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-[#e2e8f0]">
                {mode === 'trader' ? '⚡ Trader Dashboard' : '📈 Investor Dashboard'}
              </h1>
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                mode === 'trader'
                  ? 'bg-[rgba(139,92,246,0.15)] text-[#8b5cf6]'
                  : 'bg-[rgba(0,217,126,0.1)] text-[#00d97e]'
              }`}>{mode.toUpperCase()}</span>
            </div>
            {lastRefresh && (
              <span className="text-xs text-[#475569]">Updated {lastRefresh.toLocaleTimeString()}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={loadPortfolio}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#64748b] border border-[#1e1e35] hover:border-[#2a2a4a] transition-colors disabled:opacity-40"
            >
              <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
            <button
              onClick={() => router.push('/')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#64748b] border border-[#1e1e35] hover:border-[#2a2a4a] transition-colors"
            >
              <Settings size={12} /> Setup
            </button>
          </div>
        </div>

        {/* Error state */}
        {error && (
          <div className="flex items-center gap-3 p-4 rounded-xl bg-[rgba(255,61,87,0.08)] border border-[rgba(255,61,87,0.2)] text-sm text-[#ff3d57]">
            <AlertTriangle size={16} />
            {error}
            <button onClick={() => router.push('/')} className="ml-auto underline text-xs">Go to Setup</button>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && !portfolio && (
          <div className="flex items-center justify-center py-24 gap-3 text-[#64748b]">
            <Loader2 size={20} className="animate-spin" />
            Loading portfolio from Zerodha…
          </div>
        )}

        {portfolio && (
          <>
            {/* Summary cards */}
            <PortfolioSummary portfolio={portfolio} score={score ?? undefined} />

            {/* Trader-only: F&O Panel */}
            {mode === 'trader' && <TraderPanel />}

            {/* Holdings table */}
            <PositionsTable positions={portfolio.positions} onSell={setSellTarget} />

            {/* Charts row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <AllocationChart positions={portfolio.positions} />
              <SectorChart />
            </div>

            {/* News + AI */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <NewsFeed />
              <AIInsights positions={portfolio.positions} onSell={setSellTarget} />
            </div>

            {/* Alerts */}
            {score && (score.stop_loss_alerts?.length > 0 || score.take_profit_alerts?.length > 0) && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {score.stop_loss_alerts?.length > 0 && (
                  <div className="card p-4">
                    <div className="flex items-center gap-2 mb-2 text-[#ff3d57] font-semibold text-sm">
                      <AlertTriangle size={14} /> Stop-Loss Triggered
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {score.stop_loss_alerts.map(t => <span key={t} className="badge-sell">{t}</span>)}
                    </div>
                  </div>
                )}
                {score.take_profit_alerts?.length > 0 && (
                  <div className="card p-4">
                    <div className="flex items-center gap-2 mb-2 text-[#00d97e] font-semibold text-sm">
                      <AlertTriangle size={14} /> Take-Profit Target Reached
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {score.take_profit_alerts.map(t => <span key={t} className="badge-buy">{t}</span>)}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>

      {sellTarget && (
        <OrderModal position={sellTarget} onClose={() => setSellTarget(null)} />
      )}
    </div>
  );
}
