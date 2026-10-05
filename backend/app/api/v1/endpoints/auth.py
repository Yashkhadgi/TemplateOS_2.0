from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, Token
from app.schemas.user import UserProfileRead, UserRead

router = APIRouter()


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: DbSession) -> User:
    email = payload.email.lower()
    existing_user = db.scalar(select(User).where(func.lower(User.email) == email))
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        hashed_password=hash_password(payload.password),
        role="normal_user",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        ) from None
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: DbSession) -> Token:
    email = payload.email.lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserProfileRead)
def my_profile(current_user: CurrentUser) -> User:
    return current_user
