"""
Converts between a project *document* (the JSON object the QDA front-end
keeps in the browser; see static/qda/js/app.js) and the rows in
qda.models.

    project_document(project)      rows -> document (exactly what was sent)
    apply_document(project, doc)   document -> rows (insert / update / delete)

A document looks like:

    {"id": "proj_…", "title": "…", "researcher": "…", …other fields…,
     "analyses": [{"id": "ana_main", "name": "…", "question": "…"}],
     "sources":  [{"id": "src_…", "type": "KII", "name": "…", "text": "…",
                   "attributes": {"respondentId": "R01", …}, "speakers": […]}],
     "themes":   [{"id": "thm_…", "parentId": null, "analysisId": "ana_main",
                   "name": "…", "color": "#1B4F9C"}],
     "codings":  [{"id": "cod_…", "sourceId": "src_…", "themeIds": ["thm_…"],
                   "start": 10, "end": 52, "quote": "…", "weight": 7}]}

Only fields the admin shows are copied into columns; everything else rides
along in each row's `data`, so new fields in the app need no change here.
"""

from django.db import transaction

from .models import Analysis, Coding, CodingTheme, Source, Theme

LIST_KEYS = ("analyses", "sources", "themes", "codings")
MAX_ID_LENGTH = 100
BATCH = 500


class DocumentError(ValueError):
    """The upload isn't a usable project document."""


# --------------------------------------------------------------- helpers
def _text(value, limit=None):
    if value is None:
        return ""
    s = value if isinstance(value, str) else str(value)
    return s[:limit] if limit else s


def _count(value, default=0):
    """A non-negative whole number, or `default`."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value if value >= 0 else default
    if isinstance(value, float) and value.is_integer() and value >= 0:
        return int(value)
    return default


def _ref(value):
    return value if isinstance(value, str) and value else None


def _items(value, key):
    if value is None:
        return []
    if not isinstance(value, list):
        raise DocumentError(f"'{key}' must be a list.")
    seen = set()
    for item in value:
        if not isinstance(item, dict):
            raise DocumentError(f"Every entry in '{key}' must be an object.")
        cid = item.get("id")
        if not isinstance(cid, str) or not cid or len(cid) > MAX_ID_LENGTH:
            raise DocumentError(f"Every entry in '{key}' needs a text id of at most {MAX_ID_LENGTH} characters.")
        if cid in seen:
            raise DocumentError(f"'{key}' lists the id '{cid}' twice.")
        seen.add(cid)
    return value


def _chunks(seq, size=BATCH):
    seq = list(seq)
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


# ----------------------------------------------------- column extraction
# Each fill_* copies an item into a row; returns nothing. `data` is the item
# without its id (and, for sources, without the transcript text).

def _fill_analysis(row, item, data):
    row.name = _text(item.get("name"), 300)
    row.question = _text(item.get("question"))


def _fill_source(row, item, data):
    attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
    row.source_type = _text(item.get("type"), 40)
    row.name = _text(item.get("name"), 300)
    row.respondent_id = _text(attributes.get("respondentId"), 200)
    row.text = _text(item.get("text"))
    row.word_count = len(row.text.split())


def _fill_theme(row, item, data):
    row.name = _text(item.get("name"), 300)
    row.color = _text(item.get("color"), 20)


def _fill_coding(row, item, data, source_pks):
    row.source_id = source_pks.get(_ref(item.get("sourceId")))
    row.speaker_id = _text(item.get("speakerId"), 100)
    row.start = _count(item.get("start"))
    row.end = _count(item.get("end"))
    row.quote = _text(item.get("quote"))
    weight = _count(item.get("weight"), None)
    row.weight = weight if weight is not None and weight <= 32767 else None


ITEM_FIELDS = {
    Analysis: ["name", "question"],
    Source: ["source_type", "name", "respondent_id", "text", "word_count"],
    Theme: ["name", "color"],
    Coding: ["source_id", "speaker_id", "start", "end", "quote", "weight"],
}


def _sync_items(project, model, items, fill, drop_keys=("id",)):
    """Make the project's `model` rows match `items` (by client id):
    update changed rows, insert new ones, delete the rest. Returns
    {client_id: pk} for every row now in the project."""
    fields = ["position", "data"] + ITEM_FIELDS[model]
    existing = {row.client_id: row for row in model.objects.filter(project=project)}
    keep, new, changed = set(), [], []
    for position, item in enumerate(items):
        cid = item["id"]
        keep.add(cid)
        data = {k: v for k, v in item.items() if k not in drop_keys}
        row = existing.get(cid)
        if row is None:
            row = model(project=project, client_id=cid)
            new.append(row)
            before = None
        else:
            before = tuple(getattr(row, f) for f in fields)
        row.position = position
        row.data = data
        fill(row, item, data)
        if before is not None and tuple(getattr(row, f) for f in fields) != before:
            changed.append(row)
    stale = [row.pk for cid, row in existing.items() if cid not in keep]
    for chunk in _chunks(stale):
        model.objects.filter(pk__in=chunk).delete()
    if new:
        model.objects.bulk_create(new, batch_size=BATCH)
    if changed:
        model.objects.bulk_update(changed, fields, batch_size=BATCH)
    # Re-read rather than trusting bulk_create to fill in primary keys
    # (MySQL doesn't).
    return dict(model.objects.filter(project=project).values_list("client_id", "pk"))


def _link_themes(project, theme_pks, analysis_pks):
    changed = []
    for row in Theme.objects.filter(project=project).only("pk", "client_id", "data", "parent_id", "analysis_id"):
        parent_ref = _ref(row.data.get("parentId"))
        parent = theme_pks.get(parent_ref) if parent_ref != row.client_id else None
        analysis = None if parent else analysis_pks.get(_ref(row.data.get("analysisId")))
        if (row.parent_id, row.analysis_id) != (parent, analysis):
            row.parent_id, row.analysis_id = parent, analysis
            changed.append(row)
    if changed:
        Theme.objects.bulk_update(changed, ["parent", "analysis"], batch_size=BATCH)


def _link_coding_themes(project, codings, coding_pks, theme_pks):
    wanted = set()
    for item in codings:
        theme_ids = item.get("themeIds")
        if not isinstance(theme_ids, list):
            continue
        for tid in theme_ids:
            pk = theme_pks.get(_ref(tid))
            if pk:
                wanted.add((coding_pks[item["id"]], pk))
    have = {}
    for pk, coding_id, theme_id in CodingTheme.objects.filter(coding__project=project).values_list(
        "pk", "coding_id", "theme_id"
    ):
        have[(coding_id, theme_id)] = pk
    for chunk in _chunks(pk for pair, pk in have.items() if pair not in wanted):
        CodingTheme.objects.filter(pk__in=chunk).delete()
    CodingTheme.objects.bulk_create(
        [CodingTheme(coding_id=c, theme_id=t) for (c, t) in wanted if (c, t) not in have], batch_size=BATCH
    )


# ------------------------------------------------------------ public API
def validate_document(doc, sources=None):
    """Raise DocumentError unless `doc` (and `sources`, if given) can be stored."""
    if not isinstance(doc, dict):
        raise DocumentError("The project must be a JSON object.")
    for key in ("analyses", "themes", "codings"):
        _items(doc.get(key), key)
    if sources is not None:
        _items(sources, "sources")


@transaction.atomic
def apply_document(project, doc, sources=None):
    """Store `doc` as the project's content.

    `sources` is the list of sources (with transcript text) to store, or
    None to keep the stored sources as they are — the browser only uploads
    transcripts when they changed. Any `sources` inside `doc` itself are
    ignored. Saves `project` (whose own bookkeeping fields the caller sets).
    """
    validate_document(doc, sources)
    top = {k: v for k, v in doc.items() if k != "id" and k not in LIST_KEYS}
    project.data = top
    project.title = _text(top.get("title"), 300)
    project.researcher = _text(top.get("researcher"), 300)
    project.organization = _text(top.get("org"), 300)
    project.topic = _text(top.get("topic"), 300)
    project.save()

    analysis_pks = _sync_items(project, Analysis, _items(doc.get("analyses"), "analyses"), _fill_analysis)
    if sources is not None:
        source_pks = _sync_items(project, Source, _items(sources, "sources"), _fill_source, drop_keys=("id", "text"))
    else:
        source_pks = dict(Source.objects.filter(project=project).values_list("client_id", "pk"))
    theme_pks = _sync_items(project, Theme, _items(doc.get("themes"), "themes"), _fill_theme)
    _link_themes(project, theme_pks, analysis_pks)
    codings = _items(doc.get("codings"), "codings")
    coding_pks = _sync_items(
        project, Coding, codings, lambda row, item, data: _fill_coding(row, item, data, source_pks)
    )
    _link_coding_themes(project, codings, coding_pks, theme_pks)


def _item(row):
    return {"id": row.client_id, **row.data}


def project_document(project, include_sources=True):
    """The project as the app stores it (with transcripts unless told not to)."""
    doc = {"id": project.client_id, **(project.data or {})}
    doc["analyses"] = [_item(r) for r in project.analyses.all()]
    if include_sources:
        doc["sources"] = [{**_item(r), "text": r.text} for r in project.sources.all()]
    doc["themes"] = [_item(r) for r in project.themes.all()]
    doc["codings"] = [_item(r) for r in project.codings.all()]
    return doc


def source_list(project):
    return [{**_item(r), "text": r.text} for r in project.sources.all()]
