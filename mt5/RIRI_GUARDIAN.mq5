#property strict
// Attach to a separate XAUUSD chart in the SAME terminal as RIRI_EXECUTOR.
// Independent event queue: no HTTP/AI calls while supervising protection.
#include "Config.mqh"
#include "Market.mqh"
#include "Http.mqh"
#include "Trading.mqh"
#include "Utils.mqh"
#include "Protection.mqh"

int OnInit()
{
   if(_Symbol!=RIRI_SYMBOL || AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
      return INIT_PARAMETERS_INCORRECT;
   if(RIRI_AI_CAPITAL_PROFILE && (RIRI_CAPITAL_MIN_SCORE<81 || RIRI_CAPITAL_MIN_SCORE>100 ||
      RIRI_CAPITAL_MIN_CONFIDENCE<86 || RIRI_CAPITAL_MIN_CONFIDENCE>100 ||
      RIRI_CAPITAL_RISK_PERCENT<=0 || RIRI_CAPITAL_RISK_PERCENT>2 ||
      RIRI_CAPITAL_MIN_REWARD_RISK<1 || RIRI_CAPITAL_COST_BUFFER_POINTS<1))
      return INIT_PARAMETERS_INCORRECT;
   if(RIRI_TRAILING_ENABLED && (RIRI_TRAILING_START_POINTS<=0 || RIRI_TRAILING_STEP_POINTS<=0 ||
      RIRI_TRAILING_ATR_MULTIPLIER<=0 || RIRI_BREAK_EVEN_COST_POINTS<0)) return INIT_PARAMETERS_INCORRECT;
   if(!EventSetTimer(1)) return INIT_FAILED;
   Print("[GUARDIAN] Independent protection active; trailing=",RIRI_TRAILING_ENABLED," preclose=",RIRI_PRECLOSE_ENABLED);
   return INIT_SUCCEEDED;
}
void OnTick() {RIRI_Protect();}
void OnTimer() {RIRI_Protect();}
void OnDeinit(const int reason) {EventKillTimer();}
void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
{
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal,DEAL_SYMBOL)!=RIRI_SYMBOL || HistoryDealGetInteger(trans.deal,DEAL_MAGIC)!=MAGIC_NUMBER) return;
   long entry=HistoryDealGetInteger(trans.deal,DEAL_ENTRY);
   if(entry==DEAL_ENTRY_IN) RIRI_RecordEntry(HistoryDealGetInteger(trans.deal,DEAL_TIME));
   if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY)
      GlobalVariableDel(RIRI_StateKey(StringFormat("close_%I64u",trans.position)));
}
