"""Troca a senha de um usuário já existente (ex: corrigir a senha placeholder
do bootstrap_admin.py quando ela não foi substituída na hora).

Uso:
  cd backend
  .venv\\Scripts\\python.exe scripts\\reset_password.py email@exemplo.com "NOVA_SENHA"
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.user import User
from app.services.security import hash_password


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    email, new_password = sys.argv[1], sys.argv[2]
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"Usuário {email} não encontrado.")
            sys.exit(1)
        user.password_hash = hash_password(new_password)
        db.commit()
        print(f"Senha atualizada para {email} (id={user.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
