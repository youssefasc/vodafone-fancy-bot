# 🔍 Vodafone Fancy Numbers Bot

بوت بيفحص موقع فودافون مصر كل ساعة ويبعتلك على تيليجرام لو لقى أرقام مميزة جديدة.

## ✅ خطوات الإعداد

### 1. ارفع الكود على GitHub

- اعمل **New Repository** (اسمه مثلاً `vodafone-bot`)
- ارفع الملفات دي:
  ```
  scraper.py
  .github/workflows/check.yml
  ```

### 2. حط التوكنات في GitHub Secrets

روح على: **Settings → Secrets and variables → Actions → New repository secret**

أضف سيكريتين:

| Name | Value |
|------|-------|
| `TELEGRAM_TOKEN` | توكن البوت بتاعك |
| `CHAT_ID` | الـ chat_id بتاعك |

### 3. فعّل GitHub Actions

- روح على تاب **Actions** في الريبو
- لو ظهرلك زرار "Enable Actions" اضغطه

### 4. تجربة يدوية

- روح **Actions → Vodafone Fancy Numbers Bot → Run workflow**
- اضغط **Run workflow** وشوف النتيجة

---

## 🌟 إيه اللي بيتعتبر رقم مميز؟

- أرقام متكررة: `01001111111`
- أرقام متسلسلة: `01012345678`
- نص متكرر: `01012341234`
- أول أو آخر 4 متكررين: `01001111xxxx`
- رقمين فريدين بس في الكل: `01010101010`

---

## 📱 مثال رسالة تيليجرام

```
🌟 أرقام مميزة جديدة على فودافون!

📱 0100-1111-111  💰 5000 EGP
📱 0101-2345-678  💰 3500 EGP

🔗 شوف الكل هنا
```
