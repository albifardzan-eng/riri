#property strict

#include "Config.mqh"
#include "Market.mqh"
#include "Http.mqh"
#include "Trading.mqh"
#include "Utils.mqh"
#include "Protection.mqh"


//==================================================
// INIT
//==================================================

int OnInit()
{
   PrintStartup();

   if(_Symbol != RIRI_SYMBOL)
   {
      Print("[INIT] RIRI v1 supports XAUUSD only. Current=", _Symbol);
      return INIT_FAILED;
   }

   if(
      StringLen(RIRI_API_KEY) < 32 ||
      RIRI_INSTANCE_ID == "" ||
      StringFind(RIRI_INSTANCE_ID, "\r") >= 0 ||
      StringFind(RIRI_INSTANCE_ID, "\n") >= 0 ||
      StringFind(API_URL, "https://") != 0 ||
      MAX_CANDLES < 100 ||
      MAX_CANDLES > 500 ||
      TIMER_SECONDS < 5
   )
   {
      Print("[INIT] Invalid API key, HTTPS URL, instance, candle count, or timer.");
      return INIT_PARAMETERS_INCORRECT;
   }

   if(RIRI_AI_CAPITAL_PROFILE && (RIRI_CAPITAL_MIN_SCORE<81 || RIRI_CAPITAL_MIN_SCORE>100 ||
      RIRI_CAPITAL_MIN_CONFIDENCE<86 || RIRI_CAPITAL_MIN_CONFIDENCE>100 ||
      RIRI_CAPITAL_RISK_PERCENT<=0 || RIRI_CAPITAL_RISK_PERCENT>2 ||
      RIRI_CAPITAL_MIN_REWARD_RISK<1 || RIRI_CAPITAL_COST_BUFFER_POINTS<1))
      return INIT_PARAMETERS_INCORRECT;
   if(RIRI_TRAILING_ENABLED && (RIRI_TRAILING_START_POINTS<=0 || RIRI_TRAILING_STEP_POINTS<=0 ||
      RIRI_TRAILING_ATR_MULTIPLIER<=0 || RIRI_BREAK_EVEN_COST_POINTS<0))
      return INIT_PARAMETERS_INCORRECT;
   if(RIRI_ReconcileEntry()<0) Print("[INIT] Entry history unavailable; entries will fail closed.");
   if(!EventSetTimer(TIMER_SECONDS))
      return INIT_FAILED;

   Log(
      "Executor Started"
   );

   return INIT_SUCCEEDED;
}


//==================================================
// DEINIT
//==================================================

void OnDeinit(
   const int reason
)
{
   EventKillTimer();

   Log(
      "Executor Stopped"
   );
}


//==================================================
// TIMER
//==================================================

void OnTimer()
{
   ProcessCycle();
}


//==================================================
// MAIN LOOP
//==================================================

void ProcessCycle()
{
   static bool running =
      false;

   if(
      running
   )
   {
      return;
   }

   running =
      true;


   //================================================
   // ACCOUNT
   //================================================

   PrintAccountInfo();


   //================================================
   // SEND MARKET
   //================================================

   RIRI_Protect();
   RIRI_ReviewPositions();
   RIRI_Protect();
   bool marketSent =
      SendMarket();


   if(
      !marketSent
   )
   {
      Log(
         "Failed to send market data."
      );

      running =
         false;

      return;
   }


   //================================================
   // GET / EXECUTE SIGNAL
   //================================================

   ExecuteSignal();


   running =
      false;
}


//==================================================
// TICK
//
// Not used.
//==================================================

void OnTick()
{
   RIRI_Protect();
}


//==================================================
// TRADE
//==================================================

void OnTrade()
{
   Log(
      "Trade Event"
   );
}


//==================================================
// TRADE TRANSACTION
//==================================================

void OnTradeTransaction(
   const MqlTradeTransaction &trans,
   const MqlTradeRequest &request,
   const MqlTradeResult &result
)
{
   if(
      trans.type ==
      TRADE_TRANSACTION_DEAL_ADD
   )
   {
      Log(
         "Deal Executed"
      );

      if(HistoryDealSelect(trans.deal) && HistoryDealGetString(trans.deal,DEAL_SYMBOL)==RIRI_SYMBOL &&
         HistoryDealGetInteger(trans.deal,DEAL_MAGIC)==MAGIC_NUMBER &&
         HistoryDealGetInteger(trans.deal,DEAL_ENTRY)==DEAL_ENTRY_IN)
         RIRI_RecordEntry(HistoryDealGetInteger(trans.deal,DEAL_TIME));
      if(HistoryDealSelect(trans.deal) && HistoryDealGetString(trans.deal,DEAL_SYMBOL)==RIRI_SYMBOL &&
         HistoryDealGetInteger(trans.deal,DEAL_MAGIC)==MAGIC_NUMBER &&
         (HistoryDealGetInteger(trans.deal,DEAL_ENTRY)==DEAL_ENTRY_OUT || HistoryDealGetInteger(trans.deal,DEAL_ENTRY)==DEAL_ENTRY_OUT_BY))
         GlobalVariableDel(RIRI_StateKey(StringFormat("close_%I64u",trans.position)));
      ReportTradeClose(trans.deal);
   }
}


//==================================================
// TESTER
//==================================================

double OnTester()
{
   return 0;
}
