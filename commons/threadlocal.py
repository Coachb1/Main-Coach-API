from threading import local

local_data = local()


def get_attribute(attr):
    return getattr(local_data, attr, None)


def set_attribute(attr, value):
    setattr(local_data, attr, value)


def del_attribute(attr):
    try:
        delattr(local_data, attr)
    except:
        pass


def set_trace_id(trace_id):
    set_attribute("trace_id", trace_id)


def get_trace_id():
    return get_attribute("trace_id")


def del_trace_id():
    del_attribute("trace_id")


def set_user(user):
    set_attribute("user", user)


def get_user():
    return get_attribute("user")


def del_user():
    del_attribute("user")
