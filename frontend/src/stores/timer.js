/**
 * timer.js — task timer state, shared between TaskDetail.vue's
 * Start/Stop control and the persistent global indicator in the shell
 * (App.vue) so both reflect the same running timer without prop drilling.
 */
import { defineStore } from "pinia";
import { ref } from "vue";
import { getActiveTimer, startTimer, stopTimer } from "@/utils/api";

export const useTimerStore = defineStore("timer", () => {
  const active = ref(null); // { task, task_key, title, project, started_at } | null
  const loaded = ref(false);

  async function refresh() {
    try {
      active.value = await getActiveTimer();
    } catch {
      active.value = null;
    } finally {
      loaded.value = true;
    }
  }

  async function start(task) {
    const res = await startTimer(task);
    active.value = {
      task: res.task, task_key: res.task_key, title: res.title,
      started_at: res.started_at,
    };
    return res;
  }

  async function stop() {
    const res = await stopTimer();
    active.value = null;
    return res;
  }

  return { active, loaded, refresh, start, stop };
});
