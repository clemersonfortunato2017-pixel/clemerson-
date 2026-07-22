"""Processamento de foto de peça: remove fundo, centraliza em 1000x1000 branco.
Porta server-side de scripts/otimizar_imagens.py (skill anuncio-ml-autopecas) —
antes rodava no PC do usuário, agora roda no backend pra peça publicada pela
esteira automática não depender de nada local."""

import gc
import io
import os
import httpx
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

PHOTOROOM_API = "https://sdk.photoroom.com/v1/segment"

TAMANHO_ALVO = (1000, 1000)
QUALIDADE = 88
# Teto de entrada antes do rembg — só pra evitar caso extremo (foto de 48MP+),
# não é mais um aperto de memória: com o plano Hobby (até 48GB/serviço) o
# gargalo de RAM que forçou downscale agressivo + modelo leve não existe mais.
MAX_ENTRADA = (2000, 2000)
# Faixa aceitável de área ocupada pelo recorte (fração do total de pixels).
# Fora disso o rembg claramente falhou (apagou a peça quase inteira, ou não
# tirou nada) — visto em peças reais em 2026-07-21: fotos saíram praticamente
# em branco, só uma sombra fantasma da peça. Nesses casos usa a foto original
# sem remoção de fundo em vez de publicar uma imagem inútil.
AREA_MIN_FRACAO = 0.03
AREA_MAX_FRACAO = 0.98
PADDING_FRACAO = 0.06  # margem ao redor da peça depois de recortar pelo bounding box


def _remover_fundo_photoroom(img: Image.Image) -> Image.Image | None:
    """Remove fundo via API do Photoroom (qualidade melhor que rembg pra
    peça reflexiva/escura, segundo teste do usuário) — None se a chave não
    estiver configurada ou a chamada falhar, pra sempre cair no fallback."""
    if not settings.photoroom_api_key:
        return None
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    try:
        r = httpx.post(
            PHOTOROOM_API,
            headers={"x-api-key": settings.photoroom_api_key},
            files={"image_file": ("foto.jpg", buf.read(), "image/jpeg")},
            timeout=30,
        )
        if r.status_code != 200:
            return None
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception:
        return None


def _remover_fundo(img: Image.Image, session) -> Image.Image | None:
    """Retorna a imagem com fundo removido (RGBA), ou None se o recorte saiu
    claramente errado (área da peça fora da faixa aceitável). Tenta Photoroom
    primeiro (melhor qualidade); se a chave não estiver configurada ou a
    chamada falhar, cai pro rembg local — nunca deixa a peça sem nenhuma
    tentativa de remover fundo só por causa de uma API externa fora do ar."""
    sem_fundo = _remover_fundo_photoroom(img)
    if sem_fundo is None and REMBG_OK:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        resultado = rembg_remove(buf.read(), session=session)
        sem_fundo = Image.open(io.BytesIO(resultado)).convert("RGBA")

    if sem_fundo is None:
        return None

    alpha = sem_fundo.split()[3]
    bbox = alpha.getbbox()
    if bbox is None:
        return None
    area_frac = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / (sem_fundo.width * sem_fundo.height)
    if area_frac < AREA_MIN_FRACAO or area_frac > AREA_MAX_FRACAO:
        return None
    return sem_fundo


def otimizar_imagem(origem: Path, destino: Path, session) -> Path:
    """Remove fundo (com fallback pra foto original se o recorte falhar),
    recorta pelo bounding box da peça e centraliza em canvas 1000x1000
    branco, salva JPEG <10MB."""
    with Image.open(origem) as img:
        img = img.convert("RGB")
        img.thumbnail(MAX_ENTRADA, Image.LANCZOS)
        img_sem_fundo = _remover_fundo(img, session)

        if img_sem_fundo is not None:
            alpha = img_sem_fundo.split()[3]
            bbox = alpha.getbbox()
            pad_x = int((bbox[2] - bbox[0]) * PADDING_FRACAO)
            pad_y = int((bbox[3] - bbox[1]) * PADDING_FRACAO)
            crop_box = (
                max(0, bbox[0] - pad_x), max(0, bbox[1] - pad_y),
                min(img_sem_fundo.width, bbox[2] + pad_x), min(img_sem_fundo.height, bbox[3] + pad_y),
            )
            recorte = img_sem_fundo.crop(crop_box)
            fundo = Image.new("RGBA", recorte.size, (255, 255, 255, 255))
            fundo.paste(recorte, mask=recorte.split()[3])
            img_final = fundo.convert("RGB")
            recorte.close()
            fundo.close()
            img_sem_fundo.close()
        else:
            # rembg indisponível ou recorte claramente errado — melhor
            # publicar a foto original (com fundo) do que uma imagem em
            # branco/apagada.
            img_final = img.copy()

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
    # isnet-general-use: qualidade de recorte sensivelmente melhor que u2net
    # pra objetos em geral (bordas mais precisas, menos falha em peça escura/
    # reflexiva) — visto em teste real 2026-07-21 que u2net às vezes apagava
    # a peça quase inteira (fundo e peça confundidos). u2net (modelo
    # completo, antes usado aqui) voltou a rodar depois do upgrade pro plano
    # Hobby; u2netp ("lite") foi descartado antes por recorte impreciso.
    session = new_session("isnet-general-use") if REMBG_OK else None

    resultados = []
    for origem in arquivos_originais:
        destino = saida_dir / f"{origem.stem}_ml.jpg"
        otimizar_imagem(origem, destino, session)
        resultados.append(f"{settings.public_base_url}/uploads/{part_id}/otimizadas/{destino.name}")
        gc.collect()  # solta a memória da foto anterior antes de abrir a próxima

    return resultados
