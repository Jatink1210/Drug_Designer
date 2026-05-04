"""
Unit tests for Retrosynthesis Prediction Model
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from apps.api.services.ml.retrosynthesis_model import RetrosynthesisModel


@pytest.fixture
def retrosynthesis_model():
    """Fixture for retrosynthesis model instance"""
    with patch('apps.api.services.ml.retrosynthesis_model.torch'):
        model = RetrosynthesisModel()
        return model


def test_model_initialization(retrosynthesis_model):
    """Test model initialization"""
    assert retrosynthesis_model.model_name == "retrosynthesis"
    assert hasattr(retrosynthesis_model, 'model')
    assert hasattr(retrosynthesis_model, 'reaction_templates')


def test_predict_single_step(retrosynthesis_model):
    """Test single-step retrosynthesis prediction"""
    target_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"  # Aspirin
    
    with patch.object(retrosynthesis_model, 'model') as mock_model:
        mock_output = {
            'precursors': [
                {
                    'smiles': ['OC1=CC=CC=C1C(=O)O', 'CC(=O)Cl'],
                    'reaction_type': 'acylation',
                    'confidence': 0.92,
                    'rank': 1
                },
                {
                    'smiles': ['OC1=CC=CC=C1C(=O)O', 'CC(=O)OC(=O)C'],
                    'reaction_type': 'acylation',
                    'confidence': 0.85,
                    'rank': 2
                }
            ]
        }
        mock_model.return_value = mock_output
        
        result = retrosynthesis_model.predict_single_step(target_smiles)
        
        assert 'precursors' in result
        assert len(result['precursors']) == 2
        assert result['precursors'][0]['confidence'] > 0.9


def test_predict_multi_step(retrosynthesis_model):
    """Test multi-step retrosynthesis prediction"""
    target_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(retrosynthesis_model, 'model') as mock_model:
        mock_output = {
            'routes': [
                {
                    'steps': [
                        {'target': 'CC(=O)OC1=CC=CC=C1C(=O)O', 'precursors': ['OC1=CC=CC=C1C(=O)O', 'CC(=O)Cl']},
                        {'target': 'OC1=CC=CC=C1C(=O)O', 'precursors': ['OC1=CC=CCC1', 'CO2']}
                    ],
                    'total_steps': 2,
                    'confidence': 0.88,
                    'rank': 1
                }
            ]
        }
        mock_model.return_value = mock_output
        
        result = retrosynthesis_model.predict_multi_step(target_smiles, max_steps=3)
        
        assert 'routes' in result
        assert len(result['routes']) >= 1
        assert result['routes'][0]['total_steps'] <= 3


def test_reaction_template_matching(retrosynthesis_model):
    """Test reaction template matching"""
    target_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(retrosynthesis_model, 'match_templates') as mock_match:
        mock_match.return_value = {
            'matched_templates': [
                {'template_id': 'T001', 'reaction_type': 'acylation', 'confidence': 0.95},
                {'template_id': 'T042', 'reaction_type': 'esterification', 'confidence': 0.82}
            ]
        }
        
        templates = retrosynthesis_model.match_templates(target_smiles)
        
        assert 'matched_templates' in templates
        assert len(templates['matched_templates']) >= 1


def test_route_scoring(retrosynthesis_model):
    """Test synthetic route scoring"""
    route = {
        'steps': [
            {'target': 'CC(=O)OC1=CC=CC=C1C(=O)O', 'precursors': ['OC1=CC=CC=C1C(=O)O', 'CC(=O)Cl']},
            {'target': 'OC1=CC=CC=C1C(=O)O', 'precursors': ['OC1=CC=CCC1', 'CO2']}
        ]
    }
    
    with patch.object(retrosynthesis_model, 'score_route') as mock_score:
        mock_score.return_value = {
            'overall_score': 0.85,
            'complexity_score': 0.78,
            'feasibility_score': 0.92,
            'cost_estimate': 'low'
        }
        
        score = retrosynthesis_model.score_route(route)
        
        assert 'overall_score' in score
        assert 0 <= score['overall_score'] <= 1
        assert score['cost_estimate'] in ['low', 'medium', 'high']


def test_starting_material_availability(retrosynthesis_model):
    """Test starting material availability check"""
    smiles = "OC1=CC=CC=C1C(=O)O"  # Salicylic acid
    
    with patch.object(retrosynthesis_model, 'check_availability') as mock_check:
        mock_check.return_value = {
            'available': True,
            'commercial_sources': ['Sigma-Aldrich', 'TCI', 'Alfa Aesar'],
            'price_range': '$10-50/g',
            'cas_number': '69-72-7'
        }
        
        availability = retrosynthesis_model.check_availability(smiles)
        
        assert availability['available'] is True
        assert len(availability['commercial_sources']) > 0


def test_route_optimization(retrosynthesis_model):
    """Test synthetic route optimization"""
    routes = [
        {'steps': [{'target': 'A', 'precursors': ['B', 'C']}], 'confidence': 0.85},
        {'steps': [{'target': 'A', 'precursors': ['D', 'E']}], 'confidence': 0.90}
    ]
    
    with patch.object(retrosynthesis_model, 'optimize_routes') as mock_optimize:
        mock_optimize.return_value = {
            'optimized_routes': [routes[1], routes[0]],  # Sorted by confidence
            'best_route': routes[1]
        }
        
        optimized = retrosynthesis_model.optimize_routes(routes)
        
        assert 'best_route' in optimized
        assert optimized['best_route']['confidence'] >= 0.90


def test_batch_prediction(retrosynthesis_model):
    """Test batch retrosynthesis prediction"""
    target_smiles_list = [
        "CC(=O)OC1=CC=CC=C1C(=O)O",
        "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
        "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"
    ]
    
    with patch.object(retrosynthesis_model, 'predict_single_step') as mock_predict:
        mock_predict.return_value = {'precursors': []}
        
        results = retrosynthesis_model.batch_predict(target_smiles_list)
        
        assert len(results) == 3
        assert mock_predict.call_count == 3


def test_reaction_condition_prediction(retrosynthesis_model):
    """Test reaction condition prediction"""
    reaction = {
        'reactants': ['OC1=CC=CC=C1C(=O)O', 'CC(=O)Cl'],
        'product': 'CC(=O)OC1=CC=CC=C1C(=O)O',
        'reaction_type': 'acylation'
    }
    
    with patch.object(retrosynthesis_model, 'predict_conditions') as mock_conditions:
        mock_conditions.return_value = {
            'solvent': 'pyridine',
            'temperature': 25,  # °C
            'catalyst': None,
            'time': 2.0,  # hours
            'yield_estimate': 0.85
        }
        
        conditions = retrosynthesis_model.predict_conditions(reaction)
        
        assert 'solvent' in conditions
        assert 'temperature' in conditions
        assert 0 <= conditions['yield_estimate'] <= 1


def test_invalid_smiles_handling(retrosynthesis_model):
    """Test handling of invalid SMILES"""
    invalid_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O)"
    
    with pytest.raises(ValueError, match="Invalid SMILES"):
        retrosynthesis_model.predict_single_step(invalid_smiles)


def test_convergent_synthesis(retrosynthesis_model):
    """Test convergent synthesis route generation"""
    target_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(retrosynthesis_model, 'generate_convergent_route') as mock_convergent:
        mock_convergent.return_value = {
            'route_type': 'convergent',
            'branches': 2,
            'longest_linear_sequence': 3,
            'total_steps': 5
        }
        
        route = retrosynthesis_model.generate_convergent_route(target_smiles)
        
        assert route['route_type'] == 'convergent'
        assert route['branches'] >= 2


def test_green_chemistry_score(retrosynthesis_model):
    """Test green chemistry scoring"""
    route = {
        'steps': [
            {'target': 'CC(=O)OC1=CC=CC=C1C(=O)O', 'precursors': ['OC1=CC=CC=C1C(=O)O', 'CC(=O)Cl']}
        ]
    }
    
    with patch.object(retrosynthesis_model, 'calculate_green_score') as mock_green:
        mock_green.return_value = {
            'green_score': 0.72,
            'atom_economy': 0.85,
            'e_factor': 2.5,
            'hazard_score': 0.65
        }
        
        green_score = retrosynthesis_model.calculate_green_score(route)
        
        assert 'green_score' in green_score
        assert 0 <= green_score['green_score'] <= 1


def test_confidence_calibration(retrosynthesis_model):
    """Test confidence score calibration"""
    predictions = [
        {'precursors': ['A', 'B'], 'confidence': 0.95},
        {'precursors': ['C', 'D'], 'confidence': 0.88}
    ]
    
    with patch.object(retrosynthesis_model, 'calibrate_confidence') as mock_calibrate:
        mock_calibrate.return_value = [
            {'precursors': ['A', 'B'], 'confidence': 0.92, 'calibrated': True},
            {'precursors': ['C', 'D'], 'confidence': 0.85, 'calibrated': True}
        ]
        
        calibrated = retrosynthesis_model.calibrate_confidence(predictions)
        
        assert all(p['calibrated'] for p in calibrated)


def test_model_performance(retrosynthesis_model):
    """Test model inference performance"""
    target_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    with patch.object(retrosynthesis_model, 'predict_single_step') as mock_predict:
        mock_predict.return_value = {'precursors': []}
        
        import time
        start = time.time()
        retrosynthesis_model.predict_single_step(target_smiles)
        duration = time.time() - start
        
        assert duration < 5.0  # Should complete in under 5 seconds


def test_model_versioning(retrosynthesis_model):
    """Test model version tracking"""
    assert hasattr(retrosynthesis_model, 'version')
    assert retrosynthesis_model.version is not None
