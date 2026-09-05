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
  market?: MarketData
  score?: ScoreResult
  decision?: TraderDecision
  risk?: RiskDecision
  execution?: ExecutionResult
  updated_at?: string
}

export interface JournalRecord {
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
