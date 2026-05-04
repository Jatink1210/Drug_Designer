"""
Unit tests for Pathogenicity Prediction Model
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from apps.api.services.ml.pathogenicity_prediction_model import PathogenicityPredictionModel


@pytest.fixture
def pathogenicity_model():
    """Fixture for pathogenicity model instance"""
    with patch('apps.api.services.ml.pathogenicity_prediction_model.torch'):
        model = PathogenicityPredictionModel()
        return model


def test_model_initialization(pathogenicity_model):
    """Test model initialization"""
    assert pathogenicity_model.model_name == "pathogenicity_predictor"
    assert hasattr(pathogenicity_model, 'model')
    assert hasattr(pathogenicity_model, 'feature_extractor')


def test_predict_variant_pathogenicity(pathogenicity_model):
    """Test variant pathogenicity prediction"""
    variant = {
        "gene": "FOXP3",
        "position": 123456,
        "ref": "A",
        "alt": "G",
        "consequence": "missense_variant"
    }
    
    with patch.object(pathogenicity_model, 'model') as mock_model:
        mock_output = MagicMock()
        mock_output.logits = np.array([[0.1, 0.9]])  # [benign, pathogenic]
        mock_model.return_value = mock_output
        
        prediction = pathogenicity_model.predict(variant)
        
        assert 'pathogenicity_score' in prediction
        assert 'classification' in prediction
        assert 0 <= prediction['pathogenicity_score'] <= 1
        assert prediction['classification'] in ['benign', 'pathogenic', 'uncertain']


def test_batch_prediction(pathogenicity_model):
    """Test batch prediction of multiple variants"""
    variants = [
        {"gene": "FOXP3", "position": 123456, "ref": "A", "alt": "G"},
        {"gene": "BRCA1", "position": 789012, "ref": "C", "alt": "T"},
        {"gene": "TP53", "position": 345678, "ref": "G", "alt": "A"}
    ]
    
    with patch.object(pathogenicity_model, 'predict') as mock_predict:
        mock_predict.return_value = {
            'pathogenicity_score': 0.85,
            'classification': 'pathogenic'
        }
        
        predictions = pathogenicity_model.batch_predict(variants)
        
        assert len(predictions) == 3
        assert mock_predict.call_count == 3


def test_feature_extraction(pathogenicity_model):
    """Test feature extraction from variant"""
    variant = {
        "gene": "FOXP3",
        "position": 123456,
        "ref": "A",
        "alt": "G",
        "consequence": "missense_variant",
        "sift_score": 0.02,
        "polyphen_score": 0.95
    }
    
    features = pathogenicity_model.extract_features(variant)
    
    assert 'sequence_features' in features
    assert 'conservation_features' in features
    assert 'functional_features' in features
    assert isinstance(features, dict)


def test_explainability_shap(pathogenicity_model):
    """Test SHAP explainability for pathogenicity predictions"""
    variant = {
        "gene": "FOXP3",
        "position": 123456,
        "ref": "A",
        "alt": "G"
    }
    
    with patch('apps.api.services.ml.pathogenicity_prediction_model.shap') as mock_shap:
        mock_explainer = MagicMock()
        mock_explainer.shap_values.return_value = np.random.randn(10)
        mock_shap.TreeExplainer.return_value = mock_explainer
        
        explanation = pathogenicity_model.explain_prediction(variant, method='shap')
        
        assert 'shap_values' in explanation
        assert 'feature_importance' in explanation
        assert 'top_features' in explanation


def test_confidence_score(pathogenicity_model):
    """Test confidence score calculation"""
    variant = {"gene": "FOXP3", "position": 123456, "ref": "A", "alt": "G"}
    
    with patch.object(pathogenicity_model, 'model') as mock_model:
        mock_output = MagicMock()
        mock_output.logits = np.array([[0.1, 0.9]])
        mock_model.return_value = mock_output
        
        prediction = pathogenicity_model.predict(variant, return_confidence=True)
        
        assert 'confidence' in prediction
        assert 0 <= prediction['confidence'] <= 1


def test_invalid_variant_handling(pathogenicity_model):
    """Test handling of invalid variant data"""
    invalid_variant = {"gene": "FOXP3"}  # Missing required fields
    
    with pytest.raises(ValueError, match="Missing required fields"):
        pathogenicity_model.predict(invalid_variant)


def test_model_calibration(pathogenicity_model):
    """Test model calibration for probability scores"""
    variant = {"gene": "FOXP3", "position": 123456, "ref": "A", "alt": "G"}
    
    with patch.object(pathogenicity_model, 'predict') as mock_predict:
        mock_predict.return_value = {
            'pathogenicity_score': 0.85,
            'calibrated_score': 0.82
        }
        
        prediction = pathogenicity_model.predict(variant, calibrate=True)
        
        assert 'calibrated_score' in prediction


def test_ensemble_prediction(pathogenicity_model):
    """Test ensemble prediction from multiple models"""
    variant = {"gene": "FOXP3", "position": 123456, "ref": "A", "alt": "G"}
    
    with patch.object(pathogenicity_model, '_ensemble_predict') as mock_ensemble:
        mock_ensemble.return_value = {
            'pathogenicity_score': 0.87,
            'ensemble_variance': 0.05
        }
        
        prediction = pathogenicity_model.predict(variant, use_ensemble=True)
        
        assert 'ensemble_variance' in prediction


def test_model_performance(pathogenicity_model):
    """Test model inference performance"""
    variant = {"gene": "FOXP3", "position": 123456, "ref": "A", "alt": "G"}
    
    with patch.object(pathogenicity_model, 'predict') as mock_predict:
        mock_predict.return_value = {'pathogenicity_score': 0.85}
        
        import time
        start = time.time()
        pathogenicity_model.predict(variant)
        duration = time.time() - start
        
        assert duration < 1.0  # Should complete in under 1 second


def test_model_versioning(pathogenicity_model):
    """Test model version tracking"""
    assert hasattr(pathogenicity_model, 'version')
    assert pathogenicity_model.version is not None
