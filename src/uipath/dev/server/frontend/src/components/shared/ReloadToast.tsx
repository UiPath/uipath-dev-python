import { useState } from "react";
import { useRunStore } from "../../store/useRunStore";
import { reloadFactory, listEntrypoints } from "../../api/client";

export default function ReloadToast() {
  const { reloadPending, setReloadPending, setEntrypoints } = useRunStore();
  const [loading, setLoading] = useState(false);

  if (!reloadPending) return null;

  const handleReload = async () => {
    setLoading(true);
    try {
      await reloadFactory();
      const eps = await listEntrypoints();
      setEntrypoints(eps.map((e) => e.name));
      setReloadPending(false);
    } catch (err) {
      console.error("Reload failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-2 rounded-lg shadow-lg"
      style={{ background: "var(--bg-secondary)", border: "1px solid var(--bg-tertiary)" }}>
      <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
        Files changed
      </span>
      <button
        onClick={handleReload}
        disabled={loading}
        className="px-2.5 py-0.5 text-xs font-medium rounded cursor-pointer"
        style={{
          background: "var(--accent)",
          color: "#fff",
          opacity: loading ? 0.6 : 1,
        }}
      >
        {loading ? "Reloading..." : "Reload"}
      </button>
      <button
        onClick={() => setReloadPending(false)}
        aria-label="Dismiss reload prompt"
        className="text-xs cursor-pointer px-0.5"
        style={{ color: "var(--text-muted)", background: "none", border: "none" }}
      >
        ✕
      </button>
    </div>
  );
}
