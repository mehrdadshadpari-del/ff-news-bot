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

MORNING_START_HOUR = 0   # از این ساعت (به وقت تهران) پیام صبحگاهی ارسال می‌شود
MORNING_END_HOUR = 24    # بعد از این ساعت دیگر پیام صبحگاهی ارسال نمی‌شود
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

SEND_NOW_ALERT = True  # اگه نمی‌خوای پیام «زمان خبر رسید» بره، False کن


def group_by_time(events):
    groups = {}
    for e in sorted(events, key=lambda x: x["time"]):
        groups.setdefault(e["time"].isoformat(), []).append(e)
    return groups


def alert_text(group, left):
    minutes = int(left.total_seconds() // 60)
    when = "یک ساعت دیگر" if minutes >= 50 else f"{minutes} دقیقه دیگر"
    lines = ["🚨 <b>هشدار مدیریت معامله در زمان خبر</b>", ""]
    for e in group:
        lines.append(
            f"{cur_line(e['currency'])}\n{html.escape(to_fa(e['title']))}\n"
        )
    lines.append(f"⏰ ساعت {group[0]['time']:%H:%M} به وقت تهران ({when})")
    lines.append("")
    lines.append(CHANNEL_TAG)
    return "\n".join(lines)


def alert_now_text(group):
    lines = ["🔔 <b>زمان خبر مهم رسید</b>", ""]
    for e in group:
        lines.append(
            f"{cur_line(e['currency'])}\n{html.escape(to_fa(e['title']))}\n"
        )
    lines.append(f"⏰ ساعت {group[0]['time']:%H:%M} به وقت تهران (همین الان)")
    lines.append("")
    lines.append(CHANNEL_TAG)
    return "\n".join(lines)


def safe_send(text):
    try:
        send(text)
        return True
    except Exception as exc:
        print(f"send failed: {exc}", file=sys.stderr)
        return False


def main():
    now = datetime.now(TEHRAN)
    print(f"[{now:%Y-%m-%d %H:%M}] شروع اجرا")
    try:
        events = fetch_events()
    except Exception as exc:
        print(f"feed error: {exc}", file=sys.stderr)
        return

    state = load_state()
    today = now.date()
    important = [e for e in events if e["impact"] == "High"]
    print(f"کل رویدادها: {len(events)} | خبر مهم: {len(important)}")

    # 1) پیام صبحگاهی (یک بار در روز)
    if state["morning_sent"] != today.isoformat() and MORNING_START_HOUR <= now.hour < MORNING_END_HOUR:
        todays = sorted((e for e in events if e["time"].date() == today), key=lambda e: e["time"])
        if safe_send(morning_text(todays)):
            state["morning_sent"] = today.isoformat()
            print("پیام صبحگاهی ارسال شد")
    else:
        print("پیام صبحگاهی: نوبتش نیست (قبلاً رفته یا خارج از بازه ساعت)")

    # 2) هشدار یک ساعت قبل (یک پیام برای هر ساعت انتشار)
    for slot, group in group_by_time(important).items():
        if slot in state["alerts"]:
            continue
        left = group[0]["time"] - now
        if timedelta(0) < left <= ALERT_BEFORE:
            if safe_send(alert_text(group, left)):
                state["alerts"].append(slot)
                print(f"هشدار یک ساعت قبل ارسال شد: {slot}")

    # 3) هشدار «زمان خبر رسید»
    if SEND_NOW_ALERT:
        for slot, group in group_by_time(important).items():
            if slot in state["alerts_now"]:
                continue
            passed = now - group[0]["time"]
            if timedelta(0) <= passed <= ALERT_NOW_WINDOW:
                if safe_send(alert_now_text(group)):
                    state["alerts_now"].append(slot)
                    print(f"هشدار زمان خبر ارسال شد: {slot}")

    state["alerts"] = state["alerts"][-200:]
    state["alerts_now"] = state["alerts_now"][-200:]
    save_state(state)
    print("تمام شد")


if __name__ == "__main__":
    main()
