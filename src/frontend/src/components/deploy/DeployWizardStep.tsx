'use client';

import { cn } from '@/lib/utils';
import { Check } from 'lucide-react';

interface DeployWizardStepProps {
  number: number;
  title: string;
  isActive: boolean;
  isCompleted: boolean;
  icon: React.ElementType;
}

export function DeployWizardStep({
  number,
  title,
  isActive,
  isCompleted,
  icon: Icon,
}: DeployWizardStepProps) {
  return (
    <div className="flex items-center gap-3">
      <div
        className={cn(
          'flex items-center justify-center w-10 h-10 rounded-full border-2 transition-colors',
          isActive && 'border-primary bg-primary text-primary-foreground',
          isCompleted && 'border-primary bg-primary text-primary-foreground',
          !isActive && !isCompleted && 'border-muted bg-muted text-muted-foreground'
        )}
      >
        {isCompleted ? (
          <Check className="h-5 w-5" />
        ) : (
          <Icon className="h-5 w-5" />
        )}
      </div>
      <span
        className={cn(
          'text-sm font-medium',
          isActive && 'text-foreground',
          !isActive && 'text-muted-foreground'
        )}
      >
        {title}
      </span>
    </div>
  );
}
