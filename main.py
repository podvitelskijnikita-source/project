import atexit
import hashlib
import uuid
from math import ceil

from fastapi import FastAPI, Request, Form, Response
from fastapi import HTTPException, Depends
from fastapi import Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pydantic import ValidationError

from db import Database
from models import UserRegister

app = FastAPI()

db = Database("sitebase.db")
db.create_cart_table()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

sessions = {}


def get_password_hash_and_salt(plain_password: str) -> tuple[str, str]:
    """Generates a salt and hashes the password using PBKDF2 with SHA256."""
    salt = "Hello"  # Generate a random salt
    hashed_password = hashlib.pbkdf2_hmac(
        'sha256',
        plain_password.encode('utf-8'),
        salt.encode('utf-8'),
        100000  # Number of iterations, adjust as needed for security/performance
    )
    return hashed_password.hex()


def verify_password(plain_password: str, stored_hashed_password: str) -> bool:
    """Verifies a plain password against a stored hashed password and salt."""
    hashed_password = hashlib.pbkdf2_hmac(
        'sha256',
        plain_password.encode('utf-8'),
        "Hello".encode('utf-8'),
        100000
    )
    return hashed_password.hex() == stored_hashed_password


def get_cuurrent_email(request: Request) -> str:
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    return sessions.get(session_id)

def get_current_user_data(request: Request):
    email = request.state.user
    if not email:
        return None
    return db.get_user_by_email(email)



@app.get("/", response_class=HTMLResponse)
def read_index(request: Request):
    user = request.state.user
    return templates.TemplateResponse("index.html", {"request": request, "user": user, "title": "Главная"})


@app.get("/catalog/{cat}", response_class=HTMLResponse)
def read_catalog(request: Request, cat: str, page: int = Query(1, ge=1)):
    per_page = 6
    total_goods = db.count_goods_in_category(cat)
    total_pages = ceil(total_goods / per_page)
    offset = (page - 1) * per_page

    category = db.get_goods_by_category_paginated(cat, per_page, offset)
    user = request.state.user
    return templates.TemplateResponse(
        "catalog.html",
        {
            "request": request,
            "category": category,
            "page": page,
            "user": user,
            "total_pages": total_pages,
            "cat": cat
        }
    )


def read_about(request: Request, cat: str):
    category = db.get_goods_by_category(cat)
    return templates.TemplateResponse("catalog.html", {"request": request, "category": category})


@app.get("/cart", response_class=HTMLResponse)
def view_cart(request: Request):
    user_email = request.state.user
    if not user_email:
        return RedirectResponse("/login", status_code=302)

    user = db.get_user_by_email(user_email)
    cart_items = db.get_cart(user['id'])

    total_amount = sum(item['total_price'] for item in cart_items)

    return templates.TemplateResponse("cart.html", {
        "request": request,
        "user": user_email,
        "cart_items": cart_items,
        "total_amount": total_amount,
        "title": "Корзина"
    })


@app.post("/cart/add")
def add_item_to_cart(request: Request, good_id: int = Form(...)):
    user_email = request.state.user
    if not user_email:
        return RedirectResponse(url="/login", status_code=303)

    user = db.get_user_by_email(user_email)
    db.add_to_cart(user['id'], good_id)

    referer = request.headers.get("referer")
    if referer:
        return RedirectResponse(url=referer, status_code=303)
    else:
        return RedirectResponse(url="/", status_code=303)

@app.post("/cart/remove")
def remove_item_from_cart(request: Request, good_id: int = Form(...)):
    user_email = request.state.user
    if not user_email:
        return RedirectResponse(url="/login", status_code=303)

    user = db.get_user_by_email(user_email)
    db.remove_from_cart(user['id'], good_id)

    return RedirectResponse(url="/cart", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "title": "Вход"})


@app.post("/login")
def login(request: Request, response: Response, email: str = Form(...), password: str = Form(...)):
    user = db.get_user_by_email(email)
    if not user or user["password"] != get_password_hash_and_salt(password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неверный email или пароль"})
    session_id = str(uuid.uuid4())
    sessions[session_id] = email
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(key="session_id", value=session_id, httponly=True)
    return response


@app.middleware("http")
async def add_user_to_request(request: Request, call_next):
    session_id = request.cookies.get("session_id")
    user_email = sessions.get(session_id)
    request.state.user = None
    if user_email:
        request.state.user = user_email
    response = await call_next(request)
    return response


@app.post("/logout")
def logout(response: Response, request: Request):
    session_id = request.cookies.get("session_id")
    if session_id in sessions:
        del sessions[session_id]
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session_id")
    return response


@app.get("/register", response_class=HTMLResponse)
def read_contact(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "title": "Регистрация", "errors":{}})


@app.post("/register", response_class=HTMLResponse)
def register_user(
        request: Request,
        name: str = Form(...),
        surname: str = Form(...),
        email: str = Form(...),
        password: str = Form(...)):
    errors = {}

    # 1. Валидация входных данных
    try:
        user_data = UserRegister(email=email, password=password)
    except ValidationError as e:
        for err in e.errors():
            field = err['loc'][0]

            # --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ ДЛЯ КРАСИВЫХ ОШИБОК ---
            # Проверяем, пришла ли ошибка из нашего валидатора с ValueError
            if 'ctx' in err and 'error' in err['ctx']:
                # Если да, берем чистое сообщение из ValueError
                errors[field] = str(err['ctx']['error'])
            else:
                # Иначе, берем стандартное сообщение Pydantic (например, для неверного email)
                errors[field] = err['msg']

        # Если были ошибки валидации, возвращаем шаблон с ними
        return templates.TemplateResponse("register.html", {
            "request": request,
            "title": "Регистрация",
            "name": name,
            "surname": surname,
            "email": email,
            "errors": errors
        })

    # 2. Работа с базой данных (только если валидация прошла)
    try:
        hashed_password = get_password_hash_and_salt(user_data.password)
        # db.create_table() - УБРАТЬ ОТСЮДА! Вызывайте это один раз при старте приложения.
        db.insert_user(name, surname, user_data.email, hashed_password)

        # Если пользователь успешно создан, перенаправляем на страницу входа
        return RedirectResponse(url='/login', status_code=303)

    except sqlite3.IntegrityError:  # Или другое исключение для вашей БД, отвечающее за уникальность
        # Эта ошибка возникнет, если email уже есть в базе (нарушение UNIQUE constraint)
        errors['email'] = "Пользователь с таким email уже зарегистрирован"
        return templates.TemplateResponse("register.html", {
            "request": request,
            "title": "Регистрация",
            "name": name,
            "surname": surname,
            "email": email,
            "errors": errors
        })
    except Exception as e:
        # Обработка других возможных ошибок БД
        errors['general'] = f"Произошла ошибка при регистрации: {e}"
        return templates.TemplateResponse("register.html", {
            "request": request,
            "title": "Регистрация",
            "name": name,
            "surname": surname,
            "email": email,
            "errors": errors
        })


@app.get("/order-success", response_class=HTMLResponse)
def order_success(request: Request):
    user_email = request.state.user
    if user_email:
        user = db.get_user_by_email(user_email)
        db.clear_cart(user['id'])

    return templates.TemplateResponse("order-success.html",
                                      {"request": request, "user": user_email, "title": "Успешный заказ"})


@app.get("/product/{id}", response_class=HTMLResponse)
def read_contact(request: Request, id: int):
    good = db.get_good(id)
    user = request.state.user
    return templates.TemplateResponse("product.html", {"request": request, "user": user, "good": good})


@atexit.register
def close_db():
    db.close()
