"""Cria o primeiro usuário admin (Clemerson) direto no banco.
Precisa rodar uma vez só, antes do frontend exigir login — não dá pra criar
o primeiro admin via /auth/register + aprovação porque ainda não existe
ninguém pra aprovar.

Uso:
  cd backend
  .venv\\Scripts\\python.exe scripts\\bootstrap_admin.py "Clemerson Fortunato" clemersonfortunato2017@gmail.com "SUA_SENHA_AQUI"
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.user import User
from app.services.security import hash_password


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    name, email, password = sys.argv[1], sys.argv[2], sys.argv[3]
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"Usuário {email} já existe (status={existing.status}, role={existing.role}). Nada feito.")
            return
        user = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role="admin",
            status="approved",
        )
        db.add(user)
        db.commit()
        print(f"Admin criado: {email} (id={user.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
