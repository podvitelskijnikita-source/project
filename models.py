from pydantic import BaseModel, EmailStr, validator
import re
class UserRegister(BaseModel):
    email: EmailStr
    password: str

    @validator('password')
    def password_complexity(cls, v):
        if len(v) < 8:
            raise ValueError('Пароль должен быть не менее 8 символов')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Пароль должен содержать хотя бы одну заглавную букву')
        if not re.search(r'\d', v):
            raise ValueError('Пароль должен содержать хотя бы одну цифру')
        if not re.search(r'[^\w\s]', v):
            raise ValueError('Пароль должен содержать хотя бы один специальный символ')
        return v