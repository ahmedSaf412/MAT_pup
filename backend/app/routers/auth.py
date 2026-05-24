# backend/app/routers/auth.py
# Endpoints: POST /api/auth/register, POST /api/auth/login, GET /api/users/me

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, Trainee, Coach
from app.schemas.user import UserRegister, UserOut, TokenResponse
from app.services.auth import (
    hash_password, verify_password,
    create_access_token, get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: UserRegister, db: Session = Depends(get_db)):
    """Register a new user and auto-login (return JWT)."""
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    # Normalise role
    role = "trainee" if body.role in ("trainee", "trainer") else "coach"

    user = User(
        email           = body.email,
        hashed_password = hash_password(body.password),
        full_name       = body.full_name,
        role            = role,
        phone           = body.phone,
        is_active       = True,
    )
    db.add(user)
    db.flush()   # get user.id without committing

    # Create role-specific profile row
    if role == "trainee":
        db.add(Trainee(user_id=user.id, belt_level=body.belt_level or "white"))
    else:
        db.add(Coach(user_id=user.id))

    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db:   Session = Depends(get_db),
):
    """OAuth2 password flow — frontend sends email as 'username'."""
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the authenticated user's profile."""
    out = UserOut(
        id         = current_user.id,
        email      = current_user.email,
        role       = current_user.role,
        is_active  = current_user.is_active,
        full_name  = current_user.full_name,
        created_at = current_user.created_at,
    )
    # Attach profile extras
    if current_user.role == "trainee" and current_user.trainee_profile:
        out.belt_level = current_user.trainee_profile.belt_level
    return out


# Keep /api/users/me alias (frontend calls this after login)
users_router = APIRouter(prefix="/api/users", tags=["users"])

@users_router.get("/me", response_model=UserOut)
def users_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return me(current_user, db)
