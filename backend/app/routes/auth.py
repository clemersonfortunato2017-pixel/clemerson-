"""Login/senha + aprovação de usuário pelo admin. Primeiro usuário (Clemerson)
é criado via bootstrap script (scripts/bootstrap_admin.py), não por /register —
não dá pra aprovar a si mesmo por um fluxo que ainda não existe."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models.user import User
from app.services.security import hash_password, verify_password, create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def get_current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Não autenticado")
    payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    if not payload:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or user.status != "approved":
        raise HTTPException(status_code=401, detail="Usuário sem acesso")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Só o administrador pode fazer isso")
    return user


@router.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role="operator",
        status="pending",
    )
    db.add(user)
    db.commit()
    return {"ok": True, "message": "Cadastro enviado. Aguarde a aprovação do administrador."}


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    if user.status == "pending":
        raise HTTPException(status_code=403, detail="Cadastro ainda não aprovado pelo administrador")
    if user.status in ("rejected", "disabled"):
        raise HTTPException(status_code=403, detail="Acesso negado")

    token = create_access_token(user.id, user.role)
    return {
        "access_token": token,
        "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role},
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


@router.get("/pending", dependencies=[Depends(require_admin)])
def list_pending(db: Session = Depends(get_db)):
    pending = db.query(User).filter(User.status == "pending").order_by(User.created_at.asc()).all()
    return [{"id": u.id, "name": u.name, "email": u.email, "created_at": u.created_at} for u in pending]


@router.post("/{user_id}/approve")
def approve_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    target.status = "approved"
    target.approved_by = admin.id
    target.approved_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.post("/{user_id}/reject")
def reject_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    target.status = "rejected"
    target.approved_by = admin.id
    target.approved_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}
