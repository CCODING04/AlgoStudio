'use client';

import { cn } from '@/lib/utils';

interface ResourceBarProps {
  label: string;
  used: number;
  total: number;
  unit?: string;
  className?: string;
}

export function ResourceBar({ label, used, total, unit = '', className }: ResourceBarProps) {
  const percentage = total > 0 ? Math.min((used / total) * 100, 100) : 0;
  const isLow = percentage > 90;
  const isMedium = percentage > 70 && percentage <= 90;

  return (
    <div className={cn('space-y-1', className)}>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className={cn(
          'font-medium',
          isLow && 'text-destructive',
          isMedium && 'text-yellow-500'
        )}>
          {used.toFixed(1)} / {total.toFixed(1)} {unit}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-secondary overflow-hidden">
        <div
          className={cn(
            'h-full transition-all duration-300',
            isLow && 'bg-destructive',
            isMedium && 'bg-yellow-500',
            !isLow && !isMedium && 'bg-primary'
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
