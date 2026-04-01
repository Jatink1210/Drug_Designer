import pytest
from pydantic import BaseModel
from connectors.base import BaseConnector

class DummyEntity(BaseModel):
    id: str
    name: str

class MockConnector(BaseConnector):
    name = "MockConnector"
    async def fetch(self, query: str):
        if query == "fail":
            raise Exception("Mocked connection timeout")
        return {"data": [{"id": "TST1", "title": "Test Entity", "timestamp": "2026-02-26"}]}
        
    async def search(self, query: str, limit: int = 10):
        # Implement the required abstract method search() mapped for base connector
        return await self.fetch(query)
    
    def normalize(self, raw_data) -> list:
        results = []
        for row in raw_data.get("data", []):
            ent = DummyEntity(id=row["id"], name=row["title"])
            ent.__dict__["provenance"] = [self._prov(url=f"test/{row['id']}", phash=str(row))]
            results.append(ent)
        return results

@pytest.mark.asyncio
async def test_connector_normalization():
    connector = MockConnector()
    raw = await connector.fetch("success")
    normalized = connector.normalize(raw)
    
    assert len(normalized) == 1
    entity = normalized[0]
    
    assert entity.id == "TST1"
    assert entity.name == "Test Entity"
    
    # Assert Provence Model Attachment Native Implementation
    assert hasattr(entity, "provenance")
    assert len(entity.provenance) == 1
    assert entity.provenance[0].source_name == "MockConnector"
    assert entity.provenance[0].confidence_score == 1.0

@pytest.mark.asyncio
async def test_connector_failure_gracefully(caplog):
    connector = MockConnector()
    try:
        await connector.fetch("fail")
    except Exception as e:
        assert str(e) == "Mocked connection timeout"
