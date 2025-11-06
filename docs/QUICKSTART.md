# 🚀 راهنمای سریع شروع کار

## ⚠️ مهم: پوشه صحیح!

**بکند Python در این پوشه است:** `portfolio-doctor-api-python`

**پوشه قدیمی TypeScript:** `portfolio-doctor-api` (دیگر استفاده نمی‌شود - کدها حذف شدند)

## 📋 مراحل سریع

### 1. رفتن به پوشه صحیح

```powershell
cd portfolio-doctor-api-python
```

### 2. ایجاد و فعال‌سازی Virtual Environment

```powershell
# ایجاد venv
py -m venv venv

# فعال‌سازی
venv\Scripts\Activate.ps1
```

**یا از اسکریپت خودکار:**
```powershell
.\install.ps1
```

### 3. نصب Dependencies (اگر نیاز باشد)

```powershell
py -m pip install -r requirements.txt
```

### 4. اجرای سرور

```powershell
python main.py
```

**یا با uvicorn:**
```powershell
uvicorn main:app --reload --port 3001
```

## 🔍 بررسی پوشه صحیح

باید این فایل‌ها را ببینید:
- ✅ `main.py`
- ✅ `app/` (پوشه)
- ✅ `requirements.txt`
- ✅ `config.py`

## 🆘 اگر خطا گرفتید

### خطا: "can't open file 'main.py'"

**دلیل:** در پوشه اشتباه هستید!

**راه حل:**
```powershell
# بررسی پوشه فعلی
pwd

# رفتن به پوشه صحیح
cd portfolio-doctor-api-python

# بررسی وجود main.py
Test-Path main.py  # باید True برگرداند
```

### خطا: "No module named 'fastapi'"

**دلیل:** Dependencies نصب نشده‌اند

**راه حل:**
```powershell
# مطمئن شوید venv فعال است
# باید (venv) در ابتدای خط فرمان ببینید

# نصب dependencies
py -m pip install -r requirements.txt
```

## 📍 ساختار پوشه‌ها

```
Portfolio/
├── portfolio-doctor-api/          ❌ قدیمی - حذف شده
│   └── (فایل‌های TypeScript حذف شدند)
│
└── portfolio-doctor-api-python/  ✅ جدید - استفاده کنید
    ├── main.py                   ✅ نقطه ورود
    ├── app/                      ✅ کدهای اصلی
    ├── requirements.txt          ✅ Dependencies
    └── config.py                 ✅ تنظیمات
```

## ✅ چک‌لیست قبل از اجرا

- [ ] در پوشه `portfolio-doctor-api-python` هستید
- [ ] Virtual environment ایجاد و فعال شده (`(venv)` در خط فرمان)
- [ ] Dependencies نصب شده‌اند
- [ ] فایل `main.py` وجود دارد

## 🎯 دستور کامل در یک خط

```powershell
cd portfolio-doctor-api-python; if (-not (Test-Path "venv")) { py -m venv venv }; venv\Scripts\Activate.ps1; python main.py
```

