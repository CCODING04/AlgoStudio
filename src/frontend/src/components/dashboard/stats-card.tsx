import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { LucideIcon } from 'lucide-react';

interface StatsCardProps {
  title: string;
  value: number | string;
  variant?: 'default' | 'primary' | 'secondary' | 'destructive';
  icon?: LucideIcon;
}

export function StatsCard({ title, value, variant = 'default', icon: Icon }: StatsCardProps) {
  const variantClasses = {
    default: 'bg-card',
    primary: 'bg-primary text-primary-foreground',
    secondary: 'bg-secondary text-secondary-foreground',
    destructive: 'bg-destructive text-destructive-foreground',
  };

  return (
    <Card className={cn(variant !== 'default' && variantClasses[variant])}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          {Icon && <Icon className="h-4 w-4" />}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">{value}</div>
      </CardContent>
    </Card>
  );
}
