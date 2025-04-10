import csv
import datetime
import pytz
import requests
import urllib.parse
import uuid
import yfinance as yf

def lookup(symbol):
    """Look up the current adjusted closing price for the given stock symbol using yfinance."""
    try:
        stock = yf.Ticker(symbol.upper())
        hist = stock.history(period="7d")

        if hist.empty:
            print(f"[INFO] No data found for {symbol}")
            return None

        # Get the last row (most recent date)
        last_price = round(hist["Close"].iloc[-1], 2)
        return {"symbol": symbol.upper(), "price": last_price}

    except Exception as e:
        print(f"[ERROR] Failed to retrieve data for {symbol}: {e}")
        return None
result = lookup("AAPL")
if result:
    print(f"{result['symbol']} price: ${result['price']}")
else:
    print("Symbol not found or request failed.")