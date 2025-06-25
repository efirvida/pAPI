from typing import Any, Callable, Dict, Literal, Optional, Union

from pydantic import Field, field_validator

from .base import BackendSettings


class SQLAlchemyEngineConfig(BackendSettings):
    """
    Configuration model for SQLAlchemy engine.

    This model includes all commonly used parameters for SQLAlchemy engine creation.
    It ensures type safety, input validation, and enables declarative configuration.

    Attributes:
        connect_args (dict): Extra arguments passed directly to the DBAPI's `connect()` method.
        echo (bool | 'debug'): Enables SQL logging to stdout or enhanced output.
        echo_pool (bool | 'debug'): Enables logging for connection pool operations.
        enable_from_linting (bool): Warns on unlinked FROM clauses that may cause cartesian products.
        execution_options (dict): Options applied to all connections.
        future (bool): SQLAlchemy 2.x style engine enforcement (should remain True).
        hide_parameters (bool): Prevents SQL parameter values from appearing in logs.
        implicit_returning (bool): Legacy flag, only `True` allowed in SQLAlchemy 2.0.
        insertmanyvalues_page_size (int): Batch size for paged inserts.
        isolation_level (str): Transaction isolation level (e.g., 'READ COMMITTED').
        label_length (int): Max length of auto-generated SQL labels.
        logging_name (str): Custom name for engine logs.
        max_identifier_length (int): Override database identifier length limits.
        max_overflow (int): Max number of connections above `pool_size`.
        paramstyle (str): Paramstyle used for bound parameters.
        pool (Any): Custom connection pool instance.
        poolclass (Any): Custom Pool class (e.g., `QueuePool`, `NullPool`).
        pool_logging_name (str): Custom name for pool log entries.
        pool_pre_ping (bool): Enables pre-ping check on each connection checkout.
        pool_size (int): Max number of connections in pool.
        pool_recycle (int): Seconds after which a connection is recycled.
        pool_reset_on_return (str | None): What to do on connection return: 'rollback', 'commit', or None.
        pool_timeout (float): Seconds to wait for a connection from the pool.
        pool_use_lifo (bool): Use LIFO strategy in queue (instead of FIFO).
        plugins (list[str]): List of plugin names to apply to the engine.
        query_cache_size (int): Size of SQL string compilation cache.
        use_insertmanyvalues (bool): Use bulk insert + RETURNING.
    """

    connect_args: Optional[Dict[str, Any]] = Field(default_factory=dict)
    echo: Union[bool, Literal["debug"]] = False
    echo_pool: Union[bool, Literal["debug"]] = False
    enable_from_linting: bool = True
    execution_options: Optional[Dict[str, Any]] = Field(default_factory=dict)
    future: bool = True
    hide_parameters: bool = False
    implicit_returning: bool = True
    insertmanyvalues_page_size: Optional[int] = 1000
    isolation_level: Optional[str] = None
    label_length: Optional[int] = None
    logging_name: Optional[str] = None
    max_identifier_length: Optional[int] = None
    max_overflow: Optional[int] = 10
    module: Optional[Any] = None
    paramstyle: Optional[Literal["qmark", "numeric", "named", "format", "pyformat"]] = (
        None
    )
    pool: Optional[Any] = None
    poolclass: Optional[Any] = None
    pool_logging_name: Optional[str] = None
    pool_pre_ping: bool = False
    pool_size: Optional[int] = 5
    pool_recycle: int = -1
    pool_reset_on_return: Optional[Literal["rollback", "commit", None]] = "rollback"
    pool_timeout: float = 30.0
    pool_use_lifo: bool = False
    plugins: Optional[list[str]] = None
    query_cache_size: int = 500
    use_insertmanyvalues: bool = True
    json_serializer: Optional[Callable[[Any], str]] = None
    json_deserializer: Optional[Callable[[str], Any]] = None

    @field_validator("label_length")
    @classmethod
    def check_label_length(cls, v, info):
        if v is not None:
            max_len = info.data.get("max_identifier_length")
            if max_len is not None and v > max_len:
                raise ValueError(
                    "label_length cannot be greater than max_identifier_length"
                )
        return v
