from sqlalchemy import create_engine, text

url = "postgresql://tn_app_db_user:aZr9B1LSnc68js5CtLgtOzsZ2IuoZ5kd@dpg-d6o821cr85hc7398glc0-a.oregon-postgres.render.com/tn_app_db"

engine = create_engine(url)

with engine.connect() as conn:
    rows = conn.execute(
        text(
            "SELECT key, label, value_type "
            "FROM attribute_definitions "
            "WHERE key IN ('ancho_cm', 'composicion') "
            "ORDER BY key"
        )
    )
    print("attribute_definitions filtrada:")
    print(list(rows))

    rows_all = conn.execute(text("SELECT * FROM attribute_definitions ORDER BY key"))
    print("\nattribute_definitions completa:")
    print(list(rows_all))

    rows_count = conn.execute(text("SELECT COUNT(*) FROM product_attribute_values"))
    print("\ncount product_attribute_values:")
    print(list(rows_count))
