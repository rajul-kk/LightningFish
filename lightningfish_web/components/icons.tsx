/** Small inline icon set — kept as SVG rather than emoji so weight, color, and
 * animation are controllable and consistent across platforms/renderers. */

export function BoltIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden="true"
    >
      <path d="M13.2 1.5 4.5 13.8h5.4L9.6 22.5l9.9-13.2h-5.7z" />
    </svg>
  );
}
