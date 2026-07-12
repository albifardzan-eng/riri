#property strict

input string API_URL = "https://api-riri.albiagent.com";

int OnInit()
{
   EventSetTimer(10);

   Print("RIRI Executor Started");

   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   SendMarketData();

   CheckSignal();
}

void SendMarketData()
{
   double balance =
      AccountInfoDouble(
         ACCOUNT_BALANCE
      );

   double equity =
      AccountInfoDouble(
         ACCOUNT_EQUITY
      );

   double free_margin =
      AccountInfoDouble(
         ACCOUNT_MARGIN_FREE
      );

   string candles = "[";

   MqlRates rates[];

   int copied =
      CopyRates(
         _Symbol,
         PERIOD_H1,
         0,
         120,
         rates
      );

   if(copied > 0)
   {
      ArraySetAsSeries(
         rates,
         true
      );

      for(
         int i = copied - 1;
         i >= 0;
         i--
      )
      {
         candles +=
            StringFormat(
               "{"
               "\"open\":%.2f,"
               "\"high\":%.2f,"
               "\"low\":%.2f,"
               "\"close\":%.2f,"
               "\"volume\":%.0f"
               "}",
               rates[i].open,
               rates[i].high,
               rates[i].low,
               rates[i].close,
               (double)rates[i].tick_volume
            );

         if(i > 0)
            candles += ",";
      }
   }

   candles += "]";

   string body =
      StringFormat(
         "{"
         "\"symbol\":\"XAUUSD\","
         "\"bid\":%.2f,"
         "\"ask\":%.2f,"
         "\"spread\":%.2f,"
         "\"balance\":%.2f,"
         "\"equity\":%.2f,"
         "\"free_margin\":%.2f,"
         "\"tick_volume\":100,"
         "\"atr\":10,"
         "\"candles\":%s,"
         "\"positions\":[]"
         "}",
         SymbolInfoDouble(
            _Symbol,
            SYMBOL_BID
         ),
         SymbolInfoDouble(
            _Symbol,
            SYMBOL_ASK
         ),
         (double)SymbolInfoInteger(
            _Symbol,
            SYMBOL_SPREAD
         ),
         balance,
         equity,
         free_margin,
         candles
      );

   string headers =
      "Content-Type: application/json\r\n";

   char post[];
   char result[];

   ArrayResize(
      post,
      StringLen(body)
   );

   StringToCharArray(
      body,
      post,
      0,
      StringLen(body)
   );

   string response_headers;

   ResetLastError();

   int code =
      WebRequest(
         "POST",
         API_URL + "/mt5/market",
         headers,
         5000,
         post,
         result,
         response_headers
      );

   Print(
      "Market POST: ",
      code,
      " Error=",
      GetLastError()
   );

   Print(
      "Response: ",
      CharArrayToString(
         result
      )
   );
}

void CheckSignal()
{
   char result[];
   char post[];

   string response_headers;

   ResetLastError();

   int code =
      WebRequest(
         "GET",
         API_URL +
         "/execution/pending",
         "",
         5000,
         post,
         result,
         response_headers
      );

   if(code != 200)
      return;

   string json =
      CharArrayToString(
         result
      );

   Print(
      "Signal: ",
      json
   );

   if(
      StringFind(
         json,
         "\"action\":\"BUY\""
      ) != -1
   )
   {
      ExecuteBuy();
   }

   if(
      StringFind(
         json,
         "\"action\":\"SELL\""
      ) != -1
   )
   {
      ExecuteSell();
   }
}

void ExecuteBuy()
{
   MqlTradeRequest req;
   MqlTradeResult res;

   ZeroMemory(req);
   ZeroMemory(res);

   req.action =
      TRADE_ACTION_DEAL;

   req.symbol =
      _Symbol;

   req.volume =
      0.01;

   req.type =
      ORDER_TYPE_BUY;

   req.price =
      SymbolInfoDouble(
         _Symbol,
         SYMBOL_ASK
      );

   bool ok =
      OrderSend(
         req,
         res
      );

   Print(
      "BUY Result=",
      ok,
      " Retcode=",
      res.retcode
   );

   if(ok)
   {
      ConfirmExecution(
         "BUY"
      );
   }
}

void ExecuteSell()
{
   MqlTradeRequest req;
   MqlTradeResult res;

   ZeroMemory(req);
   ZeroMemory(res);

   req.action =
      TRADE_ACTION_DEAL;

   req.symbol =
      _Symbol;

   req.volume =
      0.01;

   req.type =
      ORDER_TYPE_SELL;

   req.price =
      SymbolInfoDouble(
         _Symbol,
         SYMBOL_BID
      );

   bool ok =
      OrderSend(
         req,
         res
      );

   Print(
      "SELL Result=",
      ok,
      " Retcode=",
      res.retcode
   );

   if(ok)
   {
      ConfirmExecution(
         "SELL"
      );
   }
}

void ConfirmExecution(
   string action
)
{
   string body =
      StringFormat(
         "{\"action\":\"%s\"}",
         action
      );

   string headers =
      "Content-Type: application/json\r\n";

   char post[];
   char result[];

   ArrayResize(
      post,
      StringLen(body)
   );

   StringToCharArray(
      body,
      post,
      0,
      StringLen(body)
   );

   string response_headers;

   ResetLastError();

   int code =
      WebRequest(
         "POST",
         API_URL +
         "/execution/confirm",
         headers,
         5000,
         post,
         result,
         response_headers
      );

   Print(
      "Confirm POST: ",
      code,
      " Error=",
      GetLastError()
   );

   Print(
      "Confirm Response: ",
      CharArrayToString(
         result
      )
   );
}