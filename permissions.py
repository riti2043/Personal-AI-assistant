
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


