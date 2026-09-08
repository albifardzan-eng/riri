import type { MarketData } from "@/types/market"

export interface ScoreResult {
  score: number
  qualified: boolean
  rsi: number
  reversal_score: number
}

export interface TraderDecision {
  decision: "BUY" | "SELL" | "NONE"
  confidence: number
  status?: "UNKNOWN" | "COMPLETED" | "FILTERED" | "ERROR" | "UNAVAILABLE"
  reason?: string
  latency_ms?: number | null
  input_tokens?: number | null
  output_tokens?: number | null
  reasoning_tokens?: number | null
}

export interface PipelineState {
  cycle_id: string
  status: "PROCESSING" | "COMPLETED" | "SKIPPED" | "ERROR"
  stage: string
  reason?: string | null
  started_at?: string
  updated_at?: string
  completed_at?: string | null
}

export interface RiskDecision {
  approved: boolean
  risk_score: number
  reason: string
}

export interface ExecutionResult {
  signal_created: boolean
  order_type: string
  lot: number
  reason: string
  signal_id?: string
}

export interface DashboardSnapshot {
  pipeline?: PipelineState
  market?: MarketData
  score?: ScoreResult
  decision?: TraderDecision
  risk?: RiskDecision
  execution?: ExecutionResult
  updated_at?: string
}

export interface JournalRecord {
  pipeline?: PipelineState
  gate_reason?: string
  timestamp?: string
  event?: "ANALYSIS" | "SIGNAL_CREATED" | "TRADE_EXECUTED" | "TRADE_REJECTED" | "TRADE_CLOSED"
  symbol?: string
  side?: "BUY" | "SELL"
  lot?: number
  profit?: number
  score?: ScoreResult
  decision?: TraderDecision
  risk?: RiskDecision
  execution?: ExecutionResult
  signal?: {
    signal_id: string
    symbol: string
    action: string
    lot: number
  }
  confirmation?: {
    status: string
    action: string
    filled_lot: number
    reason: string
  }
}
