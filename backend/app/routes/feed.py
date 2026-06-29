from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.part import Part

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/facebook", response_class=Response)
def facebook_feed(db: Session = Depends(get_db)):
    parts = db.query(Part).filter(Part.active == True, Part.quantity > 0, Part.sale_price > 0).all()

    lines = [
        "id\ttitle\tdescription\tavailability\tcondition\tprice\tlink\timage_link\tbrand\tgtin"
    ]
    for p in parts:
        pid = str(p.id)
        title = (p.title or "").replace("\t", " ").replace("\n", " ")[:150]
        desc = (p.description or p.title or "").replace("\t", " ").replace("\n", " ")[:500]
        availability = "in stock" if p.quantity > 0 else "out of stock"
        condition = "new" if p.condition == "new" else "used"
        price = f"{p.sale_price:.2f} BRL"
        link = f"https://fortunatoautoparts.com.br/pecas/{p.id}"
        image = p.photos[0] if p.photos else ""
        brand = (p.brand or "Fortunato Auto Parts").replace("\t", " ")
        gtin = p.code_oem or p.code_manufacturer or ""

        lines.append(f"{pid}\t{title}\t{desc}\t{availability}\t{condition}\t{price}\t{link}\t{image}\t{brand}\t{gtin}")

    content = "\n".join(lines)
    return Response(content=content, media_type="text/tab-separated-values; charset=utf-8")
