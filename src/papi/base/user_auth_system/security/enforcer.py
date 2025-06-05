import ast
import asyncio
import datetime
from typing import Any, Dict

from casbin import AsyncEnforcer, Model
from casbin.util import key_match2, regex_match
from loguru import logger

from user_auth_system.security import casbin_policies
from user_auth_system.security.casbin_adapter import AsyncCasbinAdapter as Adapter


class CasbinRequest:
    """
    Encapsulates an authorization request for Casbin evaluation.

    This class represents a request to be evaluated against Casbin policies.
    It includes the subject (user or role), object (resource), and action
    to be performed.

    Attributes:
        sub (dict): Subject attributes including:
            - username: User identifier
            - roles: List of role names
            - is_superuser: Superuser status
        obj (str): Object or resource being accessed
        act (str): Action to perform on the resource

    Example:
        request = CasbinRequest(
            sub={"username": "john", "roles": ["admin"]},
            obj="users",
            act="read"
        )
    """

    def __init__(self, sub: Dict[str, Any], obj: str, act: str):
        if not isinstance(sub, dict):
            raise ValueError("Subject must be a dictionary")
        if not isinstance(obj, str):
            raise ValueError("Object must be a string")
        if not isinstance(act, str):
            raise ValueError("Action must be a string")

        self.sub = sub
        self.obj = obj
        self.act = act

    def __str__(self) -> str:
        """Returns a human-readable representation of the request."""
        return f"CasbinRequest(sub={self.sub}, obj='{self.obj}', act='{self.act}')"

    def __repr__(self) -> str:
        """Returns a detailed string representation for debugging."""
        return f"<CasbinRequest sub={self.sub!r} obj={self.obj!r} act={self.act!r}>"

    def __eq__(self, other: object) -> bool:
        """Enables comparison between CasbinRequest objects."""
        if not isinstance(other, CasbinRequest):
            return NotImplemented
        return self.sub == other.sub and self.obj == other.obj and self.act == other.act


# --- Casbin RBAC Model with Conditions ---
CASBIN_MODEL = """
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act, condition, eft

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = (g(r.sub['username'], p.sub) || check_roles(r.sub['roles'], p.sub) || check_groups(r.sub['groups'], p.sub)) && keyMatch2(r.obj, p.obj) && regexMatch(r.act, p.act) && safe_abac_eval(p.condition)
"""


def check_roles(user_roles: list, policy_sub: str) -> bool:
    """
    Checks whether the user has a role required by the policy subject.

    Args:
        user_roles (list): Roles assigned to the user.
        policy_sub (str): Policy subject string (e.g., 'role:admin').

    Returns:
        bool: True if role matches; otherwise False.
    """
    if not isinstance(user_roles, list):
        return False
    if not policy_sub.startswith("role:"):
        return False
    try:
        role = policy_sub.split(":", 1)[1]
        return role in user_roles
    except Exception:
        return False


def check_groups(user_groups: list, policy_sub: str) -> bool:
    """
    Checks whether the user belongs to a group required by the policy subject.

    Args:
        user_groups (list): Groups assigned to the user.
        policy_sub (str): Policy subject string (e.g., 'group:editors').

    Returns:
        bool: True if group matches; otherwise False.
    """
    if not isinstance(user_groups, list):
        return False
    if not policy_sub.startswith("group:"):
        return False
    try:
        group = policy_sub.split(":", 1)[1]
        return group in user_groups
    except Exception:
        return False


def safe_abac_eval(condition: str, r: CasbinRequest) -> bool:
    """
    Safely evaluates an ABAC (Attribute-Based Access Control) condition.

    Args:
        condition (str): Condition string from the policy.
        r (CasbinRequest): The request object to use in evaluation.

    Returns:
        bool: True if condition passes; otherwise False.
    """
    if not condition or condition.strip().lower() == "true":
        return True

    try:
        allowed_names = {"r", "sub", "obj", "act"}
        tree = ast.parse(condition, mode="eval")

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id not in allowed_names:
                logger.warning(f"Unauthorized name in condition: {node.id}")
                return False

        context = {"r": r, "sub": r.sub, "obj": r.obj, "act": r.act}
        return eval(condition, {"__builtins__": None}, context)

    except Exception as e:
        logger.error(f"ABAC eval error: {e}")
        return False


async def debug_enforcement(
    enforcer: AsyncEnforcer, request_obj: CasbinRequest
) -> bool:
    """
    Prints matching policies and evaluation result for debugging authorization.

    Args:
        enforcer (AsyncEnforcer): The Casbin enforcer instance.
        request_obj (CasbinRequest): The request to evaluate.

    Returns:
        bool: True if access is allowed, False otherwise.
    """
    logger.debug("=== DEBUGGING ENFORCEMENT ===")
    logger.debug(
        f"Request: sub={request_obj.sub}, obj={request_obj.obj}, act={request_obj.act}"
    )

    matches = []
    try:
        for policy in enforcer.get_policy():
            if len(policy) < 5:
                logger.warning(f"Skipping incomplete policy: {policy}")
                continue

            pol_sub, pol_obj, pol_act, pol_cond, pol_eft = policy

            user_roles = await enforcer.get_roles_for_user(
                request_obj.sub.get("username", "")
            )
            sub_match = pol_sub == request_obj.sub.get("username") or any(
                role.strip() in user_roles for role in pol_sub.split(",")
            )
            obj_match = key_match2(request_obj.obj, pol_obj)
            act_match = regex_match(request_obj.act, pol_act)
            cond_match = safe_abac_eval(pol_cond, request_obj)
            eft_match = pol_eft.strip().lower() == "allow"

            if sub_match and obj_match and act_match and cond_match and eft_match:
                logger.info(f"- MATCHED: {policy}")
                matches.append(policy)

        result = enforcer.enforce(request_obj.sub, request_obj.obj, request_obj.act)
        logger.debug(f"Final enforce result: {result}")
        return result

    except Exception:
        logger.exception("Error during enforcement")
        return False


async def build_temp_enforcer(
    base: AsyncEnforcer, request_obj: CasbinRequest, user: Any
) -> AsyncEnforcer:
    """
    Creates a temporary Casbin enforcer with custom context and functions.

    Args:
        base (AsyncEnforcer): The base enforcer.
        request_obj (CasbinRequest): The authorization request.
        user (Any): User object, must have `casbin_roles`.

    Returns:
        AsyncEnforcer: A new enforcer with dynamic roles and functions.
    """
    temp = AsyncEnforcer(base.get_model(), base.get_adapter())
    await temp.load_policy()
    temp.add_function("check_roles", check_roles)
    temp.add_function("check_groups", check_groups)
    temp.add_function("safe_abac_eval", lambda cond: safe_abac_eval(cond, request_obj))

    if getattr(user, "casbin_roles", None):
        try:
            await temp.add_named_grouping_policies(
                "g", [policy[1:] for policy in user.casbin_roles]
            )
        except Exception as e:
            logger.error(f"Failed to assign user casbin_roles: {e}")

    return temp


# --- Global Enforcer Singleton ---
_enforcer_cache: Dict[str, AsyncEnforcer] = {}


async def get_enforcer() -> AsyncEnforcer:
    """
    Returns a singleton Casbin AsyncEnforcer instance with caching and auto-reload.

    Returns:
        AsyncEnforcer: The main Casbin enforcer with Redis policy updates.
    """
    enforcer = _enforcer_cache.get("AsyncEnforcer")
    now = datetime.datetime.now()

    if enforcer:
        if now - getattr(enforcer, "last_loaded", now) > datetime.timedelta(minutes=5):
            logger.info("Reloading policies due to cache expiration")
            await enforcer.load_policy()
            enforcer.last_loaded = now
        return enforcer

    logger.info("Initializing new Casbin enforcer")
    adapter = Adapter()
    model = Model()
    model.load_model_from_text(CASBIN_MODEL)

    enforcer = AsyncEnforcer(model, adapter)
    await enforcer.load_policy()
    enforcer.last_loaded = now
    _enforcer_cache["AsyncEnforcer"] = enforcer

    asyncio.create_task(casbin_policies.start_redis_policy_listener(enforcer))

    return enforcer
