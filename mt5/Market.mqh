#ifndef RIRI_MARKET_MQH
#define RIRI_MARKET_MQH

#include "Fundamental.mqh"


string RIRI_TimeframeName()
{
   string value = EnumToString(CANDLE_TIMEFRAME);
   StringReplace(value, "PERIOD_", "");
   return value;
}


double RIRI_GetATR()
{
   int handle = iATR(_Symbol, CANDLE_TIMEFRAME, ATR_PERIOD);
   if(handle == INVALID_HANDLE)
      return 0.0;

   double buffer[];
   ArraySetAsSeries(buffer, true);
   int copied = CopyBuffer(handle, 0, 1, 1, buffer);
   IndicatorRelease(handle);
   return copied == 1 ? buffer[0] : 0.0;
}


string BuildCandlesJson()
{
   MqlRates rates[];
   // Closed candles only. Live bid/ask and current tick volume are sent separately.
   int copied = CopyRates(_Symbol, CANDLE_TIMEFRAME, 1, MAX_CANDLES, rates);
   if(copied < 100)
      return "[]";

   ArraySetAsSeries(rates, true);
   string json = "[";
   for(int i = copied - 1; i >= 0; i--)
   {
      json += StringFormat(
         "{\"time\":%I64d,\"open\":%.5f,\"high\":%.5f,"
         "\"low\":%.5f,\"close\":%.5f,\"volume\":%I64d}",
         (long)rates[i].time, rates[i].open, rates[i].high,
         rates[i].low, rates[i].close, (long)rates[i].tick_volume
      );
      if(i > 0)
         json += ",";
   }
   return json + "]";
}


double GetTickVolume()
{
   MqlRates rates[];
   return CopyRates(_Symbol, CANDLE_TIMEFRAME, 0, 1, rates) == 1
      ? (double)rates[0].tick_volume
      : 0.0;
}


string BuildPositionsJson()
{
   string json = "[";
   bool first = true;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if(!first)
         json += ",";
      first = false;
      long position_type = PositionGetInteger(POSITION_TYPE);
      string type = position_type == POSITION_TYPE_BUY ? "BUY" : "SELL";
      json += StringFormat(
         "{\"ticket\":%I64u,\"symbol\":\"%s\",\"type\":\"%s\","
         "\"lot\":%.2f,\"profit\":%.2f,\"open_time\":%I64d,"
         "\"open_price\":%.5f,\"sl\":%.5f,\"tp\":%.5f,\"magic_number\":%I64d}",
         ticket, _Symbol, type,
         PositionGetDouble(POSITION_VOLUME), PositionGetDouble(POSITION_PROFIT),
         PositionGetInteger(POSITION_TIME), PositionGetDouble(POSITION_PRICE_OPEN),
         PositionGetDouble(POSITION_SL), PositionGetDouble(POSITION_TP),
         PositionGetInteger(POSITION_MAGIC)
      );
   }
   return json + "]";
}


string BuildMarketJson()
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double spread = point > 0 ? (ask - bid) / point : 0.0;
   long account = AccountInfoInteger(ACCOUNT_LOGIN);
   string terminal = FundamentalJsonSafeString(AccountInfoString(ACCOUNT_SERVER));

   string json = "{";
   json += StringFormat("\"symbol\":\"%s\",", _Symbol);
   json += StringFormat("\"timeframe\":\"%s\",", RIRI_TimeframeName());
   json += StringFormat("\"market_time\":%I64d,", (long)TimeGMT());
   json += StringFormat("\"account_id\":\"%I64d\",", account);
   json += StringFormat("\"terminal_id\":\"%s\",", terminal);
   json += StringFormat("\"instance_id\":\"%s\",", FundamentalJsonSafeString(RIRI_INSTANCE_ID));
   json += StringFormat("\"bid\":%.5f,\"ask\":%.5f,\"spread\":%.1f,", bid, ask, spread);
   json += StringFormat("\"point\":%.10f,\"digits\":%d,", point, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS));
   json += StringFormat("\"tick_size\":%.10f,\"tick_value\":%.5f,", tick_size, tick_value);
   json += StringFormat("\"balance\":%.2f,\"equity\":%.2f,\"free_margin\":%.2f,",
      AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY),
      AccountInfoDouble(ACCOUNT_MARGIN_FREE));
   json += StringFormat("\"tick_volume\":%.0f,\"atr\":%.5f,", GetTickVolume(), RIRI_GetATR());
   json += "\"candles\":" + BuildCandlesJson() + ",";
   json += "\"positions\":" + BuildPositionsJson() + ",";
   json += "\"fundamental\":" + GetFundamentalEventJson();
   return json + "}";
}

#endif
