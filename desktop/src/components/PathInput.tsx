import {
  useEffect,
  useRef,
  useState,
  type FocusEvent,
  type InputHTMLAttributes,
} from "react";

/** Text input that keeps the path/URL tail visible when content overflows (incl. resize). */
export function PathInput({
  className,
  value,
  onFocus,
  onBlur,
  ...rest
}: InputHTMLAttributes<HTMLInputElement>) {
  const ref = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(false);

  // While editing (LTR), keep caret area usable; when not focused, CSS rtl shows the tail.
  // Re-apply scroll-to-end if somehow still LTR overflow after layout changes.
  useEffect(() => {
    const el = ref.current;
    if (!el || focused) return;

    const showTail = () => {
      // RTL mode already shows the end; also nudge scroll for engines that ignore rtl overflow.
      el.scrollLeft = el.scrollWidth;
    };

    const id = requestAnimationFrame(showTail);
    const ro = new ResizeObserver(() => {
      requestAnimationFrame(showTail);
    });
    ro.observe(el);
    if (el.parentElement) ro.observe(el.parentElement);
    window.addEventListener("resize", showTail);

    return () => {
      cancelAnimationFrame(id);
      ro.disconnect();
      window.removeEventListener("resize", showTail);
    };
  }, [value, focused]);

  return (
    <input
      {...rest}
      ref={ref}
      value={value}
      className={[
        "path-input",
        focused ? "is-focused" : "show-tail",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      onFocus={(e: FocusEvent<HTMLInputElement>) => {
        setFocused(true);
        onFocus?.(e);
      }}
      onBlur={(e: FocusEvent<HTMLInputElement>) => {
        setFocused(false);
        // After switching back to show-tail, force end into view next frame.
        requestAnimationFrame(() => {
          const el = ref.current;
          if (el) el.scrollLeft = el.scrollWidth;
        });
        onBlur?.(e);
      }}
    />
  );
}

/** Read-only path/URL line: ellipsis on the left, always show the end (works on resize). */
export function PathTail({
  path,
  className,
  title,
}: {
  path: string;
  className?: string;
  title?: string;
}) {
  if (!path) return null;
  return (
    <div
      className={["path-tail", className].filter(Boolean).join(" ")}
      title={title || path}
    >
      <bdi>{path}</bdi>
    </div>
  );
}
