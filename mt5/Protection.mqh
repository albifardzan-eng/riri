#ifndef RIRI_PROTECTION_MQH
#define RIRI_PROTECTION_MQH

#include "CapitalProtection.mqh"

bool RIRI_PortfolioRisk(double candidate_lot,string direction,double &risk)
{
   risk=0;
   for(int i=0;i<PositionsTotal();i++)
   {
      if(PositionGetTicket(i)==0 || !RIRI_SelectedPosition()) continue;
      double stop=PositionGetDouble(POSITION_SL),profit=0;
      if(stop<=0) return false;
      bool buy=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY;
      double now=SymbolInfoDouble(_Symbol,buy?SYMBOL_BID:SYMBOL_ASK);
      if(!OrderCalcProfit(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL,_Symbol,PositionGetDouble(POSITION_VOLUME),now,stop,profit)) return false;
      risk+=MathMax(0,-profit);
   }
   for(int i=0;i<OrdersTotal();i++)
   {
      if(OrderGetTicket(i)==0 || !RIRI_SelectedOrder()) continue;
      double stop=OrderGetDouble(ORDER_SL),profit=0;
      if(stop<=0) return false;
      bool buy=RIRI_IsBuyOrder(OrderGetInteger(ORDER_TYPE));
      if(!OrderCalcProfit(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL,_Symbol,OrderGetDouble(ORDER_VOLUME_CURRENT),OrderGetDouble(ORDER_PRICE_OPEN),stop,profit)) return false;
      risk+=MathMax(0,-profit);
   }
   if(candidate_lot>0)
   {
      bool buy=direction=="BUY";
      double price=SymbolInfoDouble(_Symbol,buy?SYMBOL_ASK:SYMBOL_BID),profit=0;
      double stop=price+(buy?-1:1)*RIRI_SL_POINTS*_Point;
      if(!OrderCalcProfit(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL,_Symbol,candidate_lot,price,stop,profit)) return false;
      risk+=MathMax(0,-profit);
   }
   return true;
}

bool RIRI_RiskCapAllowed(double lot,string direction,double signal_cap)
{
   double cap=RIRI_MAX_SL_RISK_PERCENT;
   if(signal_cap>0) cap=cap>0?MathMin(cap,signal_cap):signal_cap;
   if(cap<=0) return true;
   double risk=0,equity=AccountInfoDouble(ACCOUNT_EQUITY);
   return equity>0 && RIRI_PortfolioRisk(lot,direction,risk) && risk/equity*100<=cap;
}

bool RIRI_CloseTicket(ulong ticket,string reason)
{
   if(!PositionSelectByTicket(ticket) || !RIRI_SelectedPosition()) return false;
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return false;
   string unknown=RIRI_StateKey(StringFormat("close_%I64u",ticket));
   if(GlobalVariableCheck(unknown) && GlobalVariableGet(unknown)>0) return false;
   double before=PositionGetDouble(POSITION_VOLUME);
   bool buy=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY;
   MqlTradeRequest req;MqlTradeResult res;MqlTradeCheckResult check;
   ZeroMemory(req);ZeroMemory(res);ZeroMemory(check);
   req.action=TRADE_ACTION_DEAL;req.position=ticket;req.symbol=_Symbol;req.magic=MAGIC_NUMBER;
   req.type=buy?ORDER_TYPE_SELL:ORDER_TYPE_BUY;req.volume=before;
   req.price=SymbolInfoDouble(_Symbol,buy?SYMBOL_BID:SYMBOL_ASK);
   req.deviation=(ulong)DEFAULT_SLIPPAGE;req.type_filling=RIRI_FillingMode();req.comment="RIRI risk close";
   if(!OrderCheck(req,check)) {Print("[CLOSE] check failed ticket=",ticket," code=",check.retcode);return false;}
   GlobalVariableSet(unknown,(double)TimeGMT());GlobalVariablesFlush();
   bool sent=OrderSend(req,res);
   bool remaining=PositionSelectByTicket(ticket);
   bool confirmed=sent && (res.retcode==TRADE_RETCODE_DONE || res.retcode==TRADE_RETCODE_DONE_PARTIAL);
   bool verified=confirmed && (!remaining || PositionGetDouble(POSITION_VOLUME)<before);
   bool ambiguous=!sent || res.retcode==TRADE_RETCODE_PLACED || res.retcode==TRADE_RETCODE_TIMEOUT || res.retcode==TRADE_RETCODE_CONNECTION || (confirmed && !verified);
   if(!ambiguous) GlobalVariableDel(unknown);
   Print("[CLOSE] ticket=",ticket," reason=",reason," retcode=",res.retcode," verified=",verified," remaining=",remaining);
   return verified;
}

void RIRI_TrailTicket(ulong ticket)
{
   if(RIRI_AI_CAPITAL_PROFILE) {RIRI_CapitalTrail(ticket);return;}
   if(!RIRI_TRAILING_ENABLED || !PositionSelectByTicket(ticket) || !RIRI_SelectedPosition()) return;
   bool buy=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY;
   double entry=PositionGetDouble(POSITION_PRICE_OPEN),old=PositionGetDouble(POSITION_SL);
   double tp=PositionGetDouble(POSITION_TP),volume=PositionGetDouble(POSITION_VOLUME);
   double current=SymbolInfoDouble(_Symbol,buy?SYMBOL_BID:SYMBOL_ASK);
   if((buy?current-entry:entry-current)/_Point<RIRI_TRAILING_START_POINTS) return;
   int handle=iATR(_Symbol,RIRI_TRAILING_TIMEFRAME,ATR_PERIOD);
   if(handle==INVALID_HANDLE) return;
   double buffer[];int copied=CopyBuffer(handle,0,1,1,buffer);IndicatorRelease(handle);
   if(copied!=1 || buffer[0]<=0) return;
   long identifier=PositionGetInteger(POSITION_IDENTIFIER);
   double cost=MathMax(0,-PositionGetDouble(POSITION_SWAP));
   if(!HistorySelectByPosition(identifier)) return;
   // Actual entry charges plus estimated equal exit commission/fee.
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong d=HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(d,DEAL_ENTRY)==DEAL_ENTRY_IN)
         cost+=2*MathMax(0,-HistoryDealGetDouble(d,DEAL_COMMISSION)-HistoryDealGetDouble(d,DEAL_FEE));
   }
   double tick_size=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tick_size<=0) return;
   double unit=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE)*_Point/tick_size*volume;
   if(unit<=0) return;
   double breakeven=entry+(buy?1:-1)*(cost/unit+RIRI_BREAK_EVEN_COST_POINTS)*_Point;
   double proposed=buy?MathMax(breakeven,current-buffer[0]*RIRI_TRAILING_ATR_MULTIPLIER):MathMin(breakeven,current+buffer[0]*RIRI_TRAILING_ATR_MULTIPLIER);
   proposed=NormalizeDouble((buy?MathFloor(proposed/tick_size):MathCeil(proposed/tick_size))*tick_size,_Digits);
   double distance=MathMax(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL),SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL))*_Point;
   if(buy ? current-proposed<=distance || proposed<breakeven : proposed-current<=distance || proposed>breakeven) return;
   if(old>0 && (buy?proposed-old:old-proposed)<RIRI_TRAILING_STEP_POINTS*_Point) return;
   if(old>0 && (buy?current-old:old-current)<=distance) return;
   MqlTradeRequest req;MqlTradeResult res;ZeroMemory(req);ZeroMemory(res);
   req.action=TRADE_ACTION_SLTP;req.position=ticket;req.symbol=_Symbol;req.magic=MAGIC_NUMBER;req.sl=proposed;req.tp=tp;
   bool sent=OrderSend(req,res);
   bool verified=sent && res.retcode==TRADE_RETCODE_DONE && PositionSelectByTicket(ticket) && MathAbs(PositionGetDouble(POSITION_SL)-proposed)<tick_size/2;
   Print("[TRAIL] ticket=",ticket," old=",old," new=",proposed," retcode=",res.retcode," verified=",verified);
}

bool RIRI_HoldValid(ulong ticket,long close_time)
{
   if(RIRI_HOLD_MIN_CONFIDENCE<=0 || !RIRI_RiskCapAllowed(0,"BUY",0)) return false;
   string prefix=RIRI_StateKey(StringFormat("hold_%I64u_",ticket));
   if(!GlobalVariableCheck(prefix+"close") || (long)GlobalVariableGet(prefix+"close")!=close_time) return false;
   if(!PositionSelectByTicket(ticket)) return false;
   if(MathAbs(PositionGetDouble(POSITION_SL)-GlobalVariableGet(prefix+"sl"))>_Point/2) return false;
   if(MathAbs(PositionGetDouble(POSITION_TP)-GlobalVariableGet(prefix+"tp"))>_Point/2) return false;
   return MathAbs(SymbolInfoDouble(_Symbol,SYMBOL_BID)-GlobalVariableGet(prefix+"price"))<=RIRI_GetATR();
}

void RIRI_Protect()
{
   static ulong last=0;
   if(GetTickCount64()-last<1000) return;last=GetTickCount64();
   int lock=RIRI_Lock();if(lock==INVALID_HANDLE) return;
   long close_time,next_open;bool weekly;
   bool session=RIRI_Session(close_time,next_open,weekly);
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !RIRI_SelectedPosition()) continue;
      bool deadline=RIRI_PRECLOSE_ENABLED && session && close_time-(long)TimeTradeServer()<=(weekly?900:300);
      if(deadline && (weekly || !RIRI_HoldValid(ticket,close_time)))
         RIRI_CloseTicket(ticket,weekly?"WEEKLY_DEADLINE":"DAILY_DEADLINE_NO_VALID_HOLD");
      else RIRI_TrailTicket(ticket);
   }
   FileClose(lock);
}

void RIRI_ReviewPositions()
{
   static ulong last_review=0;
   if(RIRI_AI_CAPITAL_PROFILE && GetTickCount64()-last_review<60000) return;
   double lot=0;if(RIRI_PositionCount(lot)==0) return;
   last_review=GetTickCount64();
   string response;
   if(HttpPost("/positions/review",BuildMarketJson(),response)!=200 || StringFind(response,"\"review\":null")>=0) return;
   ulong ticket=(ulong)RIRI_JsonNumber(response,"ticket");
   long expiry=(long)RIRI_JsonNumber(response,"expires_at_epoch");
   if(ticket==0 || (long)TimeGMT()>expiry || !PositionSelectByTicket(ticket) || !RIRI_SelectedPosition()) return;
   if(MathAbs(PositionGetDouble(POSITION_SL)-RIRI_JsonNumber(response,"active_sl"))>_Point/2 ||
      MathAbs(PositionGetDouble(POSITION_TP)-RIRI_JsonNumber(response,"active_tp"))>_Point/2 ||
      MathAbs(PositionGetDouble(POSITION_VOLUME)-RIRI_JsonNumber(response,"position_lot"))>0.000001) return;
   Print("[REVIEW] ticket=",ticket," decision=",RIRI_JsonString(response,"decision")," status=",RIRI_JsonString(response,"status"));
   int lock=RIRI_Lock();if(lock==INVALID_HANDLE) return;
   if(RIRI_REVIEW_EXECUTE && RIRI_JsonBool(response,"execute_close")) RIRI_CloseTicket(ticket,"AI_REVIEW");
   long session_close=(long)RIRI_JsonNumber(response,"hold_session_close");
   if(RIRI_REVIEW_EXECUTE && session_close>0 && RIRI_HOLD_MIN_CONFIDENCE>0 && RIRI_JsonNumber(response,"confidence")>=RIRI_HOLD_MIN_CONFIDENCE)
   {
      string prefix=RIRI_StateKey(StringFormat("hold_%I64u_",ticket));
      GlobalVariableSet(prefix+"close",(double)session_close);
      GlobalVariableSet(prefix+"sl",PositionGetDouble(POSITION_SL));
      GlobalVariableSet(prefix+"tp",PositionGetDouble(POSITION_TP));
      GlobalVariableSet(prefix+"price",SymbolInfoDouble(_Symbol,SYMBOL_BID));GlobalVariablesFlush();
   }
   FileClose(lock);
}
#endif
