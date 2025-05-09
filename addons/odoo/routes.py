import logging
import xmlrpc.client
from typing import List

from fastapi import HTTPException
from pydantic import BaseModel, field_validator

from papi.core import pAPIRouter

# Logger configuration for production
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Odoo connection parameters
ODOO_URL = "http://localhost:8069"  # Replace with your domain/IP
ODOO_DB = "mercurio2018"
ODOO_USERNAME = "admin"
ODOO_PASSWORD = "admin"


def get_odoo_connection():
    """
    Establishes a connection to the Odoo server using XML-RPC.

    This function authenticates the user and returns an XML-RPC object to interact with
    the Odoo models. If authentication fails or the connection cannot be established,
    it raises an HTTPException with a detailed error message.

    :return: A tuple containing the user ID (uid) and the models proxy object.
    :raises HTTPException: If connection or authentication fails.
    """
    try:
        common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
        uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
        if not uid:
            raise ValueError("Authentication failed with Odoo.")
        models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
        return uid, models
    except Exception as e:
        logger.error(f"Error connecting to Odoo: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error connecting to Odoo: {str(e)}"
        )


# API Router definition
router = pAPIRouter(prefix="/api/v1/odoo", tags=["Odoo"])


class Article(BaseModel):
    """
    Represents an article model in Odoo.

    This model is used for interacting with the Odoo article records through the API.
    It includes various fields representing the article's attributes and validators
    to ensure correct data transformation.

    Attributes:
        id (int): Unique identifier for the article.
        title (str): The title of the article.
        subtitle (str): The subtitle of the article.
        body (str): The content or body of the article.
        keywords (List[str]): A list of keywords associated with the article.
        spot (str): The spot or location related to the article.
        pagetitle (str): Article SEO meta title.
        pagedescription (str): Article SEO meta description.
    """

    id: int
    title: str
    subtitle: str
    body: str
    keywords: List[str]
    spot: str
    pagetitle: str
    pagedescription: str

    @field_validator("*", mode="before")
    def replace_false_with_empty(cls, v, field):
        """
        Converts `False` values into empty values based on the field's expected type.

        This validator ensures that fields with default values of `False` are replaced
        with their corresponding empty values (e.g., empty strings for strings, empty lists
        for lists, etc.) to avoid unintentional false values in the data model.

        :param v: The value of the field to be validated.
        :param field: The field object associated with the value.
        :return: The transformed value.
        """
        if v is False:
            type = cls.schema()["properties"][field.field_name]["type"]
            if type == "string":
                return ""
            if type == "array":
                return []
            if type == "integer":
                return 0
        return v

    @field_validator("keywords", mode="before")
    def split_comma_string(cls, v):
        """
        Converts a comma-separated string into a list of strings.

        If the `keywords` field is a string, it splits the string by commas and returns
        a list of keywords, removing any leading or trailing whitespace.

        :param v: The value of the `keywords` field to be validated.
        :return: A list of strings derived from the comma-separated string.
        """
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []


@router.get(
    "/articles",
    response_model=List[Article],
    status_code=200,
    expose_as_mcp_tool=True,
)
def get_articles(limit: int | None = 10):
    """
    Retrieves articles from Odoo using XML-RPC.

    This endpoint fetches a list of articles from Odoo and returns them as a list
    of Article objects. It uses the `search_read` method from the Odoo XML-RPC API
    to retrieve articles with specified fields.

    :param limit: The maximum number of articles to retrieve. Defaults to 10.
    :return: A list of articles fetched from Odoo.
    :raises HTTPException: If any error occurs during data retrieval from Odoo.
    """
    try:
        # Establish Odoo connection
        uid, models = get_odoo_connection()

        # Fetch articles using the search_read method
        articles = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_PASSWORD,
            "xhg.autrement.promo.article",
            "search_read",
            [[]],  # Empty filter to fetch all articles
            {
                "fields": [
                    "id",
                    "title",
                    "subtitle",
                    "body",
                    "keywords",
                    "spot",
                    "pagetitle",
                    "pagedescription",
                ],
                "limit": limit,  # Use the user-defined limit
            },
        )

        # Return the fetched articles
        return articles
    except xmlrpc.client.Fault as e:
        # Log and raise an error if XML-RPC fails
        logger.error(f"XML-RPC Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching articles from Odoo")
    except Exception as e:
        # Log and raise an error for any unexpected exceptions
        logger.error(f"Unexpected Error: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Unexpected error occurred while fetching articles"
        )


@router.get(
    "/article/{article_id}",
    response_model=Article,
    status_code=200,
    expose_as_mcp_tool=True,
)
def get_full_article_content_by_id(article_id: int) -> dict:
    """
    Retrieves the full content of a specific article from Odoo by its ID.

    This endpoint fetches a single article from Odoo based on the provided ID and returns it as an
    Article object. It uses the `search_read` method from the Odoo XML-RPC API to retrieve the
    article with all its fields.

    :param article_id: The ID of the article to retrieve.
    :return: The article with the specified ID.
    :raises HTTPException: If the article is not found or if any error occurs during data retrieval.
    """
    try:
        # Establish Odoo connection
        uid, models = get_odoo_connection()

        # Fetch the specific article using the search_read method
        articles = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_PASSWORD,
            "xhg.autrement.promo.article",
            "search_read",
            [[["id", "=", article_id]]],
        )

        if not articles:
            raise HTTPException(status_code=404, detail="Article not found")

        # Return the first (and should be only) article
        return articles[0]
    except xmlrpc.client.Fault as e:
        logger.error(f"XML-RPC Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching article from Odoo")
    except Exception as e:
        logger.error(f"Unexpected Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Unexpected error occurred while fetching the article",
        )


@router.put(
    "/articles/{article_id}",
    response_model=bool,
    status_code=200,
    expose_as_mcp_tool=True,
)
def update_article_by_article_id(article_id: int, data: dict):
    """
    Updates an article in Odoo by ID.

    This endpoint updates an existing article's attributes in Odoo using the provided
    data dictionary. If the article is not found or if an error occurs, it raises an
    HTTPException with an appropriate error message.

    :param article_id: The ID of the article to update.
    :param data: A dictionary containing the fields to update.
    :return: `True` if the article was successfully updated, otherwise raises an exception.
    :raises HTTPException: If the article is not found or an error occurs during the update process.
    """
    try:
        uid, models = get_odoo_connection()

        # Process data before updating
        update_data = data.copy()

        # Handle keywords field if present
        if "keywords" in update_data:
            if isinstance(update_data["keywords"], (list, tuple)):
                update_data["keywords"] = ", ".join(update_data["keywords"])

        result = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_PASSWORD,
            "xhg.autrement.promo.article",
            "write",
            [[article_id], update_data],
        )
        if not result:
            raise HTTPException(status_code=404, detail="Article not found")
        return True
    except xmlrpc.client.Fault as e:
        logger.error(f"XML-RPC Error: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Error updating the article in Odoo"
        )
    except Exception as e:
        logger.error(f"Unexpected Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error occurred while updating the article: {str(e)}",
        )
