import axios from 'axios';
import type {
  Portfolio, NewsArticle, MarketIndex, QuickAnalysis,
  DeepAnalysis, AppConfig, InvestorProfile, ZerodhaConfig, SellOrder,
} from './types';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const http = axios.create({ baseURL: BASE, timeout: 20_000 });

// ── Config ─────────────────────────────────────────────────────────────────
export const api = {
  config: {
    get: () => http.get<AppConfig>('/api/config').then(r => r.data),
    saveZerodha: (z: ZerodhaConfig) => http.post('/api/config/zerodha', z).then(r => r.data),
    loginUrl: () => http.post<{ login_url: string }>('/api/config/zerodha/login-url').then(r => r.data),
    generateToken: (request_token: string) =>
      http.post('/api/config/zerodha/generate-token', { request_token }).then(r => r.data),
    saveProfile: (p: InvestorProfile) => http.post('/api/config/profile', p).then(r => r.data),
    saveLLM: (provider: string, model?: string, api_key?: string) =>
      http.post('/api/config/llm', { provider, model, api_key }).then(r => r.data),
  },

  // ── Market ────────────────────────────────────────────────────────────────
  market: {
    status: () => http.get('/api/market/status').then(r => r.data),
    indices: () => http.get<{ indices: MarketIndex[] }>('/api/market/indices').then(r => r.data.indices),
    quote: (sym: string) => http.get(`/api/market/quote/${sym}`).then(r => r.data),
    gainers: () => http.get<{ data: unknown[] }>('/api/market/gainers').then(r => r.data.data),
    losers: () => http.get<{ data: unknown[] }>('/api/market/losers').then(r => r.data.data),
    sectors: () => http.get<{ data: MarketIndex[] }>('/api/market/sectors').then(r => r.data.data),
  },

  // ── Portfolio ─────────────────────────────────────────────────────────────
  portfolio: {
    get: () => http.get<Portfolio>('/api/portfolio').then(r => r.data),
    placeSell: (order: SellOrder) => http.post('/api/portfolio/orders/sell', order).then(r => r.data),
    orders: () => http.get('/api/portfolio/orders').then(r => r.data),
  },

  // ── News ──────────────────────────────────────────────────────────────────
  news: {
    all: (limit = 60) =>
      http.get<{ articles: NewsArticle[] }>(`/api/news/?limit=${limit}`).then(r => r.data.articles),
    forTicker: (sym: string) =>
      http.get<{ articles: NewsArticle[] }>(`/api/news/ticker/${sym}`).then(r => r.data.articles),
  },

  // ── Analysis ──────────────────────────────────────────────────────────────
  analysis: {
    quick: (ticker: string) =>
      http.get<QuickAnalysis>(`/api/analysis/quick/${ticker}`).then(r => r.data),
    startDeep: (ticker: string) =>
      http.post<DeepAnalysis>(`/api/analysis/deep/${ticker}`).then(r => r.data),
    getDeep: (ticker: string) =>
      http.get<DeepAnalysis>(`/api/analysis/deep/${ticker}`).then(r => r.data),
    portfolioScore: (portfolio: Portfolio) =>
      http.post('/api/analysis/portfolio-score', portfolio).then(r => r.data),
  },
};

export const WS_URL = BASE.replace(/^http/, 'ws') + '/ws/market';

// ── Chat ─────────────────────────────────────────────────────────────────────
// (extend the existing api object)
Object.assign(api, {
  chat: {
    sessions: () => http.get<{ sessions: import('./types').ChatSession[] }>('/api/chat/sessions').then(r => r.data.sessions),
    newSession: (title?: string, mode?: string) =>
      http.post<import('./types').ChatSession>('/api/chat/sessions', { title, mode }).then(r => r.data),
    deleteSession: (id: string) => http.delete(`/api/chat/sessions/${id}`).then(r => r.data),
    messages: (id: string) =>
      http.get<{ session: import('./types').ChatSession; messages: import('./types').ChatMessage[] }>(`/api/chat/sessions/${id}/messages`).then(r => r.data),
    ask: (id: string, question: string, mode: string) =>
      http.post<{ answer: string; sources: Record<string, unknown> }>(`/api/chat/sessions/${id}/ask`, { question, mode }).then(r => r.data),
    deleteMessage: (sid: string, mid: string) =>
      http.delete(`/api/chat/sessions/${sid}/messages/${mid}`).then(r => r.data),
  },

  fo: {
    optionChain: (symbol: string) =>
      http.get<import('./types').OptionChain>(`/api/fo/option-chain/${symbol}`).then(r => r.data),
    futures: (symbol = 'NIFTY') =>
      http.get<{ data: import('./types').FutureContract[] }>(`/api/fo/futures/${symbol}`).then(r => r.data.data),
    fiiDii: () => http.get('/api/fo/fii-dii').then(r => r.data),
    foPositions: () => http.get('/api/fo/fo-positions').then(r => r.data),
  },

});

export const modeApi = {
  save: (mode: string) => http.post('/api/config/mode', { mode }).then(r => r.data),
};

// typed helpers (avoids casting everywhere)
export const chatApi = (api as unknown as Record<string, unknown>).chat as {
  sessions: () => Promise<import('./types').ChatSession[]>;
  newSession: (title?: string, mode?: string) => Promise<import('./types').ChatSession>;
  deleteSession: (id: string) => Promise<unknown>;
  messages: (id: string) => Promise<{ session: import('./types').ChatSession; messages: import('./types').ChatMessage[] }>;
  ask: (id: string, q: string, mode: string) => Promise<{ answer: string; sources: Record<string, unknown> }>;
  deleteMessage: (sid: string, mid: string) => Promise<unknown>;
};

export const foApi = (api as unknown as Record<string, unknown>).fo as {
  optionChain: (s: string) => Promise<import('./types').OptionChain>;
  futures: (s?: string) => Promise<import('./types').FutureContract[]>;
  fiiDii: () => Promise<unknown>;
  foPositions: () => Promise<unknown>;
};
