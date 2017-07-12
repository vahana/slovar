from itertools import groupby

from slovar.errors import DKeyError, DValueError
from slovar.operations.strings import split_strip, str2dt
from slovar.operations.dictionaries import flat, unflat, merge
from slovar.operations.lists import process_fields


class slovar(dict):

    """Named dict, with some set functionalities

        dset = slovar(a=1,b={'c':1})
        dset.a == dset['a'] == 1
        dset.b.c == 1
        dset.subset(['a']) == {'a':1} == dset.subset('-b')

    """
    # Note: We use self.__class__ to return new instances of subclasses
    # instead of slovar when necessary

    DKeyError = DKeyError
    DValueError = DValueError


    @classmethod
    def to_dicts(cls, iterable, fields):
        return [e.extract(fields) for e in iterable]

    @classmethod
    def from_dotted(cls, dotkey, val):
        # 'a.b.c', 100 -> {a:{b:{c:100}}}
        # 'a.b.1', 100 -> {a:{b:[None,100]}}

        key, _, sufix = dotkey.partition('.')

        if not sufix:
            if key.isdigit():
                _lst = [None]*int(key) + [val]
                return _lst
            else:
                return cls({key:val})

        if key.isdigit():
            _lst = [None]*int(key) + [cls.from_dotted(sufix, val)]
            return _lst
        else:
            return cls({key: cls.from_dotted(sufix, val)})

    @classmethod
    def build_from(cls, source, rules, allow_empty=True,
                    allow_missing=False, inverse=False):
        _d = cls()

        flat_rules = cls(rules).flat()
        flat_source = cls(source).flat()
        flat_source.update(source)

        for key, val in flat_rules.items():
            if not val: # if val in the rule is missing, use the key
                val = key

            if inverse:
                key,val = val,key # flip em

            if key.endswith('.'):
                _val = flat_source.get_tree(key)
            else:
                if allow_missing:
                    _val = flat_source.get(key, key)
                else:
                    _val = flat_source[key]

            if _val != "" or allow_empty:
                _d[val] = _val

        return _d.unflat()

    def __init__(self, *arg, **kw):

        try:
            super(slovar, self).__init__(*arg, **kw)
        except ValueError as e:
            raise DValueError(e.message)

        self.to_slovar()

    def __getattr__(self, key):
        if key.startswith('__'): # dont touch the special attributes
            raise AttributeError('Attribute error %s' % key)
        try:
            return self[key]
        except KeyError as e:
            self.raise_getattr_exc(e)

    def raise_getattr_exc(self, error):
        raise AttributeError(error)

    def __setattr__(self, key, val):
        if isinstance(val, dict) and not isinstance(val, slovar):
            val = self.__class__(val)
        self[key] = val

    def __delattr__(self, key):
        self.pop(key, None)

    def __contains__(self, item):
        if isinstance(item, (tuple, list, set)):
            return bool(set(self.keys()) & set(item))
        else:
            return super(slovar, self).__contains__(item)

    def __add__(self, item):
        return self.copy().update(item)

    def __iadd__(self, item):
        return self.update(item)

    def __getitem__(self, key):
        try:
            return super(slovar, self).__getitem__(key)
        except KeyError as e:
            raise DKeyError(e.message)

    def to_dict(self, fields):
        return self.extract(fields)

    def to_slovar(self):
        cls = self.__class__
        for key, val in self.items():
            if isinstance(val, dict):
                self[key] = cls(val)
            if isinstance(val, list):
                new_list = []
                for each in val:
                    if isinstance(each, dict):
                        new_list.append(cls(each))
                    else:
                        new_list.append(each)
                self[key] = new_list

        return self

    def copy(self):
        return self.__class__(super(slovar, self).copy())

    def extract(self, fields):
        if not fields:
            return self

        only, exclude, nested, show_as, show_as_r, trans, star =\
                process_fields(fields).mget(
                               ['only','exclude', 'nested',
                                'show_as', 'show_as_r', 'transforms',
                                'star'])

        nested_keys = nested.keys()

        def process_lists(flat_d):
            for nkey, nval in nested.items():
                if '..' in nkey:
                    pref, suf = nkey.split('..', 1)
                    _lst = []

                    for ix in range(len(_d.get(nval, []))):
                        kk = '%s.%s.%s'%(pref,ix,suf)
                        _lst.append(flat_d.subset(kk))
                        ix+=1

                    new_key = '%s.%s'%(pref,suf)
                    nested_keys.append(new_key)
                    flat_d[new_key] = _lst

                    if nkey in show_as:
                        show_as[new_key] = show_as.pop(nkey)

        if star:
            _d = self
        else:
            _d = self.subset(only + ['-'+e for e in exclude])

        if nested:
            flat_d = self.flat(keep_lists=0)
            process_lists(flat_d)
            flat_d = flat_d.subset(nested_keys)
            _d.remove(nested.values())
            _d.update(flat_d)

        for new_key, key in show_as_r.items():
            if key in _d:
                _d.merge(self.__class__({new_key:_d.get(key)}))

        #remove old keys
        for _k in show_as_r.values():
            _d.pop(_k, None)

        for key, trs in trans.items():
            if key in _d:
                for tr in trs:
                    if tr == 'str':
                        _d[key] = unicode(_d[key])
                        continue
                    elif tr == 'unicode':
                        _d[key] = unicode(_d[key])
                        continue
                    elif tr == 'int':
                        _d[key] = int(_d[key]) if _d[key] else _d[key]
                        continue
                    elif tr == 'float':
                        _d[key] = float(_d[key]) if _d[key] else _d[key]
                        continue
                    elif tr == 'flat' and isinstance(_d[key], slovar):
                        _d[key] = _d[key].flat()
                        continue
                    elif tr == 'dt':
                        _d[key] = str2dt(_d[key])
                        continue

                    _type = type(_d[key])
                    try:
                        method = getattr(_type, tr)
                        if not callable(method):
                            raise slovar.DValueError(
                                '`%s` is not a callable for type `%s`'
                                    % (tr, _type))
                        _d[key] = method(_d[key])
                    except AttributeError as e:
                        raise slovar.DValueError(
                                'type `%s` does not have a method `%s`'
                                    % (_type, tr))

            else:
                for tr in trs:
                    if tr.startswith('='):
                        _d[key] = tr.partition('=')[2]
                        continue

        return _d.unflat()

    def get_by_prefix(self, prefix):
        if not isinstance(prefix, list):
            prefixes = [prefix]
        else:
            prefixes = prefix

        _d = self.__class__()
        for k, v in self.items():
            for pref in prefixes:
                _pref = pref[:-1]

                if pref.endswith('*'):
                    if k.startswith(_pref):
                        ix = _pref.rfind('.')
                        if ix > 0:
                            _pref = _pref[:ix]
                            k = k[len(_pref)+1:]
                        _d[k] = v
                else:
                    if k == pref:
                        ix = _pref.rfind('.')
                        if ix > 0:
                            _pref = _pref[:ix]
                            k = k[len(_pref)+1:]

                        _d[k]=v

        return _d.unflat()

    def subset(self, keys):

        if keys is None:
            return self

        only, exclude = process_fields(
            keys, parse=False
        ).mget(['only','exclude'])

        _d = self.__class__()

        if only and exclude:
            raise DValueError(
                'Can only supply either positive or negative keys,'
                ' but not both'
            )

        if only:
            prefixed = [it for it in only if it.endswith('*')]
            exact = [it for it in only if not it.endswith('*')]

            if exact:
                _d = self.__class__(
                    [[k, v] for (k, v) in self.items() if k in exact]
                )

            if prefixed:
                _d = _d.update_with(self.get_by_prefix(prefixed))

        elif exclude:
            _d = self.__class__([[k, v] for (k, v) in self.items()
                          if k not in exclude])

        return _d

    def remove(self, keys):
        for k in keys:
            self.pop(k, None)
        return self

    def update(self, d_):
        super(slovar, self).update(self.__class__(d_))
        return self

    def merge(self, d_):
        merge(self, d_)
        return self

    def pop_by_values(self, vals):
        if not isinstance(vals, list):
            vals = [vals]

        for k, v in self.items():
            if v in vals:
                self.pop(k)
        return self

    def get_tree(self, prefix, defaults={}, sep='.'):
        if prefix[-1] != '.':
            prefix += sep

        _dict = self.__class__(defaults)
        for key, val in self.items():
            if key.startswith(prefix):
                _k = key.partition(prefix)[-1]
                _dict[_k] = val
        return _dict

    def mget(self, keys):
        return [self[e] for e in split_strip(keys) if e in self]

    def has(self, keys, check_type=basestring,
            err='', _all=True, allow_missing=False,
            allowed_values=[]):
        errors = []

        if isinstance(keys, basestring):
            keys = [keys]

        self_flat = self.flat().update(self) # update with self to include high level keys too

        def missing_key_error(_type, key):
            if _type == dict:
                missing = ['%s.%s' % (key, val) for val in allowed_values]
            else:
                missing = allowed_values

            return 'Missing key or invalid values for `%s`. Allowed values are: `%s`'\
                                          % (key, missing)

        def error_msg(msg):
            if "%s" in err:
                error = err % msg
            elif err:
                error = err
            else:
                error = msg

            errors.append(error)
            return error

        for key in keys:
            if key in self_flat:
                if check_type and not isinstance(self_flat[key], check_type):
                    error_msg(u'`%s` must be type `%s`, got `%s` instead'\
                                          % (key, check_type.__name__,
                                             type(self_flat[key]).__name__))

                if allowed_values and self_flat[key] not in allowed_values:
                    error_msg(missing_key_error(check_type, key))

            elif not allow_missing:
                if allowed_values:
                    error_msg(missing_key_error(check_type, key))
                else:
                    error_msg('Missing key: `%s`' % key)

        if (errors and _all) or (not _all and len(errors) >= len(keys)):
            raise DValueError('.'.join(errors))

        return True

    def transform(self, rules):
        _d = self.__class__()
        flat_dict = self.flat()

        for path, val in flat_dict.items():
            if path in rules:
                _d.merge(slovar.from_dotted(rules[path], val))

        return _d

    def flat(self, keep_lists=True):
        return self.__class__(flat(self, keep_lists=keep_lists))

    def unflat(self):
        return self.__class__(unflat(self))

    def set_default(self, name, val):
        cls = self.__class__
        if name not in self.flat():
            self.merge(cls.from_dotted(name, val))
        return val

    def get_first(self, keys):
        for key in keys:
            if key in self:
                return self[key]

        raise DKeyError('Neither of `%s` keys found' % keys)

    def fget(self, key, *arg, **kw):
        return self.flat().get(key, *arg, **kw)

    def deep_update(self, _dict):
        return self.flat().update(_dict.flat()).unflat()

    def update_with(self, _dict, overwrite=True, append_to=None, append_to_set=None,
                    reverse=False, exclude=[]):

        if isinstance(append_to, basestring):
            append_to = [append_to]

        if isinstance(append_to_set, basestring):
            append_to_set = [append_to_set]

        append_to = append_to or []

        _append_to_set = {}
        for each in (append_to_set or []):
            k,_,sk = each.partition(':')
            _append_to_set[k]=sk
        append_to_set = _append_to_set

        if not reverse:
            self_dict = self.copy()
        else:
            self_dict = _dict.copy()
            _dict = self

        def _append_to(key, val):
            if isinstance(self_dict[key], list):
                if isinstance(val, list):
                    self_dict[key].extend(val)
                else:
                    self_dict[key] += val
            else:
                raise DValueError('`%s` is not a list' % key)

        def _append_to_set(key, val):
            _append_to(key, val)
            set_key = append_to_set.get(key)

            if set_key:
                _uniques = []
                _met = []
                for each in self_dict[key]:
                    # if there is not set_key, it must be treated as unique
                    if set_key not in each:
                        _uniques.append(each)
                        continue

                    if each[set_key] in _met:
                        continue

                    _met.append(each[set_key])
                    _uniques.append(each)
                self_dict[key] = _uniques
            else:
                self_dict[key] = list(set(self_dict[key]))

        for key, val in _dict.items():
            if key in exclude:
                continue
            if overwrite or key not in self_dict:
                if key in append_to and key in self_dict:
                    _append_to(key, val)
                elif key in append_to_set and key in self_dict:
                    _append_to_set(key, val)
                else:
                    self_dict[key] = val

        return self_dict

    def merge_with(self, _dict, reverse=False):
        return self.update_with(_dict, overwrite=False,
                                reverse=reverse)

    def contains(self, other, exclude=None):
        other_ = other.subset(exclude)
        return not other_ or self.subset(other_.keys()) == other_

    def pop_many(self, keys):
        poped = self.__class__()
        for key in keys:
            poped[key] = self.pop(key, None)
        return poped

    def sensor(self, patterns):
        self_f = self.flat()
        for key in self_f:
            for each in patterns:
                if key.endswith(each):
                    self_f[key] = '******'

        return self_f.unflat()
