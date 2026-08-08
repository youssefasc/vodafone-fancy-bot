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

    # 1. متكررة كلها: 11111111
    if len(set(d)) == 1:
        return {"fancy": True, "reason": "متكررة كلها 🔥"}

    # 2. متسلسلة تصاعدي: 12345678
    if all(int(d[i]) - int(d[i-1]) == 1 for i in range(1, len(d))):
        return {"fancy": True, "reason": "متسلسلة تصاعدي ⬆️"}

    # 3. متسلسلة تنازلي: 87654321
    if all(int(d[i-1]) - int(d[i]) == 1 for i in range(1, len(d))):
        return {"fancy": True, "reason": "متسلسلة تنازلي ⬇️"}

    # 4. نصف متكرر: 12341234
    if d[:4] == d[4:]:
        return {"fancy": True, "reason": "نصف متكرر 🔁"}

    # 5. أول 4 متكررة: 11112345
    if len(set(d[:4])) == 1:
        return {"fancy": True, "reason": "أول 4 متكررة ✨"}

    # 6. آخر 4 متكررة: 12345555
    if len(set(d[4:])) == 1:
        return {"fancy": True, "reason": "آخر 4 متكررة ✨"}

    # 7. رقمين فريدين فقط: 10101010
    if len(set(d)) <= 2:
        return {"fancy": True, "reason": "رقمين فريدين فقط 💎"}

    # 8. شبه متكرر: 11100111
    if len(set(d)) <= 3 and d.count(d[0]) >= 4:
        return {"fancy": True, "reason": "شبه متكرر ⭐"}

    # 9. آخر 3 أو 4 متكررة: 1700777 أو 18008888
    for tail_len in [4, 3]:
        tail = d[-tail_len:]
        if len(set(tail)) == 1:
            return {"fancy": True, "reason": f"آخر {tail_len} متكررة 🔢"}

    # 10. مجموعتين من 3 بفرق ثابت (تصاعدي أو تنازلي): 100200 / 300400 / 700600
    d6 = d[-6:]
    if len(d6) == 6:
        g1, g2 = int(d6[:3]), int(d6[3:])
        diff = g2 - g1
        # الفرق بين المجموعتين ثابت (موجب أو سالب) ومضاعف لـ 100
        if diff != 0 and diff % 100 == 0 and g1 >= 0 and g2 >= 0:
            arrow = "⬆️" if diff > 0 else "⬇️"
            return {"fancy": True, "reason": f"مجموعتين متسلسلتين ({d6[:3]}-{d6[3:]}) {arrow}"}

    # 11. مجموعتين من 3 بمضاعفة: 100200 / 200400 / 111222
    if len(d6) == 6:
        g1, g2 = int(d6[:3]), int(d6[3:])
        if g1 > 0 and g2 == g1 * 2:
            return {"fancy": True, "reason": f"مجموعتين مضاعفة ({d6[:3]}-{d6[3:]}) ✖️"}

    # 12. مجموعتين من 4 بفرق ثابت (تصاعدي أو تنازلي): 10002000 / 70006000
    d8 = d[-8:]
    if len(d8) == 8:
        g1, g2 = int(d8[:4]), int(d8[4:])
        diff = g2 - g1
        if diff != 0 and diff % 1000 == 0 and g1 >= 0 and g2 >= 0:
            arrow = "⬆️" if diff > 0 else "⬇️"
            return {"fancy": True, "reason": f"مجموعتين متسلسلتين ({d8[:4]}-{d8[4:]}) {arrow}"}

    # 13. الرقم مقسم لـ 3 مجموعات (3-3-2) وفيها نمط: 700-600-50 أو تكرار جزئي
    if len(d) == 8:
        g1, g2, g3 = d[0:3], d[3:6], d[6:8]
        n1, n2 = int(g1), int(g2)
        diff = n1 - n2
        # أول مجموعتين بفرق ثابت (100 أو مضاعف له) + المجموعة الأخيرة أي حاجة
        if diff != 0 and diff % 100 == 0:
            return {"fancy": True, "reason": f"نمط ({g1}-{g2}-{g3}) 🎯"}
        # أول مجموعتين متطابقتين: 700-700-xx
        if g1 == g2:
            return {"fancy": True, "reason": f"مجموعتين متطابقتين ({g1}-{g2}-{g3}) 🔁"}

    # 14. أزواج متكررة داخل الرقم: 70060050 → "00" بيتكرر، أو نمط ABAB بمستوى الزوج
    pairs = [d[i:i+2] for i in range(0, 8, 2)]  # 4 أزواج
    if len(set(pairs)) <= 2:
        return {"fancy": True, "reason": f"أزواج متكررة ({'-'.join(pairs)}) 🔂"}
    # لو زوج معين اتكرر مرتين على الأقل (زي 00 في 70-06-00-50)
    from collections import Counter
    pair_counts = Counter(pairs)
    most_common_pair, freq = pair_counts.most_common(1)[0]
    if freq >= 2 and most_common_pair != "":
        return {"fancy": True, "reason": f"الزوج ({most_common_pair}) متكرر {freq} مرات 🔂"}

    # 15. آخر مجموعتين من 2 متطابقتين: xxxx-50-50
    if d[-2:] == d[-4:-2]:
        return {"fancy": True, "reason": f"آخر زوجين متطابقين ({d[-4:]}) 🔁"}

    return {"fancy": False}

def scrape_numbers(page, line_type: str) -> list[dict]:
    """يجيب الأرقام حسب نوع الخط (simcard أو esim) مع scroll تدريجي قوي"""
    print(f"📡 بجيب أرقام {line_type}...")

    # قفل أي cookie banner تاني ممكن يكون ظهر (زي لو ظهر تاني بعد تفاعل)
    close_cookie_banner(page)

    # اختار نوع الخط - مع force=True كحماية لو في overlay خفي
    target = "text=Sim Card" if line_type == "simcard" else "text=eSim"
    try:
        page.click(target, timeout=10000, force=True)
    except Exception as e:
        print(f"   ⚠️ فشل الكليك العادي ({e}); بجرب تاني بعد قفل الـ cookie banner")
        close_cookie_banner(page)
        page.click(target, timeout=10000, force=True)

    time.sleep(2)

    extract_js = """
        () => {
            const allText = document.body.innerText;
            const regex = /01[0-9]\\d{8}/g;
            return [...new Set(allText.match(regex) || [])];
        }
    """

    seen_set = set()
    results = []

    def collect():
        nums = page.evaluate(extract_js)
        added = 0
        for n in nums:
            if n not in seen_set:
                seen_set.add(n)
                results.append(n)
                added += 1
        return added

    # ── دالة تشخيصية: تلاقي كل الـ containers القابلة للـ scroll ──
    diagnose_js = """
        () => {
            const phoneRe = /01[0-9]\\d{8}/g;
            const els = [...document.querySelectorAll('*')].filter(el => {
                const s = getComputedStyle(el);
                const canScroll = /(auto|scroll)/.test(s.overflowY);
                return canScroll && el.scrollHeight > el.clientHeight + 20;
            });
            return els.map(el => ({
                tag: el.tagName,
                cls: (el.className || '').toString().slice(0, 40),
                scrollHeight: el.scrollHeight,
                clientHeight: el.clientHeight,
                numbersInside: (el.innerText.match(phoneRe) || []).length
            })).sort((a,b) => b.numbersInside - a.numbersInside).slice(0, 5);
        }
    """

    # ── تعمل scroll على *كل* الـ containers القابلة للـ scroll مرة واحدة ──
    scroll_all_js = """
        () => {
            const els = [...document.querySelectorAll('*')].filter(el => {
                const s = getComputedStyle(el);
                const canScroll = /(auto|scroll)/.test(s.overflowY);
                return canScroll && el.scrollHeight > el.clientHeight + 20;
            });
            let scrolled = 0;
            for (const el of els) {
                el.scrollTop = el.scrollHeight;
                scrolled++;
            }
            // كمان الصفحة نفسها والـ documentElement
            window.scrollTo(0, document.body.scrollHeight);
            document.documentElement.scrollTop = document.documentElement.scrollHeight;
            return scrolled;
        }
    """

    # طباعة تشخيص أول مرة بس
    diag = page.evaluate(diagnose_js)
    print(f"   🔍 لقيت {len(diag)} عنصر قابل للـ scroll، أكبرهم:")
    for d in diag[:3]:
        print(f"      - {d['tag']}.{d['cls']} | أرقام جواه: {d['numbersInside']} | scrollH:{d['scrollHeight']} clientH:{d['clientHeight']}")

    collect()  # الدفعة الأولى

    no_change_count = 0
    max_scrolls = 100  # حد أقصى للأمان

    for i in range(max_scrolls):
        prev_count = len(results)

        # 1) scroll لكل الـ containers القابلة للـ scroll
        n_scrolled = page.evaluate(scroll_all_js)

        # 2) كمان محاكاة scroll فعلي بالماوس فوق منتصف الشاشة (بيفعل أي lazy-load مبني على أحداث حقيقية)
        try:
            page.mouse.wheel(0, 2000)
        except Exception:
            pass

        # 3) كمان زرار End / PageDown كـ fallback إضافي
        try:
            page.keyboard.press("End")
        except Exception:
            pass

        time.sleep(3)  # استنى التحميل

        added = collect()

        if len(results) == prev_count:
            no_change_count += 1
            if no_change_count >= 3:
                print(f"   ⏹️  توقف الـ scroll بعد {i+1} مرة (مفيش أرقام جديدة)")
                break
        else:
            no_change_count = 0
            print(f"   📜 scroll {i+1}: +{added} رقم جديد → إجمالي {len(results)} ({n_scrolled} container اتحرك)")

    # ── Shuffle عشان نجيب أرقام مختلفة كمان ──
    for i in range(3):
        try:
            page.click("text=Shuffle", timeout=5000, force=True)
            time.sleep(2)
            collect()
            for _ in range(15):
                prev = len(results)
                page.evaluate(scroll_all_js)
                try:
                    page.mouse.wheel(0, 2000)
                except Exception:
                    pass
                time.sleep(3)
                collect()
                if len(results) == prev:
                    break
        except:
            break

    print(f"✅ {line_type}: لقيت {len(results)} رقم")
    return [{"number": n, "type": line_type} for n in results]

def close_cookie_banner(page):
    """يقفل الـ Cookie Consent Banner (OneTrust) اللي بيغطي الصفحة ويمنع الكليكات"""
    selectors_to_try = [
        "#onetrust-accept-btn-handler",       # زرار "Accept All" المعتاد بتاع OneTrust
        "button#onetrust-accept-btn-handler",
        ".onetrust-close-btn-handler",
        "#onetrust-reject-all-handler",
        "button:has-text('Accept')",
        "button:has-text('Accept All')",
        "button:has-text('I Accept')",
        "button:has-text('موافق')",
    ]

    for sel in selectors_to_try:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1500):
                btn.click(timeout=3000, force=True)
                print(f"   🍪 قفلت الـ cookie banner بـ: {sel}")
                time.sleep(1)
                return True
        except Exception:
            continue

    # لو الأزرار مش موجودة، امسح الـ overlay بالـ JS مباشرة كـ fallback أخير
    try:
        removed = page.evaluate("""
            () => {
                const selectors = [
                    '#onetrust-consent-sdk',
                    '.onetrust-pc-dark-filter',
                    '#onetrust-banner-sdk',
                    '.ot-sdk-container'
                ];
                let removedCount = 0;
                for (const sel of selectors) {
                    document.querySelectorAll(sel).forEach(el => {
                        el.remove();
                        removedCount++;
                    });
                }
                return removedCount;
            }
        """)
        if removed:
            print(f"   🍪 مسحت {removed} عنصر من الـ cookie overlay بالـ JS")
            time.sleep(1)
            return True
    except Exception as e:
        print(f"   ⚠️ فشل مسح الـ cookie overlay: {e}")

    print("   ℹ️ مفيش cookie banner ظاهر (أو اتقفل من قبل)")
    return False


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

            # ── قفل الـ Cookie Consent Banner (OneTrust) قبل أي تفاعل ──
            close_cookie_banner(page)

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
        msg = "🌟 <b>أرقام مميزة جديدة على فودافون!</b>\n\n"

        for lt in ["simcard", "esim"]:
            if new_fancy[lt]:
                info = LINE_TYPES[lt]
                msg += f"{info['emoji']} <b>{info['label']}</b>\n"
                for item in new_fancy[lt]:
                    msg += f"  ├ <code>{item['number']}</code> — {item['reason']}\n"
                msg += "\n"

        msg += "🔗 <a href='https://eshop.vodafone.com.eg/en/lines/red/numbers'>شوف واشتري هنا</a>"
        send_telegram(msg)
    else:
        print("🔍 مفيش أرقام مميزة جديدة")
        send_telegram("🔍 فحص الساعة " + __import__('datetime').datetime.now().strftime('%H:%M') + "\nمفيش أرقام مميزة جديدة على فودافون دلوقتي.")

    # حفظ الأرقام المشوفة
    for lt in ["simcard", "esim"]:
        seen_list = set(seen.get(lt, []))
        for item in all_numbers[lt]:
            seen_list.add(item["number"])
        seen[lt] = list(seen_list)
    save_seen(seen)

if __name__ == "__main__":
    main()
