import logging
logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    # this is the trigger that sends notifications when jobs change
    logger.info("Create stock_quant_notify trigger")
    cr.execute(
        """
            CREATE TABLE IF NOT EXISTS stock_quant_audit (
                id INT GENERATED ALWAYS AS IDENTITY,
                product_id INT NOT NULL
            );
            DROP TRIGGER IF EXISTS stock_quant_change_notify ON stock_quant;
            CREATE OR REPLACE
                FUNCTION stock_quant_change_notify() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    INSERT INTO stock_quant_audit (product_id)
                    SELECT OLD.product_id
                    WHERE NOT EXISTS (SELECT 1 from stock_quant_audit where product_id = OLD.product_id);
                    RETURN OLD;
                ELSE
                    INSERT INTO stock_quant_audit (product_id)
                    SELECT NEW.product_id
                    WHERE NOT EXISTS (SELECT 1 from stock_quant_audit where product_id = NEW.product_id);
                    RETURN NEW;
                END IF;
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER stock_quant_change_notify
                BEFORE INSERT OR UPDATE OR DELETE
                ON stock_quant
                FOR EACH ROW EXECUTE PROCEDURE stock_quant_change_notify();
        """
    )
