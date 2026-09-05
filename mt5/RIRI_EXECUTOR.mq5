#property strict

#include "Config.mqh"
#include "Market.mqh"
#include "Http.mqh"
#include "Trading.mqh"
#include "Utils.mqh"


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

      ReportTradeClose(
         trans.deal
      );
   }
}


//==================================================
// TESTER
//==================================================

double OnTester()
{
   return 0;
}
