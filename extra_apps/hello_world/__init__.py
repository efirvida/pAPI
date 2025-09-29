from papi.core.response import create_response
from papi.core.router import RESTRouter

router = RESTRouter()


@router.get("/hello")
async def hello():
    return create_response(data={"message": "Hello from addon!"})
