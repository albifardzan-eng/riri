#ifndef __RIRI_TRADING_MQH__
#define __RIRI_TRADING_MQH__


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
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      count++;
      total_lot += PositionGetDouble(POSITION_VOLUME);
   }
   return count;
}


long RIRI_LatestPositionTime()
{
   long latest = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      long opened = PositionGetInteger(POSITION_TIME);
      if(opened > latest)
         latest = opened;
   }
   return latest;
}


bool RIRI_PositionPolicy(string action, string &reason)
{
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      long type = PositionGetInteger(POSITION_TYPE);
      string existing = type == POSITION_TYPE_BUY ? "BUY" : "SELL";
      if(existing != action)
      {
         reason = "HEDGING_FORBIDDEN";
         return false;
      }
      if(PositionGetDouble(POSITION_PROFIT) < 0)
      {
         reason = "AVERAGING_FORBIDDEN";
         return false;
      }
   }
   return true;
}


bool RIRI_ValidateSignal(const RiriSignal &signal, double &lot, string &reason)
{
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
   if(CurrentSpread() > RIRI_MAX_SPREAD)
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
      !AccountInfoInteger(ACCOUNT_TRADE_ALLOWED))
   {
      reason = "TRADING_NOT_ALLOWED";
      return false;
   }

   double active_lot = 0.0;
   int active = RIRI_PositionCount(active_lot);
   if(active >= RIRI_MAX_ACTIVE_TRADES)
   {
      reason = "MAX_ACTIVE_TRADES";
      return false;
   }
   long latest_open = RIRI_LatestPositionTime();
   if(latest_open > 0 && (long)TimeCurrent() - latest_open < 30 * 60)
   {
      reason = "MIN_ENTRY_INTERVAL";
      return false;
   }
   if(!RIRI_PositionPolicy(signal.action, reason))
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

   bool sent = OrderSend(request, result);
   bool filled = sent && (result.retcode == TRADE_RETCODE_DONE ||
      result.retcode == TRADE_RETCODE_DONE_PARTIAL);
   ConfirmSignal(
      signal,
      filled ? "EXECUTED" : "REJECTED",
      result.order,
      result.deal,
      filled ? result.volume : 0.0,
      result.price,
      result.retcode,
      result.comment
   );
   Print("[EXECUTION] signal=", signal.signal_id,
      " action=", signal.action,
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
   if(!GetSignal(signal))
      return false;

   double lot = 0.0;
   string reason = "";
   if(!RIRI_ValidateSignal(signal, lot, reason))
   {
      Print("[EXECUTION] rejected signal=", signal.signal_id,
         " action=", signal.action,
         " confidence=", signal.confidence,
         " requested_lot=", DoubleToString(signal.lot, 2),
         " reason=", reason);
      ConfirmSignal(signal, "REJECTED", 0, 0, 0, 0, 0, reason);
      return false;
   }
   return RIRI_SendOrder(signal, lot);
}

#endif
