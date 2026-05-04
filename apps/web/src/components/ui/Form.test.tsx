/**
 * Unit tests for Form component
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Form } from './Form';

describe('Form Component', () => {
  it('should render form with fields', () => {
    const fields = [
      { name: 'email', label: 'Email', type: 'email', required: true },
      { name: 'password', label: 'Password', type: 'password', required: true }
    ];

    render(<Form fields={fields} onSubmit={jest.fn()} />);
    
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });

  it('should handle form submission', async () => {
    const onSubmit = jest.fn();
    const fields = [
      { name: 'email', label: 'Email', type: 'email' }
    ];

    render(<Form fields={fields} onSubmit={onSubmit} />);
    
    const emailInput = screen.getByLabelText('Email');
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    
    const submitButton = screen.getByRole('button', { name: /submit/i });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ email: 'test@example.com' });
    });
  });

  it('should validate required fields', async () => {
    const onSubmit = jest.fn();
    const fields = [
      { name: 'email', label: 'Email', type: 'email', required: true }
    ];

    render(<Form fields={fields} onSubmit={onSubmit} />);
    
    const submitButton = screen.getByRole('button', { name: /submit/i });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText(/required/i)).toBeInTheDocument();
      expect(onSubmit).not.toHaveBeenCalled();
    });
  });

  it('should validate email format', async () => {
    const onSubmit = jest.fn();
    const fields = [
      { name: 'email', label: 'Email', type: 'email', required: true }
    ];

    render(<Form fields={fields} onSubmit={onSubmit} />);
    
    const emailInput = screen.getByLabelText('Email');
    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
    
    const submitButton = screen.getByRole('button', { name: /submit/i });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
    });
  });

  it('should handle custom validation', async () => {
    const onSubmit = jest.fn();
    const customValidator = (value: string) => {
      if (value.length < 8) return 'Must be at least 8 characters';
      return null;
    };

    const fields = [
      { 
        name: 'password', 
        label: 'Password', 
        type: 'password',
        validate: customValidator
      }
    ];

    render(<Form fields={fields} onSubmit={onSubmit} />);
    
    const passwordInput = screen.getByLabelText('Password');
    fireEvent.change(passwordInput, { target: { value: 'short' } });
    
    const submitButton = screen.getByRole('button', { name: /submit/i });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText(/must be at least 8 characters/i)).toBeInTheDocument();
    });
  });

  it('should display loading state during submission', async () => {
    const onSubmit = jest.fn(() => new Promise(resolve => setTimeout(resolve, 100)));
    const fields = [
      { name: 'email', label: 'Email', type: 'email' }
    ];

    render(<Form fields={fields} onSubmit={onSubmit} />);
    
    const emailInput = screen.getByLabelText('Email');
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    
    const submitButton = screen.getByRole('button', { name: /submit/i });
    fireEvent.click(submitButton);
    
    expect(submitButton).toBeDisabled();
    expect(screen.getByText(/submitting/i)).toBeInTheDocument();
  });

  it('should handle form reset', () => {
    const fields = [
      { name: 'email', label: 'Email', type: 'email' }
    ];

    render(<Form fields={fields} onSubmit={jest.fn()} />);
    
    const emailInput = screen.getByLabelText('Email') as HTMLInputElement;
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    
    expect(emailInput.value).toBe('test@example.com');
    
    const resetButton = screen.getByRole('button', { name: /reset/i });
    fireEvent.click(resetButton);
    
    expect(emailInput.value).toBe('');
  });

  it('should populate initial values', () => {
    const fields = [
      { name: 'email', label: 'Email', type: 'email' },
      { name: 'name', label: 'Name', type: 'text' }
    ];

    const initialValues = {
      email: 'initial@example.com',
      name: 'Initial Name'
    };

    render(<Form fields={fields} onSubmit={jest.fn()} initialValues={initialValues} />);
    
    expect(screen.getByLabelText('Email')).toHaveValue('initial@example.com');
    expect(screen.getByLabelText('Name')).toHaveValue('Initial Name');
  });

  it('should be accessible', () => {
    const fields = [
      { name: 'email', label: 'Email', type: 'email', required: true }
    ];

    render(<Form fields={fields} onSubmit={jest.fn()} />);
    
    const emailInput = screen.getByLabelText('Email');
    expect(emailInput).toHaveAttribute('required');
    expect(emailInput).toHaveAttribute('aria-required', 'true');
  });
});
