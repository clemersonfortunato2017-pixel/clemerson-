"""Processamento de foto de peça: remove fundo, centraliza em 1000x1000 branco.
Porta server-side de scripts/otimizar_imagens.py (skill anuncio-ml-autopecas) —
antes rodava no PC do usuário, agora roda no backend pra peça publicada pela
esteira automática não depender de nada local."""

import gc
import io
import os
from pathlib import Path
from PIL import Image
from app.config import settings

# Cache do modelo do rembg no volume persistente — sem isso, cada restart do
# container baixava os 176MB de novo (disco padrão do container é efêmero).
os.environ.setdefault("U2NET_HOME", str(Path(settings.uploads_dir) / ".u2net"))

try:
    from rembg import remove as rembg_remove, new_session
    REMBG_OK = True
except ImportError:
    REMBG_OK = False

TAMANHO_ALVO = (1000, 1000)
QUALIDADE = 88
# Downscale antes do rembg — foto de celular (12MP+) sem isso estourava a RAM
# do container (confirmado: crash silencioso/OOM ao reprocessar a peça #446
# com 8 fotos originais). Resultado final é 1000x1000 de qualquer forma, não
# há ganho em manter resolução maior que isso pro rembg processar.
MAX_ENTRADA = (1100, 1100)


def _remover_fundo(img: Image.Image, session) -> Image.Image:
    if not REMBG_OK:
        return img.convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    resultado = rembg_remove(buf.read(), session=session)
    return Image.open(io.BytesIO(resultado)).convert("RGBA")


def otimizar_imagem(origem: Path, destino: Path, session) -> Path:
    """Remove fundo, centraliza em canvas 1000x1000 branco, salva JPEG <10MB."""
    with Image.open(origem) as img:
        img = img.convert("RGB")
        img.thumbnail(MAX_ENTRADA, Image.LANCZOS)
        img_sem_fundo = _remover_fundo(img, session)

        fundo = Image.new("RGBA", img_sem_fundo.size, (255, 255, 255, 255))
        fundo.paste(img_sem_fundo, mask=img_sem_fundo.split()[3])
        img_final = fundo.convert("RGB")
        img_sem_fundo.close()
        fundo.close()

        img_final.thumbnail(TAMANHO_ALVO, Image.LANCZOS)

        canvas = Image.new("RGB", TAMANHO_ALVO, (255, 255, 255))
        ox = (TAMANHO_ALVO[0] - img_final.width) // 2
        oy = (TAMANHO_ALVO[1] - img_final.height) // 2
        canvas.paste(img_final, (ox, oy))
        img_final.close()

        destino.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(destino, "JPEG", quality=QUALIDADE, optimize=True)

        for q in (75, 60, 50):
            if destino.stat().st_size / 1024 / 1024 > 10:
                canvas.save(destino, "JPEG", quality=q, optimize=True)

        canvas.close()
        return destino


def processar_fotos_peca(part_id: int, arquivos_originais: list[Path], uploads_dir: Path) -> list[str]:
    """Processa todas as fotos originais de uma peça, retorna URLs públicas
    completas das otimizadas (o ML exige URL absoluta em `pictures[].source`,
    não aceita path relativo). Um único session do rembg é reaproveitado pra
    todas as fotos do lote — carregar o modelo de novo a cada foto (8x numa
    peça) multiplicava a memória usada à toa."""
    saida_dir = uploads_dir / str(part_id) / "otimizadas"
    # u2netp em vez de u2net: modelo ~40x menor (4.7MB vs 176MB) — o container
    # do Railway está derrubando o processo por falta de memória mesmo com
    # imagem reduzida e sessão reaproveitada (confirmado reproduzindo com
    # fotos sintéticas de 12MP), então a saída é um modelo mais leve.
    session = new_session("u2netp") if REMBG_OK else None

    resultados = []
    for origem in arquivos_originais:
        destino = saida_dir / f"{origem.stem}_ml.jpg"
        otimizar_imagem(origem, destino, session)
        resultados.append(f"{settings.public_base_url}/uploads/{part_id}/otimizadas/{destino.name}")
        gc.collect()  # solta a memória da foto anterior antes de abrir a próxima

    return resultados
