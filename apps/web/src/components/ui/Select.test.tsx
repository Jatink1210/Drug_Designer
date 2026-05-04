/**
 * Unit tests for Select component
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Select } from './Select';

describe('Select Component', () => {
  const mockOptions = [
    { value: 'option1', label: 'Option 1' },
    { value: 'option2', label: 'Option 2' },
    { value: 'option3', label: 'Option 3' }
  ];

  it('should render select with options', () => {
    render(<Select options={mockOptions} onChange={jest.fn()} />);
    
    const select = screen.getByRole('combobox');
    expect(select).toBeInTheDocument();
    
    fireEvent.click(select);
    
    expect(screen.getByText('Option 1')).toBeInTheDocument();
    expect(screen.getByText('Option 2')).toBeInTheDocument();
    expect(screen.getByText('Option 3')).toBeInTheDocument();
  });

  it('should handle option selection', () => {
    const onChange = jest.fn();
    render(<Select options={mockOptions} onChange={onChange} />);
    
    const select = screen.getByRole('combobox');
    fireEvent.click(select);
    
    const option2 = screen.getByText('Option 2');
    fireEvent.click(option2);
    
    expect(onChange).toHaveBeenCalledWith('option2');
  });

  it('should display placeholder', () => {
    render(
      <Select 
        options={mockOptions} 
        onChange={jest.fn()}
        placeholder="Select an option"
      />
    );
    
    expect(screen.getByText('Select an option')).toBeInTheDocument();
  });

  it('should display selected value', () => {
    render(
      <Select 
        options={mockOptions} 
        onChange={jest.fn()}
        value="option2"
      />
    );
    
    expect(screen.getByText('Option 2')).toBeInTheDocument();
  });

  it('should handle multi-select', () => {
    const onChange = jest.fn();
    render(
      <Select 
        options={mockOptions} 
        onChange={onChange}
        multiple
      />
    );
    
    const select = screen.getByRole('combobox');
    fireEvent.click(select);
    
    const option1 = screen.getByText('Option 1');
    const option2 = screen.getByText('Option 2');
    
    fireEvent.click(option1);
    fireEvent.click(option2);
    
    expect(onChange).toHaveBeenCalledWith(['option1', 'option2']);
  });

  it('should handle search/filter', () => {
    render(
      <Select 
        options={mockOptions} 
        onChange={jest.fn()}
        searchable
      />
    );
    
    const select = screen.getByRole('combobox');
    fireEvent.click(select);
    
    const searchInput = screen.getByPlaceholderText(/search/i);
    fireEvent.change(searchInput, { target: { value: 'Option 1' } });
    
    expect(screen.getByText('Option 1')).toBeInTheDocument();
    expect(screen.queryByText('Option 2')).not.toBeInTheDocument();
  });

  it('should handle disabled state', () => {
    render(
      <Select 
        options={mockOptions} 
        onChange={jest.fn()}
        disabled
      />
    );
    
    const select = screen.getByRole('combobox');
    expect(select).toBeDisabled();
  });

  it('should display error state', () => {
    render(
      <Select 
        options={mockOptions} 
        onChange={jest.fn()}
        error="This field is required"
      />
    );
    
    expect(screen.getByText('This field is required')).toBeInTheDocument();
  });

  it('should handle grouped options', () => {
    const groupedOptions = [
      {
        label: 'Group 1',
        options: [
          { value: 'g1-opt1', label: 'Group 1 Option 1' },
          { value: 'g1-opt2', label: 'Group 1 Option 2' }
        ]
      },
      {
        label: 'Group 2',
        options: [
          { value: 'g2-opt1', label: 'Group 2 Option 1' }
        ]
      }
    ];

    render(
      <Select 
        options={groupedOptions} 
        onChange={jest.fn()}
        grouped
      />
    );
    
    const select = screen.getByRole('combobox');
    fireEvent.click(select);
    
    expect(screen.getByText('Group 1')).toBeInTheDocument();
    expect(screen.getByText('Group 2')).toBeInTheDocument();
  });

  it('should be accessible', () => {
    render(
      <Select 
        options={mockOptions} 
        onChange={jest.fn()}
        label="Select Option"
        required
      />
    );
    
    const select = screen.getByRole('combobox');
    expect(select).toHaveAttribute('aria-required', 'true');
    expect(screen.getByLabelText('Select Option')).toBeInTheDocument();
  });
});
