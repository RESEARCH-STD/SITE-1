"""
JSON API the QDA front-end syncs through (static/qda/js/cloud.js).

    GET  api/projects/              -> {"projects": [{"id", "rev", "deleted"}, …]}   (version list)
    GET  api/projects/?ids=a,b      -> {"projects": [<full project>, …]}
    GET  api/projects/<id>/         -> <full project>        (?head=1: just id/rev/deleted)
    PUT  api/projects/<id>/         -> {"rev": n}            upload a change (see below)

A full project is {"id", "rev", "deleted", "title", "project": <document
without sources>, "sources": [<sources with transcript text>]}.

Uploads carry the revision they were based on ("base", null for a project
the browser has never synced). If someone else changed the project since,
the answer is 409 with the current copy ({"current": <full project> or
null}) and the browser decides what to keep: nothing is overwritten
silently. A body is {"base", "writer", "deleted": bool, "project": {…},
"sources": […] (only when the transcripts changed)}; it may be gzipped
(Content-Encoding: gzip) to save mobile data.

Every request must come from a signed-in user (401 otherwise). The browser
also sends the id of the user its page was opened for (X-TB-User); if the
session now belongs to someone else (signed in as another person in
another tab) the answer is 409 {"error": "user_changed"} and the page
reloads, so one person's work never lands in another's account.
"""

import json
import zlib
from functools import wraps

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.gzip import gzip_page
from django.views.decorators.http import require_http_methods

from .models import Project
from .sync import DocumentError, apply_document, project_document, source_list, validate_document

MAX_IDS = 200


def _error(status, code, message=""):
    return JsonResponse({"error": code, "message": message}, status=status)


def api_view(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _error(401, "signed_out", "Your session has ended. Sign in again to keep syncing.")
        expected = request.headers.get("X-TB-User")
        if expected and expected != str(request.user.pk):
            return _error(409, "user_changed", "This browser is now signed in as someone else.")
        response = view(request, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    return wrapped


def _full(project):
    return {
        "id": project.client_id,
        "rev": project.revision,
        "deleted": project.deleted,
        "title": project.title,
        "updated": int(project.updated_at.timestamp() * 1000),
        "project": project_document(project, include_sources=False),
        "sources": source_list(project),
    }


def _head(project):
    return {"id": project.client_id, "rev": project.revision, "deleted": project.deleted}


def _read_body(request):
    """The request's JSON body, gunzipped if needed, within the size limit."""
    limit = settings.QDA_MAX_UPLOAD_BYTES
    try:
        declared = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        declared = 0
    if declared > limit:
        raise _TooBig()
    raw = request.read(limit + 1)
    if len(raw) > limit:
        raise _TooBig()
    if request.headers.get("Content-Encoding", "").lower() == "gzip":
        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            raw = inflater.decompress(raw, limit + 1)
        except zlib.error:
            raise ValueError("The upload isn't valid gzip data.")
        if len(raw) > limit or inflater.unconsumed_tail:
            raise _TooBig()
    body = json.loads(raw.decode("utf-8"))
    if not isinstance(body, dict):
        raise ValueError("The upload must be a JSON object.")
    return body


class _TooBig(Exception):
    pass


@gzip_page
@require_http_methods(["GET"])
@api_view
def project_list(request):
    projects = Project.objects.filter(owner=request.user)
    ids = request.GET.get("ids")
    if ids is None:
        heads = projects.order_by("pk").values_list("client_id", "revision", "deleted")
        return JsonResponse({"projects": [{"id": c, "rev": r, "deleted": d} for c, r, d in heads]})
    wanted = [i for i in ids.split(",") if i][:MAX_IDS]
    return JsonResponse({"projects": [_full(p) for p in projects.filter(client_id__in=wanted)]})


@gzip_page
@require_http_methods(["GET", "PUT"])
@api_view
def project_detail(request, client_id):
    if request.method == "GET":
        project = Project.objects.filter(owner=request.user, client_id=client_id).first()
        if project is None:
            return _error(404, "not_found")
        return JsonResponse(_head(project) if request.GET.get("head") else _full(project))
    return _put(request, client_id)


def _put(request, client_id):
    if len(client_id) > 100:
        return _error(400, "bad_request", "Project ids are at most 100 characters.")
    try:
        body = _read_body(request)
    except _TooBig:
        return _error(413, "too_large", "This project is too large to upload in one go.")
    except (ValueError, UnicodeDecodeError) as exc:
        return _error(400, "bad_request", str(exc) or "The upload isn't valid JSON.")

    base = body.get("base")
    if base is not None and (isinstance(base, bool) or not isinstance(base, int) or base < 0):
        return _error(400, "bad_request", "'base' must be a revision number or null.")
    writer = str(body.get("writer") or "")[:64]
    deleting = body.get("deleted") is True
    doc = body.get("project")
    sources = body.get("sources") if "sources" in body else None
    if not deleting:
        try:
            validate_document(doc, sources)
        except DocumentError as exc:
            return _error(400, "bad_document", str(exc))

    # Two first uploads of the same new project can race; the loser of the
    # insert tries once more and then sees the winner's row.
    for attempt in (1, 2):
        try:
            with transaction.atomic():
                return _apply(request.user, client_id, base, writer, deleting, doc, sources)
        except IntegrityError:
            if attempt == 2:
                raise
    raise AssertionError("unreachable")


def _apply(user, client_id, base, writer, deleting, doc, sources):
    project = Project.objects.select_for_update().filter(owner=user, client_id=client_id).first()
    created = project is None
    if created:
        if base is not None:
            # The browser synced this project before, but it's gone from the
            # account now (deleted for good in the admin).
            return JsonResponse({"error": "conflict", "current": None}, status=409)
        if deleting:
            return JsonResponse({"rev": None})
        project = Project(owner=user, client_id=client_id)
    elif base != project.revision and not _resend(project, writer, base):
        return JsonResponse({"error": "conflict", "current": _full(project)}, status=409)

    project.revision += 1
    project.last_writer = writer
    project.last_write_base = base
    if deleting:
        project.deleted = True
        project.deleted_at = timezone.now()
        project.save()
    else:
        project.deleted = False
        project.deleted_at = None
        if created and sources is None:
            sources = []
        try:
            apply_document(project, doc, sources)
        except DocumentError as exc:
            transaction.set_rollback(True)
            return _error(400, "bad_document", str(exc))
    return JsonResponse({"rev": project.revision}, status=201 if created else 200)


def _resend(project, writer, base):
    """True when the stored revision was made by this same browser from the
    same starting point as this upload: an earlier upload went through but
    its answer was lost (e.g. a dropped mobile connection). The browser's
    copy already contains that change, so this upload safely replaces it."""
    return bool(writer) and project.last_writer == writer and project.last_write_base == base
