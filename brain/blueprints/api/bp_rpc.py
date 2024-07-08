from apiflask import APIBlueprint
from celery.result import AsyncResult


bp_rpc = APIBlueprint("rpc", __name__, url_prefix="/rpc")


@bp_rpc.get("/<id>")
def retrieve_rpc_result(id):
    result = AsyncResult(id)
    return {
        "ready": result.ready(),
        "successful": result.successful(),
        "result": result.result if result.ready() and result.successful() else None
    }
