#ifndef RIRI_STATE_MQH
#define RIRI_STATE_MQH

bool RIRI_HistoryReady = false;
string RIRI_StateKey(string suffix)
{
   uint hash = 2166136261;
   string server = AccountInfoString(ACCOUNT_SERVER);
   for(int i=0;i<StringLen(server);i++) hash=(hash ^ StringGetCharacter(server,i))*16777619;
   return StringFormat("R%I64d_%u_%s",AccountInfoInteger(ACCOUNT_LOGIN),hash,suffix);
}

void RIRI_RecordEntry(long when)
{
   if(when<=0) return;
   string key=RIRI_StateKey("entry");
   double old=GlobalVariableCheck(key)?GlobalVariableGet(key):0;
   if(when>old) { GlobalVariableSet(key,(double)when); GlobalVariablesFlush(); }
}

long RIRI_ReconcileEntry()
{
   string key=RIRI_StateKey("entry");
   long latest=GlobalVariableCheck(key)?(long)GlobalVariableGet(key):0;
   datetime start=latest>86400?(datetime)(latest-86400):0;
   RIRI_HistoryReady=HistorySelect(start,TimeCurrent());
   if(!RIRI_HistoryReady) return -1;
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong deal=HistoryDealGetTicket(i);
      if(HistoryDealGetString(deal,DEAL_SYMBOL)!=RIRI_SYMBOL || HistoryDealGetInteger(deal,DEAL_MAGIC)!=MAGIC_NUMBER) continue;
      long entry=HistoryDealGetInteger(deal,DEAL_ENTRY);
      if(entry==DEAL_ENTRY_IN || entry==DEAL_ENTRY_INOUT)
         latest=MathMax(latest,HistoryDealGetInteger(deal,DEAL_TIME));
   }
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || PositionGetString(POSITION_SYMBOL)!=RIRI_SYMBOL || PositionGetInteger(POSITION_MAGIC)!=MAGIC_NUMBER) continue;
      latest=MathMax(latest,PositionGetInteger(POSITION_TIME));
   }
   RIRI_RecordEntry(latest);
   return latest;
}

// Exclusive common-file handle serializes local broker sends, trailing and closes.
// The backend additionally issues only one account-scoped submission permit.
int RIRI_Lock()
{
   return FileOpen(RIRI_StateKey("trade.lock"),FILE_READ|FILE_WRITE|FILE_BIN|FILE_COMMON);
}

bool RIRI_SelectedOrder()
{
   return OrderGetString(ORDER_SYMBOL)==RIRI_SYMBOL && OrderGetInteger(ORDER_MAGIC)==MAGIC_NUMBER;
}

int RIRI_PendingCount(double &lot)
{
   int n=0; lot=0;
   for(int i=0;i<OrdersTotal();i++)
   {
      if(OrderGetTicket(i)==0 || !RIRI_SelectedOrder()) continue;
      n++; lot+=OrderGetDouble(ORDER_VOLUME_CURRENT);
   }
   return n;
}

bool RIRI_IsBuyOrder(long type)
{
   return type==ORDER_TYPE_BUY || type==ORDER_TYPE_BUY_LIMIT || type==ORDER_TYPE_BUY_STOP || type==ORDER_TYPE_BUY_STOP_LIMIT;
}

// Session boundaries use the broker clock and broker session table, never WIB.
bool RIRI_Session(long &close_time,long &next_open,bool &weekly)
{
   close_time=0; next_open=0; weekly=false;
   long now=(long)TimeTradeServer();
   MqlDateTime dt; TimeToStruct((datetime)now,dt);
   long midnight=now-dt.hour*3600-dt.min*60-dt.sec;
   long starts[160],ends[160]; int n=0;
   for(int day=-1;day<=7;day++)
   {
      int weekday=(dt.day_of_week+day+7)%7;
      for(uint index=0;index<16;index++)
      {
         datetime from,to;
         if(!SymbolInfoSessionTrade(RIRI_SYMBOL,(ENUM_DAY_OF_WEEK)weekday,index,from,to)) break;
         long f=(long)from%86400, t=(long)to%86400;
         long a=midnight+day*86400+f, b=midnight+day*86400+t;
         if(t<=f) b+=86400;
         if(n>=160) return false;
         starts[n]=a;ends[n]=b;n++;
      }
   }
   // Sort and merge touching intervals (including continuous midnight sessions).
   for(int i=0;i<n;i++) for(int j=i+1;j<n;j++) if(starts[j]<starts[i])
   { long a=starts[i],b=ends[i];starts[i]=starts[j];ends[i]=ends[j];starts[j]=a;ends[j]=b; }
   for(int i=0;i<n;i++)
   {
      if(starts[i]<=now && now<ends[i])
      {
         close_time=ends[i];
         for(int j=i+1;j<n;j++)
         {
            if(starts[j]<=close_time) close_time=MathMax(close_time,ends[j]);
            else {next_open=starts[j];break;}
         }
         // A closure spanning a non-trading day is treated as weekly/long-break.
         weekly=next_open-close_time>=86400;
         return next_open>close_time;
      }
   }
   return false;
}

bool RIRI_EntrySessionAllowed(bool force)
{
   if(!RIRI_PRECLOSE_ENABLED && !force) return true;
   long close_time,next_open;bool weekly;
   if(!RIRI_Session(close_time,next_open,weekly)) return false;
   return close_time-(long)TimeTradeServer()>(weekly?3600:1800);
}
#endif
