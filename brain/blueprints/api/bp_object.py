from apiflask import APIBlueprint
from apiflask.fields import String, Boolean
from flask import Response, current_app


bp_object = APIBlueprint("object", __name__, url_prefix="/object")


@bp_object.get("/")
@bp_object.input({
    "bucket_name": String(required=True),
    "object_name": String(required=True),
    "export": Boolean(load_default=False)
}, location="query")
def get_object(query_data):
    objstore = current_app.config["objstore"]
    bucket_name = query_data["bucket_name"]
    object_name = query_data["object_name"]
    export = query_data["export"]

    # backwards compability to old data
    if bucket_name == "landscape-analysis":
        bucket_name = object_name.split("/")[1]
        object_name = "/" + "/".join(object_name.split("/")[2:])

    try:
        r = objstore.get_object(bucket_name, object_name)
        rheaders = {"Content-Type": r.headers["Content-Type"]}
        if export:
            rheaders["Content-Disposition"] = f'attachment; filename="{bucket_name}_{object_name}"'
        return Response(headers=rheaders, response=r.data)
    except Exception as e:
        return {"success": False, "error": f"{e}", "data": None}
    finally:
        r.close()
        r.release_conn()
