import type { MarketData } from "@/types/market"

export type Tone = "neutral" | "good" | "warn" | "danger"
export interface ScoreResult { score: number; qualified: boolean; trend_score: number; momentum_score: number; volume_score: number; volatility_score: number; session_score: number; spread_score: number; rsi: number; reversal_score: number }
export interface TraderDecision { decision: "BUY" | "SELL" | "NONE"; confidence: number; status?: "UNKNOWN" | "COMPLETED" | "FILTERED" | "ERROR" | "UNAVAILABLE"; reason?: string; latency_ms?: number | null; input_tokens?: number | null; output_tokens?: number | null; reasoning_tokens?: number | null }
export interface PipelineState { cycle_id: string; status: "PROCESSING" | "COMPLETED" | "SKIPPED" | "ERROR"; stage: string; reason?: string | null; started_at?: string; updated_at?: string; completed_at?: string | null }
export interface AIGateState { call: boolean; reason: string; allowed_actions: string[]; action_reasons: Record<string, string>; news_changed: boolean }
export interface RiskDecision { approved: boolean; risk_score: number; reason: string }
export interface ExecutionResult { signal_created: boolean; order_type: string; lot: number; reason: string; signal_id?: string }
export interface FundamentalState { available?: boolean; market_sentiment?: string; confidence?: number; session?: string; liquidity?: string; volatility?: string; risk_level?: string; high_impact_news?: boolean; news_state?: string; minutes_to_news?: number | null; event?: string | null; impact?: string; phase?: string }
export interface StatisticsState { trend?: string; support?: number; resistance?: number; market_location?: string }
export interface PatternState { direction?: string; trend?: string; support?: number; resistance?: number; volume_spike?: boolean }
export interface DashboardSnapshot { pipeline?: PipelineState; ai_gate?: AIGateState; market?: MarketData; score?: ScoreResult; statistics?: StatisticsState; fundamental?: FundamentalState; pattern?: PatternState; decision?: TraderDecision; risk?: RiskDecision; execution?: ExecutionResult; updated_at?: string }
export interface JournalRecord {
  pipeline?: PipelineState; ai_gate?: AIGateState; gate_reason?: string; timestamp?: string;
  event?: "ANALYSIS" | "SIGNAL_CREATED" | "TRADE_EXECUTED" | "TRADE_REJECTED" | "TRADE_CLOSED";
  symbol?: string; side?: "BUY" | "SELL"; lot?: number; price?: number; profit?: number; deal_id?: number; order_id?: number; position_id?: number;
  score?: ScoreResult; decision?: TraderDecision; risk?: RiskDecision; execution?: ExecutionResult;
  signal?: { signal_id: string; symbol: string; action: string; lot: number };
  confirmation?: { signal_id?: string; status: string; action: string; order_id?: number; deal_id?: number; requested_lot?: number; filled_lot: number; executed_price?: number; retcode?: number; reason: string };
}
