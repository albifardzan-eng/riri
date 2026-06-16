export interface MarketData {
  symbol: string
  bid: number
  ask: number
  spread: number

  balance: number
  equity: number
  free_margin: number

  tick_volume: number
  atr: number
}