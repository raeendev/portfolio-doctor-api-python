# Portfolio Doctor API - Python Backend

بکند Python با FastAPI برای سیستم مدیریت پرتفولیو ارزهای دیجیتال

## ساختار پروژه

```
portfolio-doctor-api-python/
├── app/
│   ├── core/           # Core modules (database, security, dependencies)
│   ├── routers/        # API routers
│   ├── services/       # Business logic services
│   ├── schemas/        # Pydantic schemas
│   └── models/         # SQLAlchemy models
├── main.py             # FastAPI application entry point
├── config.py           # Application configuration
├── requirements.txt    # Python dependencies
└── README.md
```

## نصب و راه‌اندازی

1. نصب dependencies:
```bash
pip install -r requirements.txt
```

2. تنظیم متغیرهای محیطی:
```bash
cp .env.example .env
# سپس فایل .env را ویرایش کنید
```

3. دیتابیس:
- به صورت پیش‌فرض SQLite (فایل dev.db) با SQLAlchemy استفاده می‌شود و جداول در استارتاپ ساخته می‌شوند.

4. اجرای سرور:
```bash
python main.py
```

یا با uvicorn:
```bash
uvicorn main:app --reload --port 3001
```

## API Endpoints

- `POST /api/auth/register` - ثبت‌نام کاربر
- `POST /api/auth/login` - ورود کاربر
- `GET /api/auth/profile` - پروفایل کاربر (نیاز به JWT)
- `GET /api/portfolio` - دریافت پرتفولیو (نیاز به JWT)
- `POST /api/portfolio/sync` - همگام‌سازی پرتفولیو از صرافی‌ها (نیاز به JWT)
- `GET /api/exchanges/list` - لیست صرافی‌های موجود
- `GET /api/exchanges/connected` - صرافی‌های متصل کاربر (نیاز به JWT)
- `POST /api/exchanges/connect` - اتصال به صرافی (نیاز به JWT)

## مستندات API

پس از اجرای سرور، مستندات Swagger در آدرس زیر در دسترس است:
- `http://localhost:3001/api/docs`

## ویژگی‌ها

- ✅ Authentication با JWT
- ✅ اتصال به LBank Exchange
- ✅ دریافت و مدیریت پرتفولیو
- ✅ همگام‌سازی خودکار با صرافی‌ها
- ✅ SQLAlchemy ORM برای مدیریت دیتابیس
- ✅ مستندات خودکار با Swagger
- ✅ CORS برای ارتباط با Frontend

## ادمین پیش‌فرض (Development)
- ایمیل: `admin@example.com`
- یوزرنیم: `admin`
- پسورد: `Admin@12345`
می‌توانید با متغیرهای محیطی `ADMIN_EMAIL`، `ADMIN_USERNAME`، `ADMIN_PASSWORD` جایگزین کنید.

