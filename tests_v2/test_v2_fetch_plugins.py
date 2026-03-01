from __future__ import annotations

from v2.services.fetch.plugins import OpenAlexPlugin


def test_openalex_should_put_date_range_in_filter(monkeypatch):
    captured: dict = {}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": []}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params or {}
        return _Resp()

    monkeypatch.setattr("v2.services.fetch.plugins.requests.get", fake_get)

    plugin = OpenAlexPlugin()
    plugin.search(
        keywords=["agent"],
        start_date="2026-02-20",
        end_date="2026-03-01",
        page=1,
        page_size=5,
    )

    params = captured["params"]
    assert params["filter"] == "type:article,from_publication_date:2026-02-20,to_publication_date:2026-03-01"
    assert "from_publication_date" not in params
    assert "to_publication_date" not in params
