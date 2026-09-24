import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import Shortener from "@/components/Shortener";
import { ApiError, shortenUrl } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  shortenUrl: vi.fn(),
}));
const mockShorten = vi.mocked(shortenUrl);

const RESULT = { short_code: "aB3xY9", short_url: "http://localhost:8000/aB3xY9" };

beforeEach(() => {
  mockShorten.mockReset();
});

function setup() {
  const user = userEvent.setup();
  render(<Shortener />);
  return {
    user,
    input: screen.getByLabelText(/url to shorten/i),
    submit: screen.getByRole("button", { name: /shorten/i }),
  };
}

test("C1: renders a labelled input and a disabled button while empty", () => {
  const { input, submit } = setup();
  expect(input).toBeInTheDocument();
  expect(submit).toBeDisabled();
});

test("C2: submits the normalized URL", async () => {
  mockShorten.mockResolvedValue(RESULT);
  const { user, input, submit } = setup();

  await user.type(input, "example.com");
  await user.click(submit);

  expect(mockShorten).toHaveBeenCalledWith("https://example.com");
});

test("C3: pressing Enter submits the form", async () => {
  mockShorten.mockResolvedValue(RESULT);
  const { user, input } = setup();

  await user.type(input, "https://example.com{Enter}");

  expect(mockShorten).toHaveBeenCalledTimes(1);
});

test("C4: shows the loading state and blocks double submits", async () => {
  mockShorten.mockReturnValue(new Promise(() => {}));
  const { user, input, submit } = setup();

  await user.type(input, "https://example.com");
  await user.click(submit);

  expect(submit).toBeDisabled();
  expect(submit).toHaveTextContent("Shortening…");
  await user.click(submit);
  await user.type(input, "{Enter}");
  expect(mockShorten).toHaveBeenCalledTimes(1);
});

test("C5: shows the short URL as a safe external link", async () => {
  mockShorten.mockResolvedValue(RESULT);
  const { user, input, submit } = setup();

  await user.type(input, "https://example.com");
  await user.click(submit);

  const link = await screen.findByRole("link", { name: RESULT.short_url });
  expect(link).toHaveAttribute("href", RESULT.short_url);
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
});

test("C6: copies the short URL and resets the label after 2s", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockShorten.mockResolvedValue(RESULT);
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  render(<Shortener />);
  const writeText = vi.spyOn(navigator.clipboard, "writeText");

  await user.type(screen.getByLabelText(/url to shorten/i), "https://example.com");
  await user.click(screen.getByRole("button", { name: /shorten/i }));
  await user.click(await screen.findByRole("button", { name: "Copy" }));

  expect(writeText).toHaveBeenCalledWith(RESULT.short_url);
  expect(screen.getByRole("button", { name: "Copied!" })).toBeInTheDocument();

  act(() => vi.advanceTimersByTime(2000));
  expect(screen.getByRole("button", { name: "Copy" })).toBeInTheDocument();
});

test("C7: shows a message when copying fails", async () => {
  mockShorten.mockResolvedValue(RESULT);
  const { user, input, submit } = setup();
  vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("denied"));

  await user.type(input, "https://example.com");
  await user.click(submit);
  await user.click(await screen.findByRole("button", { name: "Copy" }));

  expect(await screen.findByRole("button", { name: "Copy failed" })).toBeInTheDocument();
});

test("C8: rejects invalid input without calling the API", async () => {
  const { user, input, submit } = setup();

  await user.type(input, "not a url");
  await user.click(submit);

  expect(screen.getByRole("alert")).toHaveTextContent(/valid URL/i);
  expect(mockShorten).not.toHaveBeenCalled();
});

test("C9: shows the API error and keeps the input", async () => {
  mockShorten.mockRejectedValue(new ApiError("invalid_url", "That doesn't look like a valid URL."));
  const { user, input, submit } = setup();

  await user.type(input, "https://example.com");
  await user.click(submit);

  expect(await screen.findByRole("alert")).toHaveTextContent("That doesn't look like a valid URL.");
  expect(input).toHaveValue("https://example.com");
});

test("C10: shows a generic message for unexpected errors", async () => {
  mockShorten.mockRejectedValue(new Error("boom"));
  const { user, input, submit } = setup();

  await user.type(input, "https://example.com");
  await user.click(submit);

  expect(await screen.findByRole("alert")).toHaveTextContent(/unexpected error/i);
});

test("C11: a successful retry clears the previous error", async () => {
  mockShorten
    .mockRejectedValueOnce(new ApiError("network", "Can't reach the server."))
    .mockResolvedValueOnce(RESULT);
  const { user, input, submit } = setup();

  await user.type(input, "https://example.com");
  await user.click(submit);
  expect(await screen.findByRole("alert")).toBeInTheDocument();

  await user.click(submit);
  expect(await screen.findByRole("link", { name: RESULT.short_url })).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
