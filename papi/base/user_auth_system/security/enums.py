from enum import StrEnum


class AuditLogKeys(StrEnum):
    ACCESS_ATTEMPT_INACTIVE = "access_attempt_inactive"
    ACCOUNT_LOCKED = "account_locked"
    KEY_ROTATION = "key_rotation"
    LOGIN_FAILED = "login_failed"
    LOGIN_INACTIVE = "login_inactive"
    LOGIN_LOCKOUT = "login_lockout"
    LOGIN_SUCCESS = "login_success"
    PERMISSION_DENIED = "permission_denied"
    PERMISSION_GRANTED = "permission_granted"
    SYSTEM_LOCKOUT = "system_lockout"


class PolicyEffect(StrEnum):
    """
    Defines the effect of a policy rule.
    Typically used in Casbin to indicate whether a request should be allowed or denied.
    """

    ALLOW = "allow"
    DENY = "deny"


class PolicyAction(StrEnum):
    """
    Defines a comprehensive list of standard policy actions for access control.
    These values are typically used in Casbin policy definitions.

    Use 'ALL' (".*") to represent any action when defining wildcard permissions.
    """

    # Wildcard
    ALL = ".*"  # Matches any action

    # CRUD operations
    CREATE = "create"  # Create new resources (alias of WRITE in some contexts)
    READ = "read"  # View or retrieve resources
    WRITE = "write"  # Write or submit new data (more generic than CREATE)
    UPDATE = "update"  # Modify existing resources
    DELETE = "delete"  # Remove resources
    PATCH = "patch"  # Partial update of a resource

    # Execution and control
    EXECUTE = "execute"  # Execute a command, job, or script
    APPROVE = "approve"  # Approve actions or resources (e.g., moderation)
    REJECT = "reject"  # Reject or decline actions/resources

    # Resource listing and searching
    LIST = "list"  # List resources (could be paginated)
    SEARCH = "search"  # Perform queries or search operations
    EXPORT = "export"  # Export data to file
    IMPORT = "import"  # Import data from file

    # Authentication and session
    LOGIN = "login"  # User login action
    LOGOUT = "logout"  # User logout action
    REGISTER = "register"  # Account creation

    # Permissions and roles
    ASSIGN = "assign"  # Assign roles or permissions
    REVOKE = "revoke"  # Revoke roles or permissions
    GRANT = "grant"  # Grant specific access
    DENY = "deny"  # Deny specific access
