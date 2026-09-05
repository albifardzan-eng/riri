#ifndef RIRI_HTTP_MQH
#define RIRI_HTTP_MQH


struct RiriSignal
{
   string signal_id;
   string symbol;
   string action;
   double lot;
   int tp_points;
   int sl_points;
   int confidence;
   long market_time;
   long expires_at;
};


string RIRI_AuthHeaders()
{
   return StringFormat(
      "Content-Type: application/json\r\n"
      "X-RIRI-API-Key: %s\r\n"
      "X-RIRI-Account-ID: %I64d\r\n"
      "X-RIRI-Terminal-ID: %s\r\n"
      "X-RIRI-Instance-ID: %s\r\n",
      RIRI_API_KEY,
      AccountInfoInteger(ACCOUNT_LOGIN),
      AccountInfoString(ACCOUNT_SERVER),
      RIRI_INSTANCE_ID
   );
}


int RIRI_Request(string method, string endpoint, string body, string &response)
{
   response = "";
   char data[];
   char result[];
   if(body != "")
   {
      StringToCharArray(body, data, 0, -1, CP_UTF8);
      if(ArraySize(data) > 0 && data[ArraySize(data) - 1] == 0)
         ArrayResize(data, ArraySize(data) - 1);
   }
   else
      ArrayResize(data, 0);

   string response_headers;
   ResetLastError();
   int code = WebRequest(
      method,
      API_URL + endpoint,
      RIRI_AuthHeaders(),
      REQUEST_TIMEOUT,
      data,
      result,
      response_headers
   );
   response = CharArrayToString(result, 0, -1, CP_UTF8);
   if(code < 200 || code >= 300)
      Print("[HTTP] ", method, " ", endpoint, " code=", code,
         " error=", GetLastError(), " response=", response);
   return code;
}


int HttpPost(string endpoint, string body, string &response)
{
   return RIRI_Request("POST", endpoint, body, response);
}


int HttpGet(string endpoint, string &response)
{
   return RIRI_Request("GET", endpoint, "", response);
}


string RIRI_JsonString(string json, string key)
{
   string token = "\"" + key + "\":\"";
   int start = StringFind(json, token);
   if(start < 0)
      return "";
   start += StringLen(token);
   int finish = StringFind(json, "\"", start);
   return finish > start ? StringSubstr(json, start, finish - start) : "";
}


double RIRI_JsonNumber(string json, string key, double fallback = 0.0)
{
   string token = "\"" + key + "\":";
   int start = StringFind(json, token);
   if(start < 0)
      return fallback;
   start += StringLen(token);
   int finish = start;
   while(finish < StringLen(json))
   {
      ushort c = StringGetCharacter(json, finish);
      if(c == ',' || c == '}' || c == ']')
         break;
      finish++;
   }
   return finish > start ? StringToDouble(StringSubstr(json, start, finish - start)) : fallback;
}


bool SendMarket()
{
   string response;
   int code = HttpPost(MARKET_ENDPOINT, BuildMarketJson(), response);
   return code >= 200 && code < 300;
}


bool GetSignal(RiriSignal &signal)
{
   ZeroMemory(signal);
   string response;
   int code = HttpGet(SIGNAL_ENDPOINT, response);
   if(code != 200 || StringFind(response, "\"signal\":null") >= 0)
      return false;

   signal.signal_id = RIRI_JsonString(response, "signal_id");
   signal.symbol = RIRI_JsonString(response, "symbol");
   signal.action = RIRI_JsonString(response, "action");
   signal.lot = RIRI_JsonNumber(response, "lot");
   signal.tp_points = (int)RIRI_JsonNumber(response, "tp_points");
   signal.sl_points = (int)RIRI_JsonNumber(response, "sl_points");
   signal.confidence = (int)RIRI_JsonNumber(response, "confidence");
   signal.market_time = (long)RIRI_JsonNumber(response, "market_time");
   signal.expires_at = (long)RIRI_JsonNumber(response, "expires_at_epoch");

   return signal.signal_id != "" && signal.action != "";
}


bool ConfirmSignal(
   const RiriSignal &signal,
   string status,
   ulong order_id,
   ulong deal_id,
   double filled_lot,
   double executed_price,
   uint retcode,
   string reason
)
{
   string body = StringFormat(
      "{\"signal_id\":\"%s\",\"status\":\"%s\",\"action\":\"%s\","
      "\"order_id\":%I64u,\"deal_id\":%I64u,\"requested_lot\":%.2f,"
      "\"filled_lot\":%.2f,\"executed_price\":%.5f,\"retcode\":%u,\"reason\":\"%s\"}",
      signal.signal_id, status, signal.action, order_id, deal_id,
      signal.lot, filled_lot, executed_price, retcode,
      FundamentalJsonSafeString(reason)
   );
   string response;
   int code = HttpPost(CONFIRM_ENDPOINT, body, response);
   return code >= 200 && code < 300;
}


bool ReportTradeClose(ulong deal_id)
{
   if(deal_id == 0 || !HistoryDealSelect(deal_id))
      return false;

   long entry = HistoryDealGetInteger(deal_id, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
      return false;

   string symbol = HistoryDealGetString(deal_id, DEAL_SYMBOL);
   if(symbol != RIRI_SYMBOL)
      return false;

   long deal_type = HistoryDealGetInteger(deal_id, DEAL_TYPE);
   string side = deal_type == DEAL_TYPE_BUY ? "BUY" : "SELL";
   string body = StringFormat(
      "{\"status\":\"CLOSED\",\"deal_id\":%I64u,\"order_id\":%I64d,"
      "\"position_id\":%I64d,\"symbol\":\"%s\",\"side\":\"%s\","
      "\"lot\":%.2f,\"price\":%.5f,\"profit\":%.2f,\"event_time\":%I64d}",
      deal_id,
      HistoryDealGetInteger(deal_id, DEAL_ORDER),
      HistoryDealGetInteger(deal_id, DEAL_POSITION_ID),
      symbol,
      side,
      HistoryDealGetDouble(deal_id, DEAL_VOLUME),
      HistoryDealGetDouble(deal_id, DEAL_PRICE),
      HistoryDealGetDouble(deal_id, DEAL_PROFIT),
      HistoryDealGetInteger(deal_id, DEAL_TIME)
   );
   string response;
   int code = HttpPost(TRADE_EVENT_ENDPOINT, body, response);
   return code >= 200 && code < 300;
}

#endif
