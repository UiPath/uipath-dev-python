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
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 flex items-center justify-between px-5 py-2.5 rounded-lg shadow-lg min-w-[400px]"
      style={{ background: "var(--bg-secondary)", border: "1px solid var(--bg-tertiary)" }}>
      <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
        Files changed — reload to apply
      </span>
      <div className="flex items-center gap-2">
        <button
          onClick={handleReload}
          disabled={loading}
          className="px-3 py-1 text-sm font-medium rounded cursor-pointer"
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
          className="text-sm cursor-pointer px-1"
          style={{ color: "var(--text-muted)", background: "none", border: "none" }}
        >
          ✕
        </button>
      </div>
    </div>
  );
}
