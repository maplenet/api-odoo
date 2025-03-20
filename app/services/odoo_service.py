def execute_odoo_method(conn, model, method, args, kwargs=None):

    if kwargs is None:
        kwargs = {}
    return conn['models'].execute_kw(
        conn['db'], conn['uid'], conn['password'],
        model, method, args, kwargs
    )