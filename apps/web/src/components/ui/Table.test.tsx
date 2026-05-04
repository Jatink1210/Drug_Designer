/**
 * Unit tests for Table component
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Table } from './Table';

describe('Table Component', () => {
  const mockColumns = [
    { key: 'name', label: 'Name', sortable: true },
    { key: 'score', label: 'Score', sortable: true },
    { key: 'status', label: 'Status', sortable: false }
  ];

  const mockData = [
    { id: '1', name: 'Item 1', score: 95, status: 'active' },
    { id: '2', name: 'Item 2', score: 87, status: 'inactive' },
    { id: '3', name: 'Item 3', score: 92, status: 'active' }
  ];

  it('should render table with data', () => {
    render(<Table columns={mockColumns} data={mockData} />);
    
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Score')).toBeInTheDocument();
    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('95')).toBeInTheDocument();
  });

  it('should render empty state when no data', () => {
    render(<Table columns={mockColumns} data={[]} />);
    
    expect(screen.getByText(/no data/i)).toBeInTheDocument();
  });

  it('should handle row selection', () => {
    const onRowSelect = jest.fn();
    render(
      <Table 
        columns={mockColumns} 
        data={mockData}
        selectable
        onRowSelect={onRowSelect}
      />
    );
    
    const checkbox = screen.getAllByRole('checkbox')[1]; // First data row
    fireEvent.click(checkbox);
    
    expect(onRowSelect).toHaveBeenCalledWith(['1']);
  });

  it('should handle select all', () => {
    const onRowSelect = jest.fn();
    render(
      <Table 
        columns={mockColumns} 
        data={mockData}
        selectable
        onRowSelect={onRowSelect}
      />
    );
    
    const selectAllCheckbox = screen.getAllByRole('checkbox')[0]; // Header checkbox
    fireEvent.click(selectAllCheckbox);
    
    expect(onRowSelect).toHaveBeenCalledWith(['1', '2', '3']);
  });

  it('should sort data when column header clicked', () => {
    render(<Table columns={mockColumns} data={mockData} />);
    
    const nameHeader = screen.getByText('Name');
    fireEvent.click(nameHeader);
    
    // Verify sort indicator appears
    expect(nameHeader.parentElement).toHaveClass('sorted');
  });

  it('should handle pagination', () => {
    const manyItems = Array.from({ length: 25 }, (_, i) => ({
      id: `${i}`,
      name: `Item ${i}`,
      score: 80 + i,
      status: 'active'
    }));

    render(
      <Table 
        columns={mockColumns} 
        data={manyItems}
        pagination
        pageSize={10}
      />
    );
    
    expect(screen.getByText('Item 0')).toBeInTheDocument();
    expect(screen.queryByText('Item 15')).not.toBeInTheDocument();
    
    // Click next page
    const nextButton = screen.getByLabelText(/next page/i);
    fireEvent.click(nextButton);
    
    expect(screen.getByText('Item 10')).toBeInTheDocument();
  });

  it('should handle row click', () => {
    const onRowClick = jest.fn();
    render(
      <Table 
        columns={mockColumns} 
        data={mockData}
        onRowClick={onRowClick}
      />
    );
    
    const firstRow = screen.getByText('Item 1').closest('tr');
    fireEvent.click(firstRow!);
    
    expect(onRowClick).toHaveBeenCalledWith(mockData[0]);
  });

  it('should render loading state', () => {
    render(<Table columns={mockColumns} data={[]} loading />);
    
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('should render error state', () => {
    render(
      <Table 
        columns={mockColumns} 
        data={[]}
        error="Failed to load data"
      />
    );
    
    expect(screen.getByText(/failed to load data/i)).toBeInTheDocument();
  });

  it('should apply custom row className', () => {
    const getRowClassName = (row: any) => 
      row.status === 'active' ? 'active-row' : 'inactive-row';

    render(
      <Table 
        columns={mockColumns} 
        data={mockData}
        getRowClassName={getRowClassName}
      />
    );
    
    const firstRow = screen.getByText('Item 1').closest('tr');
    expect(firstRow).toHaveClass('active-row');
  });

  it('should handle column filtering', () => {
    render(
      <Table 
        columns={mockColumns} 
        data={mockData}
        filterable
      />
    );
    
    const filterInput = screen.getByPlaceholderText(/filter/i);
    fireEvent.change(filterInput, { target: { value: 'Item 1' } });
    
    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.queryByText('Item 2')).not.toBeInTheDocument();
  });

  it('should be accessible', () => {
    const { container } = render(<Table columns={mockColumns} data={mockData} />);
    
    const table = container.querySelector('table');
    expect(table).toHaveAttribute('role', 'table');
    
    const headers = screen.getAllByRole('columnheader');
    expect(headers).toHaveLength(mockColumns.length);
  });
});
