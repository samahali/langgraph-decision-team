import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "@/components/error-boundary";

afterEach(() => vi.restoreAllMocks());

describe("ErrorBoundary", () => {
  it("renders a recovery screen after a child render failure", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const Broken = () => {
      throw new Error("render failed");
    };

    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Reload page" })).toBeEnabled();
  });
});
