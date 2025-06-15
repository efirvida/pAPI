from typing import Set, Type

from sqlalchemy.orm import DeclarativeMeta


def extract_bases_from_models(
    models: dict[str, Type[DeclarativeMeta]],
) -> Set[Type[DeclarativeMeta]]:
    """
    Extracts unique SQLAlchemy Base classes from a dict of model classes.

    Args:
        models: Dict[str, DeclarativeMeta] - model name to model class.

    Returns:
        Set of unique Base classes (DeclarativeMeta subclasses).
    """
    bases: Set[Type[DeclarativeMeta]] = set()
    for model in models.values():
        # metadata suele estar en la clase Base, no directamente en el modelo
        metadata = getattr(model, "metadata", None)
        if metadata is None:
            continue

        # Buscar en bases directas alguna clase que tenga metadata
        base_class = next((b for b in model.__bases__ if hasattr(b, "metadata")), None)
        if base_class is not None:
            bases.add(base_class)

    return bases
