from typing import Annotated, List

from beanie import operators
from family_tree.models.person import PersonalData, PersonDocument
from fastapi import Body
from pydantic import UUID4

from papi.core.router import RESTRouter

from .utils import model_to_form_schema

router = RESTRouter(prefix="/api/v2/family-tree", tags=["Family Tree"])


@router.get("/schema")
async def get_form_schema():
    """Get Person edit form schema to dinamically build the form"""
    return model_to_form_schema(PersonalData)


@router.get("/", expose_as_mcp_tool=True)
async def get_family_tree():
    """
    Get the entire family tree.

    Returns a list of all person documents in the database.
    """
    data = await PersonDocument.all().to_list()
    return [person.model_dump(exclude_none=True) for person in data]


@router.post("/update", expose_as_mcp_tool=True)
async def update_family_tree_nodes(
    payload: Annotated[
        List[PersonDocument],
        Body(..., description="List of person documents to update or create."),
    ],
):
    """
    Update existing person nodes or insert if not found.

    If a person exists (matched by ID), update its fields.
    Otherwise, insert as new document.
    """
    for person in payload:
        db_person = await PersonDocument.find_one(PersonDocument.id == person.id)

        update_data = person.model_dump(exclude_none=True, exclude={"id", "_id"})

        if db_person:
            await db_person.set(update_data)
        else:
            await person.create()


@router.delete("/remove", expose_as_mcp_tool=True)
async def remove_family_tree_nodes(
    payload: Annotated[
        List[UUID4], Body(..., description="List of UUIDs of person nodes to delete.")
    ],
):
    """
    Delete person nodes by UUIDs.

    Receives a list of UUIDs and deletes all matching documents.
    """
    await PersonDocument.find(operators.In(PersonDocument.id, payload)).delete_many()


@router.post("/add", expose_as_mcp_tool=True)
async def add_family_tree_node(
    payload: Annotated[
        List[PersonDocument],
        Body(..., description="List of new person documents to add to the tree."),
    ],
):
    """
    Add new person nodes to the family tree.

    Receives a list of person documents and inserts them into the database.
    """
    for person in payload:
        await person.create()
