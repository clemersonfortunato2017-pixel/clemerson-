"""Processamento de foto de peça: remove fundo, centraliza em 1000x1000 branco.
Porta server-side de scripts/otimizar_imagens.py (skill anuncio-ml-autopecas) —
antes rodava no PC do usuário, agora roda no backend (BackgroundTasks) pra
peça publicada pela esteira automática não depender de nada local."""

import io
from pathlib import Path
from PIL import Image

try:
    from rembg import remove as rembg_remove
    REMBG_OK = True
except ImportError:
    REMBG_OK = False

TAMANHO_ALVO = (1000, 1000)
QUALIDADE = 88


def _remover_fundo(img: Image.Image) -> Image.Image:
    if not REMBG_OK:
        return img.convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    resultado = rembg_remove(buf.read())
    return Image.open(io.BytesIO(resultado)).convert("RGBA")


def otimizar_imagem(origem: Path, destino: Path) -> Path:
    """Remove fundo, centraliza em canvas 1000x1000 branco, salva JPEG <10MB."""
    with Image.open(origem) as img:
        img = img.convert("RGB")
        img_sem_fundo = _remover_fundo(img)

        fundo = Image.new("RGBA", img_sem_fundo.size, (255, 255, 255, 255))
        fundo.paste(img_sem_fundo, mask=img_sem_fundo.split()[3])
        img_final = fundo.convert("RGB")

        img_final.thumbnail(TAMANHO_ALVO, Image.LANCZOS)

        canvas = Image.new("RGB", TAMANHO_ALVO, (255, 255, 255))
        ox = (TAMANHO_ALVO[0] - img_final.width) // 2
        oy = (TAMANHO_ALVO[1] - img_final.height) // 2
        canvas.paste(img_final, (ox, oy))

        destino.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(destino, "JPEG", quality=QUALIDADE, optimize=True)

        for q in (75, 60, 50):
            if destino.stat().st_size / 1024 / 1024 > 10:
                canvas.save(destino, "JPEG", quality=q, optimize=True)

        return destino


def processar_fotos_peca(part_id: int, arquivos_originais: list[Path], uploads_dir: Path) -> list[str]:
    """Processa todas as fotos originais de uma peça, retorna URLs públicas
    completas das otimizadas (o ML exige URL absoluta em `pictures[].source`,
    não aceita path relativo)."""
    from app.config import settings

    saida_dir = uploads_dir / str(part_id) / "otimizadas"
    resultados = []
    for origem in arquivos_originais:
        destino = saida_dir / f"{origem.stem}_ml.jpg"
        otimizar_imagem(origem, destino)
        resultados.append(f"{settings.public_base_url}/uploads/{part_id}/otimizadas/{destino.name}")
    return resultados
