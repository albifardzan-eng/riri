#ifndef __RIRI_CONFIG_MQH__
#define __RIRI_CONFIG_MQH__

input string API_URL = "https://api-riri.albiagent.com";
input string RIRI_API_KEY = "";
input string RIRI_INSTANCE_ID = "primary";
input int TIMER_SECONDS = 10;
input int REQUEST_TIMEOUT = 30000;
input int MAX_CANDLES = 120;
input ENUM_TIMEFRAMES CANDLE_TIMEFRAME = PERIOD_H1;
input int ATR_PERIOD = 14;
input double DEFAULT_SLIPPAGE = 10;
input string EA_NAME = "RIRI Executor";
input string EA_VERSION = "1.2.0";

const string MARKET_ENDPOINT = "/mt5/market";
const string SIGNAL_ENDPOINT = "/execution/pending";
const string CONFIRM_ENDPOINT = "/execution/confirm";
const string TRADE_EVENT_ENDPOINT = "/execution/trade-event";

// Immutable RIRI v1 rules.
const string RIRI_SYMBOL = "XAUUSD";
const long MAGIC_NUMBER = 20260701;
const int RIRI_MIN_CONFIDENCE = 60;
const int RIRI_STANDARD_CONFIDENCE = 70;
const double RIRI_REDUCED_CONFIDENCE_LOT = 0.01;
const int RIRI_TP_POINTS = 1000;
const int RIRI_SL_POINTS = 3000;
const int RIRI_MAX_ACTIVE_TRADES = 3;
const double RIRI_MAX_TOTAL_LOT = 0.50;
const double RIRI_MAX_SPREAD = 30.0;
const double RIRI_MIN_ATR = 1.0;
const double RIRI_DEFAULT_LOT = 0.01;
const double RIRI_EQUITY_STEP = 500.0;
const double RIRI_LOT_STEP = 0.01;

#endif
