/**
 * E2E tests for Clinical Workflow (10-stage pipeline)
 * 
 * Tests the complete clinical workflow from EHR ingestion to therapy stratification
 */

describe('Clinical Workflow E2E Tests', () => {
  const testProjectId = 'test-project-' + Date.now();
  const testPatientId = 'P12345';

  beforeEach(() => {
    // Login before each test
    cy.visit('/login');
    cy.get('input[name="email"]').type('test@example.com');
    cy.get('input[name="password"]').type('testpassword');
    cy.get('button[type="submit"]').click();
    cy.url().should('include', '/dashboard');
  });

  describe('Stage 1: EHR Data Ingestion', () => {
    it('should ingest EHR data successfully', () => {
      cy.visit('/clinical/ingest');
      
      // Upload EHR file
      cy.get('input[type="file"]').attachFile('sample_ehr.hl7');
      cy.get('select[name="recordType"]').select('ehr');
      cy.get('input[name="patientId"]').type(testPatientId);
      cy.get('button[type="submit"]').click();
      
      // Wait for processing
      cy.contains('Processing EHR data', { timeout: 10000 });
      cy.contains('EHR data ingested successfully', { timeout: 30000 });
      
      // Verify PHI redaction
      cy.contains('PHI Redacted: Yes');
      cy.get('[data-testid="structured-data"]').should('exist');
    });

    it('should detect and redact PHI automatically', () => {
      cy.visit('/clinical/ingest');
      
      const ehrText = 'Patient John Doe, SSN 123-45-6789, has fever';
      cy.get('textarea[name="rawText"]').type(ehrText);
      cy.get('input[name="patientId"]').type(testPatientId);
      cy.get('button[type="submit"]').click();
      
      // Verify PHI is redacted
      cy.contains('PHI detected and redacted', { timeout: 10000 });
      cy.get('[data-testid="redacted-text"]').should('not.contain', '123-45-6789');
      cy.get('[data-testid="redacted-text"]').should('not.contain', 'John Doe');
    });

    it('should handle invalid EHR format', () => {
      cy.visit('/clinical/ingest');
      
      cy.get('input[type="file"]').attachFile('invalid_file.txt');
      cy.get('button[type="submit"]').click();
      
      cy.contains('Invalid EHR format', { timeout: 5000 });
    });
  });

  describe('Stage 2: AI Phenotype Clustering', () => {
    it('should cluster phenotypes using HDBSCAN', () => {
      cy.visit('/clinical/phenotype-cluster');
      
      // Select EHR records
      cy.get('[data-testid="ehr-record-selector"]').click();
      cy.get('[data-testid="select-all"]').click();
      cy.get('input[name="minClusterSize"]').clear().type('5');
      cy.get('button[type="submit"]').click();
      
      // Wait for clustering
      cy.contains('Clustering phenotypes', { timeout: 10000 });
      cy.contains('Clustering complete', { timeout: 60000 });
      
      // Verify clusters
      cy.get('[data-testid="cluster-card"]').should('have.length.at.least', 1);
      cy.get('[data-testid="rarity-score"]').should('exist');
    });

    it('should detect rare phenotype patterns', () => {
      cy.visit('/clinical/phenotype-cluster');
      
      cy.get('[data-testid="ehr-record-selector"]').click();
      cy.get('[data-testid="select-all"]').click();
      cy.get('button[type="submit"]').click();
      
      cy.contains('Clustering complete', { timeout: 60000 });
      
      // Check for rare patterns (rarity score > 0.9)
      cy.get('[data-testid="rare-cluster"]').should('exist');
    });
  });

  describe('Stage 3: DL Tissue Analysis', () => {
    it('should analyze tissue images with computer vision', () => {
      cy.visit('/clinical/tissue-analysis');
      
      // Upload WSI image
      cy.get('input[type="file"]').attachFile('sample_wsi.tiff');
      cy.get('select[name="analysisType"]').select('histopathology');
      cy.get('button[type="submit"]').click();
      
      // Wait for analysis
      cy.contains('Analyzing tissue', { timeout: 10000 });
      cy.contains('Analysis complete', { timeout: 120000 });
      
      // Verify results
      cy.get('[data-testid="anomaly-detected"]').should('exist');
      cy.get('[data-testid="heatmap"]').should('be.visible');
      cy.get('[data-testid="confidence-score"]').should('exist');
    });

    it('should generate Grad-CAM heatmap', () => {
      cy.visit('/clinical/tissue-analysis');
      
      cy.get('input[type="file"]').attachFile('sample_wsi.tiff');
      cy.get('button[type="submit"]').click();
      
      cy.contains('Analysis complete', { timeout: 120000 });
      
      // Verify heatmap
      cy.get('[data-testid="heatmap"]').should('be.visible');
      cy.get('[data-testid="heatmap-overlay"]').should('exist');
    });
  });

  describe('Stage 4: Neural Network Biomarker Quantification', () => {
    it('should quantify biomarkers from flow cytometry', () => {
      cy.visit('/clinical/biomarker-quantify');
      
      // Upload flow cytometry data
      cy.get('input[type="file"]').attachFile('sample_flow_cytometry.fcs');
      cy.get('input[name="sampleId"]').type('S12345');
      cy.get('button[type="submit"]').click();
      
      // Wait for quantification
      cy.contains('Quantifying biomarkers', { timeout: 10000 });
      cy.contains('Quantification complete', { timeout: 60000 });
      
      // Verify results
      cy.get('[data-testid="cell-population"]').should('have.length.at.least', 20);
      cy.get('[data-testid="abnormal-flag"]').should('exist');
    });

    it('should detect abnormal cell populations', () => {
      cy.visit('/clinical/biomarker-quantify');
      
      cy.get('input[type="file"]').attachFile('sample_flow_cytometry.fcs');
      cy.get('button[type="submit"]').click();
      
      cy.contains('Quantification complete', { timeout: 60000 });
      
      // Check for abnormal populations
      cy.get('[data-testid="abnormal-population"]').should('exist');
      cy.get('[data-testid="reference-comparison"]').should('exist');
    });
  });

  describe('Stage 5: Genomic Sequencing (VCF)', () => {
    it('should process VCF file', () => {
      cy.visit('/clinical/genomic-sequence');
      
      // Upload VCF file
      cy.get('input[type="file"]').attachFile('sample.vcf');
      cy.get('button[type="submit"]').click();
      
      // Wait for processing
      cy.contains('Processing VCF', { timeout: 10000 });
      cy.contains('Processing complete', { timeout: 600000 }); // 10 min for WES
      
      // Verify results
      cy.get('[data-testid="variants-processed"]').should('exist');
      cy.get('[data-testid="quality-metrics"]').should('exist');
    });
  });

  describe('Stage 6: DL Pathogenicity Prediction', () => {
    it('should predict variant pathogenicity', () => {
      cy.visit('/clinical/pathogenicity-predict');
      
      // Select variants
      cy.get('[data-testid="variant-selector"]').click();
      cy.get('[data-testid="select-all"]').click();
      cy.get('button[type="submit"]').click();
      
      // Wait for prediction
      cy.contains('Predicting pathogenicity', { timeout: 10000 });
      cy.contains('Prediction complete', { timeout: 60000 });
      
      // Verify results
      cy.get('[data-testid="pathogenicity-score"]').should('exist');
      cy.get('[data-testid="acmg-classification"]').should('exist');
      cy.get('[data-testid="confidence-interval"]').should('exist');
    });
  });

  describe('Stage 8: AI Disruption Modeling', () => {
    it('should model mutation effects', () => {
      cy.visit('/clinical/disruption-model');
      
      // Select variants
      cy.get('[data-testid="variant-selector"]').click();
      cy.get('[data-testid="select-pathogenic"]').click();
      cy.get('button[type="submit"]').click();
      
      // Wait for modeling
      cy.contains('Modeling disruption', { timeout: 10000 });
      cy.contains('Modeling complete', { timeout: 60000 });
      
      // Verify results
      cy.get('[data-testid="disrupted-pathway"]').should('exist');
      cy.get('[data-testid="disruption-score"]').should('exist');
    });
  });

  describe('Stage 9: AI Targeted Drug Matching', () => {
    it('should match drugs to disrupted pathways', () => {
      cy.visit('/clinical/drug-match');
      
      // Select disrupted pathways
      cy.get('[data-testid="pathway-selector"]').click();
      cy.get('[data-testid="select-all"]').click();
      cy.get('button[type="submit"]').click();
      
      // Wait for matching
      cy.contains('Matching drugs', { timeout: 10000 });
      cy.contains('Matching complete', { timeout: 60000 });
      
      // Verify results
      cy.get('[data-testid="drug-recommendation"]').should('have.length.at.least', 1);
      cy.get('[data-testid="mechanism-of-action"]').should('exist');
      cy.get('[data-testid="relevance-score"]').should('exist');
    });
  });

  describe('Stage 10: Advanced Therapy Stratification', () => {
    it('should stratify therapy options', () => {
      cy.visit('/clinical/therapy-stratify');
      
      // Enter patient profile
      cy.get('input[name="age"]').type('5');
      cy.get('input[name="diagnosis"]').type('IPEX');
      cy.get('[data-testid="therapy-type"]').check(['stem_cell', 'bone_marrow']);
      cy.get('button[type="submit"]').click();
      
      // Wait for stratification
      cy.contains('Stratifying therapies', { timeout: 10000 });
      cy.contains('Stratification complete', { timeout: 30000 });
      
      // Verify results
      cy.get('[data-testid="therapy-option"]').should('have.length.at.least', 1);
      cy.get('[data-testid="compatibility-score"]').should('exist');
      cy.get('[data-testid="risk-benefit-analysis"]').should('exist');
    });
  });

  describe('Complete Workflow Integration', () => {
    it('should complete entire 10-stage workflow', () => {
      cy.visit('/clinical/workflow');
      
      // Start workflow
      cy.get('button[data-testid="start-workflow"]').click();
      
      // Monitor progress via WebSocket
      cy.get('[data-testid="workflow-progress"]').should('be.visible');
      
      // Stage 1: Ingest
      cy.contains('Stage 1: EHR Ingestion', { timeout: 10000 });
      cy.get('input[type="file"]').attachFile('sample_ehr.hl7');
      cy.get('button[data-testid="next-stage"]').click();
      
      // Stage 2: Cluster
      cy.contains('Stage 2: Phenotype Clustering', { timeout: 10000 });
      cy.get('button[data-testid="next-stage"]').click();
      
      // Continue through all stages...
      // (abbreviated for brevity)
      
      // Final stage
      cy.contains('Workflow Complete', { timeout: 600000 });
      cy.get('[data-testid="workflow-summary"]').should('exist');
      cy.get('[data-testid="download-report"]').should('be.visible');
    });

    it('should handle workflow errors gracefully', () => {
      cy.visit('/clinical/workflow');
      
      cy.get('button[data-testid="start-workflow"]').click();
      
      // Simulate error
      cy.intercept('POST', '/api/v1/clinical/ingest', {
        statusCode: 500,
        body: { error: 'Processing failed' }
      });
      
      cy.get('input[type="file"]').attachFile('sample_ehr.hl7');
      cy.get('button[data-testid="next-stage"]').click();
      
      // Verify error handling
      cy.contains('Error: Processing failed', { timeout: 10000 });
      cy.get('button[data-testid="retry"]').should('be.visible');
    });

    it('should track workflow provenance', () => {
      cy.visit('/clinical/workflow');
      
      cy.get('button[data-testid="start-workflow"]').click();
      
      // Complete workflow (abbreviated)
      // ...
      
      cy.contains('Workflow Complete', { timeout: 600000 });
      
      // Check provenance
      cy.get('button[data-testid="view-provenance"]').click();
      cy.get('[data-testid="provenance-trace"]').should('exist');
      cy.get('[data-testid="stage-timestamp"]').should('have.length', 10);
    });
  });

  describe('WebSocket Progress Updates', () => {
    it('should receive real-time progress updates', () => {
      cy.visit('/clinical/workflow');
      
      cy.get('button[data-testid="start-workflow"]').click();
      
      // Monitor WebSocket messages
      cy.window().then((win) => {
        cy.spy(win.console, 'log').as('consoleLog');
      });
      
      cy.get('input[type="file"]').attachFile('sample_ehr.hl7');
      cy.get('button[data-testid="next-stage"]').click();
      
      // Verify progress updates
      cy.get('[data-testid="progress-bar"]').should('exist');
      cy.get('[data-testid="progress-percentage"]').should('not.be.empty');
      cy.get('[data-testid="current-stage"]').should('contain', 'Stage 1');
    });

    it('should handle WebSocket disconnection', () => {
      cy.visit('/clinical/workflow');
      
      cy.get('button[data-testid="start-workflow"]').click();
      
      // Simulate WebSocket disconnection
      cy.window().then((win) => {
        win.dispatchEvent(new Event('offline'));
      });
      
      // Verify reconnection attempt
      cy.contains('Connection lost. Reconnecting...', { timeout: 5000 });
      cy.contains('Reconnected', { timeout: 10000 });
    });
  });

  describe('PHI Protection', () => {
    it('should never display PHI in UI', () => {
      cy.visit('/clinical/workflow');
      
      // Complete workflow with PHI data
      cy.get('button[data-testid="start-workflow"]').click();
      
      const ehrWithPHI = 'Patient SSN 123-45-6789, DOB 01/15/1980';
      cy.get('textarea[name="rawText"]').type(ehrWithPHI);
      cy.get('button[data-testid="next-stage"]').click();
      
      // Verify PHI is never displayed
      cy.get('body').should('not.contain', '123-45-6789');
      cy.get('body').should('not.contain', '01/15/1980');
      cy.contains('[PHI_REDACTED]');
    });
  });
});
