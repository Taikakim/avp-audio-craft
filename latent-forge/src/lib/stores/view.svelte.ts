// Shell state: which theme, which view, which tab, which modules are open and what
// is selected. Everything the top bar, the bottom pane and the right pane read. No
// fetching, no DOM beyond the one data-theme write.
//
// NOT owned here: pxPerSec / scrollSec (timeline viewport). Those live on the
// (pre-existing) `arrangement` store, which M5 takes over -- ruled 2026-09-16
// (WINTERMUTE) despite an earlier draft of this task's brief listing them here.
//
// $state PROXY RULE (global constraint): pushing an object into a $state array
// deep-proxies it, so the local reference you pushed is a dead handle. Every method
// here that appends returns the array's LIVE element -- see lastLogLine().

import { logStore, logTone } from "./log.svelte";
import { targetKey } from "../forge/guards";
import type { Target } from "../forge/types";

export type Theme = "light" | "dark";
export type ViewName = "workspace" | "statistics";
export type BottomTabId = "chroma" | "prompt" | "mix" | "terminal";
export type ModuleId =
  | "overlap" | "files" | "lane-chain" | "advanced-sampling" | "master-chain"
  | "legacy-inspector" | "legacy-server";
export type TerminalMode = "collapsed" | "pane" | "full";

export interface TerminalLine {
  seq: number;
  text: string;
  level: "info" | "error";
}

/** The `ui` slice of the project JSON, spec §9.2. */
export interface UiState {
  bottomTab: string;
  modules: string[];
  sideOpen: boolean;
  terminal: string;
}

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

/** spec §9.1 -- the only persisted theme key. */
export const THEME_KEY = "latentforge.theme";

/** spec §4.5 -- CHROMA · PROMPT + SIGMA · MIX + SIGNAL PATH · TERMINAL, in tab order. */
export const BOTTOM_TAB_IDS: BottomTabId[] = ["chroma", "prompt", "mix", "terminal"];

/**
 * Every id a stored project may legally carry in `ui.modules` (spec §9.2) --
 * the five spec modules plus the two legacy ones T15 re-homes. Task 12's
 * MODULE_ORDER is a different list: the five, in PANE order, for rendering.
 */
export const MODULE_IDS: ModuleId[] = [
  "overlap", "files", "lane-chain", "advanced-sampling", "master-chain",
  "legacy-inspector", "legacy-server",
];

/** spec §6.4 -- the server's LOG_RING is 400 lines; the TERMINAL tab holds the same. */
export const LOG_RING = 400;

function browserStorage(): StorageLike | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    // a hardened browser profile can throw on the very access
    return null;
  }
}

export class ViewStore {
  theme = $state<Theme>("light");
  helpOn = $state(false);
  /** The Normative-names table's `view.screen`. `setView()` is its setter. */
  screen = $state<ViewName>("workspace");
  /** Which lane the lane-scoped modules follow (spec §4.6). */
  activeLane = $state<0 | 1 | 2 | 3>(0);
  bottomTab = $state<BottomTabId>("prompt");
  openModules = $state<ModuleId[]>(["files", "lane-chain"]);
  sideOpen = $state(true);
  terminal = $state<TerminalMode>("pane");
  selection = $state<Target>({ kind: "none" });
  logLines = $state<TerminalLine[]>([]);

  /** "session" | "clip:<id>" | "overlap:<key>" -- also the per-target settings key. */
  selectionKey = $derived(targetKey(this.selection));

  private readonly storage: StorageLike | null;
  private logSeq = 0;

  constructor(storage: StorageLike | null = browserStorage()) {
    this.storage = storage;
    const stored = storage?.getItem(THEME_KEY);
    // Anything other than the two known values is light. No prefers-color-scheme.
    this.theme = stored === "dark" ? "dark" : "light";
    this.applyTheme();
  }

  // ------------------------------------------------------------------ theme

  setTheme(next: Theme): void {
    this.theme = next;
    try {
      this.storage?.setItem(THEME_KEY, next);
    } catch {
      // private mode / quota: the toggle still works for this session
    }
    this.applyTheme();
  }

  toggleTheme(): void {
    this.setTheme(this.theme === "dark" ? "light" : "dark");
  }

  /** `:root[data-theme="dark"]` is the only selector tokens.css keys off. */
  private applyTheme(): void {
    if (typeof document === "undefined") return;
    if (this.theme === "dark") document.documentElement.setAttribute("data-theme", "dark");
    else document.documentElement.removeAttribute("data-theme");
  }

  // ------------------------------------------------------------------ shell

  toggleHelp(): void {
    this.helpOn = !this.helpOn;
  }

  setView(next: ViewName): void {
    this.screen = next;
  }

  setActiveLane(next: 0 | 1 | 2 | 3): void {
    this.activeLane = next;
  }

  setBottomTab(next: BottomTabId): void {
    this.bottomTab = next;
  }

  isModuleOpen(id: ModuleId): boolean {
    return this.openModules.includes(id);
  }

  openModule(id: ModuleId): void {
    if (!this.openModules.includes(id)) this.openModules.push(id);
  }

  closeModule(id: ModuleId): void {
    const at = this.openModules.indexOf(id);
    if (at >= 0) this.openModules.splice(at, 1);
  }

  toggleModule(id: ModuleId): void {
    if (this.isModuleOpen(id)) this.closeModule(id);
    else this.openModule(id);
  }

  toggleSide(): void {
    this.sideOpen = !this.sideOpen;
  }

  setTerminal(mode: TerminalMode): void {
    this.terminal = mode;
  }

  // ------------------------------------------------------------- selection

  select(target: Target): void {
    this.selection = target;
  }

  clearSelection(): void {
    this.selection = { kind: "none" };
  }

  // -------------------------------------------------------------- terminal

  /**
   * Append one TERMINAL line and hand back the live element.
   *
   * NOT the object built below: $state deep-proxies on insert, so the local
   * reference is a dead handle whose mutations silently do not apply. This bug
   * already shipped once (fixed in faedf55 by store.svelte.ts's lastClip()).
   */
  appendLog(text: string, level: "info" | "error" = "info"): TerminalLine {
    this.logSeq += 1;
    this.logLines.push({ seq: this.logSeq, text, level });
    if (this.logLines.length > LOG_RING) {
      this.logLines.splice(0, this.logLines.length - LOG_RING);
    }
    // Fact 8 / M9 T5: TERMINAL renders logStore.lines (BottomPane passes `lines={logStore.lines}`),
    // so a line written only here was invisible -- M6's chroma errors, M7's session errors and
    // M10's stats errors all were. Mirrored rather than moved: this method's return type is part
    // of M1 T7's tested contract. appendLocal never advances the server log cursor.
    logStore.appendLocal(text, level === "error" ? "error" : logTone(text));
    return this.lastLogLine();
  }

  private lastLogLine(): TerminalLine {
    return this.logLines[this.logLines.length - 1];
  }

  clearLog(): void {
    this.logLines.splice(0, this.logLines.length);
  }

  // ------------------------------------------------------- project ui slice

  snapshotUi(): UiState {
    return {
      bottomTab: this.bottomTab,
      modules: [...this.openModules],
      sideOpen: this.sideOpen,
      terminal: this.terminal,
    };
  }

  /** A stored project can be older than the current tab/module vocabulary. */
  restoreUi(ui: UiState): void {
    if ((BOTTOM_TAB_IDS as string[]).includes(ui.bottomTab)) this.bottomTab = ui.bottomTab as BottomTabId;
    const modules = (ui.modules ?? []).filter((m): m is ModuleId => (MODULE_IDS as string[]).includes(m));
    this.openModules.splice(0, this.openModules.length, ...modules);
    this.sideOpen = Boolean(ui.sideOpen);
    if (["collapsed", "pane", "full"].includes(ui.terminal)) this.terminal = ui.terminal as TerminalMode;
  }
}

/** The app's single view store. Tests build their own with a fake storage. */
export const view = new ViewStore();
