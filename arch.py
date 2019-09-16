#!/usr/bin/python
# coding=UTF-8
import time
import datetime
import os
import sys
import ccxt
import talib
import requests
import pandas as pd

class LineNotify():
    def __init__(self):
        self.key = self.read_setting()
        self.header =  {'Authorization': 'Bearer '+ key ,'Connection':'close'}
        self.link = "https://notify-api.line.me/api/notify"

    def read_setting():
        with open('setting.json') as json_file:
            setting_data = json.load(json_file)
            self.key = setting_data['LineKey']

    def send_alert(self,msg:str):
        try:
            push = requests.post(self.link,data ={'message': msg},headers=self.header)
        except Exception as e:
                if hasattr(e, 'message'):
                    print("ERROR : " + str(datetime.datetime.now())+"\t"+"send alert:"+str(e.message))
                else:
                    print("ERROR : " + str(datetime.datetime.now())+"\t"+"send alert:"+str(e))

        if(r.status_code != requests.codes.ok):
            print("ERROR : "+ str(datetime.datetime.now())+"\t"+str(r.status_code)+"\t"+"send alert")

class BitmexFetcher(LineNotify):
    __fetch_index = ["date","open","high","low","close","volume"]
    exchange = ccxt.bitmex({   
            #'rateLimit': 10000,
            'enableRateLimit': True,    
            # 'verbose': True,
    })
    __error_hold = 60  #  seconds

    def __init__(self, trading_pair: str, k_line: str,backdays:int):
        self.trading_pair = trading_pair
        self.k_line = k_line
        self.data = pd.DataFrame()
        self.ind= []
        self.fetch_back_days(backdays)

    def str2msec(self,str_time: str): 
        '''convert string to microseconds'''
        if str_time == "1m":
            return 60 * 1000  # msec = 1000 , minute = 60 * msec
        elif str_time == "5m":
            return 5 * 60 * 1000
        elif str_time == "15m":
            return 15 * 60 * 1000
        elif str_time == "30m":
            return 30 * 60 * 1000
        elif str_time == "1h":
            return 60 * 60 * 1000
        elif str_time == "4h":
            return 4 * 60 * 60 * 1000
        elif str_time == "1d":
            return 24 * 60 * 60 * 1000

    def update_data(self,last_timestamp:int):
        ''' fetch new data and push new data to dataframe '''
        upper_bound = 1200
        lower_bound = 400

        if len(self.data.index) > upper_bound :
            remove_count = upper_bound-lower_bound
            self.data.drop(self.data.index[:remove_count], inplace=True)            
            self.data.reset_index(drop=True,inplace=True)
            
        fresh_data = self.__fetch_ohlcvs(last_timestamp)
        
        if fresh_data != [] :
            print(fresh_data)
            self.data = self.data.append(pd.DataFrame(fresh_data,columns=self.__fetch_index),ignore_index=True,sort=False)
            for x in self.ind:
                __ind_para = x.split("_")
                __para_list = []
                for i in range( 1 , len(__ind_para) ):
                    __para_list.append(__ind_para[i]) 
                self.add_indicator(__ind_para[0] , __para_list)
        
    def fetch_back_days(self,d:int):

        from_timestamp = self.exchange.milliseconds() - self.str2msec("1d") * d   # -1 day from now

        reuslt = self.__fetch_ohlcvs(from_timestamp)

        if self.data.empty:
            self.data = pd.DataFrame(reuslt, columns=self.__fetch_index)
        else :
            self.data = self.data.append(reuslt,index=self.__fetch_index,sort=False)

    def __fetch_ohlcvs(self,from_timestamp,):
        ''' fetch new data and push new data to dataframe '''
        raw_data = []
        now = self.exchange.milliseconds()    

        while from_timestamp < now:
            try:
                print(datetime.datetime.now(), 'Fetching candles starting from',
                      self.exchange.iso8601(from_timestamp))
                ohlcvs = self.exchange.fetch_ohlcv(
                    self.trading_pair, self.k_line, from_timestamp)
                print(self.exchange.milliseconds(),
                      'Fetched', len(ohlcvs), 'candles')
                if len(ohlcvs) > 0:
                    # from_timestamp += len(ohlcvs) * minute * 5  # very bad
                    from_timestamp = ohlcvs[-1][0] + self.str2msec(self.k_line)  # good
                    raw_data += ohlcvs

            except (ccxt.ExchangeError, ccxt.AuthenticationError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout) as error:
                msg = 'Fetch :　Got an error' + str(type(error).__name__,error.args) + ', retrying in' + str(self.__error_hold) + 'seconds...'
                print(msg)
                super(BitmexFetcher, self).send_alert(msg) 
                time.sleep(self.__error_hold)

        # change str date to datetime object
        for i in range(len(raw_data)):
            raw_data[i][0]=datetime.datetime.strptime(self.exchange.iso8601(raw_data[i][0]), '%Y-%m-%dT%H:%M:%S.000Z').replace(tzinfo=datetime.timezone.utc).astimezone(tz=None)

        # the last data is not closed
        return raw_data[:-1]

    def add_indicator(self,ind:str,para:list):
        """ add indicator to dataframe , but also refresh indicator data of dataframe """           
        if ind.lower()=="ma":
            #MA_Type: 0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA, 5=TRIMA, 6=KAMA, 7=MAMA, 8=T3 (Default=SMA)
            # # # SMA = talib.MA(close,30,matype=0)[-1]
            # # # EMA = talib.MA(close,30,matype=1)[-1]
            # # # WMA = talib.MA(close,30,matype=2)[-1]
            # # # DEMA = talib.MA(close,30,matype=3)[-1]
            # # # TEMA = talib.MA(close,30,matype=4)[-1]
            len = int(para[0])
            name = "ma_" + str(len)
            if name not in list(self.data):
                self.ind.append(name)
                        
            self.data[name]=talib.MA(self.data.close,len,matype=0)

        elif ind.lower() =="rsi":
            len = int(para[0])
            name = "rsi_" + str(len)
            if name not in list(self.data):
                self.ind.append(name)
                
            self.data[name]=talib.RSI(self.data.close,len)
            

        elif ind.lower() == "kd":
            k_period = int(para[0])
            ma_period =  int(para[1])
            name = "kd_"+k_period+"_"+ma_period
            if name not in list(self.data):
                self.ind.append({"kd": [k_period,ma_period]})
            
            slowk, slowd = STOCH(high, low, close, fastk_period=k_period, slowk_period=ma_period, slowk_matype=0, slowd_period=ma_period, slowd_matype=0)
            kd_list = [ [slowk[i],slowd[i] ] for i in range(0,len(slowk)) ]   
            self.data[name] = kd_list
        else:
            pass
    
class OnInit():
    # 把所有東西都先把基本的數值設置定好該讀取的東西讀取好
    def __init__(self):
        pass

class OnTick(BitmexFetcher):
    alert_last_K_count = -3 #Only notify the last K line 
    def __init__(self,trading_pair: str, k_line: str,backdays:int):
        super().__init__(trading_pair, k_line,backdays)

    def main_job(self):
        """ Main job """

        #如果時間超過最後一根K的收盤時間，則開始搜尋下一根K，並做演算法檢查
        #if(self.data.date[-1]< datetime.datetime.now() + datetime.timedelta(microseconds=self.str2msec(self.k_line))) )
        ##
        round_count=0
        sleep_time=self.str2msec(self.k_line)/1000/2
        while True:
            print("*** Start Round :\t",round_count,"***")
            self.update_data( int (datetime.datetime.timestamp(self.data.iloc[-1].date)*1000 + self.str2msec(self.k_line)))
            self.rsi_div(9)
            print(self.data)
            print("*** End Round :\t",round_count ,"& sleep ",sleep_time," seconds ***")
            time.sleep(sleep_time)
            round_count=round_count+1     
    
    def signal_match(self,singal:str,d,dsec:str):
        """ Buy & Sell singal alert """
        print(d)
        print(self.data.iloc[self.alert_last_K_count].date )
        if d > self.data.iloc[self.alert_last_K_count].date :
            __date_str = d.strftime("%m/%d %H:%M")

            if singal.lower()=="buy":
                print("BUY", __date_str ,dsec)
                
            elif singal.lower()=="sell":
                print("SELL", __date_str ,dsec)
                
            else :
                pass
            
    def rsi_div(self,rsi_len:int):
        ind_name = "rsi_" + str(rsi_len)
        HiP=80
        LoP=20
        RevH=65
        RevL=35
        Hi1Ind=0
        Hi2Ind=0
        Lo1Ind=0
        Lo2Ind=0
        PrHi1=0
        PrHi2=0
        PrLo1=0
        PrLo2=0
        Flag_3=0
        CFlag=0

        if ind_name not in list(self.data):
            super(OnTick, self).add_indicator("rsi",[rsi_len]) 
            #self.add_indicator("rsi",rsi_len) 
            
        for i in range(rsi_len-1, len(self.data[ind_name])):
            rsi_current = self.data[ind_name][i]
               
            if  rsi_current >= HiP and CFlag != 1 :
                CFlag = 1
                Hi1Ind = rsi_current
                PrHi1 = self.data.high[i]
            
            if  rsi_current <= LoP and CFlag != -1 :
                CFlag = -1
                Lo1Ind = rsi_current
                PrLo1 = self.data.low[i]
            
            if CFlag == 1 :
                if Hi1Ind < rsi_current :
                    Hi1Ind = rsi_current
                if PrHi1 < self.data.high[i] :
                    PrHi1 = self.data.high[i]
            
            if CFlag == -1 :
                if Lo1Ind > rsi_current :
                    Lo1Ind = rsi_current
                if PrLo1 < self.data.low[i] :
                    PrLo1 = self.data.low[i]
            
            if CFlag ==1 and rsi_current <= RevH :
                CFlag=2
            
            if CFlag == -1 and rsi_current >= RevL :
                CFlag =-2
            
            if CFlag == 2 and rsi_current< RevH :
                CFlag = 3
                Flag_3 = rsi_current

            if CFlag == -2 and rsi_current> RevL :
                CFlag = -3
                Flag_3 = rsi_current

            if CFlag ==3 and Flag_3 > rsi_current :
                Flag_3 = rsi_current 

            if CFlag ==-3 and Flag_3 < rsi_current :
                Flag_3 = rsi_current 

            if CFlag==3 and self.data.high[i] >= PrHi1 :
                CFlag = 4
                PrHi2 = self.data.high[i] 
                Hi2Ind = rsi_current
                    
            if CFlag==-3 and self.data.low[i] <= PrLo1 :
                CFlag = -4
                PrLo2 = self.data.low[i] 
                Lo2Ind = rsi_current

            if CFlag == 4 :
                if self.data.high[i]  > PrHi2 :
                    PrHi2 = self.data.high[i] 
                if  rsi_current > Hi2Ind:
                    Hi2Ind = rsi_current
            
            if CFlag == -4 :
                if self.data.low[i] < PrLo2 :
                    PrLo2 = self.data.low[i] 
                if  rsi_current < Lo2Ind:
                    Lo2Ind = rsi_current

            if CFlag == 4 and (Hi2Ind > Hi1Ind or Hi2Ind > HiP ) :
                CFlag = 1
                Hi1Ind = Hi2Ind
                if PrHi2 > PrHi1 :
                    PrHi1 = PrHi2

            if CFlag == -4 and (Lo2Ind < Lo1Ind or Lo2Ind < LoP ) :
                CFlag = -1
                Lo1Ind = Lo2Ind
                if PrLo2 < PrLo1 :
                    PrLo1 = PrLo2
            
            if CFlag == 4 and rsi_current < Flag_3 and Hi1Ind > Hi2Ind and PrHi1 <= PrHi2 :
                CFlag=5

                #__date_str = self.data.date[i].strftime("%m/%d %H:%M")
                #print("SELL : ", __date_str ,self.data.close[i] ,rsi_current)
                #msg += "SELL \n"+__date_str +'\n'+ str(self.data.close[i])+'\n' + str(rsi_current)+'\n'
                self.signal_match("SELL",self.data.date[i],"RSI DIV Enter:" + str(self.data.close[i]) )


            if CFlag == -4 and rsi_current > Flag_3 and Lo1Ind < Lo2Ind and PrLo1 >= PrLo2 :
                CFlag=-5
                
                #__date_str = self.data.date[i].strftime("%m/%d %H:%M")
                #print("BUY",__date_str ,self.data.close[i] ,rsi_current)

                self.signal_match("BUY",self.data.date[i],"RSI DIV Enter:" + str(self.data.close[i]) )
                #msg = "BUY\n"+ __date_str +'\n'+ str(self.data.close[i]) +'\n'+ str(rsi_current)+'\n'

            if CFlag == 5 and self.data.high[i] > PrHi2 :
                PrHi1=PrHi2
                PrHi2 = self.data.high[i]
                CFlag =4

            if CFlag == -5 and self.data.low[i] < PrLo2 :
                PrLo1=PrLo2
                PrLo2 = self.data.low[i]
                CFlag =-4



    def beforeOnBar():
        # 裡面放的是每個 Tick 都要做的事情，和 OnBar 比較沒有關係的
        # 例如和時間相關的處理，就可以放在 beforeOnBar
        # 例如我有 TimeFilter 的話，beforeOnBar 我就會判斷是不是不該進場的時間
        # 我就把所有單撤下來，或是恢復回去，這和我 OnBar 交易邏輯無關
        pass

    def OnBar():
        # 就是放我的交易邏輯，就是我在這 bar open 我要做什麼事情
        # 一般來說裡面會分成 Entry / Exit / ReEntry 三個段落
        # 也就是先判斷是不是要 Entry ，那就掛單，沒有要 Entry 就判斷要不要
        # Exit ，如果有 Exit 就判斷要不要 ReEntry 相反方向的單
        pass

    def afterOnBar():
        # afterOnBar 就是放可能和我交易有關，但是是每個 bar 都要做的事情
        # 例如移動停損的檢查，損益兩平停損的檢查，這些都要在 Tick Level
        # 一直去確認
        pass


class OnDeinit():
    def __init__(self):
        pass

class BackTest():
    def __init__(self):
        pass
