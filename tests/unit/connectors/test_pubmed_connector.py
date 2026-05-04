"""
Unit tests for PubMed Connector

Tests PubMed-specific functionality including:
- Literature search
- Article retrieval
- Citation parsing
- Author extraction
- Abstract processing
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

import sys
sys.path.insert(0, 'apps/api')
from connectors.pubmed import PubMedConnector


class TestPubMedConnector:
    """Test suite for PubMed connector"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.connector = PubMedConnector()
    
    def test_initialization(self):
        """Test PubMed connector initialization"""
        assert self.connector.name == "pubmed"
        assert "ncbi.nlm.nih.gov" in self.connector.base_url
        assert self.connector.rate_limit > 0
    
    @patch('requests.get')
    def test_search_articles(self, mock_get):
        """Test searching for articles"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "esearchresult": {
                "idlist": ["12345678", "87654321"],
                "count": "2"
            }
        }
        mock_get.return_value = mock_response
        
        result = self.connector.search("cancer treatment")
        
        assert "idlist" in result["esearchresult"]
        assert len(result["esearchresult"]["idlist"]) == 2
    
    @patch('requests.get')
    def test_fetch_article_details(self, mock_get):
        """Test fetching article details by PMID"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "12345678": {
                    "title": "Test Article",
                    "authors": [
                        {"name": "Smith J"},
                        {"name": "Doe J"}
                    ],
                    "pubdate": "2024",
                    "abstract": "This is a test abstract."
                }
            }
        }
        mock_get.return_value = mock_response
        
        result = self.connector.fetch_article("12345678")
        
        assert result["title"] == "Test Article"
        assert len(result["authors"]) == 2
        assert result["pubdate"] == "2024"
    
    @patch('requests.get')
    def test_search_with_filters(self, mock_get):
        """Test search with date and type filters"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "esearchresult": {
                "idlist": ["12345678"],
                "count": "1"
            }
        }
        mock_get.return_value = mock_response
        
        result = self.connector.search(
            "cancer",
            mindate="2020/01/01",
            maxdate="2024/12/31",
            article_type="Clinical Trial"
        )
        
        assert len(result["esearchresult"]["idlist"]) == 1
        # Verify filters were applied in request
        call_args = mock_get.call_args
        assert "mindate" in str(call_args) or "2020" in str(call_args)
    
    @patch('requests.get')
    def test_parse_authors(self, mock_get):
        """Test author name parsing"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "12345678": {
                    "authors": [
                        {"name": "Smith J", "authtype": "Author"},
                        {"name": "Doe J", "authtype": "Author"},
                        {"name": "Johnson M", "authtype": "Author"}
                    ]
                }
            }
        }
        mock_get.return_value = mock_response
        
        result = self.connector.fetch_article("12345678")
        authors = result["authors"]
        
        assert len(authors) == 3
        assert all("name" in author for author in authors)
    
    @patch('requests.get')
    def test_extract_mesh_terms(self, mock_get):
        """Test MeSH term extraction"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "12345678": {
                    "meshheadings": [
                        {"descriptor": "Neoplasms"},
                        {"descriptor": "Drug Therapy"},
                        {"descriptor": "Clinical Trials"}
                    ]
                }
            }
        }
        mock_get.return_value = mock_response
        
        result = self.connector.fetch_article("12345678")
        mesh_terms = result.get("meshheadings", [])
        
        assert len(mesh_terms) == 3
        assert any("Neoplasms" in str(term) for term in mesh_terms)
    
    @patch('requests.get')
    def test_handle_no_results(self, mock_get):
        """Test handling of empty search results"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "esearchresult": {
                "idlist": [],
                "count": "0"
            }
        }
        mock_get.return_value = mock_response
        
        result = self.connector.search("nonexistent query xyz123")
        
        assert len(result["esearchresult"]["idlist"]) == 0
        assert result["esearchresult"]["count"] == "0"
    
    @patch('requests.get')
    def test_rate_limit_compliance(self, mock_get):
        """Test that connector respects NCBI rate limits"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "esearchresult": {"idlist": ["12345678"], "count": "1"}
        }
        mock_get.return_value = mock_response
        
        import time
        start_time = time.time()
        
        # Make multiple requests
        for i in range(5):
            self.connector.search(f"query{i}")
        
        elapsed_time = time.time() - start_time
        
        # Should take some time due to rate limiting
        # NCBI allows 3 requests per second without API key
        assert elapsed_time >= 1.0
    
    @patch('requests.get')
    def test_citation_format(self, mock_get):
        """Test citation formatting"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "12345678": {
                    "title": "Test Article",
                    "authors": [{"name": "Smith J"}],
                    "pubdate": "2024",
                    "source": "Nature",
                    "volume": "123",
                    "pages": "45-50"
                }
            }
        }
        mock_get.return_value = mock_response
        
        result = self.connector.fetch_article("12345678")
        
        # Verify all citation components are present
        assert "title" in result
        assert "authors" in result
        assert "pubdate" in result
        assert "source" in result
    
    @patch('requests.get')
    def test_abstract_truncation(self, mock_get):
        """Test handling of long abstracts"""
        long_abstract = "A" * 10000  # Very long abstract
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "12345678": {
                    "title": "Test Article",
                    "abstract": long_abstract
                }
            }
        }
        mock_get.return_value = mock_response
        
        result = self.connector.fetch_article("12345678")
        
        # Abstract should be present
        assert "abstract" in result
        assert len(result["abstract"]) > 0
    
    @patch('requests.get')
    def test_error_handling_invalid_pmid(self, mock_get):
        """Test error handling for invalid PMID"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid PMID"
        mock_get.return_value = mock_response
        
        with pytest.raises(Exception):
            self.connector.fetch_article("invalid_pmid")
    
    @patch('requests.get')
    def test_batch_fetch(self, mock_get):
        """Test fetching multiple articles at once"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "12345678": {"title": "Article 1"},
                "87654321": {"title": "Article 2"}
            }
        }
        mock_get.return_value = mock_response
        
        result = self.connector.fetch_articles(["12345678", "87654321"])
        
        assert len(result["result"]) == 2
        assert "12345678" in result["result"]
        assert "87654321" in result["result"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
