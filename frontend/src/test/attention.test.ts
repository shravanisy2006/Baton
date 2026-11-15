import { attention } from "../pages/Overview";
import type { Overview } from "../lib/types";

function overview(counts: Record<string, number>, extra: Partial<Overview> = {}): Overview {
  return {
    project: { id: "p1", name: "Library", description: "", is_demo: false, departing: "Meera", incoming: "Nikhil" },
    me: { user_id: "u1", name: "Dr. Sen", role: "admin", access_level: "Restricted" },
    members: [],
    counts: {
      sources: 5,
      evidence: 23,
      claims: 20,
      verified: 12,
      unverified: 2,
      pending_review: 0,
      open_gaps: 0,
      open_conflicts: 0,
      new_evidence: 0,
      changed_since_approval: 0,
      ...counts,
    },
    steps: [],
    latest_job: {
      id: "j",
      kind: "analyse",
      status: "done",
      stage: "finished",
      warnings: [],
      error: null,
      stats: {},
      created_at: "",
      finished_at: "",
    },
    handover: { versions: 0, approved_version: null },
    ai: { configured: true, chain: [] },
    ...extra,
  } as Overview;
}

describe("what needs your attention", () => {
  it("lists disagreements before review, and links to the right pages", () => {
    const items = attention("admin", overview({ open_conflicts: 2, pending_review: 7 }), "/p/p1");
    expect(items.map((i) => i.text)).toEqual([
      "2 places where files disagree. Pick which is right.",
      "7 findings to check against the highlighted file.",
    ]);
    expect(items[0]).toMatchObject({ tone: "urgent", to: "/p/p1/gaps" });
    expect(items[1]).toMatchObject({ to: "/p/p1/review" });
  });

  it("asks for the handover once everything is reviewed", () => {
    const [item] = attention("reviewer", overview({}), "/p/p1");
    expect(item.text).toMatch(/Make the handover/);
  });

  it("flags an out-of-date handover and the next version number", () => {
    const items = attention("admin", overview({}, { handover: { versions: 1, approved_version: 1, outdated: true } }), "/p/p1");
    expect(items.some((i) => i.text.includes("Make version 2"))).toBe(true);
  });

  it("gives the new member one clear next step", () => {
    expect(attention("incoming", overview({}), "/p/p1")[0].text).toMatch(/hasn't approved/);
    const ready = attention("incoming", overview({}, { handover: { versions: 1, approved_version: 1 } }), "/p/p1");
    expect(ready[0]).toMatchObject({ to: "/p/p1/handover", cta: "Read handover" });
  });

  it("tells the leaver only about their questions", () => {
    expect(attention("departing", overview({ open_gaps: 3, pending_review: 9 }), "/p/p1").map((i) => i.text)).toEqual([
      "3 questions only you can answer before you leave.",
    ]);
  });

  it("shows only a waiting message while the analysis runs", () => {
    const o = overview({ open_conflicts: 1 }, {});
    o.latest_job = { ...o.latest_job!, status: "running" };
    expect(attention("admin", o, "/p/p1")).toEqual([
      { tone: "wait", text: "Baton is reading the files. This page updates by itself." },
    ]);
  });
});
