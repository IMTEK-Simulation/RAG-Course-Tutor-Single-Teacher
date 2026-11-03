import json

from backend.retrieval import CourseRetriever


def test_neutral_bm25_retrieval(tmp_path):
    corpus = tmp_path / "course.json"
    corpus.write_text(json.dumps({"chunks": [
        {"id": "c1", "title": "Netze", "section": "Netzwerksicherheit", "source_file": "netze.md", "text": "Eine Firewall filtert Netzwerkverkehr anhand definierter Regeln."},
        {"id": "c2", "title": "Daten", "section": "Maschinelles Lernen", "source_file": "ki.md", "text": "Ein Modell erkennt Muster in Trainingsdaten."},
    ]}), encoding="utf-8")
    retriever = CourseRetriever(corpus)
    results = retriever.lexical_search("Wie filtert eine Firewall Netzwerkverkehr?", 1)
    assert results[0]["id"] == "c1"
