"""Jac Language Features."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol, Type, TypeVar

from jaclang.jac.constant import EdgeDir


class ArchitypeProtocol(Protocol):
    """Architype Protocol."""

    _jac_: None


T = TypeVar("T")

AT = TypeVar("AT", bound=ArchitypeProtocol)


class JacFeature:
    """Jac Feature."""

    @staticmethod
    def make_architype(arch_type: str) -> Callable[[type], type]:
        """Create a new architype."""

        def decorator(cls: Type[AT]) -> Type[AT]:
            """Decorate class."""
            cls._jac_ = None
            return dataclass(cls)

        return decorator

    @staticmethod
    def make_ds_ability(event: str, trigger: Optional[type]) -> Callable[[type], type]:
        """Create a new architype."""

        def decorator(func: type) -> type:
            """Decorate class."""
            return func

        return decorator

    @staticmethod
    def elvis(op1: Optional[T], op2: T) -> T:  # noqa: ANN401
        """Jac's elvis operator feature."""
        return ret if (ret := op1) is not None else op2

    @staticmethod
    def report(expr: Any) -> None:  # noqa: ANN401
        """Jac's report stmt feature."""

    @staticmethod
    def ignore(walker_obj: Any, expr: Any) -> None:  # noqa: ANN401
        """Jac's ignore stmt feature."""

    @staticmethod
    def visit(walker_obj: Any, expr: Any) -> bool:  # noqa: ANN401
        """Jac's visit stmt feature."""
        return True

    @staticmethod
    def disengage(walker_obj: Any) -> None:  # noqa: ANN401
        """Jac's disengage stmt feature."""

    @staticmethod
    def edge_ref(
        node_obj: Any,  # noqa: ANN401
        dir: EdgeDir,
        filter_type: Optional[type],
    ) -> list[Any]:  # noqa: ANN401
        """Jac's apply_dir stmt feature."""
        return []

    @staticmethod
    def connect(op1: Optional[T], op2: T, op: Any) -> T:  # noqa: ANN401
        """Jac's connect operator feature.

        Note: connect needs to call assign compr with tuple in op
        """
        return ret if (ret := op1) is not None else op2

    @staticmethod
    def disconnect(op1: Optional[T], op2: T, op: Any) -> T:  # noqa: ANN401
        """Jac's connect operator feature."""
        return ret if (ret := op1) is not None else op2

    @staticmethod
    def assign_compr(
        target: list[T], attr_val: tuple[tuple[str], tuple[Any]]
    ) -> list[T]:
        """Jac's assign comprehension feature."""
        return target
