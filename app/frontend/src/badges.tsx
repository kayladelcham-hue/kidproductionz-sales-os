import React from 'react';

export type BadgeVariant = 'positive' | 'warning' | 'danger' | 'accent' | 'info' | 'neutral';

export function getScoreVariant(score: unknown): BadgeVariant {
  const value = Number(score);
  if (!Number.isFinite(value)) return 'neutral';
  return value >= 75 ? 'positive' : value >= 60 ? 'warning' : 'danger';
}

export function getGradeVariant(grade: unknown): BadgeVariant {
  const value = String(grade || '').toUpperCase();
  return value.startsWith('B') ? 'positive' : value.startsWith('C') ? 'warning' : value ? 'danger' : 'neutral';
}

export function getRouteVariant(route: unknown): BadgeVariant {
  const value = String(route || '').toUpperCase();
  return value === 'CALL_FIRST' ? 'accent' : value === 'RESEARCH' ? 'info' : 'neutral';
}

export function getPriorityVariant(priority: unknown): BadgeVariant {
  const value = String(priority || '').toUpperCase();
  return value === 'P1' ? 'accent' : value === 'P2' ? 'warning' : 'neutral';
}

export function getStatusVariant(status: unknown): BadgeVariant {
  const value = String(status || '').toUpperCase();
  if (['SYNCED', 'BOOKED', 'ACTIVE', 'DAILY_QUEUE'].includes(value)) return 'positive';
  if (['REVIEW_REQUIRED', 'FOLLOW_UP', 'CONSULTATION_SET', 'PAUSED', 'DEFERRED'].includes(value)) return 'warning';
  if (['SYNC_FAILED', 'INELIGIBLE', 'NOT_INTERESTED'].includes(value)) return 'danger';
  if (['RESEARCH', 'CONTACTED', 'REPLIED', 'ATTEMPTED'].includes(value)) return 'info';
  return 'neutral';
}

export function Badge({ value, variant = 'neutral', className = '' }: { value: unknown; variant?: BadgeVariant; className?: string }) {
  const text = value === null || value === undefined || value === '' ? '—' : String(value);
  return <span className={`badge badge-${variant} ${className}`.trim()}>{text}</span>;
}

export function ScoreBadge({ value }: { value: unknown }) { return <Badge value={value} variant={getScoreVariant(value)} />; }
export function GradeBadge({ value }: { value: unknown }) { return <Badge value={value} variant={getGradeVariant(value)} />; }
export function RouteBadge({ value }: { value: unknown }) { return <Badge value={value} variant={getRouteVariant(value)} />; }
export function PriorityBadge({ value }: { value: unknown }) { return <Badge value={value} variant={getPriorityVariant(value)} />; }
export function StatusBadge({ value }: { value: unknown }) { return <Badge value={value} variant={getStatusVariant(value)} />; }
