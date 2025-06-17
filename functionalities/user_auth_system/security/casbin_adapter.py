# adapter.py


from casbin import persist
from casbin.persist.adapters.asyncio import AsyncAdapter
from sqlalchemy import delete, select

from papi.core.db import get_sql_session
from user_auth_system.models.casbin import AuthRules


class AsyncCasbinAdapter(AsyncAdapter):
    """the interface for Casbin adapters."""

    def __init__(self):
        self._db_class = AuthRules

    async def _save_policy_line(self, ptype, rule):
        async with get_sql_session() as session:
            line = self._db_class(ptype=ptype)
            for i, v in enumerate(rule):
                setattr(line, "v{}".format(i), v)
            session.add(line)

    async def load_policy(self, model):
        """loads all policy rules from the storage."""
        async with get_sql_session() as session:
            lines = await session.execute(select(self._db_class))
            for line in lines.scalars():
                persist.load_policy_line(str(line), model)

    async def save_policy(self, model):
        """saves all policy rules to the storage."""
        async with get_sql_session() as session:
            stmt = delete(self._db_class)
            await session.execute(stmt)
            for sec in ["p", "g"]:
                if sec not in model.model.keys():
                    continue
                for ptype, ast in model.model[sec].items():
                    for rule in ast.policy:
                        await self._save_policy_line(ptype, rule)

    async def add_policy(self, sec, ptype, rule):
        """adds a policy rule to the storage."""
        await self._save_policy_line(ptype, rule)

    async def remove_policy(self, sec, ptype, rule):
        """removes a policy rule from the storage."""
        async with get_sql_session() as session:
            stmt = delete(self._db_class).where(self._db_class.ptype == ptype)
            for i, v in enumerate(rule):
                stmt = stmt.where(getattr(self._db_class, "v{}".format(i)) == v)
            await session.execute(stmt)

    async def remove_filtered_policy(self, sec, ptype, field_index, *field_values):
        """removes policy rules that match the filter from the storage.
        This is part of the Auto-Save feature.
        """
        async with get_sql_session() as session:
            stmt = delete(self._db_class).where(self._db_class.ptype == ptype)

            if not (0 <= field_index <= 5):
                return
            if not (1 <= field_index + len(field_values) <= 6):
                return
            for i, v in enumerate(field_values):
                if v != "":
                    v_value = getattr(self._db_class, "v{}".format(field_index + i))
                    stmt = stmt.where(v_value == v)
            await session.execute(stmt)
