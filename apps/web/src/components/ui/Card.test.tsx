/**
 * Unit tests for Card component
 */

import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Card } from './Card';

describe('Card Component', () => {
  it('renders card with children', () => {
    render(<Card>Card Content</Card>);
    expect(screen.getByText('Card Content')).toBeInTheDocument();
  });

  it('renders card with title', () => {
    render(<Card title="Card Title">Content</Card>);
    expect(screen.getByText('Card Title')).toBeInTheDocument();
  });

  it('renders card with header and footer', () => {
    render(
      <Card 
        header={<div>Header</div>}
        footer={<div>Footer</div>}
      >
        Content
      </Card>
    );
    expect(screen.getByText('Header')).toBeInTheDocument();
    expect(screen.getByText('Footer')).toBeInTheDocument();
  });

  it('applies hover effect when hoverable', () => {
    render(<Card hoverable>Hoverable Card</Card>);
    const card = screen.getByText('Hoverable Card').closest('.card');
    expect(card).toHaveClass('card-hoverable');
  });

  it('applies custom className', () => {
    render(<Card className="custom-card">Custom</Card>);
    const card = screen.getByText('Custom').closest('.card');
    expect(card).toHaveClass('custom-card');
  });

  it('renders loading state', () => {
    render(<Card loading>Content</Card>);
    expect(screen.getByTestId('card-loading')).toBeInTheDocument();
  });

  it('renders empty state', () => {
    render(<Card empty emptyMessage="No data">Content</Card>);
    expect(screen.getByText('No data')).toBeInTheDocument();
  });
});
