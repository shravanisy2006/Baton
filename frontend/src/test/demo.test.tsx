import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

vi.mock("../lib/api", () => ({
  API_URL: "http://api.test",
  api: {
    get: vi.fn(async () => ({
      accounts: [
        { role: "reviewer", name: "Priya Nair", email: "reviewer@baton.demo" },
        { role: "incoming", name: "Karan Mehta", email: "karan@baton.demo" },
      ],
      password: "Baton-Judge-2026",
      private: true,
      kept_hours: 24,
    })),
    post: vi.fn(),
  },
  getToken: () => null,
  setToken: () => undefined,
}));

import JudgeAccounts from "../components/JudgeAccounts";
import AuthForm from "../components/AuthForm";
import { SessionProvider } from "../lib/session";

describe("demo sign-ins", () => {
  it("shows the published credentials and says each sign-in is private", async () => {
    render(
      <SessionProvider>
        <MemoryRouter>
          <JudgeAccounts />
        </MemoryRouter>
      </SessionProvider>,
    );
    expect(await screen.findByText("reviewer@baton.demo")).toBeInTheDocument();
    expect(screen.getByText("Baton-Judge-2026")).toBeInTheDocument();
    expect(screen.getByText(/your own private copy/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in as Karan Mehta" })).toBeEnabled();
  });
});

describe("sign-in form", () => {
  it("offers password reset when signing in", () => {
    render(
      <SessionProvider>
        <MemoryRouter>
          <AuthForm initialMode="signin" onDone={() => undefined} />
        </MemoryRouter>
      </SessionProvider>,
    );
    expect(screen.getByRole("link", { name: "Forgot your password?" })).toHaveAttribute("href", "/forgot-password");
  });
});
