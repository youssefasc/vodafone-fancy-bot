import os
import json
import time
import requests
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID        = os.environ.get("CHAT_ID", "")
SEEN_FILE      = "seen_numbers.json"

LINE_TYPES = {
    "simcard": {"label": "SIM Card (200 EGP)", "emoji": "📱"},
    "esim":    {"label": "eSIM (350 EGP)",     "emoji": "💿"},
}

def is_fancy(number: str) -> dict:
    d = number[-8:]
    if new_set := len(set(d)):
        if new_set == 1:
            return {"fancy": True, "reason": "متكررة كلها 🔥"}
    if all(int(d[i]) - int(d[i-1]) == 1 for i in range(1, len(d))):
        return {"fancy": True, "reason": "متسلسلة تصاعدي ⬆️"}
    if all(int(d[i-1]) - int(d[i]) == 1 for i in range(1, len(d))):
        return {"fancy": True, "reason": "متسلسلة تنازلي ⬇️"}
    if d[:4] == d[4:]:
        return {"fancy": True, "reason": "نصف متكرر 🔁"}
    if len(set(d[:4])) == 1:
        return {"fancy": True, "reason": "أول 4 متكررة ✨"}
    if len(set(d[4:])) == 1:
        return {"fancy": True, "reason": "آخر 4 متكررة ✨"}
    if len(set(d)) <= 2:
        return {"fancy": True, "reason": "رقمين فريدين فقط 💎"}
    if len(set(d)) <= 3 and d.count(d[0]) >= 4:
        return {"fancy": True, "reason": "شبه متكرر ⭐"}
    return {"fancy": False}

def scrape_numbers(page, line_type: str) -> list[dict]:
    """يجيب الأرقام حسب نوع الخط (simcard أو esim)"""
    print(f"📡 بجيب أرقام {line_type}...")

    # اختار نوع الخط
    if line_type == "simcard":
        page.click("text=Sim Card", timeout=10000)
    else:
        page.click("text=eSim", timeout=10000)

    time.sleep(2)

    # جيب الأرقام بـ JS
    numbers = page.evaluate("""
        () => {
            const allText = document.body.innerText;
            const regex = /01[0-9]\d{8}/g;
            return [...new Set(allText.match(regex) || [])];
        }
    """)

    # كمّل بـ Shuffle عشان تجيب أرقام أكتر
    results = list(numbers)
    seen_set = set(numbers)

    for i in range(5):
        try:
            page.click("text=Shuffle", timeout=5000)
            time.sleep(2)
            new_nums = page.evaluate("""
                () => {
                    const allText = document.body.innerText;
                    const regex = /01[0-9]\d{8}/g;
                    return [...new Set(allText.match(regex) || [])];
                }
            """)
            for n in new_nums:
                if n not in seen_set:
                    seen_set.add(n)
                    results.append(n)
        except:
            break

    print(f"✅ {line_type}: لقيت {len(results)} رقم")
    return [{"number": n, "type": line_type} for n in results]

def scrape_vodafone() -> dict:
    """بيرجع dict فيه أرقام كل نوع"""
    all_numbers = {"simcard": [], "esim": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ))

        try:
            page.goto(
                "https://eshop.vodafone.com.eg/en/lines/red/numbers",
                wait_until="networkidle",
                timeout=60000
            )
            time.sleep(3)

            for lt in ["simcard", "esim"]:
                items = scrape_numbers(page, lt)
                all_numbers[lt] = items

        except Exception as e:
            print(f"❌ خطأ: {e}")

        browser.close()

    return all_numbers

def load_seen() -> dict:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return json.load(f)
    return {"simcard": [], "esim": []}

def save_seen(seen: dict):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f)

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=data, timeout=15)
        r.raise_for_status()
        print("✅ الرسالة اتبعتت!")
    except Exception as e:
        print(f"❌ فشل الإرسال: {e}")

def main():
    print("🚀 بدأ الفحص...")

    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ مفيش TELEGRAM_TOKEN أو CHAT_ID!")
        return

    all_numbers = scrape_vodafone()
    seen = load_seen()
    new_fancy = {"simcard": [], "esim": []}

    for lt in ["simcard", "esim"]:
        seen_set = set(seen.get(lt, []))
        for item in all_numbers[lt]:
            num = item["number"]
            if num not in seen_set:
                result = is_fancy(num)
                if result["fancy"]:
                    new_fancy[lt].append({**item, **result})

    # ابعت رسالة لو في جديد
    has_new = any(new_fancy[lt] for lt in ["simcard", "esim"])

    if has_new:
        msg = "🌟 <b>أرقام مميزة جديدة على فودافون!</b>

"

        for lt in ["simcard", "esim"]:
            if new_fancy[lt]:
                info = LINE_TYPES[lt]
                msg += f"{info['emoji']} <b>{info['label']}</b>
"
                for item in new_fancy[lt]:
                    msg += f"  ├ <code>{item['number']}</code> — {item['reason']}
"
                msg += "
"

        msg += "🔗 <a href='https://eshop.vodafone.com.eg/en/lines/red/numbers'>شوف واشتري هنا</a>"
        send_telegram(msg)
    else:
        print("🔍 مفيش أرقام مميزة جديدة")

    # حفظ الأرقام المشوفة
    for lt in ["simcard", "esim"]:
        seen_list = set(seen.get(lt, []))
        for item in all_numbers[lt]:
            seen_list.add(item["number"])
        seen[lt] = list(seen_list)
    save_seen(seen)

if __name__ == "__main__":
    main()
