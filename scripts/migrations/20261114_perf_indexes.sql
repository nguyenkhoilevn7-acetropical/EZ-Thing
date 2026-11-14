-- EZ Thing staging index migration 2026-11-14.
-- Non-destructive, rerunnable. Apply once to existing staging PostgreSQL.
-- For production-size tables, use CREATE INDEX CONCURRENTLY in independent sessions.
CREATE INDEX IF NOT EXISTS ix_orders_biz_status_paid_at
    ON sale_orders (business_id, status, paid_at);
CREATE INDEX IF NOT EXISTS ix_order_items_biz_order
    ON sale_order_items (business_id, order_id);
CREATE INDEX IF NOT EXISTS ix_stock_movements_biz_ref
    ON stock_movements (business_id, ref);
