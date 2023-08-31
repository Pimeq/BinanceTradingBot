from fastapi import FastAPI
from binance.client import Client
import pandas as pd
import pandas_ta as ta
import time
import threading
import uvicorn
from datetime import timedelta,datetime
from supabase import create_client, Client as supabaseClient
from colorama import Fore
import os
from dotenv import load_dotenv
from discord_webhook import DiscordWebhook,DiscordEmbed

load_dotenv()

class Config:

    # RSI clamp values
    RSI_LOWER_THRESHOLD = 50
    RSI_UPPER_THRESHOLD = 50

    # Active token to trade
    ACTIVE_TOKEN = 'BTCUSDT'

    KLINE_INTERVAL = Client.KLINE_INTERVAL_1MINUTE
    #in seconds
    REFRESH_INTERVAL = 60


webhook = DiscordWebhook(url=os.getenv('WEBHOOK_URL'))
app = FastAPI()

apiKey = os.getenv('BINANCE_KEY')
apiSecret = os.getenv('BINANCE_SECRET')

supabaseURL : str = os.getenv('SUPABASE_URL')
supabaseKEY : str = os.getenv('SUPABASE_KEY')

supabase: supabaseClient = create_client(supabaseURL, supabaseKEY)

client = Client(apiKey, apiSecret,testnet=True)
client.API_URL = 'https://testnet.binance.vision/api'
openPositions = {}
client.timestamp_offset = client.get_server_time().get('serverTime') - time.time()*1000
cryptoSymbol = 'BTCUSDT'


botActive = False  # Flag to control bot activation
lastCandleTimestamp = None
@app.post("/toggleBot")
async def toggle_bot(status: bool):
    global botActive
    botActive = status
    return {"message": f"Bot is now {'active' if botActive else 'inactive'}"}


@app.get("/calculateRsi")
async def calculateRsiEndpoint(symbol: str):
    rsi = calculateRsi(symbol)
    if rsi is not None:
        return {"rsi": rsi}
    else:
        return {"error": "Error calculating RSI"}

@app.get("/calculateMacd")
async def calculateMacdEndpoint(symbol: str):
    macd_info = calculateMacd(symbol)
    if macd_info is not None:
        return macd_info
    else:
        return {"error": "Error calculating MACD"}

def calculateMacd(symbol):
    try:
        klines = client.futures_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1HOUR)
        close_prices = [float(kline[4]) for kline in klines]

        # Create a DataFrame for the close prices
        df = pd.DataFrame({'close': close_prices})

        # Calculate MACD using pandas-ta
        macd_info = ta.macd(df['close'], fast=12, slow=26, signal=9)

        # Get the last MACD values
        last_macd_values = macd_info.iloc[-1]

        return {
            "macd": last_macd_values['MACD_12_26_9'],
            "signal_line": last_macd_values['MACDs_12_26_9'],
            "histogram": last_macd_values['MACDh_12_26_9']
        }
    except Exception as e:
        print(f"Error calculating MACD: {str(e)}")
        return None




@app.get("/makeTrade")
async def makeTradeEndpoint(symbol: str, side: str):
    makeTrade(symbol, side)
    return {"message": f"Placed {side} order for {symbol}"}


def calculateRsi(symbol):
    try:
        klines = client.futures_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1HOUR)

        closePrices = [float(kline[4]) for kline in klines]

        # Create a DataFrame for the close prices
        df = pd.DataFrame({'close': closePrices})

        # Calculate RSI using pandas-ta
        rsi_column = ta.rsi(df['close'], length=14)
        df['RSI_14'] = rsi_column

        # Get the last RSI value
        currentRsi = df['RSI_14'].iloc[-1]
        print(closePrices[-1])
        return currentRsi
    except Exception as e:
        print(f"Error calculating RSI: {str(e)}")
        return None


def makeTrade(symbol, side, stop_loss_price=None):
    try:
        if stop_loss_price:
            # Place a stop-loss limit order
            client.futures_create_order(
                symbol=symbol,
                side='SELL' if side == Client.SIDE_BUY else 'BUY',
                type=Client.ORDER_TYPE_STOP_MARKET,
                quantity=0.01,
                stopPrice=stop_loss_price
            )
            print(Fore.YELLOW+"[ORDER SUCCESS]: "+Fore.RESET+f"Successfully placed stop-loss order for {symbol} at {stop_loss_price}")
        
        # Place the market order
        response = client.futures_create_order(
            symbol=symbol,
            side=side,
            type=Client.ORDER_TYPE_MARKET,
            quantity=0.01
        )
        print(Fore.GREEN+"[ORDER SUCCESS]: "+Fore.RESET+f"Successfully placed {side} order for {symbol}")
        return response['orderId']
        
    except Exception as e:
        print(f"Error placing {side} order: {str(e)}")


# def tradeBasedOnRsi(symbol):
#     global openPositions
#     print(openPositions)
#     # Calculate the current RSI
#     rsi = calculateRsi(symbol)
#     print(Fore.BLUE+ Fore.BLUE+ "[TRADE INFO]:"+Fore.RESET+" Current RSI =", rsi)
    
#     if rsi is not None:
#         for position in openPositions:
#             if position['symbol'] == symbol:
#                 if position['side'] == 'SELL' and rsi <= Config.RSI_LOWER_THRESHOLD:
#                     makeTrade(symbol, side=Client.SIDE_BUY)
#                     data, count = supabase.table('openPositions').delete().eq("symbol", symbol).execute()
#                     openPositions.remove(position)
#                     print(f"Closed short position for {symbol}")
#                 elif position['side'] == 'BUY' and rsi >= Config.RSI_UPPER_THRESHOLD:
#                     makeTrade(symbol, side=Client.SIDE_SELL)
#                     data, count = supabase.table('openPositions').delete().eq("symbol", symbol).execute()
#                     openPositions.remove(position)
#                     print(f"Closed long position for {symbol}")
        
#         if symbol not in [position['symbol'] for position in openPositions]:
#             if rsi <= Config.RSI_LOWER_THRESHOLD:
#                 makeTrade(symbol, side=Client.SIDE_SELL)
#                 data, count = supabase.table('openPositions').insert({'side': "SELL", 'rsiThreshold': rsi, "symbol": symbol}).execute()
#                 print(data)
#                 openPositions.append({'id': data[1][0]['id'], 'created_at': data[1][0]['created_at'], 'side': 'BUY', 'rsiThreshold': rsi, 'symbol': symbol})
#                 print(f"Opened short position for {symbol}")
#             elif rsi >= Config.RSI_UPPER_THRESHOLD:
#                 makeTrade(symbol, side=Client.SIDE_BUY)
#                 data, count = supabase.table('openPositions').insert({'side': "BUY", 'rsiThreshold': rsi, "symbol": symbol}).execute()
#                 openPositions.append({'id': data[1][0]['id'], 'created_at': data[1][0]['created_at'], 'side': 'SELL', 'rsiThreshold': rsi, 'symbol': symbol})
#                 print(f"Opened long position for {symbol}")

def tradeBasedOnIndicators(symbol):
    global openPositions
    print(openPositions)
    # Calculate the current RSI and MACD
    rsi = calculateRsi(symbol)
    macd_info = calculateMacd(symbol)
    print(Fore.BLUE+ "[TRADE INFO]:"+Fore.RESET+" Current RSI =", rsi)
    print(Fore.BLUE+ "[TRADE INFO]:"+Fore.RESET+" Current MACD =", macd_info['macd'])
    
    if rsi is not None and macd_info is not None:
        rsi_value = rsi
        macd_value = macd_info['macd']
        signal_line_value = macd_info['signal_line']
        
        for position in openPositions:
            if position['symbol'] == symbol:
                if (
                    (position['side'] == 'SELL' and rsi_value <= Config.RSI_LOWER_THRESHOLD)
                    or (position['side'] == 'SELL' and macd_value > signal_line_value)
                ):
                    
                    ClosingTradeId = makeTrade(symbol, side=Client.SIDE_BUY)
                    tradeInfo = client.futures_account_trades(symbol=symbol,orderId=ClosingTradeId)
                    calcProfit = (float(tradeInfo[0]['price']) - float(position['entryPrice'])) * 0.01
                    
                    embed = DiscordEmbed(title=f"Trade Made!",color="fc2003")
                    embed.add_embed_field(f'Closed short position for {symbol}',f'Calculated profit/loss: {calcProfit}')
                    embed.set_timestamp()
                    webhook.add_embed(embed)
                    webhook.execute()

                    supabase.table('closedPositions').insert({'profit': calcProfit,'trade_id':position['id'],'direction': 'SHORT'}).execute()
                    supabase.table('openPositions').delete().eq('id',position['id']).execute()
                    
                    openPositions.remove(position)
                    
                    print(Fore.LIGHTRED_EX+ "[TRADE INFO]:"+Fore.RESET+ f"Closed short position for {symbol} with ID: {position['id']}")

                elif ((position['side'] == 'BUY' and rsi_value >= Config.RSI_UPPER_THRESHOLD)
                       or (position['side'] == 'BUY' and macd_value < signal_line_value)):
                    
                    ClosingTradeId = makeTrade(symbol, side=Client.SIDE_SELL)
                    tradeInfo = client.futures_account_trades(symbol=symbol,orderId=ClosingTradeId)
                    calcProfit = (float(tradeInfo[0]['price']) - float(position['entryPrice'])) * 0.01

                    embed = DiscordEmbed(title=f"Trade Made!",color="49fc03")
                    embed.add_embed_field(f'Closed long position for',f'Calculated profit/loss: {calcProfit}')
                    embed.set_timestamp()
                    webhook.add_embed(embed)
                    webhook.execute()

                    supabase.table('closedPositions').insert({'profit': calcProfit,'trade_id':position['id'],'direction': 'SHORT'}).execute()
                    supabase.table('openPositions').delete().eq('id', position['id']).execute()
                    
                    openPositions.remove(position)
                    
                    print(Fore.LIGHTRED_EX+ "[TRADE INFO]:"+Fore.RESET+ f"Closed long position for {symbol} with ID: {position['id']}")
        
        if symbol not in [position['symbol'] for position in openPositions]:
            if rsi_value <= Config.RSI_LOWER_THRESHOLD and macd_value < signal_line_value:
                tradeID = makeTrade(symbol, side=Client.SIDE_SELL)
                tradeInfo = client.futures_account_trades(symbol=symbol,orderId=tradeID)

                data,count = supabase.table('openPositions').insert({'side': "SELL", 'rsiThreshold': rsi_value, 'macdThreshold': macd_value, "symbol": symbol, 'entryPrice':tradeInfo[0]['price']}).execute()
                openPositions.append({'id': data[1][0]['id'], 'created_at': data[1][0]['created_at'], 'side': 'SELL', 'rsiThreshold': rsi_value, 'macdThreshold': macd_value, 'symbol': symbol,'entryPrice': tradeInfo[0]['price']})
                
                print(Fore.LIGHTBLUE_EX+ "[TRADE INFO]:"+Fore.RESET+ f"Opened short position for {symbol}")
            elif rsi_value >= Config.RSI_UPPER_THRESHOLD and macd_value > signal_line_value:
                tradeID = makeTrade(symbol, side=Client.SIDE_BUY)
                tradeInfo = client.futures_account_trades(symbol=symbol,orderId=tradeID)
                
                data,count = supabase.table('openPositions').insert({'side': "BUY", 'rsiThreshold': rsi_value, 'macdThreshold': macd_value, "symbol": symbol,'entryPrice': tradeInfo[0]['price']}).execute()
                openPositions.append({'id': data[1][0]['id'], 'created_at': data[1][0]['created_at'], 'side': 'BUY', 'rsiThreshold': rsi_value, 'macdThreshold': macd_value, 'symbol': symbol,'entryPrice': tradeInfo[0]['price']})
                
                print(Fore.LIGHTBLUE_EX+ "[TRADE INFO]:"+Fore.RESET+ f"Opened long position for {symbol}")


def backgroundTask():
    global lastCandleTimestamp
    global cryptoSymbol
    global openPositions
    openPositions = supabase.table('openPositions').select('*').eq('symbol',cryptoSymbol).execute().data
    print(openPositions)
    while True:
        # Replace with the cryptocurrency symbol you want to trade
        print("[INFO]: Running bg task...")
        # Fetch the latest candle's timestamp
        klines = client.futures_klines(symbol=cryptoSymbol, interval=Config.KLINE_INTERVAL, limit=1)
        latestCandleTimestamp = klines[0][0]
        # Check if a new candle has appeared
        print(lastCandleTimestamp,latestCandleTimestamp)
        if lastCandleTimestamp is None or latestCandleTimestamp > lastCandleTimestamp:
            lastCandleTimestamp = latestCandleTimestamp
            print(Fore.BLUE+ "[TRADE INFO]:"+Fore.RESET+" Launching trading function")
            #tradeBasedOnRsi(cryptoSymbol)
            tradeBasedOnIndicators(cryptoSymbol)

        # Wait for an hour before the next check
        currentTime = (datetime.now() + timedelta(seconds=Config.REFRESH_INTERVAL)).strftime("%H:%M:%S")
        print("[UPDATE INFO]: Next update - "+str(currentTime))
        time.sleep(Config.REFRESH_INTERVAL)


if __name__ == '__main__':
    thread = threading.Thread(target=backgroundTask)
    thread.start()
    uvicorn.run(app, host='0.0.0.0', port=5000)