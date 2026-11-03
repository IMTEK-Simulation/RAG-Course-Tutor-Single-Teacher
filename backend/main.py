from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.staticfiles import StaticFiles

from .providers import chat, list_models, validate_api_url
from .auth import SingleAccountAuth
from .config import COOKIE_SECURE, DEFAULT_API_URL
from .courses import CourseStore
from .ingestion import build_chunks
from .retrieval import CourseRetriever
from .schemas import AccountCredentials, CourseSettings, ChunkUpdate, CourseCreate, ModelRequest, SourceResult, TutorRequest, TutorResponse

app = FastAPI(title="RAG Course Tutor", version="1.2.0")
store = CourseStore()
auth = SingleAccountAuth()
retrievers: dict[str, CourseRetriever] = {}
STATIC_DIR = Path(__file__).resolve().parent / "static"


def require_auth(request: Request) -> str:
    return auth.require(request)


def get_retriever(course_id: str) -> CourseRetriever:
    try:
        path = store.course_path(course_id)
        if not path.exists():
            raise KeyError(course_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Kurs nicht gefunden") from exc
    if course_id not in retrievers:
        retrievers[course_id] = CourseRetriever(path)
    return retrievers[course_id]


def build_system_prompt(request: TutorRequest, sources: list[dict], course: dict) -> str:
    context = "\n\n".join(
        f"[Quelle {index}: {source['section']}]\n{source['text']}"
        for index, source in enumerate(sources, 1)
    )
    language = {
        "auto": "Antworte in der Sprache der aktuellen Frage.",
        "de": "Antworte auf Deutsch.",
        "en": "Answer in English.",
    }[request.language]
    mode = (
        "Erkläre klar, knapp und auf dem Niveau der lernenden Person. Nutze bei Bedarf ein kleines Beispiel."
        if request.mode == "direct"
        else (
            "Arbeite sokratisch in gestuften Hilfen: Stelle zunächst genau eine "
            "Leitfrage oder gib einen kleinen Hinweis. Verrate die vollständige "
            "Lösung erst, wenn die lernende Person ausdrücklich darum bittet."
        )
    )
    return f"""Du bist {course.get('tutor_role', 'ein Lernbegleiter für Studierende')} im Kurs „{course['name']}“.
{language}
{mode}

Verbindliche Regeln:
- Grundlage sind ausschließlich die unten angegebenen Kursquellen.
- Erfinde keine Kursinhalte.
- Wenn die Quellen nicht ausreichen, sage das ausdrücklich.
- Zitiere Tatsachen mit [Quelle 1], [Quelle 2] usw.
- Verwende keine Quelle, die nicht im Kontext steht.
- Fachbegriffe, Code und Formeln müssen den Quellen entsprechen.
- Prüfe vor der Antwort still, ob jede Behauptung aus dem Kontext folgt.
- Bei unzureichendem Kontext sage nur, dass das Kursmaterial die Frage nicht
  ausreichend beantwortet, und bitte um eine genauere Frage.

KURSKONTEXT:
{context}
"""


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "configured": auth.configured}


@app.get("/auth/status")
async def auth_status(request: Request) -> dict:
    username = auth.token_username(request.cookies.get("rag_tutor_session"))
    return {
        "configured": auth.configured, "authenticated": username is not None,
        "username": username, "default_api_url": DEFAULT_API_URL,
    }


@app.post("/auth/setup", status_code=201)
async def auth_setup(credentials: AccountCredentials, response: Response) -> dict:
    auth.setup(credentials.username, credentials.password)
    response.set_cookie(
        "rag_tutor_session", auth.issue_token(credentials.username), httponly=True,
        secure=COOKIE_SECURE, samesite="strict", max_age=12 * 60 * 60,
    )
    return {"status": "created", "username": credentials.username}


@app.post("/auth/login")
async def auth_login(credentials: AccountCredentials, response: Response) -> dict:
    if not auth.configured:
        raise HTTPException(status_code=409, detail="Das Dozentenkonto wurde noch nicht eingerichtet.")
    if not auth.verify(credentials.username, credentials.password):
        raise HTTPException(status_code=401, detail="Benutzername oder Passwort ist falsch.")
    response.set_cookie(
        "rag_tutor_session", auth.issue_token(credentials.username), httponly=True,
        secure=COOKIE_SECURE, samesite="strict", max_age=12 * 60 * 60,
    )
    return {"status": "ok", "username": credentials.username}


@app.post("/auth/logout")
async def auth_logout(response: Response) -> dict:
    response.delete_cookie("rag_tutor_session")
    return {"status": "logged_out"}


@app.get("/course-info")
async def course_info(course_id: str) -> dict:
    retriever = get_retriever(course_id)
    course = store.load(course_id)
    return {
        "id": course_id, "name": course["name"], "description": course.get("description", ""),
        "mode": CourseSettings(**course.get("settings", {})).mode,
        "requires_api_key": CourseSettings(**course.get("settings", {})).auth_mode == "student",
        "top_k": CourseSettings(**course.get("settings", {})).top_k,
        "chunks": len(retriever.chunks),
        "titles": sorted({item["title"] for item in retriever.chunks}),
        "modules": sorted({item["module"] for item in retriever.chunks}),
    }


@app.get("/courses")
async def courses() -> dict:
    return {"courses": store.list()}


@app.post("/courses", status_code=201)
async def create_course(request: CourseCreate, _user: str = Depends(require_auth)) -> dict:
    try:
        request.settings.base_url = validate_api_url(request.settings.base_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    course = store.create(request.name, request.description, request.tutor_role, request.language)
    course["settings"] = request.settings.model_dump()
    store.save(course["id"], course)
    return course


@app.get("/courses/{course_id}/settings")
async def get_settings(course_id: str, _user: str = Depends(require_auth)) -> dict:
    try:
        course = store.load(course_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Kurs nicht gefunden") from exc
    return CourseSettings(**course.get("settings", {})).model_dump()


@app.put("/courses/{course_id}/settings")
async def save_settings(course_id: str, settings: CourseSettings, _user: str = Depends(require_auth)) -> dict:
    try:
        course = store.load(course_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Kurs nicht gefunden") from exc
    try:
        settings.base_url = validate_api_url(settings.base_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    course["settings"] = settings.model_dump()
    store.save(course_id, course)
    return course["settings"]


@app.get("/courses/{course_id}/chunks")
async def list_chunks(course_id: str, _user: str = Depends(require_auth)) -> dict:
    try:
        course = store.load(course_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Kurs nicht gefunden") from exc
    return {"course": {k: course.get(k) for k in ("id", "name", "description")}, "chunks": course.get("chunks", [])}


@app.post("/courses/{course_id}/documents", status_code=201)
async def upload_document(course_id: str, file: UploadFile = File(...), _user: str = Depends(require_auth)) -> dict:
    try:
        course = store.load(course_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Kurs nicht gefunden") from exc
    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Datei ist größer als 25 MB")
    try:
        original_name = Path(file.filename or "dokument.txt").name
        chunks = build_chunks(course, original_name, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not chunks:
        raise HTTPException(status_code=422, detail="Aus der Datei konnte kein Inhalt extrahiert werden")
    stored_name = store.save_source(course_id, original_name, content)
    for chunk in chunks:
        chunk["source_file"] = stored_name
    course.setdefault("chunks", []).extend(chunks)
    store.save(course_id, course)
    store.invalidate_index(course_id)
    retrievers.pop(course_id, None)
    return {"file": stored_name, "chunks_added": len(chunks), "quality_flags": sum(bool(c["quality_flags"]) for c in chunks)}


@app.patch("/courses/{course_id}/chunks/{chunk_id}")
async def update_chunk(course_id: str, chunk_id: str, request: ChunkUpdate, _user: str = Depends(require_auth)) -> dict:
    try:
        course = store.load(course_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Kurs nicht gefunden") from exc
    chunk = next((item for item in course.get("chunks", []) if item["id"] == chunk_id), None)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk nicht gefunden")
    chunk.update(request.model_dump())
    chunk["quality_flags"] = []
    store.save(course_id, course); store.invalidate_index(course_id); retrievers.pop(course_id, None)
    return chunk


@app.delete("/courses/{course_id}/chunks/{chunk_id}")
async def delete_chunk(course_id: str, chunk_id: str, _user: str = Depends(require_auth)) -> dict:
    try:
        course = store.load(course_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Kurs nicht gefunden") from exc
    before = len(course.get("chunks", []))
    course["chunks"] = [item for item in course.get("chunks", []) if item["id"] != chunk_id]
    if len(course["chunks"]) == before:
        raise HTTPException(status_code=404, detail="Chunk nicht gefunden")
    store.save(course_id, course); store.invalidate_index(course_id); retrievers.pop(course_id, None)
    return {"status": "deleted", "id": chunk_id}


@app.post("/courses/{course_id}/reindex")
async def reindex(course_id: str, _user: str = Depends(require_auth)) -> dict:
    store.invalidate_index(course_id); retrievers.pop(course_id, None)
    retriever = get_retriever(course_id)
    return {"status": "ready", "chunks": len(retriever.chunks), "note": "Der lokale BM25-Index ist aktiv."}


@app.delete("/courses/{course_id}")
async def delete_course(course_id: str, _user: str = Depends(require_auth)) -> dict:
    try:
        store.delete(course_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Kurs nicht gefunden") from exc
    retrievers.pop(course_id, None)
    return {"status": "deleted", "id": course_id}


def source_results(sources: list[dict]) -> list[SourceResult]:
    return [
        SourceResult(
            id=source["id"],
            title=source["title"],
            section=source["section"],
            source_file=source["source_file"],
            score=source["score"],
            text=source["text"],
        )
        for source in sources
    ]


@app.post("/models")
async def models(request: ModelRequest, _user: str = Depends(require_auth)) -> dict:
    try:
        return {"models": await list_models(request.base_url, request.api_key, request.provider)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Modellliste nicht erreichbar: {exc}") from exc


@app.post("/tutor", response_model=TutorResponse)
async def tutor(request: TutorRequest) -> TutorResponse:
    retriever = get_retriever(request.course_id)
    course = store.load(request.course_id)
    settings = CourseSettings(**course.get("settings", {}))
    request.mode = settings.mode
    request.top_k = settings.top_k
    api_key = request.api_key if settings.auth_mode == "student" else ""
    retrieval_mode = "BM25"
    try:
        sources = retriever.lexical_search(request.message, request.top_k)
        if not sources:
            answer = (
                "Dazu finde ich im indexierten Kursmaterial keine ausreichend passende "
                "Stelle. Bitte formuliere die Frage genauer."
                if request.language != "en"
                else "I cannot find a sufficiently relevant passage in the indexed course material. Please make the question more specific."
            )
            return TutorResponse(
                answer=answer,
                provider=settings.provider,
                model=settings.model,
                retrieval=retrieval_mode,
                sources=[],
            )
        messages = [{"role": "system", "content": build_system_prompt(request, sources, course)}]
        if settings.auth_mode == "student" and not api_key:
            raise HTTPException(status_code=400, detail="Für diesen Kurs ist ein persönlicher API-Key erforderlich.")
        if settings.history_messages:
            messages.extend(message.model_dump() for message in request.messages[-settings.history_messages:])
        messages.append({"role": "user", "content": request.message})
        answer = await chat(
            settings.base_url,
            settings.model,
            api_key,
            messages,
            provider=settings.provider, temperature=settings.temperature, max_tokens=settings.max_tokens,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Tutor-Anfrage fehlgeschlagen. Bitte Server, Modell und Zugangsdaten prüfen.") from exc

    return TutorResponse(
        answer=answer,
        provider=settings.provider,
        model=settings.model,
        retrieval=retrieval_mode,
        sources=source_results(sources),
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
