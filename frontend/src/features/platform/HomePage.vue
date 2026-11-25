<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { currentActor, roleLabel, signOut } from "./session";

const router = useRouter();
const actor = computed(() => currentActor.value);
const canManageUsers = computed(() => actor.value?.permissions.includes("admin.users") ?? false);
const canManageRoles = computed(() => actor.value?.permissions.includes("admin.roles") ?? false);

function handleSignOut(): void {
  signOut();
  void router.replace({ path: "/login" });
}
</script>

<template>
  <main v-if="actor" class="home">
    <header>
      <div>
        <h1>{{ actor.display_name }}</h1>
        <p class="meta">{{ roleLabel(actor.role_id) }} · {{ actor.user_id }}</p>
      </div>
      <button type="button" class="ghost" @click="handleSignOut">退出登录</button>
    </header>

    <section class="card">
      <h2>所属班级</h2>
      <ul v-if="actor.classes.length">
        <li v-for="item in actor.classes" :key="item.class_id">
          {{ item.class_id }}（{{ item.relation === "teacher" ? "任教" : "在读" }}）
        </li>
      </ul>
      <p v-else class="empty">暂无班级</p>
    </section>

    <section class="card">
      <h2>功能权限</h2>
      <ul v-if="actor.permissions.length">
        <li v-for="code in actor.permissions" :key="code">{{ code }}</li>
      </ul>
      <p v-else class="empty">暂无授权</p>
    </section>

    <section v-if="canManageUsers || canManageRoles" class="card">
      <h2>管理入口</h2>
      <div class="links">
        <RouterLink v-if="canManageUsers" to="/admin/users">用户管理</RouterLink>
        <RouterLink v-if="canManageRoles" to="/admin/roles">角色权限</RouterLink>
      </div>
    </section>

    <p class="note">
      案例、任务与成绩计数将在 32 号票接入 P1 后显示；本页当前展示票 01 的身份结果。
    </p>
  </main>
</template>

<style scoped>
.home {
  max-width: 640px;
  margin: 0 auto;
  padding: 32px 24px 48px;
}
header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
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
  padding: 7px 12px;
  background: #fff;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}
.card {
  background: #fff;
  border: 1px solid #e2e6ec;
  border-radius: 10px;
  padding: 18px 20px;
  margin-bottom: 14px;
}
h2 {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 600;
  color: #344054;
}
ul {
  margin: 0;
  padding-left: 18px;
  font-size: 14px;
  line-height: 1.9;
}
.empty {
  margin: 0;
  color: #98a2b3;
  font-size: 13px;
}
.links {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.links a {
  padding: 8px 14px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  color: #1d4ed8;
  font-size: 13px;
  text-decoration: none;
}
.links a:hover {
  background: #eff4ff;
}
.note {
  margin: 20px 0 0;
  color: #98a2b3;
  font-size: 12px;
  line-height: 1.7;
}
</style>
