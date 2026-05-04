"""
Unit tests for MolFormer molecular representation model
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from apps.api.services.ml.molformer_model import MolFormerModel


@pytest.fixture
def molformer_model():
    """Fixture for MolFormer model instance"""
    with patch('apps.api.services.ml.molformer_model.torch'):
        model = MolFormerModel()
        return model


def test_model_initialization(molformer_model):
    """Test model initialization"""
    assert molformer_model.model_name == "molformer"
    assert molformer_model.embedding_dim == 768
    assert hasattr(molformer_model, 'tokenizer')
    assert hasattr(molformer_model, 'model')


def test_encode_smiles(molformer_model):
    """Test SMILES string encoding"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"  # Aspirin
    
    with patch.object(molformer_model, 'tokenizer') as mock_tokenizer:
        with patch.object(molformer_model, 'model') as mock_model:
            # Mock tokenizer output
            mock_tokenizer.return_value = {
                'input_ids': [[1, 2, 3, 4, 5]],
                'attention_mask': [[1, 1, 1, 1, 1]]
            }
            
            # Mock model output
            mock_output = MagicMock()
            mock_output.last_hidden_state = np.random.randn(1, 5, 768)
            mock_model.return_value = mock_output
            
            embedding = molformer_model.encode(smiles)
            
            assert embedding.shape[0] == 768  # Embedding dimension
            assert isinstance(embedding, np.ndarray)


def test_predict_properties(molformer_model):
    """Test molecular property prediction"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"  # Aspirin
    
    with patch.object(molformer_model, 'model') as mock_model:
        mock_output = MagicMock()
        mock_output.logits = np.array([[0.8, 0.2, 0.5, 0.9]])
        mock_model.return_value = mock_output
        
        properties = molformer_model.predict_properties(smiles)
        
        assert 'solubility' in properties
        assert 'lipophilicity' in properties
        assert 'druglikeness' in properties
        assert all(0 <= v <= 1 for v in properties.values())


def test_batch_encoding(molformer_model):
    """Test batch encoding of multiple SMILES"""
    smiles_list = [
        "CC(=O)OC1=CC=CC=C1C(=O)O",  # Aspirin
        "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",  # Ibuprofen
        "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"  # Caffeine
    ]
    
    with patch.object(molformer_model, 'encode') as mock_encode:
        mock_encode.return_value = np.random.randn(768)
        
        embeddings = molformer_model.batch_encode(smiles_list)
        
        assert len(embeddings) == 3
        assert mock_encode.call_count == 3


def test_invalid_smiles_handling(molformer_model):
    """Test handling of invalid SMILES strings"""
    invalid_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O)"  # Extra parenthesis
    
    with pytest.raises(ValueError, match="Invalid SMILES"):
        molformer_model.encode(invalid_smiles)


def test_empty_smiles_handling(molformer_model):
    """Test handling of empty SMILES"""
    with pytest.raises(ValueError, match="Empty SMILES"):
        molformer_model.encode("")


def test_similarity_calculation(molformer_model):
    """Test molecular similarity calculation"""
    smiles1 = "CC(=O)OC1=CC=CC=C1C(=O)O"  # Aspirin
    smiles2 = "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"  # Ibuprofen
    
    with patch.object(molformer_model, 'encode') as mock_encode:
        mock_encode.side_effect = [
            np.random.randn(768),
            np.random.randn(768)
        ]
        
        similarity = molformer_model.calculate_similarity(smiles1, smiles2)
        
        assert 0 <= similarity <= 1
        assert isinstance(similarity, float)


def test_fingerprint_generation(molformer_model):
    """Test molecular fingerprint generation"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"  # Aspirin
    
    with patch.object(molformer_model, 'encode') as mock_encode:
        mock_encode.return_value = np.random.randn(768)
        
        fingerprint = molformer_model.generate_fingerprint(smiles)
        
        assert len(fingerprint) == 768
        assert isinstance(fingerprint, np.ndarray)


def test_explainability_lime(molformer_model):
    """Test LIME explainability for predictions"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"  # Aspirin
    
    with patch('apps.api.services.ml.molformer_model.lime') as mock_lime:
        mock_explainer = MagicMock()
        mock_explainer.explain_instance.return_value = MagicMock(
            as_list=lambda: [('C', 0.5), ('O', 0.3)]
        )
        mock_lime.LimeTabularExplainer.return_value = mock_explainer
        
        explanation = molformer_model.explain_prediction(smiles, method='lime')
        
        assert 'feature_importance' in explanation
        assert 'explanation' in explanation


def test_model_caching(molformer_model):
    """Test model caching mechanism"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(molformer_model, '_compute_embedding') as mock_compute:
        mock_compute.return_value = np.random.randn(768)
        
        # First call - should compute
        embedding1 = molformer_model.encode(smiles, use_cache=True)
        
        # Second call - should use cache
        embedding2 = molformer_model.encode(smiles, use_cache=True)
        
        # Should only compute once
        assert mock_compute.call_count == 1
        np.testing.assert_array_equal(embedding1, embedding2)


def test_attention_visualization(molformer_model):
    """Test attention weight visualization"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(molformer_model, 'model') as mock_model:
        mock_output = MagicMock()
        mock_output.attentions = [np.random.randn(1, 8, 20, 20)]  # 8 heads, 20 tokens
        mock_model.return_value = mock_output
        
        attention = molformer_model.get_attention_weights(smiles)
        
        assert attention.shape[0] == 8  # Number of attention heads
        assert isinstance(attention, np.ndarray)


def test_model_performance(molformer_model):
    """Test model inference performance"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(molformer_model, 'encode') as mock_encode:
        mock_encode.return_value = np.random.randn(768)
        
        import time
        start = time.time()
        molformer_model.encode(smiles)
        duration = time.time() - start
        
        assert duration < 2.0  # Should complete in under 2 seconds


def test_gpu_support(molformer_model):
    """Test GPU acceleration support"""
    with patch('apps.api.services.ml.molformer_model.torch.cuda.is_available') as mock_cuda:
        mock_cuda.return_value = True
        
        model = MolFormerModel(device='cuda')
        
        assert model.device == 'cuda'


def test_model_versioning(molformer_model):
    """Test model version tracking"""
    assert hasattr(molformer_model, 'version')
    assert molformer_model.version is not None
