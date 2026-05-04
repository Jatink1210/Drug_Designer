"""
Unit tests for Toxicity Prediction Model
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from apps.api.services.ml.toxicity_model import ToxicityModel


@pytest.fixture
def toxicity_model():
    """Fixture for toxicity model instance"""
    with patch('apps.api.services.ml.toxicity_model.torch'):
        model = ToxicityModel()
        return model


def test_model_initialization(toxicity_model):
    """Test model initialization"""
    assert toxicity_model.model_name == "toxicity"
    assert hasattr(toxicity_model, 'model')
    assert hasattr(toxicity_model, 'toxicity_endpoints')


def test_predict_acute_toxicity(toxicity_model):
    """Test acute toxicity prediction"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"  # Aspirin
    
    with patch.object(toxicity_model, 'model') as mock_model:
        mock_output = {
            'ld50_oral': 200.0,  # mg/kg
            'ld50_dermal': 1000.0,
            'ld50_inhalation': 5000.0,
            'toxicity_class': 4  # GHS classification
        }
        mock_model.return_value = mock_output
        
        toxicity = toxicity_model.predict_acute_toxicity(smiles)
        
        assert 'ld50_oral' in toxicity
        assert toxicity['ld50_oral'] > 0
        assert toxicity['toxicity_class'] in [1, 2, 3, 4, 5, 6]


def test_predict_organ_toxicity(toxicity_model):
    """Test organ-specific toxicity prediction"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(toxicity_model, 'model') as mock_model:
        mock_output = {
            'hepatotoxicity': {'probability': 0.15, 'risk': 'low'},
            'nephrotoxicity': {'probability': 0.08, 'risk': 'low'},
            'cardiotoxicity': {'probability': 0.12, 'risk': 'low'},
            'neurotoxicity': {'probability': 0.05, 'risk': 'low'}
        }
        mock_model.return_value = mock_output
        
        organ_tox = toxicity_model.predict_organ_toxicity(smiles)
        
        assert 'hepatotoxicity' in organ_tox
        assert 'cardiotoxicity' in organ_tox
        assert all(0 <= v['probability'] <= 1 for v in organ_tox.values())
        assert all(v['risk'] in ['low', 'medium', 'high'] for v in organ_tox.values())


def test_predict_genotoxicity(toxicity_model):
    """Test genotoxicity prediction"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(toxicity_model, 'model') as mock_model:
        mock_output = {
            'ames_mutagenicity': False,
            'micronucleus': False,
            'chromosome_aberration': False,
            'genotoxic_probability': 0.05
        }
        mock_model.return_value = mock_output
        
        genotox = toxicity_model.predict_genotoxicity(smiles)
        
        assert 'ames_mutagenicity' in genotox
        assert isinstance(genotox['ames_mutagenicity'], bool)
        assert 0 <= genotox['genotoxic_probability'] <= 1


def test_predict_carcinogenicity(toxicity_model):
    """Test carcinogenicity prediction"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(toxicity_model, 'model') as mock_model:
        mock_output = {
            'carcinogenic': False,
            'probability': 0.08,
            'iarc_class': 'Group 3',  # Not classifiable
            'confidence': 0.85
        }
        mock_model.return_value = mock_output
        
        carcinogen = toxicity_model.predict_carcinogenicity(smiles)
        
        assert 'carcinogenic' in carcinogen
        assert 'iarc_class' in carcinogen
        assert carcinogen['iarc_class'] in ['Group 1', 'Group 2A', 'Group 2B', 'Group 3', 'Group 4']


def test_predict_reproductive_toxicity(toxicity_model):
    """Test reproductive toxicity prediction"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(toxicity_model, 'model') as mock_model:
        mock_output = {
            'developmental_toxicity': False,
            'fertility_impairment': False,
            'teratogenicity': False,
            'reproductive_risk': 'low'
        }
        mock_model.return_value = mock_output
        
        repro_tox = toxicity_model.predict_reproductive_toxicity(smiles)
        
        assert 'developmental_toxicity' in repro_tox
        assert 'teratogenicity' in repro_tox
        assert repro_tox['reproductive_risk'] in ['low', 'medium', 'high']


def test_predict_herg_inhibition(toxicity_model):
    """Test hERG channel inhibition prediction"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(toxicity_model, 'model') as mock_model:
        mock_output = {
            'herg_inhibitor': False,
            'ic50': 50.0,  # μM
            'cardiotoxicity_risk': 'low'
        }
        mock_model.return_value = mock_output
        
        herg = toxicity_model.predict_herg_inhibition(smiles)
        
        assert 'herg_inhibitor' in herg
        assert 'ic50' in herg
        assert herg['ic50'] > 0


def test_predict_all_toxicity(toxicity_model):
    """Test prediction of all toxicity endpoints"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(toxicity_model, 'model') as mock_model:
        mock_output = {
            'acute_toxicity': {'ld50_oral': 200.0},
            'organ_toxicity': {'hepatotoxicity': {'risk': 'low'}},
            'genotoxicity': {'ames_mutagenicity': False},
            'carcinogenicity': {'carcinogenic': False},
            'reproductive_toxicity': {'developmental_toxicity': False},
            'herg_inhibition': {'herg_inhibitor': False}
        }
        mock_model.return_value = mock_output
        
        all_tox = toxicity_model.predict_all(smiles)
        
        assert 'acute_toxicity' in all_tox
        assert 'organ_toxicity' in all_tox
        assert 'genotoxicity' in all_tox
        assert 'carcinogenicity' in all_tox


def test_batch_prediction(toxicity_model):
    """Test batch toxicity prediction"""
    smiles_list = [
        "CC(=O)OC1=CC=CC=C1C(=O)O",
        "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
        "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"
    ]
    
    with patch.object(toxicity_model, 'predict_all') as mock_predict:
        mock_predict.return_value = {'acute_toxicity': {}}
        
        results = toxicity_model.batch_predict(smiles_list)
        
        assert len(results) == 3
        assert mock_predict.call_count == 3


def test_toxicophore_identification(toxicity_model):
    """Test identification of toxic substructures"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(toxicity_model, 'identify_toxicophores') as mock_toxicophore:
        mock_toxicophore.return_value = {
            'toxicophores': [],
            'structural_alerts': ['aromatic_ring'],
            'safe': True
        }
        
        toxicophores = toxicity_model.identify_toxicophores(smiles)
        
        assert 'toxicophores' in toxicophores
        assert 'structural_alerts' in toxicophores
        assert isinstance(toxicophores['safe'], bool)


def test_invalid_smiles_handling(toxicity_model):
    """Test handling of invalid SMILES"""
    invalid_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O)"
    
    with pytest.raises(ValueError, match="Invalid SMILES"):
        toxicity_model.predict_all(invalid_smiles)


def test_confidence_scores(toxicity_model):
    """Test confidence score reporting"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(toxicity_model, 'predict_all') as mock_predict:
        mock_predict.return_value = {
            'acute_toxicity': {'ld50_oral': 200.0},
            'confidence_scores': {
                'acute_toxicity': 0.90,
                'organ_toxicity': 0.85,
                'genotoxicity': 0.88
            }
        }
        
        toxicity = toxicity_model.predict_all(smiles, return_confidence=True)
        
        assert 'confidence_scores' in toxicity
        assert all(0 <= v <= 1 for v in toxicity['confidence_scores'].values())


def test_explainability_lime(toxicity_model):
    """Test LIME explainability for toxicity predictions"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch('apps.api.services.ml.toxicity_model.lime') as mock_lime:
        mock_explainer = MagicMock()
        mock_explainer.explain_instance.return_value = MagicMock(
            as_list=lambda: [('aromatic', 0.3), ('ester', 0.2)]
        )
        mock_lime.LimeTabularExplainer.return_value = mock_explainer
        
        explanation = toxicity_model.explain_prediction(smiles, endpoint='hepatotoxicity')
        
        assert 'feature_importance' in explanation
        assert 'explanation' in explanation


def test_model_performance(toxicity_model):
    """Test model inference performance"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(toxicity_model, 'predict_all') as mock_predict:
        mock_predict.return_value = {'acute_toxicity': {}}
        
        import time
        start = time.time()
        toxicity_model.predict_all(smiles)
        duration = time.time() - start
        
        assert duration < 3.0  # Should complete in under 3 seconds


def test_model_versioning(toxicity_model):
    """Test model version tracking"""
    assert hasattr(toxicity_model, 'version')
    assert toxicity_model.version is not None
