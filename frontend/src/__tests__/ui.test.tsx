import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Badge, Confirm, Pager, Table } from "../components/ui";
import { CustomerForm } from "../pages/Customers";
import { api, ApiError } from "../lib/api";
import { money, title } from "../lib/format";

const wrap = (ui: React.ReactElement) => render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);

describe("format helpers", () => {
  it("formats currency and labels", () => {
    expect(money(1234)).toBe("$1,234");
    expect(money(null)).toBe("—");
    expect(title("in_progress")).toBe("In progress");
  });
});

describe("Badge", () => {
  it("renders a humanized label for a status value", () => {
    render(<Badge value="closed_won" />);
    expect(screen.getByText("Closed won")).toBeInTheDocument();
  });
});

describe("Table", () => {
  it("renders rows and reports clicks", () => {
    const onRow = vi.fn();
    render(<Table rows={[{ id: 1, name: "Acme" }]} cols={[{ key: "name", header: "Name" }]} onRow={onRow} />);
    fireEvent.click(screen.getByText("Acme"));
    expect(onRow).toHaveBeenCalledWith({ id: 1, name: "Acme" });
  });
  it("shows the empty state", () => {
    render(<Table rows={[]} cols={[{ key: "name", header: "Name" }]} />);
    expect(screen.getByText("Nothing to show")).toBeInTheDocument();
  });
});

describe("Pager", () => {
  it("disables previous on the first page and pages forward", () => {
    const onPage = vi.fn();
    render(<Pager meta={{ page: 1, size: 10, total: 25 }} onPage={onPage} />);
    expect(screen.getByLabelText("Previous page")).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Next page"));
    expect(onPage).toHaveBeenCalledWith(2);
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
  });
});

describe("Confirm", () => {
  it("calls back on confirm and cancel", () => {
    const ok = vi.fn(), no = vi.fn();
    render(<Confirm open title="Delete" body="Sure?" onConfirm={ok} onCancel={no} />);
    fireEvent.click(screen.getByText("Confirm"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(ok).toHaveBeenCalled();
    expect(no).toHaveBeenCalled();
  });
});

describe("CustomerForm validation", () => {
  it("requires a name and a valid email before saving", async () => {
    wrap(<CustomerForm open onClose={() => {}} onDone={() => {}} heading="New customer" />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "not-an-email" } });
    fireEvent.click(screen.getByText("Save customer"));
    expect(await screen.findByText("Name is required")).toBeInTheDocument();
    expect(await screen.findByText("Enter a valid email")).toBeInTheDocument();
  });
});

describe("api client", () => {
  afterEach(() => vi.restoreAllMocks());
  it("sends the CSRF header on writes and parses JSON", async () => {
    document.cookie = "vc_csrf=tok123";
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    await api("/api/x", { method: "POST", body: { a: 1 } });
    const init = f.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBe("tok123");
  });
  it("throws ApiError with the server message", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ detail: "Not found" }), { status: 404 }));
    await expect(api("/api/missing")).rejects.toMatchObject({ status: 404, message: "Not found" });
    await expect(api("/api/missing")).rejects.toBeInstanceOf(ApiError);
  });
});
