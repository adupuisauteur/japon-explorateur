"""Connecteur « Base locale » : interroge les notices déjà collectées ou importées."""
import time

from .base import BaseConnector, ConnectorResult, SearchResponse
from .registry import register


@register
class LocalConnector(BaseConnector):
    key = "local"
    label = "Base locale"
    description = "Notices importées ou déjà enregistrées dans l'application."
    supports_fielded_search = True
    supports_date_filter = True
    supports_fetch = True

    def search(self, query):
        from apps.catalog.search import local_search

        started = time.monotonic()
        qs = local_search(query)
        total = qs.count()
        start = (query.page - 1) * query.page_size
        results = []
        for record in qs[start:start + query.page_size]:
            results.append(ConnectorResult(
                source_id=record.record_id,
                data=record_to_data(record),
                raw={"record_id": record.record_id, "catalogue": record.catalogue.code, "source_id": record.source_id},
                raw_format="local",
            ))
        return SearchResponse(results=results, total=total, page=query.page,
                              has_more=start + query.page_size < total,
                              elapsed_ms=int((time.monotonic() - started) * 1000))

    def fetch_record(self, source_id):
        from apps.catalog.models import Record

        record = Record.objects.filter(record_id=source_id).first()
        if record is None:
            return None
        return ConnectorResult(source_id=record.record_id, data=record_to_data(record), raw_format="local")

    def test(self):
        from apps.catalog.models import Record

        return True, f"{Record.objects.count()} notices dans la base locale.", {}


def record_to_data(record):
    from apps.catalog.models import RECORD_SOURCE_FIELDS

    data = {f: getattr(record, f) for f in RECORD_SOURCE_FIELDS}
    data.update({
        "record_id": record.record_id,
        "catalogue_code": record.catalogue.code,
        "catalogue_name": record.catalogue.name,
        "period": record.period,
        "document_type": record.document_type,
        "material_type": record.material_type,
        "collected_at": record.collected_at.isoformat() if record.collected_at else "",
        "record_status": record.record_status,
    })
    return data
