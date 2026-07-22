"""Esteira automática — identificação da peça por foto + pesquisa de preço,
rodando sozinha no servidor via API da Anthropic (chamada direta por httpx,
sem SDK — evita depender de biblioteca nova no requirements.txt).

Importante: esta etapa NUNCA publica no Mercado Livre sozinha. Ela deixa a
peça pronta (title/brand/category/price/compatibilidade preenchidos,
status="ready_to_publish") e quem publica de fato é o usuário, com 1 clique
no app — decisão explícita do Clemerson em 2026-07-20: identificação e
pesquisa podem rodar sem supervisão, mas o clique de publicar (ação com
efeito financeiro real, cria anúncio de verdade) fica sempre com um humano.
"""
import json
import httpx
from sqlalchemy.orm import Session
from app.config import settings
from app.models.part import Part, MarketplaceListing, Vehicle, Compatibility

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5"  # Haiku errou marca/modelo num teste real (Hyundai Creta virou "Chevrolet Cruze") — Sonnet lê etiqueta/gravação com mais precisão, custo ainda baixo pro volume da loja


def _log_step(part: Part, step: str, detail) -> None:
    log = list(part.pipeline_log or [])
    log.append({"step": step, "detail": detail})
    part.pipeline_log = log


async def _claude_call(client: httpx.AsyncClient, messages: list, tools: list | None = None, max_tokens: int = 1024) -> dict:
    key = settings.anthropic_api_key
    non_ascii = [(i, c, ord(c)) for i, c in enumerate(key) if ord(c) > 127]
    if non_ascii:
        raise ValueError(f"ANTHROPIC_API_KEY tem {len(key)} chars, {len(non_ascii)} não-ASCII: {non_ascii[:5]}")
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {"model": MODEL, "max_tokens": max_tokens, "messages": messages}
    if tools:
        body["tools"] = tools
    r = await client.post(ANTHROPIC_API, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    return r.json()


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    return json.loads(text[start:end + 1])


async def identify_part(client: httpx.AsyncClient, photo_urls: list[str]) -> dict:
    """Manda as fotos pro Claude e pede identificação estruturada."""
    content = [{"type": "image", "source": {"type": "url", "url": url}} for url in photo_urls[:7]]
    content.append({
        "type": "text",
        "text": (
            "Estas são fotos de uma autopeça usada, tiradas por um lojista brasileiro pra "
            "anunciar no Mercado Livre. Identifique a peça e o(s) veículo(s) compatível(is). "
            "IMPORTANTE: se houver texto escrito à mão (caneta/marcador) ou etiqueta/código "
            "gravado na peça indicando o veículo, isso é a fonte MAIS confiável — use isso "
            "antes de tentar adivinhar pela forma/desenho da peça (peças de tipos parecidos "
            "existem pra marcas diferentes, é fácil confundir só pelo formato). "
            "Se não conseguir ler nenhum texto/código com clareza, marque confidence como "
            "'low' em vez de arriscar um palpite. "
            "Responda APENAS com um JSON (sem texto antes/depois) no formato:\n"
            '{"part_type": "nome genérico da peça (ex: Comando Seta Limpador)", '
            '"brand": "marca do veículo", "model": "modelo do veículo", '
            '"year_start": 2018, "year_end": 2021, '
            '"code_oem": "código gravado/etiqueta, ou null se não visível", '
            '"condition": "used ou new", '
            '"title": "título comercial curto no padrão ML, até 60 caracteres, '
            'ex: Comando Seta Limpador C Anel Airbag Ford Ka 2018 A 2021", '
            '"description": "descrição de anúncio pra Mercado Livre, 3-5 linhas: o que é a '
            'peça, condição (peça usada, testada/funcionando), compatibilidade, aviso de '
            'conferir compatibilidade antes de comprar. Tom direto de loja de autopeças.", '
            '"confidence": "high, medium ou low"}'
        ),
    })
    resp = await _claude_call(client, [{"role": "user", "content": content}])
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    return _extract_json(text)


async def research_price(client: httpx.AsyncClient, query: str) -> dict:
    """Pesquisa preço competitivo real via web search nativo da Anthropic."""
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
    messages = [{"role": "user", "content": (
        f"Pesquise o preço de venda de: {query}, usado, à venda no Mercado Livre Brasil "
        "(mercadolivre.com.br). Responda SÓ com JSON no final da sua resposta, formato: "
        '{"suggested_price": 123.45, "prices_found": [123.45, 150.0], "source_note": "texto curto"}. '
        "Escolha um preço próximo do MENOR preço real encontrado (mais competitivo), não a média."
    )}]
    resp = await _claude_call(client, messages, tools=tools, max_tokens=2048)
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    try:
        return _extract_json(text)
    except Exception:
        return {"suggested_price": None, "prices_found": [], "source_note": f"pesquisa falhou — resposta: {text[:300]}"}


def find_catalog_reference(db: Session, part_type: str, brand: str) -> dict | None:
    """Procura no próprio catálogo Pitbox uma peça do mesmo tipo já publicada,
    pra reaproveitar categoria/atributos/family_name (mesmo padrão manual
    usado em 2026-07-20 pras peças #455/#456)."""
    keyword = part_type.split()[0] if part_type else ""
    if not keyword:
        return None
    candidates = (
        db.query(Part)
        .join(MarketplaceListing, MarketplaceListing.part_id == Part.id)
        .filter(Part.title.ilike(f"%{keyword}%"), Part.active == True)  # noqa: E712
        .limit(5)
        .all()
    )
    for c in candidates:
        listing = db.query(MarketplaceListing).filter(
            MarketplaceListing.part_id == c.id,
            MarketplaceListing.marketplace == "mercadolivre",
            MarketplaceListing.status == "active",
        ).first()
        if listing:
            return {
                "reference_listing_id": listing.listing_id,
                "same_vehicle": c.brand == brand,
            }
    return None


def _get_or_create_vehicle(db: Session, brand: str, model: str, y1, y2) -> Vehicle:
    v = db.query(Vehicle).filter(
        Vehicle.brand == brand, Vehicle.model == model,
        Vehicle.year_start == y1, Vehicle.year_end == y2,
    ).first()
    if not v:
        v = Vehicle(brand=brand, model=model, year_start=y1, year_end=y2)
        db.add(v)
        db.flush()
    return v


async def prepare_part(part_id: int, db: Session) -> dict:
    """Identifica + pesquisa preço + prepara peça pra publicação com 1 clique.
    NUNCA chama a API do Mercado Livre — só deixa a peça em status
    'ready_to_publish' com tudo preenchido."""
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part or not part.photos:
        return {"error": "peça não encontrada ou sem fotos"}

    async with httpx.AsyncClient() as client:
        try:
            ident = await identify_part(client, part.photos)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            _log_step(part, "identificacao", f"erro: {e} | {tb[-800:]}")
            part.status = "error"
            db.commit()
            return {"error": str(e)}

        _log_step(part, "identificacao", ident)

        query = f"{ident.get('part_type', '')} {ident.get('brand', '')} {ident.get('model', '')} {ident.get('year_start', '')}"
        try:
            price_info = await research_price(client, query)
        except Exception as e:
            price_info = {"suggested_price": None, "source_note": f"erro: {e}"}
        _log_step(part, "concorrentes", price_info)

        # Foto de capa (veículo 0km + peça, 50/50) — Passo 1B do skill
        # anuncio-ml-autopecas, OBRIGATÓRIO em todo anúncio mas ainda não
        # portado pra esteira automática até 2026-07-21. Nunca trava o resto
        # do fluxo se não achar uma foto de veículo válida.
        tem_capa = "/otimizadas/00_capa.jpg" in (part.photos[0] if part.photos else "")
        if ident.get("brand") and ident.get("model") and part.photos and not tem_capa:
            from app.services.vehicle_photo import montar_capa
            try:
                capa_url = await montar_capa(
                    client, db, part.id, ident["brand"], ident["model"],
                    ident.get("year_start"), part.photos[0],
                )
                if capa_url:
                    part.photos = [capa_url] + list(part.photos)
                    _log_step(part, "capa_veiculo", {"foto": capa_url})
                else:
                    _log_step(part, "capa_veiculo", "nenhuma foto de veiculo valida encontrada — seguiu sem capa")
            except Exception as e:
                _log_step(part, "capa_veiculo", f"erro: {e}")

    reference = find_catalog_reference(db, ident.get("part_type", ""), ident.get("brand", ""))
    _log_step(part, "referencia", reference or "nenhuma encontrada — precisa de decisão manual de categoria")

    part.title = (ident.get("title") or ident.get("part_type") or part.title)[:60]
    part.description = ident.get("description")
    part.brand = ident.get("brand")
    part.condition = ident.get("condition") or "used"
    part.code_oem = ident.get("code_oem")
    part.quantity = 1
    if price_info.get("suggested_price"):
        part.sale_price = price_info["suggested_price"]
        part.suggested_price = price_info["suggested_price"]

    if ident.get("brand") and ident.get("model"):
        vehicle = _get_or_create_vehicle(db, ident["brand"], ident["model"], ident.get("year_start"), ident.get("year_end"))
        if not db.query(Compatibility).filter_by(part_id=part.id, vehicle_id=vehicle.id).first():
            db.add(Compatibility(part_id=part.id, vehicle_id=vehicle.id, oem_code=ident.get("code_oem")))

    if reference and ident.get("confidence") in ("high", "medium"):
        part.status = "ready_to_publish"
        _log_step(part, "pronto_pra_publicar", {
            "reference_listing_id": reference["reference_listing_id"],
            "family_name_override": None if reference["same_vehicle"] else part.title,
        })
    else:
        part.status = "needs_review"
        _log_step(part, "precisa_revisao", "confiança baixa na identificação ou nenhuma peça de referência encontrada no catálogo")

    db.commit()
    return {"part_id": part.id, "status": part.status, "identification": ident, "price": price_info}
