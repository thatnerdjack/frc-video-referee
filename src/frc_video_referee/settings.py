"""Shared base class for user-facing configuration models."""

from pydantic import AliasChoices, AliasGenerator, BaseModel, ConfigDict


def _kebab_case_aliases(field_name: str) -> AliasChoices:
    """Accept both `snake_case` and `kebab-case` spellings of a setting."""
    return AliasChoices(field_name, field_name.replace("_", "-"))


class SettingsModel(BaseModel, use_attribute_docstrings=True):
    """Base class for configuration sections.

    Command line arguments are rendered in kebab-case, so configuration files accept
    the same spelling as the equivalent command line argument in addition to the
    field's own name.
    """

    model_config = ConfigDict(
        alias_generator=AliasGenerator(validation_alias=_kebab_case_aliases),
        populate_by_name=True,
    )
