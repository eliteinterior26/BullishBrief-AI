from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, time
from zoneinfo import ZoneInfo
import yfinance as yf
import pandas as pd
import numpy as np
import math
import os

app = FastAPI(title="BullishBrief AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your app domain before production.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

IST = ZoneInfo("Asia/Kolkata")

def safe_num(value):
    try:
        x = float(value)
        return round(x, 2) if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None

def safe_text(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)

def nse_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s:
        raise HTTPException(400, "Enter an NSE stock symbol.")
    if s.endswith(".NS") or s.endswith(".BO"):
        return s
    return s + ".NS"

def market_status():
    now = datetime.now(IST)
    # Basic weekday/time status. NSE holiday calendar is not yet integrated.
    if now.weekday() >= 5:
        status = "MARKET CLOSED"
        reason = "Weekend"
    elif now.time() < time(9, 15):
        status = "PRE-MARKET"
        reason = "Research and preparation for today's session"
    elif now.time() <= time(15, 30):
        status = "MARKET OPEN"
        reason = "Regular NSE session"
    else:
        status = "MARKET CLOSED"
        reason = "Prepare research for the next session"
    return {
        "status": status,
        "reason": reason,
        "time_ist": now.strftime("%d %b %Y, %I:%M:%S %p IST"),
        "holiday_calendar": "Weekends are detected; exchange holidays are not yet included."
    }

def history(symbol, period="2y", interval="1d"):
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
        return df.dropna() if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def technicals(df):
    if df.empty or len(df) < 30:
        return {"available": False, "message": "Not enough price history"}
    c = df["Close"]
    e20 = c.ewm(span=20, adjust=False).mean()
    e50 = c.ewm(span=50, adjust=False).mean()
    e200 = c.ewm(span=200, adjust=False).mean()
    rr = rsi(c)
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    last = df.iloc[-1]
    score_parts = [
        last["Close"] > e20.iloc[-1],
        e20.iloc[-1] > e50.iloc[-1],
        rr.iloc[-1] > 50,
        macd.iloc[-1] > signal.iloc[-1],
        last["Close"] > e200.iloc[-1] if len(df) >= 200 else last["Close"] > e50.iloc[-1],
    ]
    score = round(sum(bool(x) for x in score_parts) / len(score_parts) * 10, 1)
    return {
        "available": True,
        "price": safe_num(last["Close"]),
        "change_pct": safe_num((last["Close"] / df["Close"].iloc[-2] - 1) * 100),
        "rsi_14": safe_num(rr.iloc[-1]),
        "ema20": safe_num(e20.iloc[-1]),
        "ema50": safe_num(e50.iloc[-1]),
        "ema200": safe_num(e200.iloc[-1]) if len(df) >= 200 else None,
        "macd": safe_num(macd.iloc[-1]),
        "macd_signal": safe_num(signal.iloc[-1]),
        "technical_score": score,
        "data_timestamp": str(df.index[-1]),
    }

def score_fundamentals(info, hist):
    # Transparent heuristic scores; missing metrics are not silently treated as good.
    earnings_inputs = []
    for key, direction in [("revenueGrowth", 1), ("earningsGrowth", 1), ("trailingEps", 1)]:
        v = safe_num(info.get(key))
        if v is not None:
            if key == "trailingEps":
                earnings_inputs.append(1 if v > 0 else 0)
            else:
                earnings_inputs.append(max(0, min(1, (v + 0.10) / 0.40)))
    earnings = round(10 * np.mean(earnings_inputs), 1) if earnings_inputs else None

    fundamental_inputs = []
    roe = safe_num(info.get("returnOnEquity"))
    debt = safe_num(info.get("debtToEquity"))
    margin = safe_num(info.get("profitMargins"))
    if roe is not None: fundamental_inputs.append(max(0, min(1, roe / 0.25)))
    if debt is not None: fundamental_inputs.append(max(0, min(1, 1 - debt / 200)))
    if margin is not None: fundamental_inputs.append(max(0, min(1, margin / 0.25)))
    fundamentals = round(10 * np.mean(fundamental_inputs), 1) if fundamental_inputs else None

    valuation_inputs = []
    pe = safe_num(info.get("trailingPE"))
    pb = safe_num(info.get("priceToBook"))
    if pe is not None and pe > 0: valuation_inputs.append(max(0, min(1, 1 - pe / 60)))
    if pb is not None and pb > 0: valuation_inputs.append(max(0, min(1, 1 - pb / 15)))
    valuation = round(10 * np.mean(valuation_inputs), 1) if valuation_inputs else None

    risk_inputs = []
    beta = safe_num(info.get("beta"))
    if beta is not None: risk_inputs.append(max(0, min(1, 1 - abs(beta - 0.8) / 2)))
    if debt is not None: risk_inputs.append(max(0, min(1, 1 - debt / 200)))
    risk = round(10 * np.mean(risk_inputs), 1) if risk_inputs else None

    tech = technicals(hist)
    momentum = tech.get("technical_score") if tech.get("available") else None

    categories = {
        "earnings": earnings,
        "fundamentals": fundamentals,
        "relative_valuation": valuation,
        "risk": risk,
        "price_momentum": momentum,
    }
    known = [v for v in categories.values() if v is not None]
    overall = round(float(np.mean(known)), 1) if len(known) == 5 else None
    return categories, overall

def research_verdict(overall, tech):
    if overall is None:
        return "INSUFFICIENT DATA"
    if overall >= 7.5 and tech.get("available") and tech.get("technical_score", 0) >= 6:
        return "POSITIVE RESEARCH"
    if overall >= 5:
        return "MIXED / HOLD FOR REVIEW"
    return "WEAK RESEARCH"

@app.get("/api/health")
def health():
    return {"ok": True, "service": "BullishBrief AI", "time": market_status()["time_ist"]}

@app.get("/api/market")
def market():
    return market_status()

@app.get("/api/company/{raw_symbol}")
def company(raw_symbol: str):
    symbol = nse_symbol(raw_symbol)
    ticker = yf.Ticker(symbol)
    try:
        info = ticker.get_info() or {}
    except Exception:
        info = {}
    hist = history(symbol)
    tech = technicals(hist)

    if not info and hist.empty:
        raise HTTPException(404, "Company data unavailable. Check the NSE symbol or try again later.")

    name = info.get("longName") or info.get("shortName") or symbol.replace(".NS", "")
    sector = info.get("sector")
    industry = info.get("industry")
    dividends = []
    try:
        div = ticker.dividends
        if div is not None and not div.empty:
            dividends = [
                {"date": str(idx.date()), "amount": safe_num(val)}
                for idx, val in div.tail(12).items()
            ][::-1]
    except Exception:
        pass

    news = []
    try:
        for item in (ticker.news or [])[:8]:
            content = item.get("content", item)
            title = content.get("title") or item.get("title")
            if title:
                news.append({
                    "title": title,
                    "publisher": content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict) else content.get("publisher"),
                    "link": content.get("canonicalUrl", {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else item.get("link"),
                    "published": content.get("pubDate") or item.get("providerPublishTime")
                })
    except Exception:
        pass

    analyst = {}
    try:
        rec = ticker.recommendations
        if rec is not None and not rec.empty:
            latest = rec.tail(1).iloc[0].to_dict()
            analyst = {str(k): safe_num(v) for k, v in latest.items() if safe_num(v) is not None}
    except Exception:
        pass

    categories, overall = score_fundamentals(info, hist)
    facts = {
        "market_cap": safe_num(info.get("marketCap")),
        "currency": info.get("currency") or "INR",
        "website": info.get("website"),
        "employees": safe_num(info.get("fullTimeEmployees")),
        "description": info.get("longBusinessSummary"),
        "revenue": safe_num(info.get("totalRevenue")),
        "revenue_growth": safe_num(info.get("revenueGrowth")),
        "earnings_growth": safe_num(info.get("earningsGrowth")),
        "trailing_eps": safe_num(info.get("trailingEps")),
        "trailing_pe": safe_num(info.get("trailingPE")),
        "price_to_book": safe_num(info.get("priceToBook")),
        "return_on_equity": safe_num(info.get("returnOnEquity")),
        "profit_margin": safe_num(info.get("profitMargins")),
        "debt_to_equity": safe_num(info.get("debtToEquity")),
        "dividend_yield": safe_num(info.get("dividendYield")),
        "ex_dividend_date": info.get("exDividendDate"),
        "beta": safe_num(info.get("beta")),
    }
    return {
        "symbol": symbol,
        "name": name,
        "sector": sector,
        "industry": industry,
        "market": market_status(),
        "technicals": tech,
        "fundamentals": facts,
        "dividend_history": dividends,
        "news": news,
        "analyst_recommendations": analyst,
        "scores": categories,
        "overall_score": overall,
        "research_verdict": research_verdict(overall, tech),
        "score_note": "Heuristic research scores, not investment ratings. Overall score is withheld unless all five categories have data.",
        "data_note": "Yahoo Finance coverage, freshness and fields vary by company. Verify important figures with company filings and NSE disclosures."
    }

# Serve the mobile web app when backend and frontend are deployed together.
WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "mobile", "www")
if os.path.isdir(WEB_DIR):
    app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")
    @app.get("/")
    def home():
        return FileResponse(os.path.join(WEB_DIR, "index.html"))
