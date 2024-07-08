from apiflask import APIBlueprint
from blueprints.api.bp_admin import bp_admin
from blueprints.api.bp_gts import bp_gts
from blueprints.api.bp_list import bp_list
from blueprints.api.bp_object import bp_object
from blueprints.api.bp_ping import bp_ping
from blueprints.api.bp_rabbit import bp_rabbit
from blueprints.api.bp_rpc import bp_rpc
from blueprints.api.bp_scans import bp_scans
from blueprints.api.bp_stats import bp_stats
from blueprints.api.bp_tags import bp_tags
from blueprints.api.bp_tasks import bp_tasks


bp_api = APIBlueprint("api", __name__, url_prefix="/api")


bp_api.register_blueprint(bp_admin)
bp_api.register_blueprint(bp_gts)
bp_api.register_blueprint(bp_list)
bp_api.register_blueprint(bp_object)
bp_api.register_blueprint(bp_ping)
bp_api.register_blueprint(bp_rabbit)
bp_api.register_blueprint(bp_rpc)
bp_api.register_blueprint(bp_scans)
bp_api.register_blueprint(bp_stats)
bp_api.register_blueprint(bp_tags)
bp_api.register_blueprint(bp_tasks)
