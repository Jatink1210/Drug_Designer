import pytest
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models

pytestmark = pytest.mark.integration

@pytest.fixture
def qdrant():
    url = os.environ.get("QDRANT_URL", "http://qdrant:6333")
    client = QdrantClient(url=url, timeout=5)
    # Skip the entire test if Qdrant is not reachable instead of failing
    try:
        client.get_collections()
    except Exception:
        pytest.skip(f"Qdrant server not reachable at {url}")
    return client


@pytest.mark.asyncio
async def test_qdrant_connection_and_mock_upsert(qdrant):
    # Verify connection
    assert qdrant.get_collections() is not None
    
    collection_name = "test_smoke_collection"
    
    # Create test collection
    try:
        qdrant.get_collection(collection_name)
    except Exception:
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=512, distance=models.Distance.COSINE)
        )
        
    # Test batch embedding structure (upserting a vector)
    operation_info = qdrant.upsert(
        collection_name=collection_name,
        points=[
            models.PointStruct(
                id=1,
                vector=[0.5] * 512,
                payload={"test_key": "test_value"}
            )
        ]
    )
    assert operation_info.status == models.UpdateStatus.COMPLETED
    
    # Clean up
    qdrant.delete_collection(collection_name=collection_name)
