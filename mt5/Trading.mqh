#ifndef __RIRI_TRADING_MQH__
#define __RIRI_TRADING_MQH__


bool RIRI_RiskCapAllowed(double lot,string direction,double signal_cap);

bool RIRI_SelectedPosition()
{
   return PositionGetString(POSITION_SYMBOL) == _Symbol &&
      PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER;
}


double NormalizeTradeLot(double lot)
{
   double minimum = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maximum = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(minimum <= 0 || maximum <= 0 || step <= 0 || lot < minimum || lot > maximum)
      return 0.0;
   double normalized = NormalizeDouble(MathFloor((lot + 1e-9) / step) * step, 2);
   // Never silently increase or change the backend-approved size.
   return MathAbs(normalized - lot) <= 1e-8 ? normalized : 0.0;
}


int RIRI_PositionCount(double &total_lot)
{
   int count = 0;
   total_lot = 0.0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(!RIRI_SelectedPosition())
         continue;
      count++;
      total_lot += PositionGetDouble(POSITION_VOLUME);
   }
   return count;
}


long RIRI_LatestPositionTime()
{
   return RIRI_ReconcileEntry();
}


bool RIRI_PositionPolicy(const RiriSignal &signal, string &reason)
{
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(!RIRI_SelectedPosition())
         continue;

      long type = PositionGetInteger(POSITION_TYPE);
      string existing = type == POSITION_TYPE_BUY ? "BUY" : "SELL";
      bool hedge = existing != signal.action;
      bool average = existing == signal.action && PositionGetDouble(POSITION_PROFIT) < 0;
      if((hedge || average) && signal.initial_score <= RIRI_EXCEPTION_THRESHOLD)
      {
         reason = hedge ? "HEDGING_REQUIRES_SCORE_ABOVE_80" : "AVERAGING_REQUIRES_SCORE_ABOVE_80";
         return false;
      }
      if((hedge || average) && signal.confidence <= RIRI_EXCEPTION_THRESHOLD)
      {
         reason = "POSITION_EXCEPTION_REQUIRES_CONFIDENCE_ABOVE_80";
         return false;
      }
   }
   return true;
}


bool RIRI_ValidateSignal(const RiriSignal &signal, double &lot, string &reason)
{
   if(signal.entry_policy_version != RIRI_ENTRY_POLICY_VERSION || signal.magic_number != MAGIC_NUMBER)
   {
      reason = "ENTRY_POLICY_MISMATCH";
      return false;
   }
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
   {
      reason = "HEDGING_ACCOUNT_REQUIRED";
      return false;
   }
   if(signal.initial_score < 70 || signal.initial_score > 100 || signal.confidence > 100)
   {
      reason = "INVALID_SCORE_OR_CONFIDENCE";
      return false;
   }
   if(_Symbol != RIRI_SYMBOL || signal.symbol != RIRI_SYMBOL || signal.symbol != _Symbol)
   {
      reason = "SYMBOL_NOT_ALLOWED";
      return false;
   }
   if(signal.action != "BUY" && signal.action != "SELL")
   {
      reason = "INVALID_ACTION";
      return false;
   }
   if(signal.confidence < RIRI_MIN_CONFIDENCE)
   {
      reason = "CONFIDENCE_BELOW_60";
      return false;
   }
   if(signal.tp_points != RIRI_TP_POINTS || signal.sl_points != RIRI_SL_POINTS)
   {
      reason = "PROTECTION_RULE_MISMATCH";
      return false;
   }

   long now = (long)TimeGMT();
   if(signal.market_time <= 0 || now < signal.market_time || now - signal.market_time > 60 ||
      signal.expires_at <= 0 || now > signal.expires_at)
   {
      reason = "STALE_SIGNAL";
      return false;
   }
   double spread_limit=RIRI_EXPERIMENTAL_SPREAD?60.0:RIRI_MAX_SPREAD;
   if(RIRI_EXPERIMENTAL_SPREAD && signal.initial_score>80 && signal.confidence>95) spread_limit=150;
   spread_limit=MathMin(spread_limit,signal.max_spread_points);
   if(spread_limit<=0 || CurrentSpread() > spread_limit)
   {
      reason = "SPREAD_ABOVE_LIMIT";
      return false;
   }
   if(RIRI_GetATR() < RIRI_MIN_ATR)
   {
      reason = "ATR_BELOW_LIMIT";
      return false;
   }
   if(AccountInfoDouble(ACCOUNT_MARGIN_FREE) <= 0)
   {
      reason = "INSUFFICIENT_FREE_MARGIN";
      return false;
   }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ||
      !MQLInfoInteger(MQL_TRADE_ALLOWED) ||
      !AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) ||
      !AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
   {
      reason = "TRADING_NOT_ALLOWED";
      return false;
   }

   if(AccountInfoString(ACCOUNT_CURRENCY)!="USD") {reason="USD_ACCOUNT_REQUIRED";return false;}
   if((RIRI_SMALL_EQUITY_STRICT || signal.small_equity_strict) && AccountInfoDouble(ACCOUNT_EQUITY)<=500 && signal.confidence<=85)
   {reason="SMALL_EQUITY_REQUIRES_CONFIDENCE_ABOVE_85";return false;}
   if(!RIRI_EntrySessionAllowed(signal.preclose_enabled)) {reason="PRECLOSE_ENTRY_BLOCKED";return false;}
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick) || (long)TimeTradeServer()-(long)tick.time>10)
   {reason="STALE_TICK";return false;}
   double active_lot = 0.0, pending_lot=0;
   int active = RIRI_PositionCount(active_lot)+RIRI_PendingCount(pending_lot);
   active_lot+=pending_lot;
   if(active >= RIRI_MAX_ACTIVE_TRADES)
   {
      reason = "MAX_ACTIVE_TRADES";
      return false;
   }
   long latest_open = RIRI_LatestPositionTime();
   if(latest_open < 0 || latest_open>(long)TimeCurrent())
   {
      reason = "POSITION_TIME_INVALID";
      return false;
   }
   if(latest_open > 0 && (long)TimeCurrent() - latest_open < RIRI_MIN_ENTRY_INTERVAL_SECONDS)
   {
      reason = "MIN_ENTRY_INTERVAL";
      return false;
   }
   if(!RIRI_PositionPolicy(signal, reason))
      return false;

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity < 0)
   {
      reason = "INVALID_EQUITY";
      return false;
   }
   double policy_lot = signal.confidence < RIRI_STANDARD_CONFIDENCE
      ? RIRI_REDUCED_CONFIDENCE_LOT
      : RIRI_DEFAULT_LOT + MathFloor(equity / RIRI_EQUITY_STEP) * RIRI_LOT_STEP;
   double remaining_lot = MathMax(0.0, RIRI_MAX_TOTAL_LOT - active_lot);
   remaining_lot = MathFloor((remaining_lot + 1e-9) * 100.0) / 100.0;
   policy_lot = MathMin(policy_lot, remaining_lot);
   if(signal.lot > policy_lot + 1e-8)
   {
      reason = "LOT_POLICY_EXCEEDED";
      return false;
   }

   lot = NormalizeTradeLot(signal.lot);
   if(lot <= 0)
   {
      reason = "INVALID_LOT";
      return false;
   }
   if(active_lot + lot > RIRI_MAX_TOTAL_LOT + 1e-8)
   {
      reason = "MAX_TOTAL_LOT";
      return false;
   }
   if(!RIRI_RiskCapAllowed(lot,signal.action,signal.max_sl_risk_percent)) {reason="PORTFOLIO_SL_RISK_LIMIT";return false;}
   return true;
}


ENUM_ORDER_TYPE_FILLING RIRI_FillingMode()
{
   long modes = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((modes & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      return ORDER_FILLING_FOK;
   if((modes & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
}


bool RIRI_SendOrder(const RiriSignal &signal, double lot)
{
   MqlTradeRequest request;
   MqlTradeResult result;
   MqlTradeCheckResult check;
   ZeroMemory(request);
   ZeroMemory(result);
   ZeroMemory(check);

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double price = signal.action == "BUY"
      ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
      : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(point <= 0 || price <= 0)
   {
      ConfirmSignal(signal, "REJECTED", 0, 0, 0, 0, 0, "INVALID_MARKET_PRICE");
      return false;
   }

   request.action = TRADE_ACTION_DEAL;
   request.magic = MAGIC_NUMBER;
   request.symbol = _Symbol;
   request.type = signal.action == "BUY" ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   request.volume = lot;
   request.price = price;
   request.deviation = (ulong)DEFAULT_SLIPPAGE;
   request.type_filling = RIRI_FillingMode();
   request.comment = EA_NAME;
   request.sl = NormalizeDouble(
      signal.action == "BUY"
         ? price - RIRI_SL_POINTS * point
         : price + RIRI_SL_POINTS * point,
      _Digits
   );
   request.tp = NormalizeDouble(
      signal.action == "BUY"
         ? price + RIRI_TP_POINTS * point
         : price - RIRI_TP_POINTS * point,
      _Digits
   );

   int stops = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   if(MathAbs(price - request.sl) < stops * point || MathAbs(price - request.tp) < stops * point)
   {
      ConfirmSignal(signal, "REJECTED", 0, 0, 0, price, 0, "BROKER_STOP_LEVEL");
      return false;
   }

   if(!OrderCheck(request, check))
   {
      ConfirmSignal(signal, "REJECTED", 0, 0, 0, price, check.retcode, check.comment);
      return false;
   }

   // Permit is consumed once globally; ambiguity must never result in resubmission.
   if(!ConfirmSignal(signal,"UNKNOWN",0,0,0,0,0,"BROKER_OUTCOME_UNKNOWN")) return false;
   bool sent = OrderSend(request, result);
   bool filled = sent && (result.retcode == TRADE_RETCODE_DONE ||
      result.retcode == TRADE_RETCODE_DONE_PARTIAL);
   if(filled) RIRI_RecordEntry((long)TimeCurrent());
   bool uncertain=!sent || result.retcode==TRADE_RETCODE_PLACED || result.retcode==TRADE_RETCODE_TIMEOUT || result.retcode==TRADE_RETCODE_CONNECTION;
   ConfirmSignal(
      signal,
      filled ? "EXECUTED" : uncertain ? "UNKNOWN" : "REJECTED",
      result.order,
      result.deal,
      filled ? result.volume : 0.0,
      result.price,
      result.retcode,
      result.comment
   );
   Print("[EXECUTION] signal=", signal.signal_id,
      " action=", signal.action,
      " score=", signal.initial_score,
      " confidence=", signal.confidence,
      " lot=", DoubleToString(lot, 2),
      " result=", filled ? "EXECUTED" : "REJECTED",
      " retcode=", result.retcode,
      " reason=", result.comment);
   return filled;
}


bool ExecuteSignal()
{
   RiriSignal signal;
   if(!GetSignal(signal)) return false;
   double lot=0;string reason="";
   if(!RIRI_ValidateSignal(signal,lot,reason))
   {
      ConfirmSignal(signal,"REJECTED",0,0,0,0,0,reason);
      RIRI_FlushAck(signal.signal_id);return false;
   }
   signal.execution_token=StringFormat("%I64d-%I64u-%I64d",(long)TimeGMT(),GetMicrosecondCount(),ChartID());
   string body=StringFormat("{\"signal_id\":\"%s\",\"execution_token\":\"%s\"}",signal.signal_id,signal.execution_token);
   string response;
   if(HttpPost("/execution/authorize",body,response)!=200) return false;
   int lock=RIRI_Lock();
   if(lock==INVALID_HANDLE)
   {
      ConfirmSignal(signal,"REJECTED",0,0,0,0,0,"LOCAL_BROKER_BUSY");
      RIRI_FlushAck(signal.signal_id);return false;
   }
   if(!RIRI_ValidateSignal(signal,lot,reason))
   {
      ConfirmSignal(signal,"REJECTED",0,0,0,0,0,reason);
      FileClose(lock);RIRI_FlushAck(signal.signal_id);return false;
   }
   bool done=RIRI_SendOrder(signal,lot);
   FileClose(lock);
   RIRI_FlushAck(signal.signal_id);
   return done;
}

#endif
