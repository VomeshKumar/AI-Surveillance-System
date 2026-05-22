import os
import secrets
import smtplib
import bcrypt
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, select
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from app.database.postgres import get_db_session
from app.database.models import UserModel
from app.database.redis_cache import redis_manager
from app.schemas.detection_schema import TokenResponse


# ---------------------------------------------------
# SECURITY CONFIG
# ---------------------------------------------------
SECRET_KEY = os.getenv(
    "JWT_SECRET",
    "super-secret-fallback-key-change-in-prod"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


# ---------------------------------------------------
# PASSWORD + OAUTH
# ---------------------------------------------------
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login"
)


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"]
)


class ManagedUserResponse(BaseModel):
    id: int
    name: str
    email: str
    operatorId: str
    isActive: bool


class ManagedUserCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=120)
    password: str = Field(..., min_length=1, max_length=128)
    isActive: bool = True


class ManagedUserUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=120)
    password: Optional[str] = Field(default=None, max_length=128)
    isActive: bool = True


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=120)


class ResetPasswordWithOtpRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=120)
    otp: str = Field(..., min_length=4, max_length=10)
    newPassword: str = Field(..., min_length=6, max_length=128)
    confirmPassword: str = Field(..., min_length=6, max_length=128)


class ChangePasswordRequest(BaseModel):
    currentPassword: str = Field(..., min_length=1, max_length=128)
    newPassword: str = Field(..., min_length=6, max_length=128)
    confirmPassword: str = Field(..., min_length=6, max_length=128)


class PasswordResetOtpRecord(BaseModel):
    email: str
    otp: str
    expires_at: datetime


password_reset_otps: dict[str, PasswordResetOtpRecord] = {}
ROLE_ID_PREFIXES = {
    "security_officer": "OP",
    "security_personal": "OP",
}
OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "600"))
LOGIN_RATE_LIMIT = int(os.getenv("LOGIN_RATE_LIMIT", "5"))
LOGIN_RATE_WINDOW_SECONDS = int(os.getenv("LOGIN_RATE_WINDOW_SECONDS", "30"))
OTP_RATE_LIMIT = int(os.getenv("OTP_RATE_LIMIT", "3"))
OTP_RATE_WINDOW_SECONDS = int(os.getenv("OTP_RATE_WINDOW_SECONDS", "600"))


def serialize_managed_user(user: UserModel) -> ManagedUserResponse:
    fallback_email = user.email or f"{user.username}@aiflow.local"
    fallback_name = user.full_name or user.username

    return ManagedUserResponse(
        id=user.id,
        name=fallback_name,
        email=fallback_email,
        operatorId=user.username,
        isActive=bool(user.is_active),
    )


def normalize_user_role(role: str) -> str:
    normalized_role = role.strip().lower()

    if normalized_role in {"security_personal", "security", "guard"}:
        return "security_officer"

    return normalized_role


async def generate_unique_user_identifier(db: AsyncSession, role: str) -> str:
    normalized_role = normalize_user_role(role)
    prefix = ROLE_ID_PREFIXES.get(normalized_role, "USR")

    if normalized_role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin ID must be provided manually",
        )

    for sequence in range(1, 1_000_000):
        candidate = f"{prefix}{sequence:03d}"
        existing_user = await db.execute(
            select(UserModel).where(UserModel.username == candidate)
        )

        if existing_user.scalar_one_or_none() is None:
            return candidate

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unable to generate a unique user ID right now",
    )


def generate_password_reset_otp() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def get_password_reset_otp_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=10)


def _otp_key(email: str) -> str:
    return f"ai:otp:{email}"


def _rate_limit_key(scope: str, identifier: str) -> str:
    return f"ai:rate_limit:{scope}:{identifier}"


async def enforce_rate_limit(scope: str, identifier: str, limit: int, window_seconds: int) -> None:
    redis_client = redis_manager.redis_client
    if redis_client is None:
        return

    key = _rate_limit_key(scope, identifier)
    try:
        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, window_seconds)
        if current > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Try again in {window_seconds}s.",
            )
    except HTTPException:
        raise
    except Exception:
        # Fail open for rate limiter storage errors to avoid auth outage.
        return


async def store_password_reset_otp(email: str, otp: str, expires_at: datetime) -> None:
    redis_client = redis_manager.redis_client
    if redis_client is None:
        password_reset_otps[email] = PasswordResetOtpRecord(email=email, otp=otp, expires_at=expires_at)
        return

    await redis_client.set(_otp_key(email), otp, ex=OTP_TTL_SECONDS)


async def clear_password_reset_otp(email: str) -> None:
    redis_client = redis_manager.redis_client
    if redis_client is None:
        password_reset_otps.pop(email, None)
        return

    await redis_client.delete(_otp_key(email))


def send_password_reset_email(recipient_email: str, otp: str) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_sender = os.getenv("SMTP_SENDER_EMAIL") or smtp_username
    smtp_sender_name = os.getenv("SMTP_SENDER_NAME", "AI Surveillance System")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    if not smtp_host or not smtp_sender:
        raise RuntimeError("SMTP configuration is incomplete")
    message = EmailMessage()
    message["Subject"] = "Password reset OTP"
    message["From"] = f"{smtp_sender_name} <{smtp_sender}>"
    message["To"] = recipient_email
    message.set_content(
        "\n".join(
            [
                "Password reset request received.",
                f"Your OTP is: {otp}",
                "This OTP will expire in 10 minutes.",
                "If you did not request this, you can ignore this email.",
            ]
        )
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
        if smtp_use_tls:
            smtp.starttls()

        if smtp_username and smtp_password:
            smtp.login(smtp_username, smtp_password)

        smtp.send_message(message)


def validate_reset_password_payload(payload: ResetPasswordWithOtpRequest) -> None:
    if payload.newPassword != payload.confirmPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirm password do not match",
        )

    if payload.newPassword.strip() != payload.newPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot start or end with spaces",
        )


def validate_change_password_payload(payload: ChangePasswordRequest) -> None:
    if payload.newPassword != payload.confirmPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirm password do not match",
        )

    if payload.currentPassword.strip() != payload.currentPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password cannot start or end with spaces",
        )

    if payload.newPassword.strip() != payload.newPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot start or end with spaces",
        )

    if payload.currentPassword == payload.newPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from your current password",
        )


async def get_valid_password_reset_otp(email: str, otp: str) -> PasswordResetOtpRecord:
    normalized_email = email.strip().lower()
    redis_client = redis_manager.redis_client

    if redis_client is not None:
        stored_otp = await redis_client.get(_otp_key(normalized_email))
        if stored_otp is None or str(stored_otp) != otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP",
            )
        return PasswordResetOtpRecord(
            email=normalized_email,
            otp=otp,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=OTP_TTL_SECONDS),
        )

    otp_record = password_reset_otps.get(normalized_email)

    if otp_record is None or otp_record.otp != otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP",
        )

    if otp_record.expires_at < datetime.now(timezone.utc):
        password_reset_otps.pop(normalized_email, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired",
        )

    return otp_record


# ---------------------------------------------------
# PASSWORD HELPERS
# ---------------------------------------------------
def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except Exception:
            return False


def get_password_hash(password: str) -> str:
    try:
        return pwd_context.hash(password)
    except Exception:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# ---------------------------------------------------
# TOKEN CREATION
# ---------------------------------------------------
def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta
        else timedelta(minutes=15)
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


# ---------------------------------------------------
# CURRENT AUTH USER
# ---------------------------------------------------
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Inject currently authenticated DB user
    into protected routes.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username: str = payload.get("sub")

        if username is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    result = await db.execute(
        select(UserModel).where(
            UserModel.username == username
        )
    )

    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    # inactive users blocked
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive account"
        )

    return user


# ---------------------------------------------------
# ADMIN RBAC
# ---------------------------------------------------
def require_admin(
    current_user: UserModel = Depends(get_current_user)
):
    """
    Allow only admin users to access
    mutation / destructive routes.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return current_user


# ---------------------------------------------------
# LOGIN API
# ---------------------------------------------------
@router.post("/login", response_model=TokenResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db_session),
    request: Request = None,
):
    """
    Authenticate internal security user
    and return JWT token.
    """
    # Rate-limit login attempts by IP to prevent brute-force attacks
    if request is not None and request.client:
        await enforce_rate_limit(
            scope="login_ip",
            identifier=request.client.host,
            limit=LOGIN_RATE_LIMIT,
            window_seconds=LOGIN_RATE_WINDOW_SECONDS,
        )

    result = await db.execute(
        select(UserModel).where(
            UserModel.username == form_data.username
        )
    )

    user = result.scalar_one_or_none()

    # invalid username/password
    if not user or not verify_password(
        form_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # disabled account
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive account"
        )

    access_token_expires = timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    access_token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role
        },
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "name": user.full_name or user.username,
    }


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def request_password_reset_otp(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db_session),
    request: Request = None,
):
    normalized_email = payload.email.strip().lower()
    await enforce_rate_limit(
        scope="forgot_password_email",
        identifier=normalized_email,
        limit=OTP_RATE_LIMIT,
        window_seconds=OTP_RATE_WINDOW_SECONDS,
    )
    if request is not None and request.client:
        await enforce_rate_limit(
            scope="forgot_password_ip",
            identifier=request.client.host,
            limit=OTP_RATE_LIMIT,
            window_seconds=OTP_RATE_WINDOW_SECONDS,
        )

    result = await db.execute(
        select(UserModel).where(UserModel.email == normalized_email)
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registered email not found",
        )

    otp = generate_password_reset_otp()
    expiry = get_password_reset_otp_expiry()
    await store_password_reset_otp(normalized_email, otp, expiry)

    try:
        send_password_reset_email(normalized_email, otp)
    except Exception as exc:
        await clear_password_reset_otp(normalized_email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to send OTP email: {exc}",
        ) from exc

    return {
        "message": "OTP sent successfully to your registered email address."
    }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password_with_otp(
    payload: ResetPasswordWithOtpRequest,
    db: AsyncSession = Depends(get_db_session),
):
    validate_reset_password_payload(payload)
    normalized_email = payload.email.strip().lower()
    await get_valid_password_reset_otp(normalized_email, payload.otp.strip())

    result = await db.execute(
        select(UserModel).where(UserModel.email == normalized_email)
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found for this email",
        )

    user.hashed_password = get_password_hash(payload.newPassword)

    try:
        await db.commit()
        await clear_password_reset_otp(normalized_email)
        return {"message": "Password updated successfully"}
    except Exception:
        await db.rollback()
        raise


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    validate_change_password_payload(payload)

    if not verify_password(payload.currentPassword, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = get_password_hash(payload.newPassword)

    try:
        await db.commit()
        return {"message": "Password changed successfully"}
    except Exception:
        await db.rollback()
        raise


@router.get("/users", response_model=list[ManagedUserResponse])
async def get_managed_users(
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(require_admin),
):
    result = await db.execute(
        select(UserModel)
        .where(UserModel.role != "admin")
        .order_by(desc(UserModel.created_at))
    )

    users = result.scalars().all()
    return [serialize_managed_user(user) for user in users]


@router.post("/users", response_model=ManagedUserResponse, status_code=status.HTTP_201_CREATED)
async def create_managed_user(
    payload: ManagedUserCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(require_admin),
):
    normalized_email = payload.email.strip().lower()
    normalized_name = payload.name.strip()
    generated_operator_id = await generate_unique_user_identifier(db, "security_officer")

    new_user = UserModel(
        username=generated_operator_id,
        full_name=normalized_name,
        email=normalized_email,
        hashed_password=get_password_hash(payload.password.strip()),
        role="security_officer",
        is_active=payload.isActive,
    )

    try:
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return serialize_managed_user(new_user)
    except Exception:
        await db.rollback()
        raise


@router.put("/users/{user_id}", response_model=ManagedUserResponse)
async def update_managed_user(
    user_id: int,
    payload: ManagedUserUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(require_admin),
):
    user = await db.get(UserModel, user_id)

    if user is None or user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operator not found",
        )

    normalized_email = payload.email.strip().lower()
    normalized_name = payload.name.strip()

    user.full_name = normalized_name
    user.email = normalized_email
    user.is_active = payload.isActive

    if payload.password and payload.password.strip():
        user.hashed_password = get_password_hash(payload.password.strip())

    try:
        await db.commit()
        await db.refresh(user)
        return serialize_managed_user(user)
    except Exception:
        await db.rollback()
        raise


@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
async def delete_managed_user(
    user_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(require_admin),
):
    user = await db.get(UserModel, user_id)

    if user is None or user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operator not found",
        )

    try:
        await db.delete(user)
        await db.commit()
        return {"message": "Operator deleted successfully", "id": user_id}
    except Exception:
        await db.rollback()
        raise
