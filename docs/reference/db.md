# Database Utilities

pAPI provides utilities for working with multiple database backends including Redis, SQL databases (via SQLAlchemy), and MongoDB (via Beanie).

## API Reference

:::papi.core.db 
    options:
        members:
            - get_redis_client
            - get_redis_uri_with_db
            - get_sql_session
            - sql_session
            - query_helper
            - create_database_if_not_exists