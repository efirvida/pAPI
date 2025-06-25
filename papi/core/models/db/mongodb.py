from typing import Literal, Optional, Union

from pydantic import Field

from .base import BackendSettings


class MongoDBEngineConfig(BackendSettings):
    """
    MongoDB configuration options for customizing client behavior.

    These settings define connection pool parameters, timeouts, retry policies,
    compression, TLS options, and MongoDB-specific behaviors such as read and
    write concerns. Parameters defined in the MongoDB URI are excluded.

    Attributes:
        max_pool_size (Optional[int]):
            The maximum number of concurrent connections per server. Default is 100.

        min_pool_size (Optional[int]):
            The minimum number of concurrent connections per server. Default is 0.

        max_idle_time_ms (Optional[int]):
            Maximum time (in milliseconds) that a connection can remain idle in the pool
            before being closed. Default is None (no limit).

        max_connecting (Optional[int]):
            Maximum number of concurrent connection attempts allowed per pool. Default is 2.

        timeout_ms (Optional[int]):
            Maximum time (in milliseconds) allowed for operations before timing out.
            Default is None (no timeout).

        connect_timeout_ms (Optional[int]):
            Time (in milliseconds) to wait for a connection to be established before
            raising an error. Default is 20000 (20 seconds).

        socket_timeout_ms (Optional[int]):
            Time (in milliseconds) to wait for a response after a request is sent.
            Default is None (no timeout).

        server_selection_timeout_ms (Optional[int]):
            Time (in milliseconds) to wait for a suitable server to be selected.
            Default is 30000 (30 seconds).

        wait_queue_timeout_ms (Optional[int]):
            Maximum time (in milliseconds) a thread will wait for a socket when the
            pool is exhausted. Default is None (no timeout).

        compressors (Optional[list[Literal["zlib", "snappy", "zstd"]]]):
            List of compression algorithms to negotiate with the server.
            Compression must also be enabled on the server side.

        zlib_compression_level (Optional[int]):
            Compression level for zlib (from -1 to 9). -1 uses the default level.
            Default is -1.

        retry_reads (Optional[bool]):
            Whether to retry supported read operations after a transient error.
            Default is True.

        retry_writes (Optional[bool]):
            Whether to retry supported write operations after a transient error.
            Default is True.

        read_preference (Optional[Literal["primary", "primaryPreferred", "secondary", "secondaryPreferred", "nearest"]]):
            Determines which member of a replica set to read from.
            Default is "primary".

        read_concern_level (Optional[str]):
            The read concern level to apply to read operations
            (e.g., "local", "majority", "linearizable", etc.). Default is None.

        write_concern_w (Optional[Union[int, str]]):
            Write acknowledgment level. Can be an integer or a tag set string.
            Default is None.

        journal (Optional[bool]):
            If True, write operations will only return after being committed to the journal.
            Cannot be used with `fsync`.

        fsync (Optional[bool]):
            If True, write operations will block until data is flushed to disk.
            Cannot be used with `journal`.

        tls (Optional[bool]):
            Whether to use TLS/SSL to connect. Default is None.

        tls_insecure (Optional[bool]):
            Enables all insecure TLS options (disables cert and hostname verification).
            Use with caution. Default is None.

        tls_allow_invalid_certificates (Optional[bool]):
            If True, skip certificate validation during the TLS handshake.
            Default is None.

        tls_allow_invalid_hostnames (Optional[bool]):
            If True, disable verification of the server hostname in the certificate.
            Default is None.

        tls_ca_file (Optional[str]):
            Path to a file containing the Certificate Authority certificate(s).
            Default is None.

        tls_certificate_key_file (Optional[str]):
            Path to a file containing the client certificate and private key.
            Default is None.

        tls_certificate_key_file_password (Optional[str]):
            Password to decrypt the TLS key file, if encrypted. Default is None.

        tls_disable_ocsp_endpoint_check (Optional[bool]):
            If True, disables OCSP endpoint verification. Default is None.

        appname (Optional[str]):
            Logical name of the application, sent to the server and used in logs.
            Default is None.

        uuid_representation (Optional[Literal["standard", "pythonLegacy", "javaLegacy", "csharpLegacy", "unspecified"]]):
            The BSON representation of UUIDs. "standard" is recommended for new applications.
            Default is "unspecified".

    Example:
        ```python
        config = MongoDBConfig(
            max_pool_size=200,
            connect_timeout_ms=15000,
            retry_reads=True,
            retry_writes=True,
            read_preference="secondaryPreferred",
            compressors=["zlib", "snappy"],
            zlib_compression_level=6,
            tls=True,
            tls_ca_file="/path/to/ca.pem",
            appname="my-cool-service",
            uuid_representation="standard",
        )
        ```
    """

    max_pool_size: Optional[int] = Field(default=100)
    min_pool_size: Optional[int] = Field(default=0)
    max_idle_time_ms: Optional[int] = None
    max_connecting: Optional[int] = Field(default=2)

    timeout_ms: Optional[int] = None
    connect_timeout_ms: Optional[int] = Field(default=20000)
    socket_timeout_ms: Optional[int] = None
    server_selection_timeout_ms: Optional[int] = Field(default=30000)
    wait_queue_timeout_ms: Optional[int] = None

    compressors: Optional[list[Literal["zlib", "snappy", "zstd"]]] = None
    zlib_compression_level: Optional[int] = Field(default=-1)

    retry_reads: Optional[bool] = Field(default=True)
    retry_writes: Optional[bool] = Field(default=True)
    read_preference: Optional[
        Literal[
            "primary", "primaryPreferred", "secondary", "secondaryPreferred", "nearest"
        ]
    ] = Field(default="primary")
    read_concern_level: Optional[str] = None
    write_concern_w: Optional[Union[int, str]] = None
    journal: Optional[bool] = None
    fsync: Optional[bool] = None

    tls: Optional[bool] = None
    tls_insecure: Optional[bool] = None
    tls_allow_invalid_certificates: Optional[bool] = None
    tls_allow_invalid_hostnames: Optional[bool] = None
    tls_ca_file: Optional[str] = None
    tls_certificate_key_file: Optional[str] = None
    tls_certificate_key_file_password: Optional[str] = None
    tls_disable_ocsp_endpoint_check: Optional[bool] = None

    appname: Optional[str] = None
    uuid_representation: Optional[
        Literal["standard", "pythonLegacy", "javaLegacy", "csharpLegacy", "unspecified"]
    ] = Field(default="unspecified")
