"""The administrator of a DS Wizard instance, DSW_USER: ``admin()`` logs in as
it, or creates it through the demo administrator of a new instance, then
deletes the demo accounts the published password still opens.
"""

from __future__ import annotations

from madmp.dsw.client import DswClient, Instance, login
from madmp.errors import DswError, PublishError

# DSW's demo accounts, which DSW creates on a new database, all with the one
# published password.
DEMO_PASSWORD = "password"
DEMO_ADMIN = "albert.einstein@example.com"
DEMO_ACCOUNTS = (
    DEMO_ADMIN,
    "nikola.tesla@example.com",
    "isaac.newton@example.com",
)

# The status of a login DSW refuses.
_REFUSED = 400


def _logged_in(instance: Instance) -> DswClient | None:
    """A client logged in as the instance's account, or ``None`` when DSW
    refuses it."""
    try:
        return login(instance)
    except DswError as err:
        if err.status != _REFUSED:
            raise
        return None


def _create(instance: Instance) -> DswClient:
    """Create the administrator through the demo one, and log in as it."""
    demo = _logged_in(Instance(instance.api_url, DEMO_ADMIN, DEMO_PASSWORD))
    if demo is None:
        raise PublishError(
            [
                (
                    f"DSW refuses {instance.user!r} and has no demo administrator "
                    "left: create it by hand, an administrator with DSW_USER and "
                    "DSW_PASSWORD, or set its password in DSW back to DSW_PASSWORD."
                )
            ]
        )
    try:
        demo.post(
            "/users",
            {
                "firstName": "maDMP",
                "lastName": "admin",
                "email": instance.user,
                "password": instance.password,
                "role": "admin",
            },
        )
    except DswError as err:
        raise PublishError(
            [
                (
                    f"DSW refuses {instance.user!r} and cannot create it ({err}): "
                    "if it exists, set its password in DSW back to DSW_PASSWORD."
                )
            ]
        ) from err
    return login(instance)


def _delete_open_demo_accounts(dsw: DswClient, instance: Instance) -> list[str]:
    """Delete every demo account the published password still opens, but the
    instance's own account."""
    open_ones = [
        email
        for email in DEMO_ACCOUNTS
        if email != instance.user
        and _logged_in(Instance(instance.api_url, email, DEMO_PASSWORD)) is not None
    ]
    if open_ones:
        for user in dsw.list_all("/users", "users"):
            if user["email"] in open_ones:
                dsw.delete(f"/users/{user['uuid']}")
    return open_ones


def admin(instance: Instance) -> list[str]:
    """Make sure of the instance's administrator, and say what it took, one
    line each."""
    lines = []
    dsw = _logged_in(instance)
    if dsw is None:
        dsw = _create(instance)
        lines.append(f"Administrator {instance.user} created.")
    else:
        lines.append(f"Administrator {instance.user} logs in.")
    if deleted := _delete_open_demo_accounts(dsw, instance):
        lines.append(f"Demo accounts deleted: {', '.join(deleted)}.")
    return lines
