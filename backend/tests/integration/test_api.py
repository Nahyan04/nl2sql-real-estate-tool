"""Small API smoke test against the configured fresh database; model calls are mocked."""
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from app.main import app
from app.api.routes.query import chat_model_factory


class Model:
    def __init__(self):
        self.responses = iter(['<sql>SELECT count(*) AS observations FROM transactions</sql>', '122936 exported sales observations.'])
    def invoke(self, messages):
        return AIMessage(content=next(self.responses))


def test_fresh_api_query_schema_examples_and_readiness():
    app.dependency_overrides[chat_model_factory] = lambda: lambda _: Model()
    try:
        with TestClient(app) as client:
            assert client.get('/ready').json()['snapshot_id'] == '2026-09-24'
            schema = client.get('/api/v1/schema').json()
            assert {t['name'] for t in schema['tables']} == {'transactions','price_indices','rental_observations','dataset_coverage'}
            assert client.get('/api/v1/examples').status_code == 200
            response = client.post('/api/v1/query', json={'question':'How many exported sales observations?'})
            assert response.status_code == 200
            body = response.json()
            assert body['rows'] == [[122936]] and body['tables_used'] == ['transactions']
    finally:
        app.dependency_overrides.clear()
