"""Document workspace API and processing helpers."""

from . import service, storage, api

router = api.router
shutdown_document_jobs = service.shutdown_document_jobs


def __getattr__(name: str):
    for module in (service, storage, api):
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
