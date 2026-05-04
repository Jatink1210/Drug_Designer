"""
Unit tests for ESM-2 (Evolutionary Scale Modeling) protein language model
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from apps.api.services.ml.esm2_model import ESM2Model


@pytest.fixture
def esm2_model():
    """Fixture for ESM2 model instance"""
    with patch('apps.api.services.ml.esm2_model.torch'):
        model = ESM2Model()
        return model


def test_model_initialization(esm2_model):
    """Test model initialization"""
    assert esm2_model.model_name == "esm2"
    assert esm2_model.embedding_dim == 1280
    assert hasattr(esm2_model, 'tokenizer')
    assert hasattr(esm2_model, 'model')


def test_encode_protein_sequence(esm2_model):
    """Test protein sequence encoding"""
    sequence = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL"
    
    with patch.object(esm2_model, 'tokenizer') as mock_tokenizer:
        with patch.object(esm2_model, 'model') as mock_model:
            # Mock tokenizer output
            mock_tokenizer.return_value = {
                'input_ids': [[1, 2, 3, 4, 5]],
                'attention_mask': [[1, 1, 1, 1, 1]]
            }
            
            # Mock model output
            mock_output = MagicMock()
            mock_output.last_hidden_state = np.random.randn(1, 5, 1280)
            mock_model.return_value = mock_output
            
            embedding = esm2_model.encode(sequence)
            
            assert embedding.shape[0] == 1280  # Embedding dimension
            assert isinstance(embedding, np.ndarray)


def test_predict_structure_features(esm2_model):
    """Test structure feature prediction"""
    sequence = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL"
    
    with patch.object(esm2_model, 'model') as mock_model:
        mock_output = MagicMock()
        mock_output.last_hidden_state = np.random.randn(1, len(sequence), 1280)
        mock_model.return_value = mock_output
        
        features = esm2_model.predict_structure_features(sequence)
        
        assert 'secondary_structure' in features
        assert 'contact_map' in features
        assert 'disorder_regions' in features


def test_batch_encoding(esm2_model):
    """Test batch encoding of multiple sequences"""
    sequences = [
        "MKTAYIAKQRQISFVK",
        "SHFSRQLEERLGLIEV",
        "QAPILSRVGDGTQDNL"
    ]
    
    with patch.object(esm2_model, 'encode') as mock_encode:
        mock_encode.return_value = np.random.randn(1280)
        
        embeddings = esm2_model.batch_encode(sequences)
        
        assert len(embeddings) == 3
        assert mock_encode.call_count == 3


def test_invalid_sequence_handling(esm2_model):
    """Test handling of invalid protein sequences"""
    invalid_sequence = "MKTAYIAKQRQISFVK123"  # Contains invalid characters
    
    with pytest.raises(ValueError, match="Invalid amino acid"):
        esm2_model.encode(invalid_sequence)


def test_empty_sequence_handling(esm2_model):
    """Test handling of empty sequences"""
    with pytest.raises(ValueError, match="Empty sequence"):
        esm2_model.encode("")


def test_model_caching(esm2_model):
    """Test model caching mechanism"""
    sequence = "MKTAYIAKQRQISFVK"
    
    with patch.object(esm2_model, '_compute_embedding') as mock_compute:
        mock_compute.return_value = np.random.randn(1280)
        
        # First call - should compute
        embedding1 = esm2_model.encode(sequence, use_cache=True)
        
        # Second call - should use cache
        embedding2 = esm2_model.encode(sequence, use_cache=True)
        
        # Should only compute once
        assert mock_compute.call_count == 1
        np.testing.assert_array_equal(embedding1, embedding2)


def test_attention_weights_extraction(esm2_model):
    """Test extraction of attention weights"""
    sequence = "MKTAYIAKQRQISFVK"
    
    with patch.object(esm2_model, 'model') as mock_model:
        mock_output = MagicMock()
        mock_output.attentions = [np.random.randn(1, 12, 16, 16)]  # 12 heads, 16 tokens
        mock_model.return_value = mock_output
        
        attention = esm2_model.get_attention_weights(sequence)
        
        assert attention.shape[0] == 12  # Number of attention heads
        assert isinstance(attention, np.ndarray)


def test_explainability_shap(esm2_model):
    """Test SHAP explainability for predictions"""
    sequence = "MKTAYIAKQRQISFVK"
    
    with patch('apps.api.services.ml.esm2_model.shap') as mock_shap:
        mock_explainer = MagicMock()
        mock_explainer.shap_values.return_value = np.random.randn(16, 1280)
        mock_shap.DeepExplainer.return_value = mock_explainer
        
        shap_values = esm2_model.explain_prediction(sequence, method='shap')
        
        assert 'shap_values' in shap_values
        assert 'feature_importance' in shap_values


def test_model_performance_metrics(esm2_model):
    """Test model performance tracking"""
    sequence = "MKTAYIAKQRQISFVK"
    
    with patch.object(esm2_model, 'encode') as mock_encode:
        mock_encode.return_value = np.random.randn(1280)
        
        # Track inference time
        import time
        start = time.time()
        esm2_model.encode(sequence)
        duration = time.time() - start
        
        assert duration < 5.0  # Should complete in under 5 seconds


def test_gpu_acceleration(esm2_model):
    """Test GPU acceleration when available"""
    with patch('apps.api.services.ml.esm2_model.torch.cuda.is_available') as mock_cuda:
        mock_cuda.return_value = True
        
        model = ESM2Model(device='cuda')
        
        assert model.device == 'cuda'


def test_model_versioning(esm2_model):
    """Test model version tracking"""
    assert hasattr(esm2_model, 'version')
    assert esm2_model.version is not None
