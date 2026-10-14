"""Registers every blueprint. Route files only handle HTTP; logic lives in services/ and analysis/."""


def register_blueprints(app):
    from .auth import bp as auth_bp
    from .dashboard import bp as dashboard_bp
    from .complaints import bp as complaints_bp
    from .customers import bp as customers_bp
    from .analytics import bp as analytics_bp
    from .reports import bp as reports_bp
    from .settings import bp as settings_bp
    from .api import bp as api_bp
    for blueprint in (auth_bp, dashboard_bp, complaints_bp, customers_bp, analytics_bp,
                      reports_bp, settings_bp, api_bp):
        app.register_blueprint(blueprint)
