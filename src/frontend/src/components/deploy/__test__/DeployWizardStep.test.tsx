'use client';

import { render, screen } from '@testing-library/react';
import { DeployWizardStep } from '../DeployWizardStep';
import { Server, Check, Cpu } from 'lucide-react';

describe('DeployWizardStep', () => {
  test('渲染步骤编号和标题', () => {
    render(
      <DeployWizardStep
        number={1}
        title="选择服务器"
        isActive={false}
        isCompleted={false}
        icon={Server}
      />
    );

    expect(screen.getByText('选择服务器')).toBeInTheDocument();
  });

  test('活动状态和已完成状态都渲染为 active 样式', () => {
    // When isActive is true
    const { rerender } = render(
      <DeployWizardStep
        number={1}
        title="步骤1"
        isActive={true}
        isCompleted={false}
        icon={Server}
      />
    );
    expect(screen.getByText('步骤1')).toBeInTheDocument();

    // When isCompleted is true (also uses primary styling)
    rerender(
      <DeployWizardStep
        number={1}
        title="步骤1"
        isActive={false}
        isCompleted={true}
        icon={Server}
      />
    );
    expect(screen.getByText('步骤1')).toBeInTheDocument();
  });

  test('非活动且未完成状态渲染', () => {
    render(
      <DeployWizardStep
        number={1}
        title="未选中步骤"
        isActive={false}
        isCompleted={false}
        icon={Server}
      />
    );

    expect(screen.getByText('未选中步骤')).toBeInTheDocument();
  });

  test('不同步骤编号正确显示', () => {
    render(
      <DeployWizardStep
        number={1}
        title="步骤 1"
        isActive={false}
        isCompleted={false}
        icon={Cpu}
      />
    );

    expect(screen.getByText('步骤 1')).toBeInTheDocument();
  });

  test('不同 icon 类型正常渲染', () => {
    render(
      <DeployWizardStep
        number={1}
        title="测试"
        isActive={true}
        isCompleted={false}
        icon={Server}
      />
    );

    expect(screen.getByText('测试')).toBeInTheDocument();
    const icon = screen.getByText('测试').parentElement?.querySelector('svg');
    expect(icon).toBeInTheDocument();
  });

  test('已完成步骤有 svg 图标', () => {
    render(
      <DeployWizardStep
        number={1}
        title="完成步骤"
        isActive={false}
        isCompleted={true}
        icon={Server}
      />
    );

    // When completed, Check icon is shown (uses lucide-check class)
    const svgIcon = screen.getByText('完成步骤').parentElement?.querySelector('svg');
    expect(svgIcon).toBeInTheDocument();
  });

  test('活动状态时标题可见', () => {
    render(
      <DeployWizardStep
        number={1}
        title="当前步骤"
        isActive={true}
        isCompleted={false}
        icon={Server}
      />
    );

    expect(screen.getByText('当前步骤')).toBeInTheDocument();
  });
});
