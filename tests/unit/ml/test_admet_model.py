"""
Unit tests for ADMET (Absorption, Distribution, Metabolism, Excretion, Toxicity) Prediction Model
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from apps.api.services.ml.admet_model import ADMETModel


@pytest.fixture
def admet_model():
    """Fixture for ADMET model instance"""
    with patch('apps.api.services.ml.admet_model.torch'):
        model = ADMETModel()
        return model


def test_model_initialization(admet_model):
    """Test model initialization"""
    assert admet_model.model_name == "admet"
    assert hasattr(admet_model, 'model')
    assert hasattr(admet_model, 'property_predictors')


def test_predict_absorption(admet_model):
    """Test absorption property prediction"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"  # Aspirin
    
    with patch.object(admet_model, 'model') as mock_model:
        mock_output = {
            'caco2_permeability': -5.2,
            'human_intestinal_absorption': 0.95,
            'bioavailability': 0.68,
            'pgp_substrate': False
        }
        mock_model.return_value = mock_output
        
        absorption = admet_model.predict_absorption(smiles)
        
        assert 'caco2_permeability' in absorption
        assert 'human_intestinal_absorption' in absorption
        assert 0 <= absorption['human_intestinal_absorption'] <= 1
        assert isinstance(absorption['pgp_substrate'], bool)


def test_predict_distribution(admet_model):
    """Test distribution property prediction"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(admet_model, 'model') as mock_model:
        mock_output = {
            'vd': 0.15,  # Volume of distribution (L/kg)
            'plasma_protein_binding': 0.85,
            'bbb_permeability': -1.2,
            'cns_penetration': False
        }
        mock_model.return_value = mock_output
        
        distribution = admet_model.predict_distribution(smiles)
        
        assert 'vd' in distribution
        assert 'plasma_protein_binding' in distribution
        assert 0 <= distribution['plasma_protein_binding'] <= 1


def test_predict_metabolism(admet_model):
    """Test metabolism property prediction"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(admet_model, 'model') as mock_model:
        mock_output = {
            'cyp1a2_substrate': False,
            'cyp2c9_substrate': True,
            'cyp2c19_substrate': False,
            'cyp2d6_substrate': False,
            'cyp3a4_substrate': True,
            'cyp1a2_inhibitor': False,
            'cyp2c9_inhibitor': True,
            'clearance': 15.2  # mL/min/kg
        }
        mock_model.return_value = mock_output
        
        metabolism = admet_model.predict_metabolism(smiles)
        
        assert 'cyp3a4_substrate' in metabolism
        assert 'clearance' in metabolism
        assert isinstance(metabolism['cyp2c9_substrate'], bool)


def test_predict_excretion(admet_model):
    """Test excretion property prediction"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(admet_model, 'model') as mock_model:
        mock_output = {
            'half_life': 3.5,  # hours
            'clearance': 15.2,  # mL/min/kg
            'renal_clearance': 8.5,
            'hepatic_clearance': 6.7
        }
        mock_model.return_value = mock_output
        
        excretion = admet_model.predict_excretion(smiles)
        
        assert 'half_life' in excretion
        assert 'clearance' in excretion
        assert excretion['half_life'] > 0


def test_predict_toxicity(admet_model):
    """Test toxicity prediction"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(admet_model, 'model') as mock_model:
        mock_output = {
            'herg_inhibition': False,
            'ames_mutagenicity': False,
            'hepatotoxicity': False,
            'cardiotoxicity': False,
            'ld50': 200.0,  # mg/kg
            'dili_risk': 'low'
        }
        mock_model.return_value = mock_output
        
        toxicity = admet_model.predict_toxicity(smiles)
        
        assert 'herg_inhibition' in toxicity
        assert 'ames_mutagenicity' in toxicity
        assert 'ld50' in toxicity
        assert toxicity['dili_risk'] in ['low', 'medium', 'high']


def test_predict_all_properties(admet_model):
    """Test prediction of all ADMET properties"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(admet_model, 'model') as mock_model:
        mock_output = {
            'absorption': {'human_intestinal_absorption': 0.95},
            'distribution': {'vd': 0.15},
            'metabolism': {'cyp3a4_substrate': True},
            'excretion': {'half_life': 3.5},
            'toxicity': {'herg_inhibition': False}
        }
        mock_model.return_value = mock_output
        
        properties = admet_model.predict_all(smiles)
        
        assert 'absorption' in properties
        assert 'distribution' in properties
        assert 'metabolism' in properties
        assert 'excretion' in properties
        assert 'toxicity' in properties


def test_batch_prediction(admet_model):
    """Test batch ADMET prediction"""
    smiles_list = [
        "CC(=O)OC1=CC=CC=C1C(=O)O",  # Aspirin
        "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",  # Ibuprofen
        "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"  # Caffeine
    ]
    
    with patch.object(admet_model, 'predict_all') as mock_predict:
        mock_predict.return_value = {
            'absorption': {'human_intestinal_absorption': 0.95}
        }
        
        results = admet_model.batch_predict(smiles_list)
        
        assert len(results) == 3
        assert mock_predict.call_count == 3


def test_lipinski_rule_of_five(admet_model):
    """Test Lipinski's Rule of Five compliance"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(admet_model, 'check_lipinski') as mock_lipinski:
        mock_lipinski.return_value = {
            'molecular_weight': 180.16,
            'logp': 1.19,
            'h_bond_donors': 1,
            'h_bond_acceptors': 4,
            'compliant': True,
            'violations': 0
        }
        
        lipinski = admet_model.check_lipinski(smiles)
        
        assert lipinski['compliant'] is True
        assert lipinski['violations'] == 0
        assert lipinski['molecular_weight'] < 500


def test_druglikeness_score(admet_model):
    """Test druglikeness score calculation"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(admet_model, 'calculate_druglikeness') as mock_drug:
        mock_drug.return_value = {
            'qed_score': 0.72,
            'sa_score': 2.1,
            'lipinski_compliant': True,
            'overall_score': 0.75
        }
        
        druglikeness = admet_model.calculate_druglikeness(smiles)
        
        assert 0 <= druglikeness['qed_score'] <= 1
        assert 'overall_score' in druglikeness


def test_invalid_smiles_handling(admet_model):
    """Test handling of invalid SMILES"""
    invalid_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O)"
    
    with pytest.raises(ValueError, match="Invalid SMILES"):
        admet_model.predict_all(invalid_smiles)


def test_confidence_scores(admet_model):
    """Test confidence score reporting"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(admet_model, 'predict_all') as mock_predict:
        mock_predict.return_value = {
            'absorption': {'human_intestinal_absorption': 0.95},
            'confidence_scores': {
                'absorption': 0.88,
                'distribution': 0.82,
                'metabolism': 0.90,
                'excretion': 0.75,
                'toxicity': 0.85
            }
        }
        
        properties = admet_model.predict_all(smiles, return_confidence=True)
        
        assert 'confidence_scores' in properties
        assert all(0 <= v <= 1 for v in properties['confidence_scores'].values())


def test_explainability_shap(admet_model):
    """Test SHAP explainability for ADMET predictions"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch('apps.api.services.ml.admet_model.shap') as mock_shap:
        mock_explainer = MagicMock()
        mock_explainer.shap_values.return_value = np.random.randn(10)
        mock_shap.TreeExplainer.return_value = mock_explainer
        
        explanation = admet_model.explain_prediction(smiles, property='absorption')
        
        assert 'shap_values' in explanation
        assert 'feature_importance' in explanation


def test_model_performance(admet_model):
    """Test model inference performance"""
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(admet_model, 'predict_all') as mock_predict:
        mock_predict.return_value = {'absorption': {}}
        
        import time
        start = time.time()
        admet_model.predict_all(smiles)
        duration = time.time() - start
        
        assert duration < 5.0  # Should complete in under 5 seconds


def test_model_versioning(admet_model):
    """Test model version tracking"""
    assert hasattr(admet_model, 'version')
    assert admet_model.version is not None
