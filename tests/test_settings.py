import pytest
from fastapi.testclient import TestClient
from backend import main, providers
from backend.courses import CourseStore
from test_courses_api import configured_client


def test_persisted_settings_enforced_for_public_requests(tmp_path, monkeypatch):
    client, store = configured_client(tmp_path, monkeypatch)
    course = store.create('Settings Test', '', 'Tutor', 'de')
    cid = course['id']
    uploaded = client.post(f'/courses/{cid}/documents', files={'file': ('test.md', b'# Lernen\n\nLernen mit Daten erkennt Muster. Maschinelles Lernen verwendet viele Daten und Beispiele zur Erkennung von Mustern im Material.')})
    assert uploaded.status_code == 201
    settings = dict(mode='socratic', provider='ollama', base_url='http://localhost:11434', model='local-model', auth_mode='none', top_k=5, temperature=0.3, max_tokens=700, history_messages=0)
    assert client.put(f'/courses/{cid}/settings', json=settings).status_code == 200
    monkeypatch.setattr(main, 'store', CourseStore(store.root))
    assert client.get(f'/courses/{cid}/settings').json() == settings
    calls = []
    async def fake_chat(*args, **kwargs):
        calls.append((args, kwargs)); return 'Testantwort'
    monkeypatch.setattr(main, 'chat', fake_chat)
    client.post('/auth/logout')
    assert client.put(f'/courses/{cid}/settings', json=settings).status_code == 401
    assert client.get(f'/courses/{cid}/settings').status_code == 401
    assert client.post('/models', json={'base_url': 'http://evil.invalid'}).status_code == 401
    response = client.post('/tutor', json=dict(course_id=cid, message='Lernen Daten', mode='direct', base_url='http://evil.invalid', model='evil', top_k=1, api_key='must-not-forward', messages=[{'role':'user','content':'old message'}]))
    assert response.status_code == 200, response.text
    args, kwargs = calls[0]
    assert args[:3] == ('http://localhost:11434', 'local-model', '')
    assert len(args[3]) == 2
    assert 'Arbeite sokratisch' in args[3][0]['content']
    assert kwargs == dict(provider='ollama', temperature=0.3, max_tokens=700)
    info = client.get(f'/course-info?course_id={cid}').json()
    assert info['top_k'] == 5 and not info['requires_api_key']
    assert 'base_url' not in info and 'model' not in info


def test_validation_and_legacy_defaults(tmp_path, monkeypatch):
    client, store = configured_client(tmp_path, monkeypatch)
    course = store.create('Old course', '', 'Tutor', 'de'); cid=course['id']
    assert client.get(f'/courses/{cid}/settings').json()['top_k'] == 2
    for payload in [{'top_k': 0}, {'top_k':21}, {'temperature':3}, {'max_tokens':0}, {'base_url':'file:///tmp/test'}, {'base_url':'http://user:password@host'}]:
        assert client.put(f'/courses/{cid}/settings', json=payload).status_code == 422
    assert 'settings' not in store.load(cid)


@pytest.mark.parametrize('provider', ['ollama', 'openai-compatible'])
def test_provider_wire_protocol(monkeypatch, provider):
    import asyncio
    import httpx
    seen=[]
    def handler(request):
        import json
        body=json.loads(request.content) if request.content else {}
        seen.append((request, body))
        if request.method=='GET':
            return httpx.Response(200,json={'models':[{'name':'local'}]} if provider=='ollama' else {'data':[{'id':'local'}]})
        return httpx.Response(200,json={'message':{'content':'yes'}} if provider=='ollama' else {'choices':[{'message':{'content':'yes'}}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kw: original(transport=httpx.MockTransport(handler),**kw))
    assert asyncio.run(providers.list_models('http://localhost:11434','',provider))[0]['id']=='local'
    assert asyncio.run(providers.chat('http://localhost:11434','local','',[],provider,0.2,512))=='yes'
    request, body=seen[-1]
    assert 'authorization' not in request.headers
    if provider=='ollama':
        assert request.url.path=='/api/chat' and body['options']['num_predict']==512
    else:
        assert request.url.path=='/chat/completions' and body['max_tokens']==512
