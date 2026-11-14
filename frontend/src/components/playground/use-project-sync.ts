"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { createProject, duplicateProject, getProject, saveProject } from "@/lib/projects";
import { SUPABASE_ENABLED } from "@/lib/supabase";
import { toGraph, usePlayground } from "./store";

export type SaveState = "local" | "loading" | "saved" | "dirty" | "saving" | "error" | "viewing" | "missing";

const AUTOSAVE_MS = 1200;

/**
 * 주소의 ?p=<프로젝트 id> 와 캔버스를 맞추고, 내 프로젝트면 자동 저장한다.
 * - p 가 없으면: 이 브라우저에만 있는 임시 캔버스 (마지막에 열었던 내 프로젝트가 있으면 그쪽으로 이동)
 * - p 가 내 프로젝트면: 불러와서 편집 + 자동 저장
 * - p 가 남이 공유한 프로젝트면: 보기 전용 (수정해도 저장하지 않음)
 */
export function useProjectSync() {
  const router = useRouter();
  const param = useSearchParams().get("p");
  const { ready, user } = useAuth();
  const projectId = usePlayground((s) => s.projectId);
  const owned = usePlayground((s) => s.owned);
  const [state, setState] = useState<SaveState>("local");
  const [error, setError] = useState("");
  const loadedFor = useRef<string | null>(null); // 마지막으로 서버에서 불러온 "id:사용자"
  const savedJson = useRef<string>("");

  // 주소에서 프로젝트가 빠지면 임시 캔버스 상태로 (렌더 중 상태 조정)
  const [prevParam, setPrevParam] = useState(param);
  if (prevParam !== param) {
    setPrevParam(param);
    if (!param) setState("local");
  }

  const payload = () => {
    const s = usePlayground.getState();
    return { name: s.projectName.trim().slice(0, 80) || "제목 없는 프로젝트", graph: toGraph(s), overrides: s.overrides, pattern_id: s.patternId };
  };

  /* 주소 → 캔버스 */
  useEffect(() => {
    if (!SUPABASE_ENABLED || !ready) return;
    const s = usePlayground.getState();
    if (!param) {
      if (s.projectId && s.owned && user) router.replace(`/playground?p=${s.projectId}`);
      else {
        if (s.projectId) s.leaveProject(); // 공유받아 보던 프로젝트나 로그아웃 전 프로젝트는 닫는다
        loadedFor.current = null;
      }
      return;
    }
    const key = `${param}:${user?.id ?? ""}`;
    if (loadedFor.current === key) return;
    loadedFor.current = key;
    let alive = true;
    setState("loading");
    getProject(param)
      .then((p) => {
        if (!alive) return;
        if (!p) {
          if (usePlayground.getState().projectId) usePlayground.getState().leaveProject();
          return setState("missing");
        }
        const mine = !!user && p.owner === user.id;
        usePlayground.getState().openProject(p, mine);
        savedJson.current = JSON.stringify(payload());
        setState(mine ? "saved" : "viewing");
      })
      .catch((e) => {
        if (!alive) return;
        loadedFor.current = null;
        setError((e as Error).message);
        setState("error");
      });
    return () => {
      alive = false;
    };
  }, [param, ready, user, router]);

  /* 캔버스 → 서버 (자동 저장) */
  const flush = useCallback(async () => {
    const s = usePlayground.getState();
    if (!s.projectId || !s.owned) return;
    const body = payload();
    const json = JSON.stringify(body);
    if (json === savedJson.current) return setState("saved");
    setState("saving");
    try {
      await saveProject(s.projectId, body);
      savedJson.current = json;
      setError("");
      // 저장하는 동안 또 바뀌었으면 다음 자동 저장이 이어서 처리한다
      setState(JSON.stringify(payload()) === json ? "saved" : "dirty");
    } catch (e) {
      setError((e as Error).message);
      setState("error");
    }
  }, []);

  useEffect(() => {
    if (!projectId || !owned) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const unsub = usePlayground.subscribe((s, prev) => {
      if (s.projectId !== projectId) return;
      if (s.nodes === prev.nodes && s.edges === prev.edges && s.settings === prev.settings && s.overrides === prev.overrides && s.projectName === prev.projectName && s.patternId === prev.patternId) return;
      if (!savedJson.current) return;
      setState((cur) => (cur === "saving" ? cur : "dirty"));
      clearTimeout(timer);
      timer = setTimeout(flush, AUTOSAVE_MS);
    });
    const onHide = () => document.visibilityState === "hidden" && flush();
    document.addEventListener("visibilitychange", onHide);
    return () => {
      unsub();
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onHide);
      flush(); // 화면을 떠날 때 남은 변경을 저장
    };
  }, [projectId, owned, flush]);

  /** 임시 캔버스를 내 프로젝트로 저장한다. */
  const saveAsProject = useCallback(async () => {
    setState("saving");
    try {
      const made = await createProject(payload());
      usePlayground.getState().attachProject(made);
      savedJson.current = JSON.stringify(payload());
      loadedFor.current = `${made.id}:${useAuth.getState().user?.id ?? ""}`;
      setState("saved");
      router.replace(`/playground?p=${made.id}`);
    } catch (e) {
      setError((e as Error).message);
      setState("error");
    }
  }, [router]);

  /** 보고 있는 (공유받은) 프로젝트를 내 작업 공간에 복제하고 그 사본을 연다. */
  const duplicate = useCallback(async () => {
    const body = payload();
    try {
      const made = await duplicateProject({ ...body, overrides: body.overrides });
      router.push(`/playground?p=${made.id}`);
    } catch (e) {
      setError((e as Error).message);
      setState("error");
    }
  }, [router]);

  const setPublic = useCallback(async (v: boolean) => {
    const s = usePlayground.getState();
    if (!s.projectId || !s.owned) return;
    await saveProject(s.projectId, { is_public: v });
    s.setIsPublic(v);
  }, []);

  return { state, error, flush, saveAsProject, duplicate, setPublic };
}
