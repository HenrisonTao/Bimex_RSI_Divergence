# -*- coding: utf-8 -*-
import os
import sys
import time
import ccxt
import datetime
import talib 
import numpy as np 
import math
import requests
import json

def read_setting():
    global _Lineheader
    with open('setting.json') as json_file:
        data = json.load(json_file)
        _Lineheader = {'Authorization': 'Bearer '+ data['LineKey'] ,'Connection':'close'}

def intial_crawl_data():
    global raw_data
    raw_data = []
    from_timestamp = exchange.milliseconds () - 86400000 * back_days   # -1 day from now
    now = exchange.milliseconds()

    while from_timestamp < now:
        try:
            print( datetime.datetime.now() , 'Fetching candles starting from', exchange.iso8601(from_timestamp))
            ohlcvs = exchange.fetch_ohlcv(trading_pair, k_line, from_timestamp)
            print(exchange.milliseconds(), 'Fetched', len(ohlcvs), 'candles')
            if len(ohlcvs) > 0:
                # from_timestamp += len(ohlcvs) * minute * 5  # very bad
                from_timestamp = ohlcvs[-1][0] + poll_hold  # good
                raw_data += ohlcvs

        except (ccxt.ExchangeError, ccxt.AuthenticationError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout) as error:
            # print('Got an error', type(error).__name__, error.args, ', retrying in', error_hold, 'seconds...')
            print(colored('Got an error', type(error).__name__, error.args, ', retrying in', error_hold, 'seconds...'))
            time.sleep(error_hold)
    # [
    #     1504541580000, // UTC timestamp in milliseconds, integer
    #     4235.4,        // (O)pen price, float
    #     4240.6,        // (H)ighest price, float
    #     4230.0,        // (L)owest price, float
    #     4230.7,        // (C)losing price, float
    #     37.72941911    // (V)olume (in terms of the base currency), float
    # ],

def covert_5_15m(ohlcv5):
    ohlcv15 = []
    timestamp = 0
    open = 1
    high = 2
    low = 3
    close = 4
    volume = 5

    # convert 5m → 15m
    if len(ohlcv5) > 2:
        for i in range(0, len(ohlcv5) - 2, 3):
            highs = [ohlcv5[i + j][high] for j in range(0, 3) if ohlcv5[i + j][high]]
            lows = [ohlcv5[i + j][low] for j in range(0, 3) if ohlcv5[i + j][low]]
            volumes = [ohlcv5[i + j][volume] for j in range(0, 3) if ohlcv5[i + j][volume]]
            candle = [
                ohlcv5[i + 0][timestamp],
                ohlcv5[i + 0][open],
                max(highs) if len(highs) else None,
                min(lows) if len(lows) else None,
                ohlcv5[i + 2][close],
                sum(volumes) if len(volumes) else None,
            ]
            ohlcv15.append(candle)
    else:
        raise Exception('Too few 5m candles')

    return ohlcv15

def cal_rsi(input_data):
    global rsi,data,rsi_ema
    np_data = np.array(input_data)
    data = {
        'time' : np_data[:,0],
        'open': np_data[:,1],
        'high': np_data[:,2],
        'low': np_data[:,3],
        'close': np_data[:,4],
        'volume': np_data[:,5]
    }
    rsi = talib.RSI(data['close'], rsi_length)
    rsi_ema = talib.EMA(rsi, rsi_ema_length)
    
def send_alert(msg):
    push=requests.post(Linelink,data ={'message': msg},headers=_Lineheader)
    #print(msg,file=open("btc.txt","a+"))

def algo():
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
    msg=""

    for i in range(rsi_length, len(rsi)-1):

        if  rsi[i] >= HiP and CFlag != 1 :
            CFlag = 1
            Hi1Ind = rsi[i]
            PrHi1 = data['high'][i]
        
        if  rsi[i] <= LoP and CFlag != -1 :
            CFlag = -1
            Lo1Ind = rsi[i]
            PrLo1 = data['low'][i]
        
        if CFlag == 1 :
            if Hi1Ind < rsi[i] :
                Hi1Ind = rsi[i]
            if PrHi1 < data['high'][i] :
                PrHi1 = data['high'][i]
        
        if CFlag == -1 :
            if Lo1Ind > rsi[i] :
                Lo1Ind = rsi[i]
            if PrLo1 < data['low'][i] :
                PrLo1 = data['low'][i]
        
        if CFlag ==1 and rsi[i] <= RevH :
            CFlag=2
        
        if CFlag == -1 and rsi[i] >= RevL :
            CFlag =-2
        
        if CFlag == 2 and rsi[i]< RevH :
            CFlag = 3
            Flag_3 = rsi[i]

        if CFlag == -2 and rsi[i]> RevL :
            CFlag = -3
            Flag_3 = rsi[i]

        if CFlag ==3 and Flag_3 > rsi[i] :
            Flag_3 = rsi[i] 

        if CFlag ==-3 and Flag_3 < rsi[i] :
            Flag_3 = rsi[i] 

        if CFlag==3 and data['high'][i] >= PrHi1 :
            CFlag = 4
            PrHi2 = data['high'][i] 
            Hi2Ind = rsi[i]
                
        if CFlag==-3 and data['low'][i] <= PrLo1 :
            CFlag = -4
            PrLo2 = data['low'][i] 
            Lo2Ind = rsi[i]

        if CFlag == 4 :
            if data['high'][i]  > PrHi2 :
                PrHi2 = data['high'][i] 
            if  rsi[i] > Hi2Ind:
                Hi2Ind = rsi[i]
        
        if CFlag == -4 :
            if data['low'][i] < PrLo2 :
                PrLo2 = data['low'][i] 
            if  rsi[i] < Lo2Ind:
                Lo2Ind = rsi[i]

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
        
        if CFlag == 4 and rsi[i] < Flag_3 and Hi1Ind > Hi2Ind and PrHi1 <= PrHi2 :
            CFlag=5

            s = data['time'][i]
            fmt = "%Y-%m-%d %H:%M:%S"
            t = datetime.datetime.fromtimestamp(float(s)/1000.)
            print("SELL", t.strftime(fmt) ,data['close'][i] ,rsi[i])
            msg += "SELL \n"+ t.strftime(fmt) +'\n'+ str(data['close'][i])+'\n' + str(rsi[i])+'\n'
        

        if CFlag == -4 and rsi[i] > Flag_3 and Lo1Ind < Lo2Ind and PrLo1 >= PrLo2 :
            CFlag=-5
            
            s = data['time'][i]
            fmt = "%Y-%m-%d %H:%M:%S"
            t = datetime.datetime.fromtimestamp(float(s)/1000.)
            print("BUY", t.strftime(fmt) ,data['close'][i] ,rsi[i])
            msg = "BUY\n"+ t.strftime(fmt) +'\n'+ str(data['close'][i]) +'\n'+ str(rsi[i])+'\n'

        if CFlag == 5 and data['high'][i] > PrHi2 :
            PrHi1=PrHi2
            PrHi2 = data['high'][i]
            CFlag =4

        if CFlag == -5 and data['low'][i] < PrLo2 :
            PrLo1=PrLo2
            PrLo2 = data['low'][i]
            CFlag =-4    
    
    if(msg != "") :
        send_alert(msg)

############################################################################

##### Trading parameter
back_days = 30
k_line="1h"
trading_pair = 'BTC/USD'
rsi_length = 12
rsi_ema_length = 15

#### RSI_DIV Algo parameter
HiP=80
LoP=20
RevH=65
RevL=35

###### system settting 
error_hold = 30 ## error waiting time (second)
poll_hold = 60 * 60 * 1000 #  msec = 1000 , minute = 60 * msec , poll_hold = 60分鐘 (By K-line )

#######  LINE Notify
_Lineheader = {}
Linelink="https://notify-api.line.me/api/notify"
############################################################################

raw_data=[]
rsi=[]
data=[]

# fetch_time=

exchange = ccxt.bitmex({   
    #'rateLimit': 10000,
    'enableRateLimit': True,    
    # 'verbose': True,
})

while(True):
    read_setting()
    intial_crawl_data()
    read_setting()
    cal_rsi(raw_data)
    algo()
    time.sleep(60*60) #1Hour
