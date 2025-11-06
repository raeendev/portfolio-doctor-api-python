# راه‌اندازی Virtual Environment

## ایجاد Virtual Environment

```bash
# Windows
python -m venv venv

# فعال‌سازی
venv\Scripts\activate

# نصب dependencies
pip install -r requirements.txt
```

## اجرای برنامه

```bash
# فعال کردن venv
venv\Scripts\activate

# اجرای سرور
python main.py

# یا با uvicorn
uvicorn main:app --reload --port 3001
```

## نکته

اگر پیام "No pyvenv.cfg file" دریافت کردید:
1. مطمئن شوید Python 3.8+ نصب است
2. virtual environment را مجدداً ایجاد کنید:
   ```bash
   python -m venv venv --clear
   ```

