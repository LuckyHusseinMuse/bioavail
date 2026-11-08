// Inline icons (no icon library needed). stroke = currentColor.
import type { ReactNode } from "react";

type P = { className?: string };
const S = (d: ReactNode) => {
  const Icon = ({ className = "w-6 h-6" }: P) => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      {d}
    </svg>
  );
  return Icon;
};

export const IconBell = S(<><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></>);
export const IconHome = S(<><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /></>);
export const IconPlus = S(<path d="M12 5v14M5 12h14" />);
export const IconChat = S(<path d="M21 12a8 8 0 0 1-11.6 7.1L3 21l1.9-6.4A8 8 0 1 1 21 12Z" />);
export const IconGraph = S(<><circle cx="6" cy="6" r="2.5" /><circle cx="18" cy="8" r="2.5" /><circle cx="12" cy="18" r="2.5" /><path d="M8 7l7.6 1M7.2 8.2l3.6 7.6M16.8 10.2 13.2 16" /></>);
export const IconUser = S(<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>);
export const IconCamera = S(<><path d="M3 8h4l2-3h6l2 3h4v12H3z" /><circle cx="12" cy="13" r="4" /></>);
export const IconText = S(<path d="M4 6h16M4 12h16M4 18h10" />);
export const IconSearch = S(<><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>);
export const IconAlert = S(<><path d="M12 3 2 21h20L12 3Z" /><path d="M12 10v5M12 18h.01" /></>);
export const IconCheck = S(<path d="m5 12 5 5L20 7" />);
export const IconX = S(<path d="M6 6l12 12M18 6 6 18" />);
export const IconClock = S(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>);
export const IconSpark = S(<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" />);
