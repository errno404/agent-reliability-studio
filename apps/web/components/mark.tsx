/** The ARS mark: a confidence interval — two whisker caps, the bar between them, and the point estimate. Measurement, not mascots. */
export function Mark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden fill="none" strokeLinecap="round">
      <path d="M7 7v18M25 7v18" stroke="var(--accent)" strokeWidth="2.6" />
      <path d="M7 16h18" stroke="currentColor" strokeWidth="2.6" />
      <circle cx="17" cy="16" r="3.6" fill="var(--panel)" stroke="currentColor" strokeWidth="2.4" />
    </svg>
  );
}
