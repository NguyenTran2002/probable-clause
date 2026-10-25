"""A small in-memory stand-in for the parts of pymongo's AsyncDatabase that MongoStore uses (tests only).

It exists so MongoStore's own flow (the conditional update, the compare-and-swap loops, the failure handling)
runs hermetically. It implements the query and update operators MongoStore sends and nothing else, and it raises
pymongo's own exceptions where Atlas would. It is not Mongo: `tests/state/test_store_atlas.py` runs the same
cases against the real thing when PC_ATLAS_TEST=1.

Fidelity points that matter to the money code:
- `$expr` follows MongoDB's rules where null is involved: `$add` with a missing operand gives null, and null sorts
  below every number, so `{"$lte": [null, cap]}` is true. MongoStore must guard every field read with `$ifNull`.
- an update that names a path and its parent (or the same path twice) is refused, as MongoDB refuses it.
- `$expr` in an upsert's filter raises WriteError code 224, as Atlas does (matched or not)
- a unique index (and `_id`) raises DuplicateKeyError; insert_many(ordered=False) raises BulkWriteError.
"""

import asyncio
import copy
from datetime import datetime

from pymongo.errors import BulkWriteError, DuplicateKeyError, OperationFailure, WriteError

MISSING = object()


def get_path(doc, path):
    cur = doc
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return MISSING
    return cur


def set_path(doc, path, value):
    """Create the path; like MongoDB, refuse to go through a value that is not a document (code 28)."""
    parts = path.split(".")
    cur = doc
    for part in parts[:-1]:
        nxt = cur.get(part)
        if nxt is None and part not in cur:
            nxt = {}
            cur[part] = nxt
        elif not isinstance(nxt, dict):
            raise OperationFailure(f"fake: cannot create field {part!r} in an element that is not a document", code=28)
        cur = nxt
    cur[parts[-1]] = value


def unset_path(doc, path):
    parts = path.split(".")
    cur = doc
    for part in parts[:-1]:
        cur = cur.get(part)
        if not isinstance(cur, dict):
            return
    cur.pop(parts[-1], None)


def _cmp_key(v):
    # BSON order for what we compare: null < numbers < strings < dates
    if v is None:
        return (0, 0)
    if isinstance(v, bool):
        return (3, int(v))
    if isinstance(v, (int, float)):
        return (1, v)
    if isinstance(v, str):
        return (2, v)
    if isinstance(v, datetime):
        return (4, v.timestamp())
    return (5, 0)


def eval_expr(expr, doc):
    if isinstance(expr, str) and expr.startswith("$"):
        v = get_path(doc, expr[1:])
        return None if v is MISSING else v
    if isinstance(expr, dict) and len(expr) == 1:
        (op, args), = expr.items()
        if op == "$and":
            return all(eval_expr(a, doc) for a in args)
        if op in ("$lte", "$lt", "$gte", "$gt", "$eq"):
            a, b = (_cmp_key(eval_expr(x, doc)) for x in args)
            return {"$lte": a <= b, "$lt": a < b, "$gte": a >= b, "$gt": a > b, "$eq": a == b}[op]
        if op == "$add":
            vals = [eval_expr(x, doc) for x in args]
            if any(v is None for v in vals):
                return None
            return sum(vals)
        if op == "$ifNull":
            first, fallback = args
            v = eval_expr(first, doc)
            return eval_expr(fallback, doc) if v is None else v
        raise OperationFailure(f"fake: unsupported expression operator {op}", code=168)
    if isinstance(expr, (int, float, bool)) or expr is None:
        return expr
    raise OperationFailure(f"fake: unsupported expression {expr!r}", code=168)


def _is_operator_doc(v):
    return isinstance(v, dict) and v and all(k.startswith("$") for k in v)


def _field_matches(value, cond):
    if _is_operator_doc(cond):
        for op, arg in cond.items():
            if op == "$exists":
                if (value is not MISSING) != bool(arg):
                    return False
            elif op == "$ne":
                if value is not MISSING and value == arg:
                    return False
            elif op == "$in":
                if value is MISSING or value not in arg:
                    return False
            elif op in ("$gt", "$gte", "$lt", "$lte"):
                if value is MISSING:
                    return False
                a, b = _cmp_key(value), _cmp_key(arg)
                if not {"$gt": a > b, "$gte": a >= b, "$lt": a < b, "$lte": a <= b}[op]:
                    return False
            else:
                raise OperationFailure(f"fake: unsupported query operator {op}", code=2)
        return True
    return value is not MISSING and value == cond


def matches(doc, flt):
    for key, cond in (flt or {}).items():
        if key == "$expr":
            if not eval_expr(cond, doc):
                return False
        elif key == "$and":
            if not all(matches(doc, f) for f in cond):
                return False
        elif key.startswith("$"):
            raise OperationFailure(f"fake: unsupported top-level operator {key}", code=2)
        elif not _field_matches(get_path(doc, key), cond):
            return False
    return True


def _project(doc, projection):
    if not projection:
        return copy.deepcopy(doc)
    inc = {k for k, v in projection.items() if v and k != "_id"}
    exc = {k for k, v in projection.items() if not v}
    if inc:
        out = {}
        if projection.get("_id", 1) and "_id" in doc:
            out["_id"] = doc["_id"]
        for path in inc:
            v = get_path(doc, path)
            if v is not MISSING:
                set_path(out, path, copy.deepcopy(v))
        return out
    out = copy.deepcopy(doc)
    for path in exc:
        unset_path(out, path)
    return out


def _check_no_conflicts(update):
    paths = []
    for op, fields in update.items():
        if not op.startswith("$"):
            raise OperationFailure("fake: update document must use operators", code=9)
        paths.extend(fields)
    for i, p in enumerate(paths):
        for q in paths[i + 1:]:
            if p == q or p.startswith(q + ".") or q.startswith(p + "."):
                raise OperationFailure(f"fake: conflicting update paths {p!r} and {q!r}", code=40)


def _apply(doc, update, inserting):
    _check_no_conflicts(update)
    for op, fields in update.items():
        for path, v in fields.items():
            if op == "$inc":
                cur = get_path(doc, path)
                if cur is not MISSING and (isinstance(cur, bool) or not isinstance(cur, (int, float))):
                    raise OperationFailure("fake: cannot apply $inc to a value of non-numeric type", code=14)
                set_path(doc, path, v if cur is MISSING else cur + v)
            elif op == "$set":
                set_path(doc, path, copy.deepcopy(v))
            elif op == "$setOnInsert":
                if inserting:
                    set_path(doc, path, copy.deepcopy(v))
            elif op == "$unset":
                unset_path(doc, path)
            elif op == "$max":
                cur = get_path(doc, path)
                if cur is MISSING or _cmp_key(v) > _cmp_key(cur):
                    set_path(doc, path, v)
            else:
                raise OperationFailure(f"fake: unsupported update operator {op}", code=9)


def _has_expr(flt) -> bool:
    if isinstance(flt, dict):
        return any(k == "$expr" or _has_expr(v) for k, v in flt.items())
    if isinstance(flt, list):
        return any(_has_expr(v) for v in flt)
    return False


def _refuse_expr_in_upsert(flt):
    """Atlas: WriteError 224 "$expr is not allowed in the query predicate for an upsert", matched or not."""
    if _has_expr(flt):
        raise WriteError("$expr is not allowed in the query predicate for an upsert", code=224)


class _Result:
    def __init__(self, matched=0, modified=0, upserted_id=None, inserted_id=None):
        self.matched_count = matched
        self.modified_count = modified
        self.upserted_id = upserted_id
        self.inserted_id = inserted_id
        self.acknowledged = True


class FakeCursor:
    def __init__(self, coll, flt, projection):
        self._coll, self._flt, self._projection = coll, flt, projection
        self._sort = []

    def sort(self, key, direction=1):
        self._sort = [(key, direction)] if isinstance(key, str) else list(key)
        return self

    async def to_list(self, length=None):
        await self._coll._enter("find", filter=self._flt, projection=self._projection)
        selected = [d for d in self._coll.docs if matches(d, self._flt)]
        for k, d in reversed(self._sort):
            selected.sort(key=lambda doc, k=k: _cmp_key(None if get_path(doc, k) is MISSING else get_path(doc, k)),
                          reverse=(d == -1))
        docs = [_project(d, self._projection) for d in selected]
        return docs if length is None else docs[:length]


class FakeCollection:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.docs: list[dict] = []
        self.indexes: dict[str, dict] = {}   # name -> {"keys": [...], "options": {...}}

    async def _enter(self, op, **args):
        self.db.calls.append({"collection": self.name, "op": op, **copy.deepcopy(args)})
        if self.db.hang:
            await asyncio.sleep(3600)
        for hook in list(self.db.hooks):
            await hook(self, op, args)
        await asyncio.sleep(0)

    async def _leave(self, op, **args):
        """After a write has been applied: a hook may raise, as when the reply is lost on the way back."""
        for hook in list(self.db.after_hooks):
            await hook(self, op, args)

    # unique indexes -----------------------------------------------------------------------------------------------
    def _unique_keys(self):
        yield ["_id"]
        for spec in self.indexes.values():
            if spec["options"].get("unique"):
                yield [k for k, _ in spec["keys"]]

    def _check_unique(self, doc, ignore=None):
        for keys in self._unique_keys():
            tup = tuple(None if get_path(doc, k) is MISSING else get_path(doc, k) for k in keys)
            for other in self.docs:
                if other is ignore:
                    continue
                if tuple(None if get_path(other, k) is MISSING else get_path(other, k) for k in keys) == tup:
                    raise DuplicateKeyError(f"E11000 duplicate key error collection: {self.name} index: {keys}", 11000)

    # reads -------------------------------------------------------------------------------------------------------
    async def find_one(self, flt=None, projection=None, **kw):
        await self._enter("find_one", filter=flt, projection=projection)
        for d in self.docs:
            if matches(d, flt):
                return _project(d, projection)
        return None

    def find(self, flt=None, projection=None, **kw):
        # pymongo's find() builds a cursor without any I/O; the I/O happens in to_list()
        return FakeCursor(self, flt, projection)

    # writes ------------------------------------------------------------------------------------------------------
    async def insert_one(self, doc, **kw):
        await self._enter("insert_one", doc=doc)
        d = copy.deepcopy(doc)
        d.setdefault("_id", f"fake-{len(self.docs)}-{id(d)}")
        self._check_unique(d)
        self.docs.append(d)
        return _Result(inserted_id=d["_id"])

    async def insert_many(self, docs, ordered=True, **kw):
        await self._enter("insert_many", docs=docs, ordered=ordered)
        errors, n = [], 0
        for i, doc in enumerate(docs):
            d = copy.deepcopy(doc)
            d.setdefault("_id", f"fake-{len(self.docs)}-{id(d)}")
            try:
                self._check_unique(d)
            except DuplicateKeyError as e:
                errors.append({"index": i, "code": 11000, "errmsg": str(e)})
                if ordered:
                    break
                continue
            self.docs.append(d)
            n += 1
        if errors:
            raise BulkWriteError({"writeErrors": errors, "writeConcernErrors": [], "nInserted": n, "nUpserted": 0,
                                  "nMatched": 0, "nModified": 0, "nRemoved": 0, "upserted": []})
        return _Result()

    async def update_one(self, flt, update, upsert=False, **kw):
        if isinstance(update, list):
            raise OperationFailure("fake: pipeline updates are not implemented", code=9)
        await self._enter("update_one", filter=flt, update=update, upsert=upsert)
        if upsert:
            _refuse_expr_in_upsert(flt)
        for d in self.docs:
            if matches(d, flt):
                before = copy.deepcopy(d)
                trial = copy.deepcopy(d)
                _apply(trial, update, inserting=False)
                d.clear()
                d.update(trial)
                await self._leave("update_one", filter=flt, update=update)
                return _Result(matched=1, modified=int(before != d))
        if not upsert:
            return _Result()
        base = {}
        for key, cond in (flt or {}).items():
            if not key.startswith("$") and not _is_operator_doc(cond):
                set_path(base, key, copy.deepcopy(cond))
        _apply(base, update, inserting=True)
        base.setdefault("_id", f"fake-{len(self.docs)}-{id(base)}")
        self._check_unique(base)
        self.docs.append(base)
        await self._leave("update_one", filter=flt, update=update)
        return _Result(upserted_id=base["_id"])

    async def replace_one(self, flt, replacement, upsert=False, **kw):
        await self._enter("replace_one", filter=flt, replacement=replacement, upsert=upsert)
        if upsert:
            _refuse_expr_in_upsert(flt)
        for d in self.docs:
            if matches(d, flt):
                new = copy.deepcopy(replacement)
                new["_id"] = d["_id"]
                self._check_unique(new, ignore=d)
                d.clear()
                d.update(new)
                return _Result(matched=1, modified=1)
        if not upsert:
            return _Result()
        new = copy.deepcopy(replacement)
        for key, cond in (flt or {}).items():
            if not key.startswith("$") and not _is_operator_doc(cond):
                new.setdefault(key, cond)
        new.setdefault("_id", f"fake-{len(self.docs)}-{id(new)}")
        self._check_unique(new)
        self.docs.append(new)
        return _Result(upserted_id=new["_id"])

    async def create_index(self, keys, **options):
        await self._enter("create_index", keys=keys, options=options)
        keys = [(keys, 1)] if isinstance(keys, str) else list(keys)
        name = options.get("name") or "_".join(f"{k}_{d}" for k, d in keys)
        opts = {k: v for k, v in options.items() if k != "name"}
        if name in self.indexes:
            if self.indexes[name]["options"] != opts or self.indexes[name]["keys"] != keys:
                raise OperationFailure(f"fake: index {name} exists with different options", code=85)
            return name
        self.indexes[name] = {"keys": keys, "options": opts}
        return name


class FakeDatabase:
    def __init__(self):
        self.collections: dict[str, FakeCollection] = {}
        self.calls: list[dict] = []
        self.hooks: list = []     # async (collection, op, args): run before each operation; may raise or mutate
        self.after_hooks: list = []   # async (collection, op, args): run after a write was applied; may raise
        self.hang = False         # every operation waits forever (a dead Atlas)
        self.commands: list[dict] = []

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection(self, name))

    def collection(self, name):
        return self[name]

    async def command(self, cmd, **kw):
        self.commands.append(copy.deepcopy(cmd))
        if "collMod" in cmd:
            coll = self[cmd["collMod"]]
            spec = cmd["index"]
            idx = coll.indexes[spec["name"]]
            idx["options"]["expireAfterSeconds"] = spec["expireAfterSeconds"]
        return {"ok": 1}

    def calls_to(self, collection, op):
        return [c for c in self.calls if c["collection"] == collection and c["op"] == op]
