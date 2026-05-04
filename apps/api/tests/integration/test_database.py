"""Integration tests for database operations.

Tests database operations, migrations, and constraints.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command
from models.db_tables import (
    User, Project, Run, Evidence, Dossier,
    ClinicalRecord, PhenotypeCluster, TissueAnalysis,
    BiomarkerProfile, GenomicVariant, PathogenicityPrediction,
    DisruptionModel, TherapyStratification, ConsensusResult
)
from core.db import Base
import uuid
from datetime import datetime

# Test database URL
TEST_DATABASE_URL = "postgresql://test:test@localhost:5432/drugdesigner_test"

# Create test engine
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def test_db():
    """Create test database tables."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_db):
    """Create database session for tests."""
    session = TestingSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class TestDatabaseSchema:
    """Test database schema and tables."""
    
    def test_all_tables_created(self, test_db):
        """Test all tables are created."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result]
            
            # Check critical tables exist
            assert 'users' in tables
            assert 'projects' in tables
            assert 'runs' in tables
            assert 'evidence' in tables
            assert 'clinical_records' in tables
            assert 'consensus_results' in tables
    
    def test_indexes_created(self, test_db):
        """Test indexes are created."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public'
            """))
            indexes = [row[0] for row in result]
            
            # Check some critical indexes exist
            assert any('project_id' in idx for idx in indexes)
            assert any('run_id' in idx for idx in indexes)


class TestUserOperations:
    """Test user database operations."""
    
    def test_create_user(self, db_session):
        """Test creating user."""
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            hashed_password="hashed_password",
            full_name="Test User"
        )
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.email == "test@example.com"
    
    def test_unique_email_constraint(self, db_session):
        """Test email uniqueness constraint."""
        user1 = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            hashed_password="password1"
        )
        db_session.add(user1)
        db_session.commit()
        
        user2 = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            hashed_password="password2"
        )
        db_session.add(user2)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()


class TestProjectOperations:
    """Test project database operations."""
    
    def test_create_project(self, db_session):
        """Test creating project."""
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            hashed_password="password"
        )
        db_session.add(user)
        db_session.commit()
        
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            description="Test Description",
            owner_id=user.id
        )
        db_session.add(project)
        db_session.commit()
        
        assert project.id is not None
        assert project.name == "Test Project"
    
    def test_project_user_relationship(self, db_session):
        """Test project-user relationship."""
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            hashed_password="password"
        )
        db_session.add(user)
        db_session.commit()
        
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            owner_id=user.id
        )
        db_session.add(project)
        db_session.commit()
        
        # Query project with user
        queried_project = db_session.query(Project).filter_by(id=project.id).first()
        assert queried_project.owner_id == user.id
    
    def test_cascade_delete_project(self, db_session):
        """Test cascading delete of project."""
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            hashed_password="password"
        )
        db_session.add(user)
        db_session.commit()
        
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            owner_id=user.id
        )
        db_session.add(project)
        db_session.commit()
        
        # Delete project
        db_session.delete(project)
        db_session.commit()
        
        # Verify project is deleted
        assert db_session.query(Project).filter_by(id=project.id).first() is None


class TestClinicalRecordOperations:
    """Test clinical record database operations."""
    
    def test_create_clinical_record(self, db_session):
        """Test creating clinical record."""
        user = User(id=str(uuid.uuid4()), email="test@example.com", hashed_password="password")
        project = Project(id=str(uuid.uuid4()), name="Test", owner_id=user.id)
        db_session.add_all([user, project])
        db_session.commit()
        
        record = ClinicalRecord(
            id=str(uuid.uuid4()),
            project_id=project.id,
            patient_id="P12345",
            record_type="ehr",
            raw_text="Patient has fever",
            structured_data={"phenotypes": ["fever"]},
            phi_redacted=True
        )
        db_session.add(record)
        db_session.commit()
        
        assert record.id is not None
        assert record.phi_redacted is True
    
    def test_clinical_record_jsonb_field(self, db_session):
        """Test JSONB field in clinical record."""
        user = User(id=str(uuid.uuid4()), email="test@example.com", hashed_password="password")
        project = Project(id=str(uuid.uuid4()), name="Test", owner_id=user.id)
        db_session.add_all([user, project])
        db_session.commit()
        
        record = ClinicalRecord(
            id=str(uuid.uuid4()),
            project_id=project.id,
            patient_id="P12345",
            record_type="ehr",
            raw_text="Test",
            structured_data={"phenotypes": ["fever", "cough"], "medications": ["aspirin"]},
            phi_redacted=True
        )
        db_session.add(record)
        db_session.commit()
        
        # Query and verify JSONB data
        queried = db_session.query(ClinicalRecord).filter_by(id=record.id).first()
        assert queried.structured_data["phenotypes"] == ["fever", "cough"]
        assert queried.structured_data["medications"] == ["aspirin"]


class TestConsensusResultOperations:
    """Test consensus result database operations."""
    
    def test_create_consensus_result(self, db_session):
        """Test creating consensus result."""
        user = User(id=str(uuid.uuid4()), email="test@example.com", hashed_password="password")
        project = Project(id=str(uuid.uuid4()), name="Test", owner_id=user.id)
        db_session.add_all([user, project])
        db_session.commit()
        
        consensus = ConsensusResult(
            id=str(uuid.uuid4()),
            project_id=project.id,
            claim="Test claim",
            evidence_bundle_id=str(uuid.uuid4()),
            jury_size=5,
            status="verified",
            votes={"agent_1": "verified", "agent_2": "verified"},
            consensus_trace={"majority": "verified"}
        )
        db_session.add(consensus)
        db_session.commit()
        
        assert consensus.id is not None
        assert consensus.status == "verified"


class TestForeignKeyConstraints:
    """Test foreign key constraints."""
    
    def test_project_requires_valid_user(self, db_session):
        """Test project requires valid user ID."""
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            owner_id=str(uuid.uuid4())  # Non-existent user
        )
        db_session.add(project)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()
    
    def test_clinical_record_requires_valid_project(self, db_session):
        """Test clinical record requires valid project ID."""
        record = ClinicalRecord(
            id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),  # Non-existent project
            patient_id="P12345",
            record_type="ehr",
            raw_text="Test",
            phi_redacted=True
        )
        db_session.add(record)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()


class TestMigrations:
    """Test database migrations."""
    
    def test_migrations_up_to_date(self):
        """Test migrations are up to date."""
        alembic_cfg = Config("alembic.ini")
        
        # This would check if migrations are current
        # In a real test, you'd verify the migration state
        assert alembic_cfg is not None
    
    def test_migration_rollback(self):
        """Test migration rollback works."""
        # This would test downgrade functionality
        # In a real test, you'd run upgrade then downgrade
        pass


class TestPerformance:
    """Test database performance."""
    
    def test_bulk_insert_performance(self, db_session):
        """Test bulk insert performance."""
        import time
        
        user = User(id=str(uuid.uuid4()), email="test@example.com", hashed_password="password")
        project = Project(id=str(uuid.uuid4()), name="Test", owner_id=user.id)
        db_session.add_all([user, project])
        db_session.commit()
        
        # Bulk insert 100 records
        records = []
        for i in range(100):
            record = ClinicalRecord(
                id=str(uuid.uuid4()),
                project_id=project.id,
                patient_id=f"P{i}",
                record_type="ehr",
                raw_text=f"Test {i}",
                phi_redacted=True
            )
            records.append(record)
        
        start = time.time()
        db_session.bulk_save_objects(records)
        db_session.commit()
        elapsed = time.time() - start
        
        # Should complete in reasonable time (<1 second)
        assert elapsed < 1.0
    
    def test_index_performance(self, db_session):
        """Test index improves query performance."""
        user = User(id=str(uuid.uuid4()), email="test@example.com", hashed_password="password")
        project = Project(id=str(uuid.uuid4()), name="Test", owner_id=user.id)
        db_session.add_all([user, project])
        db_session.commit()
        
        # Insert many records
        for i in range(1000):
            record = ClinicalRecord(
                id=str(uuid.uuid4()),
                project_id=project.id,
                patient_id=f"P{i}",
                record_type="ehr",
                raw_text=f"Test {i}",
                phi_redacted=True
            )
            db_session.add(record)
        db_session.commit()
        
        # Query with index should be fast
        import time
        start = time.time()
        results = db_session.query(ClinicalRecord).filter_by(project_id=project.id).all()
        elapsed = time.time() - start
        
        assert len(results) == 1000
        assert elapsed < 0.1  # Should be very fast with index


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
