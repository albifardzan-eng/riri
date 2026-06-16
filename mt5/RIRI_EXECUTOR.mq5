#property strict

input string ApiUrl =
"http://YOUR_SERVER:8000/mt5/market";

int OnInit()
{
   EventSetTimer(5);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   SendMarketData();
}

void SendMarketData()
{
   string payload =
      "{"
      "\"symbol\":\"XAUUSD\""
      "}";

   char post[];
   StringToCharArray(payload, post);

   char result[];
   string headers =
      "Content-Type: application/json\r\n";

   int timeout = 5000;

   string response_headers;

   int res = WebRequest(
      "POST",
      ApiUrl,
      headers,
      timeout,
      post,
      result,
      response_headers
   );

   Print("RIRI Response=", res);
}