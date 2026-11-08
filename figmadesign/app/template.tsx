"use client";
// Re-mounts on every navigation: a short slide-and-fade between screens.
import { motion } from "motion/react";
import { useEffect } from "react";

export default function Template({ children }: { children: React.ReactNode }) {
  useEffect(() => { document.getElementById("scroller")?.scrollTo({ top: 0 }); }, []);
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}>
      {children}
    </motion.div>
  );
}
