#ifndef RIRI_CAPITAL_PROTECTION_MQH
#define RIRI_CAPITAL_PROTECTION_MQH

bool RIRI_CapitalSignalAllowed(const RiriSignal &s,string &reason)
{
   if(s.initial_score<RIRI_CAPITAL_MIN_SCORE || s.confidence<RIRI_CAPITAL_MIN_CONFIDENCE)
   {reason="CAPITAL_HIGH_CONFIDENCE_REQUIRED";return false;}
   double active=0,pending=0;
   if(RIRI_PositionCount(active)+RIRI_PendingCount(pending)>0)
   {reason="CAPITAL_SINGLE_POSITION";return false;}
   int cost=(int)MathMax(RIRI_CAPITAL_COST_BUFFER_POINTS,s.cost_buffer_points);
   double spread=CurrentSpread();
   double floor=MathMax((double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)+spread+1,
      MathMax(RIRI_GetATR()/_Point*.5,MathMax(spread*3,cost)));
   if(s.sl_points<floor || s.tp_points<floor ||
      (double)(s.tp_points-cost)/(s.sl_points+cost)<RIRI_CAPITAL_MIN_REWARD_RISK ||
      s.trailing_start_points<=cost || s.trailing_start_points>=s.tp_points ||
      s.trailing_distance_points<=0 || s.trailing_distance_points>=s.trailing_start_points ||
      s.trailing_step_points<=0 || s.trailing_step_points>s.trailing_distance_points)
   {reason="AI_PROTECTION_PLAN_INVALID";return false;}
   if(spread>30 || s.max_sl_risk_percent<=0)
   {reason="CAPITAL_SPREAD_OR_RISK_INVALID";return false;}
   bool buy=s.action=="BUY";
   double price=SymbolInfoDouble(_Symbol,buy?SYMBOL_ASK:SYMBOL_BID),profit=0;
   // Include configured cost reserve and allowed entry slippage in sizing.
   double stop=price+(buy?-1:1)*(s.sl_points+cost+DEFAULT_SLIPPAGE)*_Point;
   if(!OrderCalcProfit(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL,_Symbol,s.lot,price,stop,profit))
   {reason="BROKER_RISK_UNKNOWN";return false;}
   double cap=MathMin(RIRI_CAPITAL_RISK_PERCENT,s.max_sl_risk_percent);
   if(-profit>AccountInfoDouble(ACCOUNT_EQUITY)*cap/100 || profit>=0)
   {reason="CAPITAL_RISK_BUDGET_EXCEEDED";return false;}
   return true;
}

// Durable write before submission: recovery also covers an ambiguous broker ack.
// Single-position policy and bounded broker-clock window prevent legacy binding.
void RIRI_SaveCapitalPlan(const RiriSignal &s)
{
   string p=RIRI_StateKey("aip_");
   GlobalVariableSet(p+"time",(double)TimeTradeServer());
   GlobalVariableSet(p+"buy",s.action=="BUY"?1:0);
   GlobalVariableSet(p+"start",s.trailing_start_points);
   GlobalVariableSet(p+"distance",s.trailing_distance_points);
   GlobalVariableSet(p+"step",s.trailing_step_points);
   GlobalVariableSet(p+"cost",MathMax(RIRI_CAPITAL_COST_BUFFER_POINTS,s.cost_buffer_points));
   GlobalVariablesFlush();
}

bool RIRI_BindCapitalPlan(ulong ticket,string &p)
{
   if(!PositionSelectByTicket(ticket) || !RIRI_SelectedPosition()) return false;
   long identifier=PositionGetInteger(POSITION_IDENTIFIER);
   p=RIRI_StateKey(StringFormat("a%I64d_",identifier));
   if(GlobalVariableCheck(p+"ready") && GlobalVariableGet(p+"ready")==1) return true;
   string source=RIRI_StateKey("aip_");
   if(!GlobalVariableCheck(source+"time")) return false;
   long sent=(long)GlobalVariableGet(source+"time"),opened=PositionGetInteger(POSITION_TIME);
   bool buy=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY;
   if(opened<sent || opened>sent+60 || (buy?1:0)!=(int)GlobalVariableGet(source+"buy")) return false;
   GlobalVariableSet(p+"start",GlobalVariableGet(source+"start"));
   GlobalVariableSet(p+"distance",GlobalVariableGet(source+"distance"));
   GlobalVariableSet(p+"step",GlobalVariableGet(source+"step"));
   GlobalVariableSet(p+"cost",GlobalVariableGet(source+"cost"));
   GlobalVariablesFlush();
   GlobalVariableSet(p+"ready",1);GlobalVariablesFlush();
   return true;
}

void RIRI_CapitalTrail(ulong ticket)
{
   string p;if(!RIRI_BindCapitalPlan(ticket,p)) return;
   double start=GlobalVariableGet(p+"start"),gap=GlobalVariableGet(p+"distance");
   double step=GlobalVariableGet(p+"step"),buffer=GlobalVariableGet(p+"cost");
   if(start<=0 || gap<=0 || step<=0 || gap>=start || buffer<=0) return;
   bool buy=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY;
   double entry=PositionGetDouble(POSITION_PRICE_OPEN),old=PositionGetDouble(POSITION_SL);
   double tp=PositionGetDouble(POSITION_TP),volume=PositionGetDouble(POSITION_VOLUME);
   double current=SymbolInfoDouble(_Symbol,buy?SYMBOL_BID:SYMBOL_ASK);
   MqlTick tick;
   if(old<=0 || tp<=0 || !SymbolInfoTick(_Symbol,tick) || TimeTradeServer()-tick.time>10) return;
   if((buy?current-entry:entry-current)/_Point<start) return;
   long identifier=PositionGetInteger(POSITION_IDENTIFIER);
   double cost=MathMax(0,-PositionGetDouble(POSITION_SWAP));
   if(!HistorySelectByPosition(identifier)) return;
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong deal=HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(deal,DEAL_ENTRY)==DEAL_ENTRY_IN)
         cost+=2*MathMax(0,-HistoryDealGetDouble(deal,DEAL_COMMISSION)-HistoryDealGetDouble(deal,DEAL_FEE));
   }
   double size=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double value=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   if(size<=0 || value<=0 || volume<=0) return;
   double cost_points=cost/(value*_Point/size*volume)+buffer;
   double breakeven=entry+(buy?1:-1)*cost_points*_Point;
   double proposed=buy?MathMax(breakeven,current-gap*_Point):MathMin(breakeven,current+gap*_Point);
   proposed=NormalizeDouble((buy?MathFloor(proposed/size):MathCeil(proposed/size))*size,_Digits);
   double minimum=MathMax(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL),SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL))*_Point;
   if(buy?(current-proposed<=minimum || proposed<breakeven || proposed-old<step*_Point || current-old<=minimum):
          (proposed-current<=minimum || proposed>breakeven || old-proposed<step*_Point || old-current<=minimum)) return;
   MqlTradeRequest req;MqlTradeResult res;ZeroMemory(req);ZeroMemory(res);
   req.action=TRADE_ACTION_SLTP;req.position=ticket;req.symbol=_Symbol;req.magic=MAGIC_NUMBER;
   req.sl=proposed;req.tp=tp;
   bool sent=OrderSend(req,res);
   bool verified=sent && res.retcode==TRADE_RETCODE_DONE && PositionSelectByTicket(ticket) &&
      MathAbs(PositionGetDouble(POSITION_SL)-proposed)<size/2;
   Print("[AI_TRAIL] ticket=",ticket," old=",old," new=",proposed," verified=",verified," retcode=",res.retcode);
}
#endif
