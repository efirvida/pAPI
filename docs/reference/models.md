# Models

Core data models and schemas used throughout the pAPI framework.

## Configuration Models

:::papi.core.models.config 
    options:
        members:
            - AppConfig
            - FastAPIAppConfig
            - UvicornServerConfig
            - AddonsConfig
            - LoggerConfig
            - DatabaseConfig
            - StorageConfig

## Addon Models

:::papi.core.models.addons 
    options:
        members:
            - AddonManifest

## Response Models

:::papi.core.models.response 
    options:
        members:
            - Meta
            - APIError
            - APIResponse
