from functools import wraps
# import json
# from simplejson import JSONDecodeError

import colander

from flask import request
# from zvooq.web.response import BadParams
# from zvooq.range import RangeInfo, PageBasedRangeInfo


class TopLevelMapping(colander.Mapping):
    def _impl(self, node, value, callback):
        value = self._validate(node, value)
        error = None
        result = {}

        for num, subnode in enumerate(node.children):
            name = subnode.name
            if getattr(subnode, 'toplevel', False):
                subval = value
            else:
                subval = value.pop(name, colander.null)

            try:
                result[subnode._name] = callback(subnode, subval)
            except colander.Invalid as e:
                if error is None:
                    error = colander.Invalid(node)
                error.add(e, num)

        if error is not None:
            raise error  # pylint: disable=E0702

        return result


class _SchemaMeta(type):

    def __init__(cls, name, bases, clsattrs):
        nodes = []
        # raise Exception('TEST')

        for name, value in clsattrs.items():
            if isinstance(value, (colander._SchemaNode, SchemaNode)):
                delattr(cls, name)
                if not value.name:
                    value.name = name
                value._name = name
                if value.raw_title is colander._marker:
                    value.title = name.replace('_', ' ').title()
                nodes.append((value._order, value))

        nodes.sort()
        cls.__class_schema_nodes__ = [ n[1] for n in nodes ]

        # Combine all attrs from this class and its _SchemaNode superclasses.
        cls.__all_schema_nodes__ = []
        for c in reversed(cls.__mro__):
            csn = getattr(c, '__class_schema_nodes__', [])
            cls.__all_schema_nodes__.extend(csn)


SchemaNode = _SchemaMeta(
    'SchemaNode',
    (colander._SchemaNode,),
    {}
    )


class Schema(SchemaNode):
    schema_type = TopLevelMapping


class String(colander.String):
    def deserialize(self, node, cstruct):
        if cstruct is colander.null:
            return colander.null

        try:
            result = cstruct
            if isinstance(result, (colander.text_type, bytes)):
                if self.encoding:
                    result = colander.text_(cstruct, self.encoding)
                else:
                    result = colander.text_type(cstruct)
            else:
                result = colander.text_type(cstruct)
        except Exception as e:
            raise colander.Invalid(node,
                                   colander._('${val} is not a string: ${err}',
                                              mapping={'val': cstruct, 'err': e}))

        return result


_typ_mapping = {
    int: colander.Int,
    str: String,
    bool: colander.Boolean, }


def _get_type(obj):
    if isinstance(obj, colander.SchemaType):
        return obj

    if issubclass(obj, colander.SchemaType):
        return obj()

    return _typ_mapping[obj]()


def _get_node(obj):
    if isinstance(obj, SchemaNode):
        return obj

    if isinstance(obj, type) and issubclass(obj, SchemaNode):
        return obj()

    return Arg(obj)


def validate(schema, data):
    try:
        return schema.deserialize(data)
    except colander.Invalid as e:
        raise BadParams(e.asdict())


def _make_validator(get_data, *args, **kwargs):
    schema = make_schema(*args, **kwargs)

    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            clean_data = validate(schema, get_data())
            clean_data.update(kwargs)
            return func(*args, **clean_data)

        return inner

    return decorator


def make_schema(*args, **kwargs):
    fields = {k: _get_node(v) for k, v in kwargs.iteritems()}
    if not args:
        args = (Schema,)

    return type('Schema', args, fields)(TopLevelMapping())


def query_string(*args, **kwargs):
    return _make_validator(lambda: request.GET, *args, **kwargs)


def form(*args, **kwargs):
    return _make_validator(lambda: request.POST, *args, **kwargs)


def params(*args, **kwargs):
    return _make_validator(lambda: request.params, *args, **kwargs)


def jsonbody(*args, **kwargs):
    def get_json():
        try:
            return request.json
        except JSONDecodeError:
            raise BadParams("Json required")

    return _make_validator(get_json, *args, **kwargs)


def rparams(*args, **kwargs):
    schema = make_schema(*args, **kwargs)

    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            clean_data = validate(schema, kwargs)
            kwargs.update(clean_data)
            return func(*args, **kwargs)

        return inner

    return decorator


class Arg(SchemaNode):
    def __init__(self, typ, *args, **kwargs):
        self.coerce = kwargs.pop('coerce', None)
        super(Arg, self).__init__(_get_type(typ), *args, **kwargs)

    def deserialize(self, cstruct=colander.null):
        result = super(Arg, self).deserialize(cstruct)
        if self.coerce:
            result = self.coerce(result)

        return result


class opt(Arg):
    def __init__(self, *args, **kwargs):
        kwargs['missing'] = kwargs.get('missing')
        super(opt, self).__init__(*args, **kwargs)


class JSONArray(colander.SchemaType):
    def serialize(self, node, appstruct):
        if appstruct is colander.null:
            return colander.null

        if not isinstance(appstruct, list):
            raise colander.Invalid(node, "%r is not a list")

        return json.dumps(appstruct)

    def deserialize(self, node, cstruct):
        if cstruct is colander.null:
            return colander.null

        if not isinstance(cstruct, basestring):
            raise colander.Invalid(node, '%r is not a string' % cstruct)

        appstruct = json.loads(cstruct)
        if not isinstance(appstruct, list):
            raise colander.Invalid(node, "%r is not a list")

        return appstruct


class CSVArray(colander.SchemaType):
    def __init__(self, typ):
        self.typ = _get_node(typ)

    def serialize(self, node, appstruct):
        if appstruct is colander.null:
            return colander.null

        if not isinstance(appstruct, list):
            raise colander.Invalid(node, "%r is not a list")

        return ",".join(self.typ.serialize(x) for x in appstruct)

    def deserialize(self, node, cstruct):
        if cstruct is colander.null:
            return colander.null

        if not isinstance(cstruct, basestring):
            raise colander.Invalid(node, '%r is not a string' % cstruct)

        nums = (x.strip() for x in cstruct.split(","))
        return [self.typ.deserialize(x) for x in nums if x]



def maybe_int(value, default=0):
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return default


class RangeType(colander.SchemaType):
    def deserialize(self, node, data):
        page = maybe_int(data.get("_page"))
        if page is None:
            offset = maybe_int(data.get("_offset"))
            if offset is None:
                offset = maybe_int(data.get("_skip"))

            if offset is None or offset < 0:
                offset = 0

            limit = maybe_int(data.get("_limit"))
            if limit is not None and limit < 0:
                limit = None

            rnginfo = RangeInfo(offset, limit)
        else:
            page = max(1, page)
            rnginfo = PageBasedRangeInfo(page)

        return rnginfo


class Range(SchemaNode):
    schema_type = RangeType
    toplevel = True


class enum(colander.SchemaType):
    def __init__(self, *choices):
        self._validate = colander.OneOf(choices)

    def deserialize(self, node, data):
        if data is not colander.null:
            self._validate(node, data)
        return data


class intrange(colander.Integer):
    def __init__(self, min=None, max=None):
        self._validate = colander.Range(min, max)

    def deserialize(self, node, data):
        result = super(intrange, self).deserialize(node, data)
        if result is not colander.null:
            self._validate(node, result)
        return result
