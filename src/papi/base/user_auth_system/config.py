from papi.core.settings import get_config
from user_auth_system.schemas import AuthSettings, BaseSecurity

config = get_config()
main_config = config.addons.config.get("user_auth_system", {})
auth_settings = AuthSettings(**main_config)
security: BaseSecurity = auth_settings.security
