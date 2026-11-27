<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import { ApiError, createRole, listRoles, updateRole, type AdminRole } from "./api";
import PermissionNotes from "./PermissionNotes.vue";
import { PERMISSION_CODES } from "./permission-notes";

type Draft = { name: string; permissions: string[] };

const roles = ref<AdminRole[]>([]);
const drafts = ref<Record<string, Draft>>({});
const loading = ref(true);
const busyId = ref("");
const submitting = ref(false);
const error = ref("");
const notice = ref("");

const form = reactive<{ role_id: string; name: string; permissions: string[] }>({
  role_id: "",
  name: "",
  permissions: [],
});

function messageOf(cause: unknown): string {
  return cause instanceof ApiError ? cause.message : "操作失败，请稍后重试。";
}

function applyRole(role: AdminRole): void {
  roles.value = roles.value.map((item) => (item.role_id === role.role_id ? role : item));
  drafts.value[role.role_id] = { name: role.name, permissions: [...role.permissions] };
}

function toggleIn(list: string[], code: string): string[] {
  return list.includes(code) ? list.filter((item) => item !== code) : [...list, code];
}

function toggleDraft(roleId: string, code: string): void {
  const draft = drafts.value[roleId];
  if (!draft) return;
  draft.permissions = toggleIn(draft.permissions, code);
}

function toggleForm(code: string): void {
  form.permissions = toggleIn(form.permissions, code);
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const page = await listRoles();
    roles.value = page.items;
    drafts.value = Object.fromEntries(
      page.items.map((role) => [role.role_id, { name: role.name, permissions: [...role.permissions] }]),
    );
  } catch (cause) {
    error.value = messageOf(cause);
  } finally {
    loading.value = false;
  }
}

async function submit(): Promise<void> {
  submitting.value = true;
  error.value = "";
  notice.value = "";
  try {
    const created = await createRole({
      role_id: form.role_id.trim(),
      name: form.name.trim(),
      permissions: form.permissions,
    });
    roles.value = [...roles.value, created].sort((a, b) => a.role_id.localeCompare(b.role_id));
    drafts.value[created.role_id] = { name: created.name, permissions: [...created.permissions] };
    notice.value = `已创建角色 ${created.name}（${created.role_id}）。`;
    form.role_id = "";
    form.name = "";
    form.permissions = [];
  } catch (cause) {
    error.value = messageOf(cause);
  } finally {
    submitting.value = false;
  }
}

async function save(roleId: string): Promise<void> {
  const draft = drafts.value[roleId];
  if (!draft) return;
  busyId.value = roleId;
  error.value = "";
  notice.value = "";
  try {
    const updated = await updateRole(roleId, {
      name: draft.name.trim(),
      permissions: draft.permissions,
    });
    applyRole(updated);
    notice.value = `角色 ${updated.name} 已保存；持有它的账号下一次请求即按新权限执行。`;
  } catch (cause) {
    error.value = messageOf(cause);
  } finally {
    busyId.value = "";
  }
}

onMounted(load);
</script>

<template>
  <main class="page">
    <header>
      <div>
        <h1>角色权限</h1>
        <p class="meta">调整功能权限码；班级范围仍由班内关系决定。</p>
      </div>
      <RouterLink class="ghost" to="/">返回首页</RouterLink>
    </header>

    <p v-if="error" class="banner error">{{ error }}</p>
    <p v-if="notice" class="banner notice">{{ notice }}</p>

    <section class="card">
      <h2>新建角色</h2>
      <form class="form" @submit.prevent="submit">
        <label>
          角色键
          <input v-model="form.role_id" required placeholder="assistant" autocomplete="off" />
        </label>
        <label>
          显示名
          <input v-model="form.name" required placeholder="助教" autocomplete="off" />
        </label>
        <button type="submit" :disabled="submitting">{{ submitting ? "创建中…" : "创建" }}</button>
      </form>
      <div class="codes">
        <label v-for="code in PERMISSION_CODES" :key="code" class="check">
          <input
            type="checkbox"
            :checked="form.permissions.includes(code)"
            @change="toggleForm(code)"
          />
          {{ code }}
        </label>
      </div>
    </section>

    <p v-if="loading" class="empty">加载中…</p>

    <section v-for="role in roles" :key="role.role_id" class="card">
      <div class="role-head">
        <div>
          <h2>{{ role.name }}</h2>
          <p class="meta mono">{{ role.role_id }}</p>
        </div>
        <div class="role-actions">
          <input v-model="drafts[role.role_id].name" class="name-input" aria-label="角色显示名" />
          <button
            type="button"
            :disabled="busyId === role.role_id"
            @click="save(role.role_id)"
          >
            {{ busyId === role.role_id ? "保存中…" : "保存" }}
          </button>
        </div>
      </div>
      <div class="codes">
        <label v-for="code in PERMISSION_CODES" :key="code" class="check">
          <input
            type="checkbox"
            :checked="drafts[role.role_id].permissions.includes(code)"
            @change="toggleDraft(role.role_id, code)"
          />
          {{ code }}
        </label>
      </div>
    </section>

    <section class="card">
      <h2>权限说明</h2>
      <PermissionNotes />
    </section>
  </main>
</template>

<style scoped>
.page {
  max-width: 880px;
  margin: 0 auto;
  padding: 32px 24px 48px;
}
header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
}
.meta {
  margin: 4px 0 0;
  color: #667085;
  font-size: 13px;
}
.mono {
  font-family: Consolas, "Courier New", monospace;
}
.ghost {
  display: inline-block;
  padding: 7px 12px;
  background: #fff;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  color: #344054;
  font-size: 13px;
  text-decoration: none;
  cursor: pointer;
}
.banner {
  margin: 0 0 14px;
  padding: 9px 12px;
  border-radius: 6px;
  font-size: 13px;
}
.banner.error {
  background: #fef3f2;
  color: #b42318;
}
.banner.notice {
  background: #ecfdf3;
  color: #027a48;
}
.card {
  background: #fff;
  border: 1px solid #e2e6ec;
  border-radius: 10px;
  padding: 18px 20px;
  margin-bottom: 14px;
}
h2 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: #344054;
}
.form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  align-items: end;
  margin-bottom: 12px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #475467;
}
input {
  padding: 7px 9px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  font-size: 13px;
}
button {
  padding: 8px 14px;
  border: none;
  border-radius: 6px;
  background: #1d4ed8;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}
button:disabled {
  background: #98a2b3;
  cursor: not-allowed;
}
.codes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  padding-top: 4px;
}
.check {
  flex-direction: row;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #475467;
  font-family: Consolas, "Courier New", monospace;
}
.check input {
  padding: 0;
  margin: 0;
}
.role-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.role-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.name-input {
  width: 150px;
}
.empty {
  margin: 0 0 14px;
  color: #98a2b3;
  font-size: 13px;
}
</style>
