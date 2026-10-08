"""A YAML loader that refuses a duplicated mapping key.

PyYAML keeps the last of two equal keys and says nothing, so a lane could
carry one ``runs-on`` or ``if:`` in the file and another in the parse. The
suite-runs-once contract reads workflows through this loader.
"""

from __future__ import annotations

import typing as typ

import yaml


class ContractError(ValueError):
    """A workflow the contract refuses to read."""


class StrictLoader(yaml.SafeLoader):
    """A SafeLoader that refuses a mapping declaring a key twice."""

    def construct_mapping(
        self, node: yaml.MappingNode, deep: bool = False
    ) -> dict[typ.Any, typ.Any]:
        """Construct a mapping, raising on a repeated key."""
        seen: set[typ.Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise ContractError(f"duplicate key {key!r} {key_node.start_mark}")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)
