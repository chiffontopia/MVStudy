<script setup lang="ts">
import { computed } from "vue";
import { permissionNote, PERMISSION_NOTES, type PermissionNote } from "./permission-notes";

const props = withDefaults(defineProps<{ codes?: string[] }>(), { codes: () => [] });

/** 传了 codes 就只解释这些码；没传则列出全部白名单。 */
const notes = computed<PermissionNote[]>(() =>
  props.codes.length ? props.codes.map((code) => permissionNote(code)) : PERMISSION_NOTES,
);
</script>

<template>
  <ul class="notes">
    <li v-for="note in notes" :key="note.code">
      <span class="label">{{ note.label }}</span>
      <code>{{ note.code }}</code>
      <span class="scope">{{ note.scope }}</span>
    </li>
  </ul>
</template>

<style scoped>
.notes {
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 13px;
}
li {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  padding: 7px 0;
  border-bottom: 1px dashed #eef1f5;
}
li:last-child {
  border-bottom: none;
}
.label {
  min-width: 72px;
  font-weight: 600;
  color: #344054;
}
code {
  padding: 1px 6px;
  border-radius: 4px;
  background: #f2f4f7;
  color: #475467;
  font-size: 12px;
}
.scope {
  color: #667085;
}
</style>
