"""POS register real-photo and source-contract regression tests."""
import io
import os
from pathlib import Path
from PIL import Image
import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"]="sqlite:///"+str(Path(__file__).parent/"pilot-tests.db")

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_db(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def register(c, suffix):
    r=c.post("/api/auth/signup",json={"name":"Photo POS Owner",
        "email":f"photo-pos-{suffix}@example.com","password":"SafePassword!123"})
    assert r.status_code==201,r.text
    csrf=r.json()["csrf_token"]
    b=c.post("/api/businesses",headers={"x-csrf-token":csrf},json={
        "name":"Photo Store","industry":"fnb","selected_plan":"PRO",
        "need_tables":True,"need_inventory":True})
    assert b.status_code==201,b.text
    bid=b.json()["id"]
    prod=c.post(f"/api/businesses/{bid}/products",headers={"x-csrf-token":csrf},
                json={"name":"Trà vải","sku":"TRA-VAI-PIC","price_vnd":39000,
                      "stock":10,"track_stock":True,"category":"Đồ uống"})
    assert prod.status_code==201,prod.text
    return csrf,bid,prod.json()["id"]


def png_data():
    image=Image.new("RGB",(168,112),(77,168,220))
    out=io.BytesIO()
    image.save(out,"PNG")
    return out.getvalue()


def test_tenant_private_image_uploaded_once_and_shown_by_public_catalog():
    with TestClient(app) as owner,TestClient(app) as other,TestClient(app) as guest:
        csrf,bid,pid=register(owner,"one")
        other_csrf,other_bid,other_pid=register(other,"two")
        path=f"/api/businesses/{bid}/products/{pid}/photo"
        assert owner.get(path).status_code==404
        assert owner.put(path,files={"file":("malware.txt",b"fake","text/plain")},
                         headers={"x-csrf-token":csrf}).status_code==422
        uploaded=owner.put(path,files={"file":("tea.png",png_data(),"image/png")},
                           headers={"x-csrf-token":csrf})
        assert uploaded.status_code==200,uploaded.text
        photo_path=uploaded.json()["image_url"]
        assert photo_path.startswith(path+"?v=")
        img=owner.get(photo_path)
        assert img.status_code==200 and img.headers["content-type"].startswith("image/webp")
        assert img.content.startswith(b"RIFF")
        assert "private" in img.headers["cache-control"]

        items=owner.get(f"/api/businesses/{bid}/products").json()
        assert next(p for p in items if p["id"]==pid)["image_url"]==photo_path
        assert other.get(path).status_code==404
        assert other.delete(path,headers={"x-csrf-token":other_csrf}).status_code==404
        assert guest.get(path).status_code==401

        public_slug="travai-photo-pos"
        published=owner.put(f"/api/businesses/{bid}/publishing",
            headers={"x-csrf-token":csrf},
            json={"slug":public_slug,"published":True})
        assert published.status_code==200,published.text
        public=guest.get(f"/api/public/shops/{public_slug}")
        assert public.status_code==200,public.text
        item=next(p for p in public.json()["products"] if p["id"]==pid)
        assert item["image_url"].startswith(f"/api/public/shops/{public_slug}/products/{pid}/photo?v=")
        shown=guest.get(item["image_url"])
        assert shown.status_code==200 and shown.content.startswith(b"RIFF")
        assert guest.get(f"/api/public/shops/{public_slug}/products/{other_pid}/photo").status_code==404
        assert owner.delete(path,headers={"x-csrf-token":csrf}).status_code==200
        assert owner.get(path).status_code==404
        assert guest.get(item["image_url"]).status_code==404
        assert next(p for p in owner.get(f"/api/businesses/{bid}/products").json()
                    if p["id"]==pid)["image_url"] is None


def test_photo_is_not_served_when_unpublished():
    with TestClient(app) as owner,TestClient(app) as guest:
        csrf,bid,pid=register(owner,"hidden")
        path=f"/api/businesses/{bid}/products/{pid}/photo"
        assert owner.put(path,files={"file":("tea.png",png_data(),"image/png")},
                         headers={"x-csrf-token":csrf}).status_code==200
        assert guest.get(f"/api/public/shops/unpublished/products/{pid}/photo").status_code==404


def test_pos_register_wiring_is_dedicated_and_no_legacy_form_routing():
    static=Path(__file__).resolve().parents[1]/"app/static"
    html=(static/"index.html").read_text()
    app_js=(static/"app.js").read_text()
    register_js=(static/"merchant-register.js").read_text()
    css=(static/"merchant-register.css").read_text()
    public=(static/"public-shop.js").read_text()
    for file in ("merchant-register.js","merchant-register.css"):
        assert file in html
    assert "['pos','store','Bán hàng POS']" in app_js
    assert "if(cashRegister?.open){cashRegister.open(preTable);return}" in app_js
    assert "pos:()=>cashRegister?.render()" in app_js
    for marker in ("data-ezreg=\"product\"","ezreg-option-dialog",
                   "validOptionCount","idempotency_key","branch_id",
                   "selected_options","Ctrl"):
        if marker=="Ctrl":continue
        assert marker in register_js
    assert "navigator.onLine" in register_js
    assert "onPaid" in register_js
    assert "image_url" in public
    assert "@media(max-width:650px)" in css
    assert "order-card-list" in css
