import requests
import time
import pandas as pd
from datetime import datetime, timezone
import os

# =====================
# CONFIG (AMBIL DARI RENDER ENV)
# =====================
TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SYMBOL = "XAUUSDT"
TF = "5m"  # ganti ke "15m" kalau mau

PIP_SIZE = 0.1
DEFAULT_PIP = 35 if TF == "5m" else 45
MIN_RANGE = DEFAULT_PIP * PIP_SIZE

# =====================
# TELEGRAM
# =====================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, json=data)

# =====================
# GET DATA
# =====================
def get_data():
    url = f"https://api.binance.com/api/v3/klines?symbol={SYMBOL}&interval={TF}&limit=100"
    data = requests.get(url).json()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "_","_","_","_","_","_"
    ])

    df["open"] = df["open"].astype(float)
    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["time"] = pd.to_datetime(df["time"], unit='ms', utc=True)

    return df

# =====================
# TIME LEFT
# =====================
def seconds_to_close(df):
    last_open = df.iloc[-1]["time"]
    tf_minutes = 5 if TF == "5m" else 15
    close_time = last_open + pd.Timedelta(minutes=tf_minutes)
    now = datetime.now(timezone.utc)
    return (close_time - now).total_seconds()

# =====================
# LOGIC
# =====================
def check_signal(df):
    row = df.iloc[-1]
    prev = df.iloc[-2]

    open_ = row["open"]
    close = row["close"]
    high = row["high"]
    low = row["low"]

    body = abs(close - open_)
    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low
    wick = upper_wick + lower_wick

    total = body + wick if (body + wick) != 0 else 1e-9

    body_pct = (body / total) * 100
    wick_pct = (wick / total) * 100

    body_pips = body / PIP_SIZE
    wick_pips = wick / PIP_SIZE

    is_big = body >= MIN_RANGE
    is_wick_short = (wick / total) <= 0.3

    is_bull = close > open_
    is_bear = (close < open_) or (close > open_ and close < prev["close"])

    if is_big and is_wick_short:
        if is_bull:
            return "BUY", body_pips, body_pct, wick_pips, wick_pct
        elif is_bear:
            return "SELL", body_pips, body_pct, wick_pips, wick_pct

    return None, body_pips, body_pct, wick_pips, wick_pct

# =====================
# LOOP
# =====================
last_bar = None
sent = False

send_telegram("🤖 BOT RUNNING (Momentum Candle)")

while True:
    try:
        df = get_data()
        current_bar = df.iloc[-1]["time"]

        if last_bar is None or current_bar != last_bar:
            last_bar = current_bar
            sent = False

        sec_left = seconds_to_close(df)

        signal, body_pips, body_pct, wick_pips, wick_pct = check_signal(df)

        if 20 <= sec_left <= 90 and not sent and signal:
            tf_label = "M5" if TF == "5m" else "M15"

            msg = (
                f"{'🚀' if signal=='BUY' else '🔻'} {signal} XAUUSD {tf_label} (pre-close)\n"
                f"Momentum Candle\n\n"
                f"Body  : {body_pips:.1f} pip ({body_pct:.1f}%)\n"
                f"Wicks : {wick_pips:.1f} pip ({wick_pct:.1f}%)"
            )

            send_telegram(msg)
            print(msg)
            sent = True

    except Exception as e:
        print("Error:", e)

    time.sleep(5)
