from apiflask import APIBlueprint
from blueprints.api.stats.bp_gt import bp_gt
from blueprints.api.stats.bp_login_trace import bp_login_trace
from blueprints.api.stats.bp_loginpage import bp_loginpage
from blueprints.api.stats.bp_resolve import bp_resolve
from blueprints.api.stats.bp_scans import bp_scans
from blueprints.api.stats.bp_sso import bp_sso
from blueprints.api.stats.bp_wra import bp_wra


bp_stats = APIBlueprint("stats", __name__, url_prefix="/stats")


bp_stats.register_blueprint(bp_gt)
bp_stats.register_blueprint(bp_login_trace)
bp_stats.register_blueprint(bp_loginpage)
bp_stats.register_blueprint(bp_resolve)
bp_stats.register_blueprint(bp_scans)
bp_stats.register_blueprint(bp_sso)
bp_stats.register_blueprint(bp_wra)
