'use client';

import { render, screen } from '@testing-library/react';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '../table';

describe('Table', () => {
  test('渲染 Table 组件', () => {
    render(
      <Table>
        <TableBody>
          <TableRow>
            <TableCell>Data</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
    expect(screen.getByText('Data')).toBeInTheDocument();
  });

  test('渲染带 className 的 Table', () => {
    const { container } = render(
      <Table className="custom-class">
        <TableBody>
          <TableRow>
            <TableCell>Data</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
    const tableWrapper = container.querySelector('.relative.w-full.overflow-auto');
    expect(tableWrapper).toBeInTheDocument();
  });

  test('渲染 TableHeader', () => {
    render(
      <Table>
        <TableHeader data-testid="table-header">
          <TableRow>
            <TableHead>Header 1</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Data 1</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
    expect(screen.getByText('Header 1')).toBeInTheDocument();
  });

  test('TableHeader 应用正确样式', () => {
    const { container } = render(
      <Table>
        <TableHeader data-testid="header">
          <TableRow>
            <TableHead>Head</TableHead>
          </TableRow>
        </TableHeader>
      </Table>
    );
    const thead = container.querySelector('thead');
    expect(thead).toBeInTheDocument();
  });

  test('渲染 TableBody', () => {
    const { container } = render(
      <Table>
        <TableBody data-testid="table-body">
          <TableRow>
            <TableCell>Body Data</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
    const tbody = container.querySelector('tbody');
    expect(tbody).toBeInTheDocument();
    expect(screen.getByText('Body Data')).toBeInTheDocument();
  });

  test('渲染 TableRow', () => {
    render(
      <Table>
        <TableBody>
          <TableRow data-testid="table-row">
            <TableCell>Row Data</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
    expect(screen.getByText('Row Data')).toBeInTheDocument();
  });

  test('TableRow 具有 hover 样式类', () => {
    const { container } = render(
      <Table>
        <TableBody>
          <TableRow>
            <TableCell>Hover Row</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
    const tr = container.querySelector('tr');
    expect(tr).toHaveClass('border-b');
    expect(tr).toHaveClass('transition-colors');
  });

  test('渲染 TableHead', () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Column Header</TableHead>
          </TableRow>
        </TableHeader>
      </Table>
    );
    expect(screen.getByText('Column Header')).toBeInTheDocument();
  });

  test('TableHead 应用对齐样式', () => {
    const { container } = render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Aligned</TableHead>
          </TableRow>
        </TableHeader>
      </Table>
    );
    const th = container.querySelector('th');
    expect(th).toHaveClass('h-12');
    expect(th).toHaveClass('px-4');
    expect(th).toHaveClass('text-left');
  });

  test('渲染 TableCell', () => {
    render(
      <Table>
        <TableBody>
          <TableRow>
            <TableCell>Cell Data</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
    expect(screen.getByText('Cell Data')).toBeInTheDocument();
  });

  test('TableCell 具有正确样式', () => {
    const { container } = render(
      <Table>
        <TableBody>
          <TableRow>
            <TableCell>Styled Cell</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
    const td = container.querySelector('td');
    expect(td).toHaveClass('p-4');
    expect(td).toHaveClass('align-middle');
  });

  test('TableHead 和 TableCell 可接受自定义 className', () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="custom-head">Custom Head</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell className="custom-cell">Custom Cell</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
    expect(screen.getByText('Custom Head')).toBeInTheDocument();
    expect(screen.getByText('Custom Cell')).toBeInTheDocument();
  });

  test('完整表格渲染', () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Node 1</TableCell>
            <TableCell>Online</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Node 2</TableCell>
            <TableCell>Offline</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Node 1')).toBeInTheDocument();
    expect(screen.getByText('Node 2')).toBeInTheDocument();
  });

  test('TableRow 支持 selected 状态', () => {
    const { container } = render(
      <Table>
        <TableBody>
          <TableRow data-state="selected">
            <TableCell>Selected Row</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
    const tr = container.querySelector('tr');
    expect(tr).toHaveAttribute('data-state', 'selected');
  });
});
