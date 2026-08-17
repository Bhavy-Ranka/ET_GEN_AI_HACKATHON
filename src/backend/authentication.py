import os
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from database import UserDB, get_db

try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gen_ai", ".env"))
except ModuleNotFoundError:
    pass

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "bhavyranka@gmail.com")

if not SECRET_KEY or not ADMIN_EMAIL:
    raise ValueError("Missing required environment variables.")

try:
    import bcrypt
    if not hasattr(bcrypt, "__about__"):
        class _BcryptAbout:
            __version__ = getattr(bcrypt, "__version__", "4.0.1")
        bcrypt.__about__ = _BcryptAbout()
except ImportError:
    pass

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)
router = APIRouter()

# In-memory OTP storage: email -> {"otp": str, "expires_at": datetime, "type": str, "hashed_password": Optional[str]}
OTP_STORE: Dict[str, dict] = {}


class RequestOTPSchema(BaseModel):
    email: str
    password: str


class VerifyOTPSchema(BaseModel):
    email: str
    otp: str


class RefreshTokenSchema(BaseModel):
    refresh_token: str


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def generate_otp() -> str:
    return f"{random.randint(100000, 999999)}"


def send_otp_email(to_email: str, otp: str, purpose: str = "login") -> bool:
    load_dotenv(override=True)
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME", ADMIN_EMAIL)
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()


    subject = f"AI Smart City - OTP Code for {purpose.title()}"
    body = (
        f"Hello,\n\n"
        f"Your 6-digit OTP code for {purpose} is: {otp}\n\n"
        f"This code will expire in 10 minutes.\n"
        f"Sent from Admin ({ADMIN_EMAIL}).\n\n"
        f"Regards,\nAI Smart City Team"
    )

    print(f"[OTP SYSTEM] Sending OTP email to {to_email} (Purpose: {purpose.upper()})...")

    allow_console = os.getenv("ALLOW_CONSOLE_OTP", "false").lower() in ("true", "1", "yes")

    if not smtp_pass:
        print("[OTP SYSTEM ERROR] SMTP_PASSWORD is not set in .env! Cannot send email via SMTP.")
        if allow_console:
            print(f"[OTP DEV CONSOLE] Generated OTP for {to_email}: {otp}")
            return True
        raise HTTPException(
            status_code=500,
            detail="SMTP password not set in .env. Gmail requires a 16-character App Password (not your normal account password)."
        )

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = to_email

        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to_email], msg.as_string())
        print(f"[OTP SYSTEM] Email successfully sent to {to_email} via SMTP.")
        return True
    except smtplib.SMTPAuthenticationError as auth_exc:
        print(f"[OTP SMTP AUTH ERROR] Gmail authentication failed: {auth_exc}")
        if allow_console:
            print(f"[OTP DEV CONSOLE FALLBACK] Generated OTP for {to_email}: {otp}")
            return True
        raise HTTPException(
            status_code=500,
            detail=(
                "Gmail rejected the password (535 Bad Credentials). "
                "Google does NOT allow standard account passwords for SMTP. "
                "Please generate a 16-character 'App Password' at https://myaccount.google.com/apppasswords "
                "and set SMTP_PASSWORD in .env."
            )
        )
    except Exception as exc:
        print(f"[OTP SYSTEM ERROR] Failed to send email via SMTP: {exc}")
        if allow_console:
            print(f"[OTP DEV CONSOLE FALLBACK] Generated OTP for {to_email}: {otp}")
            return True
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send OTP email via SMTP. Error: {exc}"
        )



async def _parse_auth_request(request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        email = (form.get("username") or form.get("email") or "").strip().lower()
        password = form.get("password") or ""
        otp = (form.get("otp") or "").strip()
    else:
        try:
            body = await request.json()
            email = (body.get("email") or body.get("username") or "").strip().lower()
            password = body.get("password") or ""
            otp = (body.get("otp") or "").strip()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request payload")
    return email, password, otp


@router.post("/signup/request-otp")
async def signup_request_otp(request: Request, db: Session = Depends(get_db)):
    email, password, _ = await _parse_auth_request(request)

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    existing_user = db.query(UserDB).filter(UserDB.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email is already registered. Please log in.")

    otp = generate_otp()
    hashed_pwd = get_password_hash(password)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    OTP_STORE[email] = {
        "otp": otp,
        "expires_at": expires_at,
        "type": "signup",
        "hashed_password": hashed_pwd
    }

    send_otp_email(to_email=email, otp=otp, purpose="Sign Up")

    return {
        "msg": f"OTP sent to {email}. Please enter the 6-digit OTP to complete registration.",
        "email": email
    }




@router.post("/signup/verify-otp")
async def signup_verify_otp(request: Request, db: Session = Depends(get_db)):
    email, _, otp = await _parse_auth_request(request)

    if not email or not otp:
        raise HTTPException(status_code=400, detail="Email and OTP are required.")

    stored = OTP_STORE.get(email)
    if not stored or stored.get("type") != "signup":
        raise HTTPException(status_code=400, detail="No OTP request found for this email. Please request OTP first.")

    if datetime.now(timezone.utc) > stored["expires_at"]:
        OTP_STORE.pop(email, None)
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new OTP.")

    if stored["otp"] != otp.strip():
        raise HTTPException(status_code=400, detail="Invalid OTP code. Please try again.")

    hashed_pwd = stored["hashed_password"]
    OTP_STORE.pop(email, None)

    existing_user = db.query(UserDB).filter(UserDB.email == email).first()
    if not existing_user:
        new_user = UserDB(
            email=email,
            username=email.split("@")[0],
            hashed_password=hashed_pwd,
            auth_provider="local"
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    access_token = create_access_token(data={"sub": email})
    refresh_token = create_refresh_token(data={"sub": email})
    is_admin = (email == ADMIN_EMAIL)

    return {
        "msg": "User created and authenticated successfully",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {"email": email, "is_admin": is_admin}
    }


@router.post("/login/request-otp")
async def login_request_otp(request: Request, db: Session = Depends(get_db)):
    email, password, _ = await _parse_auth_request(request)

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")

    user = db.query(UserDB).filter(UserDB.email == email).first()
    if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    otp = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    OTP_STORE[email] = {
        "otp": otp,
        "expires_at": expires_at,
        "type": "login"
    }

    send_otp_email(to_email=email, otp=otp, purpose="Login")

    return {
        "msg": f"OTP sent to {email}. Please enter the 6-digit OTP to complete login.",
        "email": email
    }




@router.post("/login/verify-otp")
async def login_verify_otp(request: Request, db: Session = Depends(get_db)):
    email, _, otp = await _parse_auth_request(request)

    if not email or not otp:
        raise HTTPException(status_code=400, detail="Email and OTP are required.")

    stored = OTP_STORE.get(email)
    if not stored or stored.get("type") != "login":
        raise HTTPException(status_code=400, detail="No OTP request found for this email. Please request OTP first.")

    if datetime.now(timezone.utc) > stored["expires_at"]:
        OTP_STORE.pop(email, None)
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new OTP.")

    if stored["otp"] != otp.strip():
        raise HTTPException(status_code=400, detail="Invalid OTP code. Please try again.")

    OTP_STORE.pop(email, None)

    access_token = create_access_token(data={"sub": email})
    refresh_token = create_refresh_token(data={"sub": email})
    is_admin = (email == ADMIN_EMAIL)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {"email": email, "is_admin": is_admin}
    }


@router.post("/signup")
async def signup(request: Request, db: Session = Depends(get_db)):
    return await signup_request_otp(request, db)


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    return await login_request_otp(request, db)


@router.post("/refresh")
async def refresh_tokens(payload: RefreshTokenSchema, db: Session = Depends(get_db)):
    try:
        data = jwt.decode(payload.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if data.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type for refresh")

        email = data.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token claims")

        user = db.query(UserDB).filter(UserDB.email == email).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        new_access_token = create_access_token(data={"sub": email})
        new_refresh_token = create_refresh_token(data={"sub": email})
        is_admin = (email == ADMIN_EMAIL)

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "user": {"email": email, "is_admin": is_admin}
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> str:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") and payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token type")
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        return email
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
