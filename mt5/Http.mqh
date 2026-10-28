#ifndef RIRI_HTTP_MQH
#define RIRI_HTTP_MQH


struct RiriSignal
{
   string signal_id;
   string execution_token;
   string symbol;
   string action;
   double lot;
   bool ai_capital_profile;
   int trailing_start_points;
   int trailing_distance_points;
   int trailing_step_points;
   int cost_buffer_points;
   int tp_points;
   int sl_points;
   int confidence;
   int initial_score;
   int entry_policy_version;
   double max_spread_points;
   double max_sl_risk_percent;
   bool small_equity_strict;
   bool preclose_enabled;
   long magic_number;
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
   string raw = StringSubstr(json, start, finish - start);
   if(raw == "null" || raw == "")
      return fallback;
   return StringToDouble(raw);
}


bool RIRI_JsonBool(string json, string key, bool fallback = false)
{
   string token = "\"" + key + "\":";
   int start = StringFind(json, token);
   if(start < 0)
      return fallback;
   start += StringLen(token);
   return StringSubstr(json, start, 4) == "true" ? true :
      StringSubstr(json, start, 5) == "false" ? false : fallback;
}


void RIRI_PrintAnalysis(string response)
{
   Print("[ANALYSIS] score=", (int)RIRI_JsonNumber(response, "score", -1),
      " qualified=", RIRI_JsonBool(response, "qualified") ? "true" : "false",
      " ai_called=", RIRI_JsonBool(response, "ai_called") ? "true" : "false",
      " gate=", RIRI_JsonString(response, "ai_gate_reason"),
      " decision=", RIRI_JsonString(response, "ai_decision"),
      " confidence=", (int)RIRI_JsonNumber(response, "ai_confidence", 0),
      " risk=", RIRI_JsonString(response, "risk_reason"),
      " execution=", RIRI_JsonString(response, "execution_reason"),
      " signal_lot=", DoubleToString(RIRI_JsonNumber(response, "signal_lot", 0.0), 2));
   Print("[ENTRY_GATE] cooldown_remaining_s=", (int)RIRI_JsonNumber(response, "cooldown_remaining_seconds", -1),
      " last_entry_age_s=", (long)RIRI_JsonNumber(response, "latest_entry_age_seconds", -1),
      " last_entry_broker_epoch=", (long)RIRI_JsonNumber(response, "latest_entry_server_time", -1),
      " riri_positions=", (int)RIRI_JsonNumber(response, "riri_position_count"),
      " other_positions=", (int)RIRI_JsonNumber(response, "foreign_position_count"),
      " riri_profit=", DoubleToString(RIRI_JsonNumber(response, "riri_position_profit"), 2),
      " BUY=", RIRI_JsonString(response, "buy_blockers"),
      " buy_min_conf=", (int)RIRI_JsonNumber(response, "buy_min_confidence"),
      " SELL=", RIRI_JsonString(response, "sell_blockers"),
      " sell_min_conf=", (int)RIRI_JsonNumber(response, "sell_min_confidence"),
      " ai_retry_s=", (int)RIRI_JsonNumber(response, "ai_retry_after_seconds"));
}


bool SendMarket()
{
   string response;
   int code = HttpPost(MARKET_ENDPOINT, BuildMarketJson(), response);
   if(code >= 200 && code < 300)
      RIRI_PrintAnalysis(response);
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
   // IDs become filenames, so reject any server output outside UUID characters.
   if(StringLen(signal.signal_id)!=36) return false;
   for(int i=0;i<StringLen(signal.signal_id);i++)
      if(StringFind("0123456789abcdef-",StringSubstr(signal.signal_id,i,1))<0) return false;
   string ack=RIRI_StateKey("ack_"+signal.signal_id+".json");
   if(FileIsExist(ack,FILE_COMMON))
   {
      int handle=FileOpen(ack,FILE_READ|FILE_TXT|FILE_COMMON|FILE_ANSI);
      if(handle!=INVALID_HANDLE)
      {
         string body=FileReadString(handle);FileClose(handle);
         string retry;HttpPost(CONFIRM_ENDPOINT,body,retry);
      }
      return false;
   }
   signal.symbol = RIRI_JsonString(response, "symbol");
   signal.action = RIRI_JsonString(response, "action");
   signal.lot = RIRI_JsonNumber(response, "lot");
   signal.ai_capital_profile=RIRI_JsonBool(response,"ai_capital_profile",false);
   signal.trailing_start_points=(int)RIRI_JsonNumber(response,"trailing_start_points");
   signal.trailing_distance_points=(int)RIRI_JsonNumber(response,"trailing_distance_points");
   signal.trailing_step_points=(int)RIRI_JsonNumber(response,"trailing_step_points");
   signal.cost_buffer_points=(int)RIRI_JsonNumber(response,"cost_buffer_points");
   signal.tp_points = (int)RIRI_JsonNumber(response, "tp_points");
   signal.sl_points = (int)RIRI_JsonNumber(response, "sl_points");
   signal.confidence = (int)RIRI_JsonNumber(response, "confidence");
   signal.initial_score = (int)RIRI_JsonNumber(response, "initial_score");
   signal.entry_policy_version = (int)RIRI_JsonNumber(response, "entry_policy_version");
   signal.max_spread_points=RIRI_JsonNumber(response,"max_spread_points",30);
   signal.max_sl_risk_percent=RIRI_JsonNumber(response,"max_sl_risk_percent",0);
   signal.small_equity_strict=RIRI_JsonBool(response,"small_equity_strict",true);
   signal.preclose_enabled=RIRI_JsonBool(response,"preclose_enabled",false);
   signal.magic_number = (long)RIRI_JsonNumber(response, "magic_number");
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
      "\"order_id\":%I64u,\"deal_id\":%I64u,\"requested_lot\":%.8f,"
      "\"filled_lot\":%.8f,\"executed_price\":%.5f,\"retcode\":%u,\"reason\":\"%s\",\"entry_server_time\":%I64d,\"execution_token\":\"%s\"}",
      signal.signal_id, status, signal.action, order_id, deal_id,
      signal.lot, filled_lot, executed_price, retcode,
      FundamentalJsonSafeString(reason), status=="EXECUTED"?(long)TimeCurrent():0, signal.execution_token
   );
   string name=RIRI_StateKey("ack_"+signal.signal_id+".json");
   int handle=FileOpen(name,FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(handle==INVALID_HANDLE) return false;
   FileWriteString(handle,body);FileFlush(handle);FileClose(handle);
   // Network delivery is performed after releasing the broker/protection lock.
   return true;
}


void RIRI_FlushAck(string signal_id)
{
   int handle=FileOpen(RIRI_StateKey("ack_"+signal_id+".json"),FILE_READ|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(handle==INVALID_HANDLE) return;
   string body=FileReadString(handle);FileClose(handle);
   string response;HttpPost(CONFIRM_ENDPOINT,body,response);
}


bool ReportTradeClose(ulong deal_id)
{
   if(deal_id == 0 || !HistoryDealSelect(deal_id))
      return false;

   long entry = HistoryDealGetInteger(deal_id, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
      return false;

   string symbol = HistoryDealGetString(deal_id, DEAL_SYMBOL);
   if(symbol != RIRI_SYMBOL || HistoryDealGetInteger(deal_id, DEAL_MAGIC) != MAGIC_NUMBER)
      return false;

   long deal_type = HistoryDealGetInteger(deal_id, DEAL_TYPE);
   string side = deal_type == DEAL_TYPE_BUY ? "BUY" : "SELL";
   string body = StringFormat(
      "{\"status\":\"CLOSED\",\"deal_id\":%I64u,\"order_id\":%I64d,"
      "\"position_id\":%I64d,\"symbol\":\"%s\",\"side\":\"%s\","
      "\"lot\":%.8f,\"price\":%.5f,\"profit\":%.2f,\"event_time\":%I64d}",
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
