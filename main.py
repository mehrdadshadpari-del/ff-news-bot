import html
import json
import os
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "@academymehrdadT")
CHANNEL_TAG = "@academymehrdadT"

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
TEHRAN = ZoneInfo("Asia/Tehran")
STATE_FILE = "state.json"

MORNING_START_HOUR = 9   # از این ساعت (به وقت تهران) پیام صبحگاهی ارسال می‌شود
MORNING_END_HOUR = 12    # بعد از این ساعت دیگر پیام صبحگاهی ارسال نمی‌شود
ALERT_BEFORE = timedelta(minutes=60)
ALERT_NOW_WINDOW = timedelta(minutes=15)  # هشدار «زمان خبر» تا ۱۵ دقیقه بعد از زمان خبر هم ارسال می‌شود

FLAGS = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "AUD": "🇦🇺", "CAD": "🇨🇦", "NZD": "🇳🇿", "CHF": "🇨🇭", "CNY": "🇨🇳",
}
SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
    "AUD": "A$", "CAD": "C$", "NZD": "NZ$", "CHF": "₣", "CNY": "¥",
}

# ترجمه‌ی دستی چند خبر پرتکرار (برای دقت بیشتر). بقیه با مترجم خودکار ترجمه می‌شوند.
DICT = {
    "BOE Gov Bailey Speaks": "سخنرانی بیلی (رئیس بانک مرکزی انگلستان)",
    "BOJ Gov Ueda Speaks": "سخنرانی اوئدا (رئیس بانک مرکزی ژاپن)",
    "BOC Gov Macklem Speaks": "سخنرانی مکلم (رئیس بانک مرکزی کانادا)",
    "RBA Gov Bullock Speaks": "سخنرانی بولاک (رئیس بانک مرکزی استرالیا)",
    "RBNZ Gov Breman Speaks": "سخنرانی برمن (رئیس بانک مرکزی نیوزیلند)",
    "SNB Chairman Schlegel Speaks": "سخنرانی اشلگل (رئیس بانک مرکزی سوئیس)",
    "FOMC Member Waller Speaks": "سخنرانی والر (عضو فدرال رزرو)",
    "ECB Monetary Policy Meeting Accounts": "صورتجلسه سیاست پولی بانک مرکزی اروپا",
    "Average Hourly Earnings m/m": "میانگین دستمزد ساعتی ماهانه",
    "PPI m/m": "شاخص قیمت تولیدکننده (PPI) ماهانه",
    "Core PPI m/m": "PPI هسته ماهانه",
    "Non-Farm Employment Change": "تغییر اشتغال غیرکشاورزی (NFP)",
    "Unemployment Rate": "نرخ بیکاری",
    "CPI m/m": "شاخص قیمت مصرف‌کننده (CPI) ماهانه",
    "CPI y/y": "شاخص قیمت مصرف‌کننده (CPI) سالانه",
    "Core CPI m/m": "CPI هسته ماهانه",
    "Federal Funds Rate": "نرخ بهره فدرال رزرو",
    "FOMC Statement": "بیانیه FOMC",
    "FOMC Meeting Minutes": "صورتجلسه FOMC",
    "Core PCE Price Index m/m": "شاخص قیمت PCE هسته ماهانه",
    "ADP Non-Farm Employment Change": "تغییر اشتغال غیرکشاورزی ADP",
    "Unemployment Claims": "درخواست‌های بیمه بیکاری",
    "Retail Sales m/m": "فروش خرده‌فروشی ماهانه",
    "Core Retail Sales m/m": "فروش خرده‌فروشی هسته ماهانه",
    "ISM Manufacturing PMI": "شاخص PMI تولیدی ISM",
    "ISM Services PMI": "شاخص PMI خدماتی ISM",
    "Advance GDP q/q": "تولید ناخالص داخلی (GDP) فصلی - برآورد اولیه",
    "Prelim GDP q/q": "تولید ناخالص داخلی (GDP) فصلی - برآورد مقدماتی",
    "Final GDP q/q": "تولید ناخالص داخلی (GDP) فصلی - نهایی",
    "Main Refinancing Rate": "نرخ بهره اصلی (بانک مرکزی اروپا)",
    "ECB Press Conference": "کنفرانس خبری بانک مرکزی اروپا",
    "Official Bank Rate": "نرخ بهره رسمی (بانک انگلستان)",
    "MPC Official Bank Rate Votes": "رای‌گیری کمیته سیاست پولی (بانک انگلستان)",
    "BOJ Policy Rate": "نرخ بهره بانک مرکزی ژاپن",
    "Cash Rate": "نرخ بهره (بانک مرکزی استرالیا)",
    "BOC Rate Statement": "بیانیه نرخ بهره بانک مرکزی کانادا",
    "Overnight Rate": "نرخ بهره شبانه (بانک مرکزی کانادا)",
    "Official Cash Rate": "نرخ بهره رسمی (بانک مرکزی نیوزیلند)",
    "Fed Chair Powell Speaks": "سخنرانی پاول (رئیس فدرال رزرو)",
    "ECB President Lagarde Speaks": "سخنرانی لاگارد (رئیس بانک مرکزی اروپا)",
    "Crude Oil Inventories": "ذخایر نفت خام",
}

_tr_cache = {}


def to_fa(title):
    if title in DICT:
        return DICT[title]
    if title in _tr_cache:
        return _tr_cache[title]
    try:
        from deep_translator import GoogleTranslator

        time.sleep(0.5)  # برای اینکه مترجم به‌خاطر درخواست زیاد بلاک نکند
        fa = GoogleTranslator(source="en", target="fa").translate(title)
        _tr_cache[title] = fa or title
    except Exception as exc:  # اگر مترجم کار نکرد، عنوان انگلیسی ارسال می‌شود
        print(f"translate failed for {title!r}: {exc}", file=sys.stderr)
        _tr_cache[title] = title
    return _tr_cache[title]


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    state.setdefault("morning_sent", "")
    state.setdefault("alerts", [])
    state.setdefault("alerts_now", [])
    return state


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_events():
    r = requests.get(FEED_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    events = []
    for e in r.json():
        try:
            t = datetime.fromisoformat(e["date"]).astimezone(TEHRAN)
        except Exception:
            continue
        events.append(
            {
                "id": f'{e["date"]}|{e.get("country", "")}|{e.get("title", "")}',
                "time": t,
                "currency": e.get("country", ""),
                "title": e.get("title", ""),
                "impact": "High" if (e.get("impact") == "High" or (e.get("impact") == "Medium" and e.get("country") == "USD")) else e.get("impact", ""),
            }
        )
    return events


def send(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    if not r.ok:
        print("TELEGRAM ERROR:", r.status_code, r.text)
    r.raise_for_status()


def cur_line(cur):
    return f"{FLAGS.get(cur, '🏳️')} {SYMBOLS.get(cur, '')} {cur}".replace("  ", " ")


def morning_text(todays):
    high = [e for e in todays if e["impact"] == "High"]
    if high:
        lines = ["📅 <b>اخبار مهم امروز</b>", ""]
        for e in high:
            lines.append(
                f"{cur_line(e['currency'])} | ⏰ {e['time']:%H:%M}\n"
                f"{html.escape(to_fa(e['title']))}\n"
            )
        body = "\n".join(lines)
    elif any(e["impact"] == "Holiday" for e in todays):
        body = "امروز تعطیله و خبری نیست"
    else:
        body = "امروز خبر مهمی نداریم 🤲🏻"
    return f"{body}\n\n{CHANNEL_TAG}"


def alert_text(e):
    return (
        "🚨 <b>هشدار مدیریت معامله در زمان خبر</b>\n\n"
        f"{cur_line(e['currency'])}\n"
        f"{html.escape(to_fa(e['title']))}\n"
        f"⏰ ساعت {e['time']:%H:%M} به وقت تهران (یک ساعت دیگر)\n\n"
        f"{CHANNEL_TAG}"
    )


def alert_now_text(e):
    return (
        "🔔 <b>زمان خبر مهم رسید</b>\n\n"
        f"{cur_line(e['currency'])}\n"
        f"{html.escape(to_fa(e['title']))}\n"
        f"⏰ ساعت {e['time']:%H:%M} به وقت تهران (همین الان)\n\n"
        f"{CHANNEL_TAG}"
    )


def main():
    now = datetime.now(TEHRAN)
    try:
        events = fetch_events()
    except Exception as exc:
        print(f"feed error: {exc}", file=sys.stderr)
        return

    state = load_state()
    today = now.date()

    # 1) پیام صبحگاهی (یک بار در روز)
    if state["morning_sent"] != today.isoformat() and MORNING_START_HOUR <= now.hour < MORNING_END_HOUR:
        todays = sorted((e for e in events if e["time"].date() == today), key=lambda e: e["time"])
        send(morning_text(todays))
        state["morning_sent"] = today.isoformat()
