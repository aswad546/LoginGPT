from apiflask import APIBlueprint
from flask import render_template, send_from_directory, current_app


bp_views = APIBlueprint("views", __name__, url_prefix="/", enable_openapi=False)


@bp_views.get("/")
def index():
    return render_template("views/index.html")


@bp_views.get("/archive")
def sso_archive():
    db = current_app.config["db"]
    return render_template("views/archive.html",
        lists=db["top_sites_lists"].distinct("id"),
        gts=db["ground_truth"].distinct("gt_id"),
        idps=sorted(list(set(db["ground_truth"].find({"idp_name": {"$ne": None}}).distinct("idp_name")))),
        queries=list(db["queries"].find({}, {"_id": False}))
    )


@bp_views.get("/stats")
def sso_stats():
    return render_template("views/stats.html")


@bp_views.get("/diff")
def sso_diff():
    return render_template("views/diff.html")


@bp_views.get("/list")
def sso_list():
    return render_template("views/list.html")


@bp_views.get("/admin")
def admin():
    return render_template("views/admin.html", config=current_app.config)


@bp_views.get("/info")
def info():
    return send_from_directory("./static", "info.html")


@bp_views.get("/code")
def code():
    return send_from_directory("./static", "code.zip")


@bp_views.get("/paper.pdf")
def paper():
    return send_from_directory("./static", "paper.pdf", as_attachment=True)


@bp_views.get("/paper.bib")
def bib():
    return send_from_directory("./static", "paper.bib", as_attachment=True)
