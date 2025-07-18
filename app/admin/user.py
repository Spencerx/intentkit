import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.auth import verify_admin_jwt
from intentkit.models.user import User, UserUpdate

logger = logging.getLogger(__name__)

user_router = APIRouter(prefix="/users", tags=["User"])
user_router_readonly = APIRouter(prefix="/users", tags=["User"])


@user_router_readonly.get(
    "/{user_id}",
    response_model=User,
    operation_id="get_user",
    summary="Get User",
    dependencies=[Depends(verify_admin_jwt)],
)
async def get_user(
    user_id: Annotated[str, Path(description="ID of the user")],
) -> User:
    """Get a user by ID.

    Args:
        user_id: ID of the user to get

    Returns:
        User model
    """
    user = await User.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@user_router.put(
    "/{user_id}",
    response_model=User,
    operation_id="put_user",
    summary="Replace User",
    dependencies=[Depends(verify_admin_jwt)],
)
async def put_user(
    user_id: Annotated[str, Path(description="ID of the user")],
    user_update: UserUpdate,
) -> User:
    """Replace all fields of a user with the provided values.

    Args:
        user_id: ID of the user to update
        user_update: New user data to replace existing data

    Returns:
        Updated User model
    """
    return await user_update.put(user_id)


@user_router.patch(
    "/{user_id}",
    response_model=User,
    operation_id="patch_user",
    summary="Update User",
    dependencies=[Depends(verify_admin_jwt)],
)
async def patch_user(
    user_id: Annotated[str, Path(description="ID of the user")],
    user_update: UserUpdate,
) -> User:
    """Update only the provided fields of a user.

    Args:
        user_id: ID of the user to update
        user_update: User data to update

    Returns:
        Updated User model
    """
    return await user_update.patch(user_id)
