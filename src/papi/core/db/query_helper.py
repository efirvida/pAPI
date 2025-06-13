from typing import Any, Union

from sqlalchemy import Select
from sqlalchemy.engine import Result
from sqlalchemy.exc import SQLAlchemyError

from .sql_session import get_sql_session


async def query_helper(statement: Any) -> Union[list[Any], int, Result]:
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
