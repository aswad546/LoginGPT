from apiflask import APIBlueprint
from apiflask.fields import Integer
from apiflask.validators import Range
from flask import current_app


bp_gts = APIBlueprint("gts", __name__, url_prefix="/gts")


@bp_gts.get("/")
@bp_gts.input({
    "offset": Integer(load_default=0, validate=Range(min=0)),
    "limit": Integer(load_default=100, validate=Range(min=1, max=100))
}, location="query")
def get_ground_truths(query_data):
    db = current_app.config["db"]
    offset = query_data["offset"]
    limit = query_data["limit"]

    total = len(db["ground_truth"].distinct("gt_id"))
    pipeline = [
        {"$group": {"_id": "$gt_id", "list_id": {"$first": "$list_id"}, "timestamp": {"$first": "$timestamp"}}},
        {"$project": {"_id": False, "gt_id": "$_id", "list_id": "$list_id", "timestamp": "$timestamp"}},
        {"$sort": {"gt_id": -1}},
        {"$skip": offset},
        {"$limit": limit}
    ]
    result = list(db["ground_truth"].aggregate(pipeline))

    return {"success": True, "error": None, "data": {"total": total, "result": result}}
