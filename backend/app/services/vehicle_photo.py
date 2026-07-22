"""Foto de capa (veículo 0km + peça, 50/50) — Passo 1B do skill
anuncio-ml-autopecas, portado pra rodar sozinho na esteira automática dentro
de prepare_part(). Busca uma foto de estúdio/imprensa do veículo via Claude +
web_search, valida removendo o fundo (mesmo critério de área do
image_processor), monta o painel e devolve a URL pública — ou None se nenhum
candidato passar na validação (a esteira segue sem capa nesse caso, não
trava o resto do fluxo por causa disso)."""

import io
import re
import httpx
from pathlib import Path
from urllib.parse import urljoin
from PIL import Image, ImageChops
from sqlalchemy.orm import Session
from app.config import settings
from app.models.part import Vehicle
from app.services.image_processor import (
    _remover_fundo_photoroom,
    REMBG_OK,
    ALPHA_LIMIAR_BBOX,
    AREA_MIN_FRACAO,
    AREA_MAX_FRACAO,
)

if REMBG_OK:
    from rembg import remove as rembg_remove, new_session

CAPA_SIZE = (1000, 1000)
PAINEL_SIZE = (1000, 500)
# Tamanho FIXO pra ambos os painéis (veículo e peça) — garante proporção
# visual 50/50 igual ao script original da skill, independente do formato
# de cada foto.
MAX_W, MAX_H = 860, 420


def _local_photo_path(url: str) -> Path:
    rel = url.replace(settings.public_base_url, "").lstrip("/")
    if rel.startswith("uploads/"):
        rel = rel[len("uploads/"):]
    return Path(settings.uploads_dir) / rel


async def _find_vehicle_photo_candidates(client: httpx.AsyncClient, brand: str, model: str, year) -> list[str]:
    from app.services.auto_listing import _claude_call, _extract_json

    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}]
    ano_txt = f" {year}" if year else ""
    messages = [{"role": "user", "content": (
        f"Preciso de uma foto de estúdio/imprensa do veículo {brand} {model}{ano_txt} "
        "(0km, sem uso, fundo branco ou neutro liso, SEM placa visível, ângulo lateral ou "
        "3/4 frontal esquerdo, resolução mínima 800px de largura) pra usar como foto de "
        "capa de anúncio no Mercado Livre. "
        "PROIBIDO: Wikimedia Commons, fotos de rua/estacionamento/anúncio de venda usado, "
        "fotos com placa visível, fotos com pessoas ou outros veículos ao fundo. "
        "Priorize, nessa ordem: material de imprensa oficial da montadora > catálogo/"
        "concessionária > portal especializado (Car and Driver, Motor1, Quatro Rodas) com "
        "foto de estúdio. "
        "As URLs encontradas pela busca geralmente são da PÁGINA (artigo, galeria), não do "
        "arquivo de imagem em si — isso é esperado, pode retornar a URL da página que "
        "melhor descreve/contém essa foto, meu sistema extrai a imagem da página depois. "
        "Responda SÓ com JSON no final da resposta: "
        '{"candidates": ["url_da_pagina_1", "url_da_pagina_2", "url_da_pagina_3"]}'
    )}]
    resp = await _claude_call(client, messages, tools=tools, max_tokens=2048)
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    try:
        data = _extract_json(text)
        candidates = data.get("candidates", [])[:3]
        print(f"[capa] candidatos pra {brand} {model}{ano_txt}: {candidates}")
        return candidates
    except Exception as e:
        print(f"[capa] falha ao extrair candidatos pra {brand} {model}{ano_txt}: {e} | resposta: {text[:300]}")
        return []


def _extrair_imagens_da_pagina(html: str, base_url: str) -> list[str]:
    """web_search devolve URL da página (artigo/galeria), não do arquivo de
    imagem — extrai candidatos direto do HTML: og:image (geralmente a foto
    principal/hero do artigo) primeiro, depois <img src> em geral como
    reserva."""
    candidatos = []
    og = re.findall(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    candidatos.extend(og)
    imgs = re.findall(r'<img[^>]+src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)
    candidatos.extend(imgs)
    vistos, resultado = set(), []
    for c in candidatos:
        url = urljoin(base_url, c)
        if url not in vistos:
            vistos.add(url)
            resultado.append(url)
    return resultado[:8]


def _remover_fundo_carro(img: Image.Image) -> Image.Image | None:
    """Recorte do veículo com fundo branco — sem fallback pra foto original:
    se não conseguir separar bem do fundo, é melhor descartar o candidato e
    tentar o próximo do que usar uma capa com fundo errado."""
    sem_fundo = _remover_fundo_photoroom(img)
    if sem_fundo is None and REMBG_OK:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        resultado = rembg_remove(buf.read(), session=new_session("isnet-general-use"))
        sem_fundo = Image.open(io.BytesIO(resultado)).convert("RGBA")
    if sem_fundo is None:
        return None

    alpha = sem_fundo.split()[3]
    bbox = alpha.point(lambda p: 255 if p > ALPHA_LIMIAR_BBOX else 0).getbbox()
    if bbox is None:
        return None
    area_frac = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / (sem_fundo.width * sem_fundo.height)
    if area_frac < AREA_MIN_FRACAO or area_frac > AREA_MAX_FRACAO:
        return None

    pad_x = int((bbox[2] - bbox[0]) * 0.03)
    pad_y = int((bbox[3] - bbox[1]) * 0.03)
    crop_box = (
        max(0, bbox[0] - pad_x), max(0, bbox[1] - pad_y),
        min(sem_fundo.width, bbox[2] + pad_x), min(sem_fundo.height, bbox[3] + pad_y),
    )
    recorte = sem_fundo.crop(crop_box)
    fundo = Image.new("RGBA", recorte.size, (255, 255, 255, 255))
    fundo.paste(recorte, mask=recorte.split()[3])
    return fundo.convert("RGB")


def _recortar_peca_branco(path: Path, margem: int = 20) -> Image.Image:
    """A primeira foto otimizada da peça já está em fundo branco — recorta
    só a borda branca sobrando (sem numpy/scipy, só PIL, igual ao resto do
    backend)."""
    img = Image.open(path).convert("RGB")
    diff = ImageChops.difference(img, Image.new("RGB", img.size, (255, 255, 255))).convert("L")
    mask = diff.point(lambda p: 255 if p > 15 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return img
    cmin, rmin, cmax, rmax = bbox
    cmin = max(0, cmin - margem)
    rmin = max(0, rmin - margem)
    cmax = min(img.width, cmax + margem)
    rmax = min(img.height, rmax + margem)
    return img.crop((cmin, rmin, cmax, rmax))


def _criar_painel(img_crop: Image.Image) -> Image.Image:
    img = img_crop.copy()
    img.thumbnail((MAX_W, MAX_H), Image.LANCZOS)
    canvas = Image.new("RGB", PAINEL_SIZE, (255, 255, 255))
    ox = (PAINEL_SIZE[0] - img.width) // 2
    oy = (PAINEL_SIZE[1] - img.height) // 2
    canvas.paste(img, (ox, oy))
    return canvas


async def montar_capa(
    client: httpx.AsyncClient, db: Session, part_id: int,
    brand: str, model: str, year_start, primeira_foto_url: str,
) -> str | None:
    """Busca a foto do veículo (com cache por marca/modelo em Vehicle.ref_photo_url),
    remove fundo, monta a capa 1000x1000 (veículo em cima, peça embaixo) e
    devolve a URL pública — ou None se nenhum candidato validar."""
    vehicle = db.query(Vehicle).filter(Vehicle.brand == brand, Vehicle.model == model).first()
    car_crop = None
    fonte_usada = None

    if vehicle and vehicle.ref_photo_url:
        try:
            r = await client.get(
                vehicle.ref_photo_url, timeout=20, follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PitboxBot/1.0)"},
            )
            if r.status_code == 200:
                car_crop = _remover_fundo_carro(Image.open(io.BytesIO(r.content)).convert("RGB"))
                if car_crop is not None:
                    fonte_usada = vehicle.ref_photo_url
        except Exception:
            car_crop = None

    if car_crop is None:
        pages = await _find_vehicle_photo_candidates(client, brand, model, year_start)
        # Expande cada página (artigo/galeria) nas imagens reais que ela
        # contém — web_search só devolve a URL da página, não do arquivo.
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PitboxBot/1.0)"}
        image_urls: list[str] = []
        for page_url in pages:
            try:
                r = await client.get(page_url, timeout=15, follow_redirects=True, headers=headers)
                ctype = r.headers.get("content-type", "")
                if r.status_code != 200:
                    print(f"[capa] pagina descartada {page_url}: status={r.status_code}")
                    continue
                if ctype.startswith("image"):
                    image_urls.append(page_url)
                elif "html" in ctype:
                    extraidas = _extrair_imagens_da_pagina(r.text, str(r.url))
                    print(f"[capa] {page_url} -> {len(extraidas)} imagem(ns) extraida(s)")
                    image_urls.extend(extraidas)
            except Exception as e:
                print(f"[capa] erro ao abrir pagina {page_url}: {e}")
                continue

        for url in image_urls:
            try:
                r = await client.get(url, timeout=20, follow_redirects=True, headers=headers)
                ctype = r.headers.get("content-type", "")
                if r.status_code != 200 or not ctype.startswith("image"):
                    print(f"[capa] descartado {url}: status={r.status_code} content-type={ctype}")
                    continue
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                if img.width < 500:
                    print(f"[capa] descartado {url}: largura={img.width}px (min 500)")
                    continue
                car_crop = _remover_fundo_carro(img)
                if car_crop is None:
                    print(f"[capa] descartado {url}: remocao de fundo falhou ou area fora da faixa aceitavel")
                    continue
                fonte_usada = url
                print(f"[capa] usando {url}")
                break
            except Exception as e:
                print(f"[capa] erro ao baixar/processar {url}: {e}")
                continue

    if car_crop is None:
        return None

    if fonte_usada and (not vehicle or vehicle.ref_photo_url != fonte_usada):
        if not vehicle:
            vehicle = Vehicle(brand=brand, model=model, year_start=year_start)
            db.add(vehicle)
            db.flush()
        vehicle.ref_photo_url = fonte_usada
        db.commit()

    peca_crop = _recortar_peca_branco(_local_photo_path(primeira_foto_url))

    comp = Image.new("RGB", CAPA_SIZE, (255, 255, 255))
    comp.paste(_criar_painel(car_crop), (0, 0))
    comp.paste(_criar_painel(peca_crop), (0, 500))

    destino_dir = Path(settings.uploads_dir) / str(part_id) / "otimizadas"
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / "00_capa.jpg"
    comp.save(destino, "JPEG", quality=92, optimize=True)

    return f"{settings.public_base_url}/uploads/{part_id}/otimizadas/{destino.name}"
