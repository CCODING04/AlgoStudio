'use client';

import { render, screen } from '@testing-library/react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../card';

describe('Card', () => {
  test('渲染 Card', () => {
    render(<Card>Card Content</Card>);
    expect(screen.getByText('Card Content')).toBeInTheDocument();
  });

  test('渲染 CardHeader', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Title</CardTitle>
        </CardHeader>
      </Card>
    );
    expect(screen.getByText('Title')).toBeInTheDocument();
  });

  test('渲染 CardContent', () => {
    render(
      <Card>
        <CardContent>Content</CardContent>
      </Card>
    );
    expect(screen.getByText('Content')).toBeInTheDocument();
  });

  test('渲染 CardTitle', () => {
    render(<CardTitle>My Title</CardTitle>);
    expect(screen.getByText('My Title')).toBeInTheDocument();
  });

  test('渲染 CardDescription', () => {
    render(<CardDescription>This is a description</CardDescription>);
    expect(screen.getByText('This is a description')).toBeInTheDocument();
  });

  test('CardDescription 具有正确样式', () => {
    const { container } = render(<CardDescription>Description</CardDescription>);
    const desc = container.querySelector('.text-sm.text-muted-foreground');
    expect(desc).toBeInTheDocument();
  });

  test('Card 应用正确样式', () => {
    const { container } = render(<Card>Styled Card</Card>);
    const card = container.querySelector('.rounded-lg.border.bg-card.text-card-foreground.shadow-sm');
    expect(card).toBeInTheDocument();
  });

  test('CardHeader 应用正确样式', () => {
    const { container } = render(
      <Card>
        <CardHeader data-testid="card-header">
          <CardTitle>Title</CardTitle>
        </CardHeader>
      </Card>
    );
    const header = container.querySelector('.flex.flex-col.space-y-1\\.5.p-6');
    expect(header).toBeInTheDocument();
  });

  test('CardTitle 应用正确样式', () => {
    const { container } = render(<CardTitle>Styled Title</CardTitle>);
    const title = container.querySelector('.font-semibold.leading-none.tracking-tight');
    expect(title).toBeInTheDocument();
  });

  test('CardContent 应用正确样式', () => {
    const { container } = render(
      <Card>
        <CardContent data-testid="card-content">Content</CardContent>
      </Card>
    );
    const content = container.querySelector('.p-6.pt-0');
    expect(content).toBeInTheDocument();
  });

  test('Card 接受自定义 className', () => {
    const { container } = render(<Card className="custom-class">Custom</Card>);
    const card = container.querySelector('.rounded-lg.border.bg-card.text-card-foreground.shadow-sm');
    expect(card).toHaveClass('custom-class');
  });

  test('完整 Card 组合渲染', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Card Title</CardTitle>
          <CardDescription>Card Description</CardDescription>
        </CardHeader>
        <CardContent>Card Content</CardContent>
      </Card>
    );
    expect(screen.getByText('Card Title')).toBeInTheDocument();
    expect(screen.getByText('Card Description')).toBeInTheDocument();
    expect(screen.getByText('Card Content')).toBeInTheDocument();
  });
});
