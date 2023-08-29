# Binance Bot

A **shrimple** Binance Bot, that uses Supabase for storing positions (open and closed).

It also uncludes REST API for making manual trades, fetching Technical Indicators and controlling the bot itself.

It features a config class for changing variables used in trades:

```python
class Config:

    # RSI clamp values
    RSI_LOWER_THRESHOLD = 30
    RSI_UPPER_THRESHOLD = 70

    # Active token to trade
    ACTIVE_TOKEN = 'BTCUSDT'

    KLINE_INTERVAL = Client.KLINE_INTERVAL_1HOUR
    #in seconds
    REFRESH_INTERVAL = 3600
```

_will implement dynamic config later (I think)_
