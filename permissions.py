from typing import Callable

_permission_handler: Callable | None = None


SENSITIVE_ACTIONS = {
    "github_read",
    "github_write",
    "filesystem_read",
    "filesystem_write",
    "filesystem_delete",
    "gmail_read",
    "gmail_send",
    "calendar_read",
    "calendar_create",
    "calendar_update",
    "calendar_delete",
}


def register_permission_handler(
    handler: Callable,
):
    """
    Register the function responsible for requesting user approval.
    """

    global _permission_handler

    _permission_handler = handler


def needs_permission(
    permission_type: str,
) -> bool:
    """
    Return whether a permission requires user approval.
    """

    return permission_type in SENSITIVE_ACTIONS


def request_permission(
    action: str,
    target: str,
    reason: str,
) -> bool:
    """
    Ask the registered handler for permission.
    """

    if _permission_handler is None:
        raise RuntimeError(
            "Permission handler has not been registered."
        )

    return _permission_handler(
        action=action,
        target=target,
        reason=reason,
    )


def check_permission(
    permission_type: str,
    action: str,
    target: str,
    reason: str,
) -> bool:

    if not needs_permission(permission_type):
        return True

    approved = request_permission(
        action=action,
        target=target,
        reason=reason,
    )

    return bool(approved)


