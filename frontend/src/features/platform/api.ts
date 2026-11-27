import { clearToken, getToken } from "./token";

export type ClassRelation = { class_id: string; relation: string };

export type Actor = {
  user_id: string;
  display_name: string;
  role_id: string;
  permissions: string[];
  classes: ClassRelation[];
};

export type Member = {
  user_id: string;
  display_name: string;
  relation: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`/api${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "network_error", "无法连接服务，请确认后端已启动。");
  }

  const payload = (await response.json().catch(() => null)) as
    | { error?: { code?: string; message?: string } }
    | null;

  if (!response.ok) {
    if (response.status === 401) clearToken();
    const error = payload?.error ?? {};
    throw new ApiError(
      response.status,
      error.code ?? "unexpected_error",
      error.message ?? "服务暂时不可用，请稍后再试。",
    );
  }
  return payload as T;
}

export function login(login: string, password: string): Promise<{ access_token: string }> {
  return request<{ access_token: string }>("/login", {
    method: "POST",
    body: JSON.stringify({ login, password }),
  });
}

export function fetchMe(): Promise<Actor> {
  return request<Actor>("/me");
}

export function fetchMembers(
  classId: string,
  relation?: string,
): Promise<{ items: Member[] }> {
  const query = relation ? `?relation=${encodeURIComponent(relation)}` : "";
  return request<{ items: Member[] }>(`/classes/${encodeURIComponent(classId)}/members${query}`);
}

/** U3：管理端账号条目。服务端不回传 password_hash。 */
export type AdminUser = {
  user_id: string;
  login: string;
  display_name: string;
  role_id: string;
  enabled: boolean;
};

/** U4：角色与权限码。 */
export type AdminRole = {
  role_id: string;
  name: string;
  permissions: string[];
};

export type NewUser = {
  login: string;
  display_name: string;
  password: string;
  role_id: string;
};

export type UserPatch = Partial<Pick<AdminUser, "display_name" | "role_id" | "enabled">>;
export type RolePatch = Partial<Pick<AdminRole, "name" | "permissions">>;

export function listUsers(): Promise<{ items: AdminUser[] }> {
  return request<{ items: AdminUser[] }>("/admin/users");
}

export function createUser(body: NewUser): Promise<AdminUser> {
  return request<AdminUser>("/admin/users", { method: "POST", body: JSON.stringify(body) });
}

export function updateUser(userId: string, body: UserPatch): Promise<AdminUser> {
  return request<AdminUser>(`/admin/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function listRoles(): Promise<{ items: AdminRole[] }> {
  return request<{ items: AdminRole[] }>("/admin/roles");
}

export function createRole(body: AdminRole): Promise<AdminRole> {
  return request<AdminRole>("/admin/roles", { method: "POST", body: JSON.stringify(body) });
}

export function updateRole(roleId: string, body: RolePatch): Promise<AdminRole> {
  return request<AdminRole>(`/admin/roles/${encodeURIComponent(roleId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}
