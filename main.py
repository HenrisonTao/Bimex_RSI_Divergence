# -*- coding: utf-8 -*-
import arch as trading

MonitorBot= trading.OnTick("BTC/USD","5m",7)
MonitorBot.main_job()
