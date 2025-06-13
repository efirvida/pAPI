from papi.core.settings import get_config
from user_auth_system.schemas import AuthSettings, BaseSecurity

config = get_config()
auth_settings = AuthSettings(**config.addons.config["user_auth_system"])
security: BaseSecurity = auth_settings.security
