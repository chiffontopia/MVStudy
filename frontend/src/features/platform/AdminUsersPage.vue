<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import {
  ApiError,
  createUser,
  listRoles,
  listUsers,
  updateUser,
  type AdminRole,
  type AdminUser,
} from "./api";
import { currentActor } from "./session";

const users = ref<AdminUser[]>([]);
const roles = ref<AdminRole[]>([]);
const loading = ref(true);
const busyId = ref("");
const submitting = ref(false);
const error = ref("");
const notice = ref("");

const form = reactive({ login: "", display_name: "", password: "", role_id: "" });

const selfId = computed(() => currentActor.value?.user_id ?? "");

function messageOf(cause: unknown): string {
  return cause instanceof ApiError ? cause.message : "操作失败，请稍后重试。";
}

function roleName(roleId: string): string {
  return roles.value.find((item) => item.role_id === roleId)?.name ?? roleId;
}

function replaceUser(updated: AdminUser): void {
  users.value = users.value.map((item) => (item.user_id === updated.user_id ? updated : item));
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [userPage, rolePage] = await Promise.all([listUsers(), listRoles()]);
    users.value = userPage.items;
    roles.value = rolePage.items;
    if (!form.role_id && rolePage.items.length) form.role_id = rolePage.items[0].role_id;
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
    const created = await createUser({
      login: form.login.trim(),
      display_name: form.display_name.trim(),
      password: form.password,
      role_id: form.role_id,
    });
    users.value = [...users.value, created].sort((a, b) => a.login.localeCompare(b.login));
    notice.value = `已创建 ${created.display_name}（${created.login}），可用新口令登录。`;
    form.login = "";
    form.display_name = "";
    form.password = "";
  } catch (cause) {
    error.value = messageOf(cause);
  } finally {
    submitting.value = false;
  }
}

async function toggle(user: AdminUser): Promise<void> {
  busyId.value = user.user_id;
  error.value = "";
  notice.value = "";
  try {
    const updated = await updateUser(user.user_id, { enabled: !user.enabled });
    replaceUser(updated);
    notice.value = `${updated.display_name} 已${updated.enabled ? "启用" : "停用"}；旧凭证的下一次请求即按新状态处理。`;
  } catch (cause) {
    error.value = messageOf(cause);
  } finally {
    busyId.value = "";
  }
}

async function changeRole(user: AdminUser, event: Event): Promise<void> {
  const roleId = (event.target as HTMLSelectElement).value;
  if (roleId === user.role_id) return;
  busyId.value = user.user_id;
  error.value = "";
  notice.value = "";
  try {
    const updated = await updateUser(user.user_id, { role_id: roleId });
    replaceUser(updated);
    notice.value = `${updated.display_name} 的角色已改为 ${roleName(updated.role_id)}。`;
  } catch (cause) {
    error.value = messageOf(cause);
    (event.target as HTMLSelectElement).value = user.role_id;
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
        <h1>用户管理</h1>
        <p class="meta">启停账号、调整角色；改动在下一次请求生效。</p>
      </div>
      <RouterLink class="ghost" to="/">返回首页</RouterLink>
    </header>

    <p v-if="error" class="banner error">{{ error }}</p>
    <p v-if="notice" class="banner notice">{{ notice }}</p>

    <section class="card">
      <h2>新建账号</h2>
      <form class="form" @submit.prevent="submit">
        <label>
          登录名
          <input v-model="form.login" required autocomplete="off" />
        </label>
        <label>
          姓名
          <input v-model="form.display_name" required autocomplete="off" />
        </label>
        <label>
          初始口令
          <input v-model="form.password" type="password" required autocomplete="new-password" />
        </label>
        <label>
          角色
          <select v-model="form.role_id" required>
            <option v-for="role in roles" :key="role.role_id" :value="role.role_id">
              {{ role.name }}（{{ role.role_id }}）
            </option>
          </select>
        </label>
        <button type="submit" :disabled="submitting || !roles.length">
          {{ submitting ? "创建中…" : "创建" }}
        </button>
      </form>
    </section>

    <section class="card">
      <h2>账号列表</h2>
      <p v-if="loading" class="empty">加载中…</p>
      <p v-else-if="!users.length" class="empty">暂无账号</p>
      <table v-else>
        <thead>
          <tr>
            <th>登录名</th>
            <th>姓名</th>
            <th>角色</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.user_id">
            <td class="mono">{{ user.login }}</td>
            <td>{{ user.display_name }}</td>
            <td>
              <select
                :value="user.role_id"
                :disabled="busyId === user.user_id"
                @change="changeRole(user, $event)"
              >
                <option v-for="role in roles" :key="role.role_id" :value="role.role_id">
                  {{ role.name }}
                </option>
              </select>
            </td>
            <td>
              <span class="tag" :class="user.enabled ? 'on' : 'off'">
                {{ user.enabled ? "启用" : "停用" }}
              </span>
            </td>
            <td>
              <button
                type="button"
                class="ghost"
                :disabled="busyId === user.user_id || user.user_id === selfId"
                :title="user.user_id === selfId ? '不能停用当前登录的管理员账号' : ''"
                @click="toggle(user)"
              >
                {{ user.enabled ? "停用" : "启用" }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
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
.ghost:disabled {
  color: #98a2b3;
  cursor: not-allowed;
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
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: #344054;
}
.form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  align-items: end;
}
label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #475467;
}
input,
select {
  padding: 7px 9px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
}
button[type="submit"] {
  padding: 8px 14px;
  border: none;
  border-radius: 6px;
  background: #1d4ed8;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}
button[type="submit"]:disabled {
  background: #98a2b3;
  cursor: not-allowed;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th,
td {
  padding: 9px 8px;
  border-bottom: 1px solid #eef1f5;
  text-align: left;
}
th {
  color: #667085;
  font-weight: 500;
}
.mono {
  font-family: Consolas, "Courier New", monospace;
}
.tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 12px;
}
.tag.on {
  background: #ecfdf3;
  color: #027a48;
}
.tag.off {
  background: #fef3f2;
  color: #b42318;
}
.empty {
  margin: 0;
  color: #98a2b3;
  font-size: 13px;
}
</style>
