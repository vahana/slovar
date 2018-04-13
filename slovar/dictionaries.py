# from prf.utils.utils import json_dumps
# from prf.utils.errors import DKeyError, DValueError

from slovar import slovar
from slovar.convert import *


class dictset(slovar):

    def asbool(self, *arg, **kw):
        return asbool(self, *arg, **kw)

    def aslist(self, *arg, **kw):
        return aslist(self, *arg, **kw)

    def asset(self, *arg, **kw):
        return asset(self, *arg, **kw)

    def asint(self, *arg, **kw):
        return asint(self, *arg, **kw)

    def asfloat(self, *arg, **kw):
        return asfloat(self, *arg, **kw)

    def asdict(self, *arg, **kw):
        return asdict(self, *arg, **kw)

    def asdt(self, *arg, **kw):
        return asdt(self, *arg, **kw)

    def asstr(self, *arg, **kw):
        return asstr(self, *arg, **kw)

    def asrange(self, *arg, **kw):
        return asrange(self, *arg, **kw)

    def asqs(self, *arg, **kw):
        return asqs(self, *arg, **kw)

    def json(self):
        return json_dumps(self)

    def __setattr__(self, key, val):
        if isinstance(val, dict):
            val = dictset(val)
        self[key] = val


# class dkdict(dictset):
#     def raise_getattr_exc(self, error):
#         raise DKeyError(error)

#     def raise_value_exc(self, error):
#         raise DValueError(error)


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat().split(".")[0]
        try:
            return super(JSONEncoder, self).default(obj)
        except TypeError:
            return str(obj)  # fallback to unicode


def json_dumps(body):
    return json.dumps(body, cls=JSONEncoder)


def _extend_list(_list, length):
    if len(_list) < length:
        for _ in range(length - len(_list)):
            _list.append({})


def unflat(_dict):
    result = {}

    for dotted_path, leaf_value in list(_dict.items()):
        path = dotted_path.split('.')
        ctx = result
        # Last item is a leaf, we save time by doing it outside the loop
        for i, part in enumerate(path[:-1]):
            # If context is a list, part should be an int
            # Testing part.isdigit() is significantly faster than isinstance(ctx, list)
            ctx_is_list = part.isdigit()
            if ctx_is_list:
                part = int(part)
            # If the next part is an int, we need to contain a list
            ctx_contains_list = path[i+1].isdigit()

            # Set the current node to placeholder value, {} or []
            if not ctx_is_list and not ctx.get(part):
                ctx[part] = [] if ctx_contains_list else {}

            # If we're dealing with a list, make sure it's big enough
            # for part to be in range
            if ctx_is_list:
                _extend_list(ctx, part + 1)

            # If we're empty and contain a list
            if not ctx[part] and ctx_contains_list:
                ctx[part] = []

            ctx = ctx[part]

        leaf_key = path[-1]
        if leaf_key.isdigit():
            leaf_key = int(leaf_key)
            _extend_list(ctx, leaf_key + 1)

        ctx[leaf_key] = leaf_value

    return result


def flat(_dict, base_key='', keep_lists=False):
    result = {}
    # Make a dict regardless, ints as keys for a list
    iterable = _dict if isinstance(_dict, dict) else dict(enumerate(_dict))
    for key, value in list(iterable.items()):
        # Join keys but prevent keys from starting by '.'
        dotted_key = key if not base_key else '.'.join([base_key, str(key)])
        # Recursion if we find a dict or list, except if we're keeping lists
        if isinstance(value, dict) or (isinstance(value, list) and not keep_lists):
            result.update(flat(value, base_key=dotted_key, keep_lists=keep_lists))
        # Otherwise just set attribute
        else:
            result[dotted_key] = value
    return result


def merge(d1, d2, path=None):
    if path is None: path = []

    for key in d2:
        if key in d1:
            if isinstance(d1[key], dict) and isinstance(d2[key], dict):
                merge(d1[key], d2[key], path + [str(key)])
        else:
            d1[key] = d2[key]
    return d1
