#ifndef __RIRI_UTILS_MQH__
#define __RIRI_UTILS_MQH__

void Log(string message)
{
   Print("[RIRI] ", message);
}


double CurrentSpread()
{
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0)
      return 1.0e100;
   return (
      SymbolInfoDouble(_Symbol, SYMBOL_ASK) -
      SymbolInfoDouble(_Symbol, SYMBOL_BID)
   ) / point;
}


void PrintAccountInfo()
{
   Print(
      "Balance=", AccountInfoDouble(ACCOUNT_BALANCE),
      " Equity=", AccountInfoDouble(ACCOUNT_EQUITY),
      " Margin=", AccountInfoDouble(ACCOUNT_MARGIN_FREE)
   );
}


void PrintStartup()
{
   Print("==============================");
   Print(EA_NAME, " ", EA_VERSION);
   Print("Symbol  : ", _Symbol);
   Print("Server  : ", AccountInfoString(ACCOUNT_SERVER));
   Print("Account : ", AccountInfoInteger(ACCOUNT_LOGIN));
   Print("==============================");
}

#endif
