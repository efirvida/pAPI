from typing import Any, Union

from sqlalchemy import Select
from sqlalchemy.engine import Result
from sqlalchemy.exc import SQLAlchemyError

from .sql_session import get_sql_session


async def query_helper(statement: Any) -> Union[list[Any], int, Result]:
    """
    Execute a SQL statement asynchronously using a managed SQLAlchemy session.

    This helper detects the type of the SQL statement and returns the appropriate result:

    - For `INSERT`, `UPDATE`, or `DELETE` operations, it returns the number of affected rows (`rowcount`).
    - For `SELECT` operations:
      - If only one column is selected: returns a list of scalar values.
      - If multiple columns are selected: returns a list of tuples (rows).
    - For other kinds of queries, it returns the raw `Result` object.

    Args:
        statement (Any): A SQLAlchemy statement, such as `select(...)`, `update(...)`, etc.

    Returns:
        Union[list[Any], int, Result]: Query result depending on the statement type.

    Raises:
        RuntimeError: If an error occurs while executing the query.

    Example:
        Selecting users:
        ```python
        from sqlalchemy import select
        from myapp.models import User
        from myapp.db.helpers import query_helper

        stmt = select(User).where(User.is_active == True)
        users = await query_helper(stmt)
        ```

        Updating a user:
        ```python
        from sqlalchemy import update

        stmt = update(User).where(User.name == "John").values(is_active=False)
        affected_rows = await query_helper(stmt)
        ```
    """
    async with get_sql_session() as session:
        try:
            result: Result = await session.execute(statement)

            if (
                getattr(statement, "is_insert", False)
                or getattr(statement, "is_update", False)
                or getattr(statement, "is_delete", False)
            ):
                return result.rowcount

            if isinstance(statement, Select):
                if len(statement.selected_columns) == 1:
                    return result.scalars().all()
                return result.all()

            return result

        except SQLAlchemyError as e:
            raise RuntimeError(f"SQLAlchemy error during query execution: {e}") from e
