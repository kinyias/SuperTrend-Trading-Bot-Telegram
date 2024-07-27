import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
import pytz
import telegram
import schedule
import time
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram bot token and chat ID
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Function to fetch OHLCV data
def fetch_ohlcv(symbol, timeframe, limit):
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# Function to calculate ATR
def calculate_atr(df, length):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = high_low.combine(high_close, max).combine(low_close, max)
    atr = tr.rolling(window=length, min_periods=1).mean()
    return atr

# Function to calculate Supertrend
def calculate_supertrend(df, atr_length, multiplier):
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = calculate_atr(df, atr_length)
    df['basic_upperband'] = hl2 + (multiplier * df['atr'])
    df['basic_lowerband'] = hl2 - (multiplier * df['atr'])
    df['upperband'] = 0.0
    df['lowerband'] = 0.0
    df['supertrend'] = 0.0
    df['trend'] = 0

    for i in range(1, len(df)):
        df.loc[i,'upperband'] = (df['basic_upperband'][i] if df['basic_upperband'][i] < df['upperband'][i - 1] or df['close'][i - 1] > df['upperband'][i - 1] else df['upperband'][i - 1])
        df.loc[i,'lowerband'] = (df['basic_lowerband'][i] if df['basic_lowerband'][i] > df['lowerband'][i - 1] or df['close'][i - 1] < df['lowerband'][i - 1] else df['lowerband'][i - 1])
        if df['trend'][i - 1] == 1:
            df.loc[i,'trend'] = 1 if df['close'][i] > df['lowerband'][i] else -1
        else:
            df.loc[i,'trend'] = -1 if df['close'][i] < df['upperband'][i] else 1

        df.loc[i,'supertrend'] = df['lowerband'][i] if df['trend'][i] == 1 else df['upperband'][i]

    df['isUpTrend'] = df['trend'] == 1
    df['isDownTrend'] = df['trend'] == -1
    df['continue_up_trend'] = (df['trend'] == 1) & (df['trend'].shift() == 1)
    df['continue_down_trend'] = (df['trend'] == -1) & (df['trend'].shift() == -1)

    vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert(vietnam_tz)
    df['timestamp'] = df['timestamp'].apply(lambda x: x.strftime('%H:%M:%S %d/%m/%Y'))

    return df[['timestamp', 'close', 'isUpTrend', 'isDownTrend', 'continue_up_trend', 'continue_down_trend']]

# Function to send a message via Telegram
async def send_telegram_message(bot_token, chat_id, message):
    async with telegram.Bot(token=bot_token) as bot:
        try:
            await bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            print(f"Error sending Telegram message: {e}")

# Main function to run the script
def fetch_and_send():
    symbol = ['BTC/USDT','ETH/USDT','ICP/USDT','BNB/USDT']
    timeframe = '15m' #Time frame 15 minutes
    limit = 100
    atr_length = 10
    multiplier = 3.0
    for i in symbol:
        df = fetch_ohlcv(i, timeframe, limit)
        df = calculate_supertrend(df, atr_length, multiplier)
        last_two = df.tail(2)
        message = "RECOMMENDATION: BUY (Long)\n" + str(i) + "\nCURRENT PRICE: " + str(round(last_two.iloc[1]['close'],2)) + "\nTP: " + str(round(last_two.iloc[1]['close']*1.02,2)) + "\nSL: " + str(round(last_two.iloc[0]['close']*0.995,2))
        asyncio.run(send_telegram_message(BOT_TOKEN, CHAT_ID, message))  
        # Compare the 'continue_up_trend' values
        # Is up trend can to long
        # if last_two.iloc[0]['continue_up_trend'] != last_two.iloc[1]['continue_up_trend'] and last_two.iloc[1]['continue_up_trend'] == True:
        #     message = "RECOMMENDATION: BUY (Long)\n" + str(i) + "\nCURRENT PRICE: " + str(round(last_two.iloc[1]['close'],2)) + "\nTP: " + str(round(last_two.iloc[1]['close']*1.02,2)) + "\nSL: " + str(round(last_two.iloc[0]['close']*0.995,2))
        #     asyncio.run(send_telegram_message(BOT_TOKEN, CHAT_ID, message))  
        # # Is down trend can to short
        # if last_two.iloc[0]['continue_down_trend'] != last_two.iloc[1]['continue_down_trend'] and last_two.iloc[1]['continue_down_trend'] == True:
        #     message = "RECOMMENDATION: SELL (Short)\n" + str(i) + "\nCURRENT PRICE: " + str(round(last_two.iloc[1]['close'],2)) + "\nTP: " + str(round(last_two.iloc[1]['close']*0.98,2)) + "\nSL: " + str(round(last_two.iloc[0]['close']*1.005,2))
        #     asyncio.run(send_telegram_message(BOT_TOKEN, CHAT_ID, message))      
    print("On running...") # Check bot are running on server

# Schedule the job every 15 minutes
schedule.every(15).minutes.do(fetch_and_send) 
# Main loop to run the scheduled tasks
if __name__ == "__main__":
    while True:
        schedule.run_pending()
        time.sleep(1)


