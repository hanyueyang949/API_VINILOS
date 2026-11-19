from typing_extensions import Annotated

from pydantic import AfterValidator, Field


def reject_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("El texto no puede estar vacío ni contener solo espacios.")
    return value


NonBlankText = Annotated[str, Field(min_length=1), AfterValidator(reject_blank)]
