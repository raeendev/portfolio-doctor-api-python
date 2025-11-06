# 🔧 حل مشکل pip و Virtual Environment

## مشکل: "Fatal error in launcher: Unable to create process"

این خطا زمانی رخ می‌دهد که `pip.exe` به یک virtual environment قدیمی اشاره می‌کند که دیگر وجود ندارد.

## ✅ راه حل‌ها

### روش 1: استفاده از `python -m pip` (پیشنهادی)

```powershell
# به جای pip
python -m pip install -r requirements.txt

# یا
py -m pip install -r requirements.txt
```

### روش 2: استفاده از اسکریپت خودکار

**Windows (Batch):**
```cmd
install.bat
```

**Windows (PowerShell):**
```powershell
.\install.ps1
```

### روش 3: ایجاد venv جدید و نصب مجدد

```powershell
# حذف venv قدیمی (اگر وجود دارد)
Remove-Item -Recurse -Force venv -ErrorAction SilentlyContinue

# ایجاد venv جدید
py -m venv venv

# فعال‌سازی
venv\Scripts\Activate.ps1

# نصب با python -m pip
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### روش 4: تعمیر pip

```powershell
# حذف pip.exe مشکل‌دار
Remove-Item "C:\python11\Scripts\pip.exe" -ErrorAction SilentlyContinue

# نصب مجدد pip
python -m ensurepip --upgrade
```

## 📝 دستورات صحیح برای این پروژه

```powershell
# 1. رفتن به پوشه پروژه
cd portfolio-doctor-api-python

# 2. ایجاد venv (اگر ندارید)
py -m venv venv

# 3. فعال‌سازی venv
venv\Scripts\Activate.ps1

# 4. نصب dependencies (استفاده از python -m pip)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 5. اجرای سرور
python main.py
```

## ⚠️ نکات مهم

1. **همیشه از `python -m pip` استفاده کنید** به جای `pip` مستقیم
2. اگر پیام "No pyvenv.cfg file" دیدید، نگران نباشید - این فقط یک هشدار است
3. اگر خطای Execution Policy در PowerShell دیدید:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

## 🆘 اگر هنوز مشکل دارید

1. بررسی کنید Python نصب است:
   ```powershell
   py --version
   ```

2. بررسی کنید pip کار می‌کند:
   ```powershell
   py -m pip --version
   ```

3. از venv مستقیم استفاده کنید:
   ```powershell
   venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

