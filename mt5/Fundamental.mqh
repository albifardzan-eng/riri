#ifndef RIRI_FUNDAMENTAL_MQH
#define RIRI_FUNDAMENTAL_MQH

//==================================================
// FUNDAMENTAL NEWS DATA
//==================================================
//
// MT5 Economic Calendar
//
// Focus:
// - USD
// - High impact
// - Upcoming event
// - Recently released event
// - Actual / Forecast / Previous
//
// Window:
// - 30 minutes backward
// - 60 minutes forward
//
//==================================================


//==================================================
// JSON SAFE STRING
//==================================================

string FundamentalJsonSafeString(string value)
{
   string result = value;

   StringReplace(result, "\\", "\\\\");
   StringReplace(result, "\"", "\\\"");
   StringReplace(result, "\r", "\\r");
   StringReplace(result, "\n", "\\n");
   StringReplace(result, "\t", "\\t");

   return result;
}


//==================================================
// CALENDAR VALUE JSON
//==================================================

string FundamentalCalendarValueJson(
   MqlCalendarValue &value
)
{
   string actual   = "null";
   string forecast = "null";
   string previous = "null";

   if(value.HasActualValue())
   {
      actual =
         DoubleToString(
            value.GetActualValue(),
            6
         );
   }

   if(value.HasForecastValue())
   {
      forecast =
         DoubleToString(
            value.GetForecastValue(),
            6
         );
   }

   if(value.HasPreviousValue())
   {
      previous =
         DoubleToString(
            value.GetPreviousValue(),
            6
         );
   }

   return
      StringFormat(
         "\"actual\":%s,"
         "\"forecast\":%s,"
         "\"previous\":%s",
         actual,
         forecast,
         previous
      );
}


//==================================================
// BUILD FUNDAMENTAL EVENT JSON
//==================================================

string GetFundamentalEventJson()
{
   datetime now =
      TimeTradeServer();

   if(now <= 0)
      now = TimeCurrent();


   //================================================
   // TIME WINDOW
   //================================================

   datetime from_time =
      now - (30 * 60);

   datetime to_time =
      now + (60 * 60);


   //================================================
   // CURRENCY
   //================================================

   string calendar_currency =
      "USD";


   //================================================
   // CALENDAR HISTORY
   //================================================

   MqlCalendarValue values[];

   ResetLastError();

   int total =
      CalendarValueHistory(
         values,
         from_time,
         to_time,
         NULL,
         calendar_currency
      );


   //================================================
   // NO DATA
   //================================================

   if(total <= 0)
   {
      return
         "{"
         "\"available\":false,"
         "\"high_impact_news\":false,"
         "\"event\":null,"
         "\"currency\":\"USD\","
         "\"impact\":\"NONE\","
         "\"phase\":\"NONE\","
         "\"minutes_to_news\":null,"
         "\"news_time\":null,"
         "\"event_id\":null,"
         "\"actual\":null,"
         "\"forecast\":null,"
         "\"previous\":null"
         "}";
   }


   //================================================
   // SELECT EVENT
   //================================================

   bool found = false;

   MqlCalendarValue selected_value = {};

   MqlCalendarEvent selected_event = {};

   long selected_distance =
      LONG_MAX;

   bool selected_released = false;


   //================================================
   // LOOP EVENTS
   //================================================

   for(int i = 0; i < total; i++)
   {
      MqlCalendarValue value =
         values[i];

      MqlCalendarEvent event = {};


      //================================================
      // EVENT LOOKUP
      //================================================

      if(
         !CalendarEventById(
            value.event_id,
            event
         )
      )
      {
         continue;
      }


      //================================================
      // HIGH IMPACT ONLY
      //================================================

      if(
         event.importance
         != CALENDAR_IMPORTANCE_HIGH
      )
      {
         continue;
      }


      //================================================
      // EXACT TIME EVENTS ONLY
      //================================================

      if(
         event.time_mode
         != CALENDAR_TIMEMODE_DATETIME
      )
      {
         continue;
      }


      //================================================
      // DISTANCE FROM CURRENT TIME
      //================================================

      long difference =
         (long)(
            value.time -
            now
         );

      long distance =
         (long)MathAbs(
            (double)difference
         );

      bool future =
         value.time >= now;

      bool released =
         !future &&
         value.HasActualValue();


      //================================================
      // FIRST VALID EVENT
      //================================================

      if(!found)
      {
         found = true;

         selected_value =
            value;

         selected_event =
            event;

         selected_distance =
            distance;

         selected_released =
            released;

         continue;
      }


      //================================================
      // PREFER A RECENT RELEASE WITH AN ACTUAL VALUE
      //================================================

      if(
         released &&
         !selected_released
      )
      {
         selected_value =
            value;

         selected_event =
            event;

         selected_distance =
            distance;

         selected_released =
            true;

         continue;
      }


      //================================================
      // SAME RELEASE STATE -> CLOSEST EVENT
      //================================================

      if(
         released ==
         selected_released
      )
      {
         if(
            distance <
            selected_distance
         )
         {
            selected_value =
               value;

            selected_event =
               event;

            selected_distance =
               distance;

            selected_released =
               released;
         }
      }
   }


   //================================================
   // NO HIGH IMPACT EVENT
   //================================================

   if(!found)
   {
      return
         "{"
         "\"available\":true,"
         "\"high_impact_news\":false,"
         "\"event\":null,"
         "\"currency\":\"USD\","
         "\"impact\":\"NONE\","
         "\"phase\":\"NONE\","
         "\"minutes_to_news\":null,"
         "\"news_time\":null,"
         "\"event_id\":null,"
         "\"actual\":null,"
         "\"forecast\":null,"
         "\"previous\":null"
         "}";
   }


   //================================================
   // EVENT TIME DIFFERENCE
   //================================================

   long seconds_difference =
      (long)(
         selected_value.time -
         now
      );

   long minutes_difference =
      seconds_difference / 60;


   //================================================
   // EVENT NAME
   //================================================

   string event_name =
      FundamentalJsonSafeString(
         selected_event.name
      );


   //================================================
   // PHASE
   //================================================

   string phase;

   if(
      selected_value.time >= now
   )
   {
      phase =
         "UPCOMING";
   }
   else
   {
      phase =
         "RECENT";
   }


   //================================================
   // IMPACT
   //================================================

   string impact =
      "HIGH";


   //================================================
   // ACTUAL / FORECAST / PREVIOUS
   //================================================

   string values_json =
      FundamentalCalendarValueJson(
         selected_value
      );


   //================================================
   // RESULT
   //================================================

   return
      StringFormat(
         "{"
         "\"available\":true,"
         "\"high_impact_news\":true,"
         "\"event\":\"%s\","
         "\"currency\":\"USD\","
         "\"impact\":\"%s\","
         "\"phase\":\"%s\","
         "\"minutes_to_news\":%I64d,"
         "\"news_time\":%I64d,"
         "\"event_id\":%I64u,"
         "%s"
         "}",
         event_name,
         impact,
         phase,
         minutes_difference,
         (long)selected_value.time,
         selected_value.event_id,
         values_json
      );
}

#endif
