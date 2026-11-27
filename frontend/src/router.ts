import { createRouter, createWebHistory } from "vue-router";
import AdminRolesPage from "./features/platform/AdminRolesPage.vue";
import AdminUsersPage from "./features/platform/AdminUsersPage.vue";
import HomePage from "./features/platform/HomePage.vue";
import LoginPage from "./features/platform/LoginPage.vue";
import { currentActor, restoreSession } from "./features/platform/session";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginPage, meta: { public: true } },
    { path: "/", name: "home", component: HomePage },
    { path: "/admin/users", name: "admin-users", component: AdminUsersPage, meta: { permission: "admin.users" } },
    { path: "/admin/roles", name: "admin-roles", component: AdminRolesPage, meta: { permission: "admin.roles" } },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

router.beforeEach(async (to) => {
  if (to.meta.public === true) {
    return currentActor.value ? { path: "/" } : true;
  }
  if (!currentActor.value) {
    const restored = await restoreSession();
    if (!restored) return { path: "/login", query: { redirect: to.fullPath } };
  }
  // 前端守卫只负责体验；真正的权限判断在后端接口，直接请求同样返回 403。
  const required = to.meta.permission as string | undefined;
  if (required && !currentActor.value?.permissions.includes(required)) {
    return { path: "/" };
  }
  return true;
});

export default router;
