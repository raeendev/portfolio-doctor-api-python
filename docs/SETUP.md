# راه‌اندازی Virtual Environment برای Portfolio Doctor API

## ⚠️ درباره پیام "No pyvenv.cfg file"

این پیام یک **هشدار** است، نه خطا! معمولاً مشکلی ایجاد نمی‌کند و می‌توانید ادامه دهید.

## 📋 مراحل نصب و راه‌اندازی

### 1. بررسی نصب Python

```bash
python --version
# باید Python 3.8 یا بالاتر باشد
```

اگر Python نصب نیست:
- دانلود از: https://www.python.org/downloads/
- هنگام نصب، گزینه "Add Python to PATH" را فعال کنید

### 2. ایجاد Virtual Environment

```bash
# در پوشه portfolio-doctor-api-python
python -m venv venv
```

**نکته:** اگر پیام "No pyvenv.cfg file" دیدید، نگران نباشید! این فقط یک هشدار است.

### 3. فعال‌سازی Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

بعد از فعال‌سازی، باید `(venv)` در ابتدای خط فرمان ببینید.

### 4. نصب Dependencies

```bash
pip install -r requirements.txt
```

### 5. اجرای سرور

```bash
# روش 1: مستقیم با Python
python main.py

# روش 2: با uvicorn (پیشنهادی)
uvicorn main:app --reload --port 3001
```

### 6. تست API

بعد از اجرا، این آدرس‌ها را بررسی کنید:
- API Root: http://localhost:3001/api
- Swagger Docs: http://localhost:3001/api/docs
- Health Check: http://localhost:3001/api/health

## 🔧 عیب‌یابی

### مشکل: python command not found
**راه حل:** Python را به PATH اضافه کنید یا از `py` به جای `python` استفاده کنید:
```bash
py -m venv venv
```

### مشکل: pip install خطا می‌دهد
**راه حل:** pip را آپدیت کنید:
```bash
python -m pip install --upgrade pip
```

### مشکل: virtual environment ایجاد نمی‌شود
**راه حل:** 
1. مطمئن شوید Python 3.8+ نصب است
2. از دستور `python -m venv venv --clear` استفاده کنید
3. اگر هنوز کار نکرد، از `virtualenv` استفاده کنید:
   ```bash
   pip install virtualenv
   virtualenv venv
   ```

## 📝 ساختار پروژه

```
portfolio-doctor-api-python/
├── app/              # کدهای اصلی برنامه
├── venv/            # Virtual environment (بعد از ایجاد)
├── main.py          # نقطه ورود برنامه
├── requirements.txt  # Dependencies
└── config.py        # تنظیمات
```

## ✅ بعد از نصب موفق

اگر همه چیز درست کار کرد، باید این خروجی را ببینید:
```
Portfolio Doctor API (Python) is starting...
Database connected successfully
INFO:     Uvicorn running on http://0.0.0.0:3001
```

## 🆘 نیاز به کمک؟

اگر مشکلی داشتید، مطمئن شوید:
1. ✅ Python 3.8+ نصب است
2. ✅ Virtual environment فعال است
3. ✅ همه dependencies نصب شده‌اند
4. ✅ پورت 3001 آزاد است

