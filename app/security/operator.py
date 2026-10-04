from secrets import compare_digest

from fastapi import HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials


security = HTTPBasic()


def validate_operator(
    credentials: HTTPBasicCredentials,
    expected_username: str | None,
    expected_password: str | None,
) -> None:
    if not expected_username or not expected_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operator authentication is not configured.",
        )

    valid_username = compare_digest(
        credentials.username,
        expected_username,
    )
    valid_password = compare_digest(
        credentials.password,
        expected_password,
    )

    if not (valid_username and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid operator credentials.",
            headers={"WWW-Authenticate": "Basic"},
        )
