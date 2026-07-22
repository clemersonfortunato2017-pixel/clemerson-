"""Relatório diário da esteira automática — o que foi publicado sozinho,
por quanto, e o que deu erro (pra auditar decisão tomada sem revisão humana)."""

import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.database import get_db, SessionLocal
from app.models.part import Part, MarketplaceListing
from app.models.sale import Sale, SaleItem
from app.services.ml_importer import get_item_visits, fetch_all_item_ids
from app.services.platform_registry import get_accounts_for_platform, resolve_account_for_listing
from app.routes.auth import get_current_user
from fastapi import BackgroundTasks

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(get_current_user)])

desc_audit_state = {"running": False, "processed": 0, "total": 0, "ja_tinha": 0, "corrigido": 0, "sem_descricao_local": [], "erro": [], "done": True}


@router.get("/daily")
def daily_report(date: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """date no formato YYYY-MM-DD; default = hoje (UTC)."""
    day = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now(timezone.utc).date()
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    listings = (
        db.query(MarketplaceListing)
        .filter(MarketplaceListing.created_at >= start, MarketplaceListing.created_at < end)
        .all()
    )
    published = []
    total_value = 0.0
    for listing in listings:
        part = db.query(Part).filter(Part.id == listing.part_id).first()
        published.append({
            "part_id": listing.part_id,
            "title": part.title if part else None,
            "marketplace": listing.marketplace,
            "listing_id": listing.listing_id,
            "url": listing.url,
            "price": listing.price,
        })
        total_value += listing.price or 0

    errors = (
        db.query(Part)
        .filter(Part.status == "error", Part.updated_at >= start, Part.updated_at < end)
        .all()
    )
    error_list = [
        {"part_id": p.id, "title": p.title, "log": p.pipeline_log}
        for p in errors
    ]

    return {
        "date": day.isoformat(),
        "published_count": len(published),
        "total_value": round(total_value, 2),
        "published": published,
        "error_count": len(error_list),
        "errors": error_list,
    }


@router.get("/anuncios-status")
async def anuncios_status(db: Session = Depends(get_db)):
    """Classifica cada anúncio ativo do ML em 4 categorias (método da aula
    'Líder ao Platinum', Alex Moro, 2026-07-21):
    - parado_visibilidade: 30+ dias sem venda E poucas visitas (<100) —
      problema de tráfego/visibilidade.
    - parado_conversao: 30+ dias sem venda MAS visitas altas (>=100) —
      problema de oferta/preço/foto, não de visibilidade.
    - estrela: vendeu nos últimos 30 dias com margem e volume acima da
      média da conta — prioridade de investimento (ads, Full, destaque).
    - saudavel: vendeu nos últimos 30 dias, dentro da média.
    Visitas do ML atualizam com até 48h de atraso (limitação da própria API,
    não é bug daqui).

    IMPORTANTE: o campo status do MarketplaceListing local pode estar
    desatualizado (visto hoje, 2026-07-21: banco mostrava ~700 "ativos", API
    real da conta PJ mostrou só 349) — por isso este endpoint sempre cruza
    com a lista real de itens ativos da API antes de classificar, igual foi
    feito na publicação em massa da conta PF."""
    local_listings = db.query(MarketplaceListing).filter(MarketplaceListing.marketplace == "mercadolivre").all()
    if not local_listings:
        return {"parado_visibilidade": [], "parado_conversao": [], "estrela": [], "saudavel": [], "desatualizados": [], "media_conta": {}}

    # Fonte de verdade: IDs realmente ativos na API, por conta (não confiar
    # no status salvo localmente).
    accounts = await get_accounts_for_platform("mercadolivre", db)
    real_active_ids: set[str] = set()
    account_by_external_id: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=30) as client:
        for account in accounts:
            if not account.get("external_id") or not account.get("access_token"):
                continue
            headers = {"Authorization": f"Bearer {account['access_token']}"}
            try:
                ids = await fetch_all_item_ids(account["external_id"], headers, client)
                real_active_ids.update(ids)
                for iid in ids:
                    account_by_external_id[iid] = account
            except Exception:
                continue

    listings = [l for l in local_listings if l.listing_id in real_active_ids]
    desatualizados = [
        {"part_id": l.part_id, "listing_id": l.listing_id, "status_local": l.status}
        for l in local_listings if l.listing_id not in real_active_ids
    ]
    if not listings:
        return {"parado_visibilidade": [], "parado_conversao": [], "estrela": [], "saudavel": [], "desatualizados": desatualizados, "media_conta": {}}

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # Média da conta (últimos 30 dias) pra decidir o que é "estrela"
    recent_items = (
        db.query(SaleItem, Sale)
        .join(Sale, SaleItem.sale_id == Sale.id)
        .filter(Sale.platform == "mercadolivre", Sale.sold_at >= cutoff)
        .all()
    )
    qty_by_part: dict[int, int] = {}
    margin_by_part: dict[int, list[float]] = {}
    for item, sale in recent_items:
        qty_by_part[item.part_id] = qty_by_part.get(item.part_id, 0) + item.quantity
        margin_by_part.setdefault(item.part_id, []).append(item.margin_pct or 0)

    avg_qty = (sum(qty_by_part.values()) / len(qty_by_part)) if qty_by_part else 0
    all_margins = [m for ms in margin_by_part.values() for m in ms]
    avg_margin = (sum(all_margins) / len(all_margins)) if all_margins else 0

    # Conta dona de cada anúncio já resolvida acima (account_by_external_id,
    # montada a partir da mesma busca real que confirmou o item ativo) —
    # anúncio da conta PF só pode ser consultado com o token da PF, não o da
    # PJ (legada). Sem isso, visita de anúncio PF sempre voltaria 0/erro.
    sem = asyncio.Semaphore(5)

    async def visits_for(listing: MarketplaceListing) -> int:
        account = account_by_external_id.get(listing.listing_id)
        if not account or not account.get("access_token"):
            return 0
        headers = {"Authorization": f"Bearer {account['access_token']}"}
        async with sem:
            async with httpx.AsyncClient() as client:
                return await get_item_visits(listing.listing_id, headers, client)

    visit_counts = await asyncio.gather(*(visits_for(l) for l in listings))

    buckets = {"parado_visibilidade": [], "parado_conversao": [], "estrela": [], "saudavel": []}
    for listing, visits in zip(listings, visit_counts):
        part = db.query(Part).filter(Part.id == listing.part_id).first()
        if not part:
            continue
        account = account_by_external_id.get(listing.listing_id)
        last_sale = (
            db.query(func.max(Sale.sold_at))
            .join(SaleItem, SaleItem.sale_id == Sale.id)
            .filter(SaleItem.part_id == part.id, Sale.platform == "mercadolivre")
            .scalar()
        )
        vendeu_recente = last_sale is not None and last_sale >= cutoff
        entry = {
            "part_id": part.id, "title": part.title, "listing_id": listing.listing_id,
            "url": listing.url, "visits_total": visits,
            "conta": account["label"] if account else "desconhecida",
            "last_sale_at": last_sale.isoformat() if last_sale else None,
        }
        if not vendeu_recente:
            entry["categoria"] = "parado_conversao" if visits >= 100 else "parado_visibilidade"
        else:
            qty = qty_by_part.get(part.id, 0)
            margins = margin_by_part.get(part.id, [])
            margin = (sum(margins) / len(margins)) if margins else 0
            entry["categoria"] = "estrela" if (qty >= avg_qty and margin >= avg_margin and avg_qty > 0) else "saudavel"
        buckets[entry["categoria"]].append(entry)

    return {
        **buckets,
        "desatualizados": desatualizados,
        "media_conta": {"qtd_media_30d": round(avg_qty, 2), "margem_media_30d_pct": round(avg_margin, 2)},
    }


async def _run_audit_descricoes():
    """Regra sem exceção (Clemerson, 2026-07-22): nenhum anúncio pode ficar
    no ar sem descrição. Varre TODOS os anúncios ML ativos, confirma via
    GET /items/{id}/description se cada um realmente tem texto — se não
    tiver mas a peça já tem part.description salvo localmente, empurra e
    confirma na hora; se a peça também não tem descrição local nenhuma
    (não passou pela identificação automática, ex: publicada manualmente
    fora da esteira), só reporta — não dá pra inventar uma descrição sem
    rodar a identificação de novo."""
    desc_audit_state.update({"running": True, "processed": 0, "total": 0, "ja_tinha": 0, "corrigido": 0,
                             "sem_descricao_local": [], "erro": [], "done": False})
    db = SessionLocal()
    try:
        listings = db.query(MarketplaceListing).filter(
            MarketplaceListing.marketplace == "mercadolivre",
            MarketplaceListing.status == "active",
        ).all()
        desc_audit_state["total"] = len(listings)
        sem = asyncio.Semaphore(6)

        async def processa(listing: MarketplaceListing):
            async with sem:
                account = await resolve_account_for_listing(listing, db)
                if not account or not account.get("access_token"):
                    desc_audit_state["erro"].append({"listing_id": listing.listing_id, "motivo": "conta não resolvida"})
                    return
                headers = {"Authorization": f"Bearer {account['access_token']}", "Content-Type": "application/json"}
                async with httpx.AsyncClient(timeout=20) as client:
                    try:
                        r = await client.get(f"https://api.mercadolibre.com/items/{listing.listing_id}/description", headers=headers)
                        tem_desc = r.status_code == 200 and bool((r.json() or {}).get("plain_text", "").strip())
                        if tem_desc:
                            desc_audit_state["ja_tinha"] += 1
                            return
                        part = db.query(Part).filter(Part.id == listing.part_id).first()
                        desc_text = (part.description or part.notes or "").strip() if part else ""
                        if not desc_text:
                            desc_audit_state["sem_descricao_local"].append({
                                "part_id": listing.part_id, "listing_id": listing.listing_id,
                                "title": part.title if part else None,
                            })
                            return
                        await client.post(
                            f"https://api.mercadolibre.com/items/{listing.listing_id}/description",
                            json={"plain_text": desc_text[:50000]}, headers=headers,
                        )
                        check = await client.get(f"https://api.mercadolibre.com/items/{listing.listing_id}/description", headers=headers)
                        if check.status_code == 200 and (check.json() or {}).get("plain_text", "").strip():
                            desc_audit_state["corrigido"] += 1
                        else:
                            desc_audit_state["erro"].append({"listing_id": listing.listing_id, "motivo": "push falhou na confirmação"})
                    except Exception as e:
                        desc_audit_state["erro"].append({"listing_id": listing.listing_id, "motivo": str(e)})
                    finally:
                        desc_audit_state["processed"] += 1

        await asyncio.gather(*(processa(l) for l in listings))
    finally:
        desc_audit_state.update({"running": False, "done": True})
        db.close()


@router.post("/audit-descricoes")
def audit_descricoes_start(background_tasks: BackgroundTasks):
    """Inicia a varredura de TODOS os anúncios ML ativos: confirma descrição
    de verdade (GET), corrige na hora se a peça já tem descrição local, e
    reporta quais não têm nenhuma descrição salva em lugar nenhum (essas
    precisam rodar a identificação de novo pra gerar uma)."""
    if desc_audit_state["running"]:
        return {"status": "already_running", **desc_audit_state}
    background_tasks.add_task(_run_audit_descricoes)
    return {"status": "started"}


@router.get("/audit-descricoes/status")
def audit_descricoes_status():
    return desc_audit_state
