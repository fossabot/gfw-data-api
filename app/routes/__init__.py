import requests
from fastapi import Depends, HTTPException, Path
from fastapi.logger import logger
from fastapi.security import OAuth2PasswordBearer
from requests import Response

from app.settings.globals import ENV

DATASET_REGEX = r"^[a-z][a-z0-9_-]{2,}$"
VERSION_REGEX = r"^v\d{1,8}\.?\d{1,3}\.?\d{1,3}$|^latest$"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


async def dataset_dependency(
    dataset: str = Path(..., title="Dataset", regex=DATASET_REGEX)
) -> str:
    if dataset == "latest":
        raise HTTPException(
            status_code=400, detail="Name `latest` is reserved for versions only.",
        )
    return dataset


async def version_dependency(
    version: str = Path(..., title="Dataset version", regex=VERSION_REGEX),
) -> str:
    # Middleware should have redirected GET requests to latest version already.
    # Any other request method should not use `latest` keyword.
    if version == "latest":
        raise HTTPException(
            status_code=400,
            detail="You must list version name explicitly for this operation.",
        )
    return version


async def is_admin(token: str = Depends(oauth2_scheme)) -> bool:
    """Calls GFW API to authorize user.

    User must be ADMIN for gfw app
    """

    response = who_am_i(token)

    if response.status_code == 401 or not (
        response.json()["role"] == "ADMIN"
        and "gfw" in response.json()["extraUserData"]["apps"]
    ):
        logger.info("Unauthorized user")
        raise HTTPException(status_code=401, detail="Unauthorized")
    else:
        return True


async def is_service_account(token: str = Depends(oauth2_scheme)) -> bool:
    """Calls GFW API to authorize user.

    User must be service account with email gfw-sync@wri.org
    """

    response = who_am_i(token)

    if response.status_code == 401 or not (
        response.json()["email"] == "gfw-sync@wri.org"
        and "gfw" in response.json()["extraUserData"]["apps"]
    ):
        logger.info("Unauthorized user")
        raise HTTPException(status_code=401, detail="Unauthorized")
    else:
        return True


def who_am_i(token) -> Response:
    """Call GFW API to get token's identity."""

    if ENV == "dev":
        prefix = "staging"
    else:
        prefix = ENV

    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://{prefix}-api.globalforestwatch.org/auth/check-logged"
    response: Response = requests.get(url, headers=headers)

    if response.status_code != 200 and response.status_code != 401:
        logger.warning(
            f"Failed to authorize user. Server responded with response code: {response.status_code} and message: {response.text}"
        )
        raise HTTPException(
            status_code=500, detail="Call to authorization server failed"
        )

    return response
