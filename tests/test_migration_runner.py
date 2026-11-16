"""Versioned additive migrations validate on a throwaway local database only."""
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from app.models import User, Business

from app.database import Base
from app.main import app  # noqa: F401 - registers all tenant models


ROOT=Path(__file__).resolve().parents[1]

def test_alembic_adds_team_and_site_schema_without_touching_business_rows(tmp_path,monkeypatch):
    url="sqlite:///"+str(tmp_path/"migration-test.db")
    engine=create_engine(url)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        db.add(User(id="user-1",email="owner@test.invalid",name="Owner",password_hash="hash"))
        db.add(Business(id="biz-1",name="My shop",industry="retail",plan="PRO",
                        requested_plan="PRO",subscription_status="pilot"))
        db.commit()
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE team_invitations")
        conn.exec_driver_sql("DROP TABLE public_storefronts")
    cfg=Config(str(ROOT/"alembic.ini"))
    monkeypatch.setenv("DATABASE_URL",url)
    command.upgrade(cfg,"head")
    with engine.connect() as conn:
        inspector=inspect(conn)
        assert inspector.has_table("team_invitations")
        assert inspector.has_table("public_storefronts")
        assert inspector.has_table("print_devices")
        assert inspector.has_table("print_jobs")
        assert inspector.has_table("product_media")
        assert inspector.has_table("manual_tender_receipts")
        assert inspector.has_table("workstations")
        version=conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version=="20261116_11"
        assert inspector.has_table("pos_check_meta")
        assert inspector.has_table("pos_check_mutations")
        assert inspector.has_table("product_modifier_sets")
        assert inspector.has_table("sale_order_item_modifiers")
        assert inspector.has_table("storefront_media")
        assert inspector.has_table("public_order_requests")
        assert inspector.has_table("auth_email_verifications")
        assert conn.execute(text("SELECT name FROM businesses WHERE id='biz-1'")).scalar_one()=="My shop"
        assert conn.execute(text("SELECT email FROM users WHERE id='user-1'")).scalar_one()=="owner@test.invalid"
    # Re-running the migration should be idempotent.
    command.upgrade(cfg,"head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM businesses")).scalar_one()==1


def test_baseline_fails_closed_on_unrecognized_empty_database(tmp_path,monkeypatch):
    url="sqlite:///"+str(tmp_path/"empty.db")
    monkeypatch.setenv("DATABASE_URL",url)
    cfg=Config(str(ROOT/"alembic.ini"))
    import pytest
    with pytest.raises(RuntimeError,match="Cannot baseline unknown/empty database"):
        command.upgrade(cfg,"head")
