import { describe, expect, it } from "vitest";

import type { LaunchCrewAgentStatus } from "@/components/workspace/ecom-launch/launch-crew-activity-model";
import {
  frameForAgent,
  type AgentFrame,
} from "@/components/workspace/ecom-launch/pixel-office";

function frame(status: LaunchCrewAgentStatus, selected = false): AgentFrame {
  return frameForAgent({ status, selected });
}

describe("pixel office agent frames", () => {
  it("maps live agent statuses to sprite-ready frames", () => {
    expect(frame("idle")).toBe("idle");
    expect(frame("idle", true)).toBe("talking");
    expect(frame("working")).toBe("working");
    expect(frame("searching")).toBe("working");
    expect(frame("reading")).toBe("working");
    expect(frame("writing")).toBe("working");
    expect(frame("done")).toBe("complete");
    expect(frame("delivered")).toBe("complete");
    expect(frame("error")).toBe("error");
  });
});
