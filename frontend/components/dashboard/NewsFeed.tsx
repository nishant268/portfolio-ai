'use client';
import { useEffect, useRef, useState } from 'react';
import { ExternalLink, Newspaper, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import type { NewsArticle } from '@/lib/types';

function timeAgo(isoDate: string): string {
  try {
    const diff = Date.now() - new Date(isoDate).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  } catch { return ''; }
}

function sourceColor(source: string): string {
  const map: Record<string, string> = {
    'Economic Times':    '#f59e0b',
    'LiveMint':          '#3b82f6',
    'Business Standard': '#8b5cf6',
    'Moneycontrol':      '#00d97e',
    'Financial Express': '#06b6d4',
    'NDTV Profit':       '#ec4899',
    'Zee Business':      '#f97316',
    'Reuters India':     '#ef4444',
    'Reuters Markets':   '#ef4444',
    'Bloomberg':         '#6366f1',
    'CNBC':              '#22c55e',
  };
  return map[source] ?? '#64748b';
}

export default function NewsFeed({ ticker }: { ticker?: string }) {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [spinning, setSpinning] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  async function load(showSpin = false) {
    if (showSpin) setSpinning(true);
    setLoading(true);
    try {
      const data = ticker
        ? await api.news.forTicker(ticker)
        : await api.news.all(30);
      setArticles(data);
      setLastRefresh(new Date());
    } finally {
      setLoading(false);
      setSpinning(false);
    }
  }

  useEffect(() => {
    load();
    // Auto-refresh every 60 seconds with spin
    intervalRef.current = setInterval(() => load(true), 60_000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]);

  return (
    <div className="card flex flex-col" style={{ maxHeight: 520 }}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#1e1e35] shrink-0">
        <div className="flex items-center gap-2">
          <Newspaper size={15} className="text-[#64748b]" />
          <h2 className="font-semibold text-sm text-[#e2e8f0]">
            {ticker ? `${ticker} News` : 'Market News'}
          </h2>
          {spinning && (
            <span className="text-[10px] text-[#00d97e] font-medium animate-pulse">● refreshing</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {lastRefresh && !spinning && (
            <span className="text-[10px] text-[#334155]">
              {lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
          <span className="text-[10px] text-[#334155]">1min</span>
          <button
            onClick={() => load(true)}
            className="p-1.5 rounded-lg hover:bg-[#1e1e35] transition-colors"
            title="Refresh now"
          >
            <RefreshCw size={12} className={`text-[#64748b] ${spinning ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="overflow-y-auto flex-1 divide-y divide-[#1e1e35]">
        {loading && !articles.length && (
          <div className="p-4 text-center text-[#64748b] text-sm">Loading news...</div>
        )}
        {!loading && !articles.length && (
          <div className="p-4 text-center text-[#64748b] text-sm">No news found.</div>
        )}
        {articles.map(a => (
          <a
            key={a.id}
            href={a.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex gap-3 px-4 py-3 hover:bg-[#0f0f1a] transition-colors group"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span
                  className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                  style={{
                    color: sourceColor(a.source),
                    background: `${sourceColor(a.source)}18`,
                    border: `1px solid ${sourceColor(a.source)}44`,
                  }}
                >
                  {a.source}
                </span>
                <span className="text-[10px] text-[#475569]">{timeAgo(a.published_at)}</span>
              </div>
              <div className="text-xs font-medium text-[#cbd5e1] leading-snug line-clamp-2 group-hover:text-[#e2e8f0] transition-colors">
                {a.title}
              </div>
              {a.summary && (
                <div className="text-[11px] text-[#475569] mt-0.5 line-clamp-1">{a.summary}</div>
              )}
            </div>
            <ExternalLink size={12} className="text-[#334155] group-hover:text-[#64748b] shrink-0 mt-1 transition-colors" />
          </a>
        ))}
      </div>
    </div>
  );
}
