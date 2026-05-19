export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  cost_basis: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  day_change_pct: number;
  broker: string;
  isin?: string;
}

export interface Portfolio {
  positions: Position[];
  cash: number;
  total_value: number;
  total_cost_basis: number;
  total_unrealized_pnl: number;
  total_pnl_pct: number;
  position_count: number;
}

export interface NewsArticle {
  id: string;
  title: string;
  summary: string;
  url: string;
  source: string;
  category: string;
  published_at: string;
}

export interface MarketIndex {
  indexSymbol: string;
  last: number;
  variation: number;
  percentChange: number;
  open: number;
  high: number;
  low: number;
  previousClose: number;
}

export interface QuickAnalysis {
  ticker: string;
  quick_signal: 'STRONG_SELL' | 'SELL' | 'WEAK_SELL' | 'HOLD' | 'WEAK_BUY' | 'BUY' | 'STRONG_BUY';
  fundamentals: Record<string, unknown>;
  technicals: Record<string, number | string>;
  recent_headlines: string[];
}

export interface DeepAnalysis {
  status: 'not_started' | 'running' | 'done' | 'error';
  ticker: string;
  signal?: string;
  confidence?: number;
  analyst_summary?: string;
  target_price?: number;
  stop_loss?: number;
  reasoning?: Record<string, string>;
  error?: string;
}

export interface AllocationConfig {
  large_cap: number;
  mid_cap: number;
  small_cap: number;
  debt: number;
  cash: number;
}

export interface InvestorProfile {
  name: string;
  risk_tolerance: 'conservative' | 'moderate' | 'aggressive';
  investment_horizon: 'short' | 'medium' | 'long';
  target_annual_return: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  rebalance_frequency: 'monthly' | 'quarterly' | 'annually';
  allocation: AllocationConfig;
  auto_sell_enabled: boolean;
}

export interface ZerodhaConfig {
  api_key: string;
  api_secret: string;
  access_token: string;
  user_id: string;
}

export interface AppConfig {
  zerodha: ZerodhaConfig;
  profile: InvestorProfile;
  llm_provider: string;
  llm_model: string | null;
  configured: boolean;
  mode: Mode;
}

export interface SellOrder {
  ticker: string;
  quantity: number;
  order_type: 'market' | 'limit';
  limit_price?: number;
  reason?: string;
  confirmed?: boolean;
}

export type Mode = 'investor' | 'trader';

// ── Chat ─────────────────────────────────────────────────────────────────────
export interface ChatSession {
  id: string;
  title: string;
  mode: Mode;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  sources_json: string;
  sources?: Record<string, unknown>;
  created_at: string;
}

// ── F&O ──────────────────────────────────────────────────────────────────────
export interface OptionStrike {
  strike: number;
  ce_oi: number;
  ce_ltp: number;
  ce_iv: number;
  pe_oi: number;
  pe_ltp: number;
  pe_iv: number;
}

export interface OptionChain {
  symbol: string;
  underlying: number;
  expiry: string[];
  pcr: number;
  max_pain: number;
  total_ce_oi: number;
  total_pe_oi: number;
  top_strikes: OptionStrike[];
  is_theoretical?: boolean;
  vix?: number;
  dte?: number;
}

export interface FutureContract {
  expiry: string;
  ltp: number;
  change_pct: number;
  oi: number;
}
