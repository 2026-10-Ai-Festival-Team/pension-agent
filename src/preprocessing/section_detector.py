from typing import Optional

from src.models.document import DocumentElement, ElementType


def section_from_element(element: DocumentElement) -> Optional[str]:
    """Return a conservative section label only for explicit headings."""
    if element.kind in {ElementType.TITLE, ElementType.HEADING}:
        return element.text
    return None
