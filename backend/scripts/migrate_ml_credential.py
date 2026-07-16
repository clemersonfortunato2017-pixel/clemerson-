"""Migra o token ML do HD externo F: pra tabela MLCredential no Postgres —
depois disso o F: não é mais necessário pra publicar/consultar ML (esteira
automática e platform_registry passam a usar o Postgres primeiro).

Rodar uma vez só, contra o DATABASE_URL de produção:
  cd backend
  DATABASE_URL="postgresql://...(URL do Railway)..." .venv\\Scripts\\python.exe scripts\\migrate_ml_credential.py
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.ml_credential import MLCredential

TOKENS_FILE = r"F:\FORTUNATO AUTO PARTS\ml_tokens.json"


def main():
    path = Path(TOKENS_FILE)
    if not path.exists():
        print(f"Não achei {TOKENS_FILE} — HD externo F: conectado?")
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8-sig"))
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    if not access_token or not refresh_token:
        print("Arquivo de token não tem access_token/refresh_token.")
        sys.exit(1)

    db = SessionLocal()
    try:
        cred = db.query(MLCredential).first()
        if cred:
            cred.access_token = access_token
            cred.refresh_token = refresh_token
            print(f"MLCredential existente (id={cred.id}) atualizado.")
        else:
            cred = MLCredential(access_token=access_token, refresh_token=refresh_token)
            db.add(cred)
            print("MLCredential criado.")
        db.commit()
        print("Migração concluída — a partir de agora o Postgres é a fonte de verdade do token ML.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
