@echo off
REM نصب Dependencies برای Portfolio Doctor API
echo ========================================
echo نصب Dependencies برای Portfolio Doctor API
echo ========================================
echo.

REM بررسی Python
py --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python نصب نیست!
    echo لطفاً از https://www.python.org/downloads/ نصب کنید
    pause
    exit /b 1
)

echo [1/3] ایجاد Virtual Environment...
py -m venv venv
if errorlevel 1 (
    echo [ERROR] خطا در ایجاد venv
    pause
    exit /b 1
)
echo [OK] Virtual Environment ایجاد شد
echo.

echo [2/3] فعال‌سازی Virtual Environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] خطا در فعال‌سازی venv
    pause
    exit /b 1
)
echo [OK] Virtual Environment فعال شد
echo.

echo [3/3] نصب Dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] خطا در نصب dependencies
    pause
    exit /b 1
)
echo.
echo ========================================
echo [SUCCESS] نصب با موفقیت انجام شد!
echo ========================================
echo.
echo برای اجرای سرور:
echo   1. venv\Scripts\activate
echo   2. python main.py
echo.
pause

