const BASE = "/api";

export async function startLogin(environment: string): Promise<{ auth_url: string; status: string }> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ environment }),
  });
  if (!res.ok) throw new Error(`Login failed: ${res.status}`);
  return res.json();
}

export async function getAuthStatus(): Promise<{
  status: "unauthenticated" | "pending" | "needs_tenant" | "authenticated" | "expired";
  tenants?: string[];
  uipath_url?: string;
}> {
  const res = await fetch(`${BASE}/auth/status`);
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
  return res.json();
}

export async function selectTenant(tenantName: string): Promise<{ status: string; uipath_url: string }> {
  const res = await fetch(`${BASE}/auth/select-tenant`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tenant_name: tenantName }),
  });
  if (!res.ok) throw new Error(`Tenant selection failed: ${res.status}`);
  return res.json();
}

export async function logout(): Promise<void> {
  await fetch(`${BASE}/auth/logout`, { method: "POST" });
}
