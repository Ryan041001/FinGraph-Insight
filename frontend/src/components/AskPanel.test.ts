import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { askGraphRag } from "../api/qa";
import AskPanel from "./AskPanel.vue";

vi.mock("../api/qa", () => ({
  askGraphRag: vi.fn(),
}));

const askGraphRagMock = vi.mocked(askGraphRag);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AskPanel", () => {
  it("submits a productized follow-up question and shows only the answer", async () => {
    askGraphRagMock.mockResolvedValue({
      answer: "该企业与关联机构存在融资关系，建议结合证据链复核。",
      raw_payload: { cypher: "MATCH (n)" },
    });

    const wrapper = mount(AskPanel, {
      props: {
        companyName: "浙江数科控股有限公司",
      },
    });

    await wrapper
      .find("textarea")
      .setValue("这家公司有哪些需要关注的关联关系？");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(askGraphRagMock).toHaveBeenCalledWith(
      "浙江数科控股有限公司：这家公司有哪些需要关注的关联关系？",
    );
    expect(wrapper.text()).toContain("该企业与关联机构存在融资关系");
    expect(wrapper.text()).not.toContain("MATCH");
    expect(wrapper.text()).not.toContain("raw_payload");
  });

  it("renders safe styled inline html in the answer", async () => {
    askGraphRagMock.mockResolvedValue({
      answer: [
        "该企业当前证据如下：",
        '<div style="border: 1px solid #bae6fd; background: #f0f9ff;">',
        '<strong style="color: #075985;">审计证据摘要</strong>',
        '<table style="border-collapse: collapse;">',
        '<tbody><tr><td style="border: 1px solid #bae6fd;">星河数据</td></tr></tbody>',
        "</table>",
        "</div>",
      ].join(""),
    });

    const wrapper = mount(AskPanel, {
      props: {
        companyName: "浙江数科控股有限公司",
      },
    });

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    const card = wrapper.find(".answer-content div");
    expect(card.exists()).toBe(true);
    expect(card.attributes("style")).toContain("border");
    expect(wrapper.find(".answer-content table").exists()).toBe(true);
    expect(wrapper.find(".answer-content").html()).not.toContain("qa-evidence-table");
    expect(wrapper.text()).toContain("星河数据");
  });

  it("renders marked and entity-encoded html fragments", async () => {
    askGraphRagMock.mockResolvedValue({
      answer:
        '<!-- html-render-start -->&lt;div style="border: 1px solid #bae6fd; padding: 8px;"&gt;<strong>实时预览</strong>&lt;/div&gt;<!-- html-render-end -->',
    });

    const wrapper = mount(AskPanel, {
      props: {
        companyName: "浙江数科控股有限公司",
      },
    });

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    const card = wrapper.find(".answer-content div");
    expect(card.exists()).toBe(true);
    expect(card.attributes("style")).toContain("border");
    expect(wrapper.text()).toContain("实时预览");
    expect(wrapper.text()).not.toContain("html-render-start");
    expect(wrapper.find(".answer-content").html()).not.toContain("&lt;div");
  });

  it("removes unsafe html from rendered answers", async () => {
    askGraphRagMock.mockResolvedValue({
      answer:
        '<div style="border: 1px solid #bae6fd;" class="qa-insight-card" onclick="alert(1)"><strong>风险卡</strong><script>alert(1)</script></div>',
    });

    const wrapper = mount(AskPanel, {
      props: {
        companyName: "浙江数科控股有限公司",
      },
    });

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("风险卡");
    expect(wrapper.html()).not.toContain("<script");
    expect(wrapper.find(".answer-content").html()).not.toContain("qa-insight-card");
    expect(wrapper.html()).not.toContain("onclick");
  });

  it("shows a business-friendly retry message when the question fails", async () => {
    askGraphRagMock.mockRejectedValue(new Error("backend stack trace"));

    const wrapper = mount(AskPanel, {
      props: {
        companyName: "浙江数科控股有限公司",
      },
    });

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("未能完成本次追问，请稍后重试。");
    expect(wrapper.text()).not.toContain("backend stack trace");
  });

  it("treats a response without an answer as an unavailable result", async () => {
    askGraphRagMock.mockResolvedValue({ citations: [] });

    const wrapper = mount(AskPanel, {
      props: {
        companyName: "浙江数科控股有限公司",
      },
    });

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("未能完成本次追问，请稍后重试。");
    expect(wrapper.text()).not.toContain("已生成回答");
  });

  it("does not render engineering content returned as an answer", async () => {
    askGraphRagMock.mockResolvedValue({ answer: "MATCH (n) RETURN n" });

    const wrapper = mount(AskPanel, {
      props: {
        companyName: "浙江数科控股有限公司",
      },
    });

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("未能完成本次追问，请稍后重试。");
    expect(wrapper.text()).not.toContain("MATCH");
  });

  it.each([
    "TypeError: failed to read property",
    '{"answer":"风险摘要","citations":[]}',
    "根据示例图谱，红杉资本参与了示例科技的B轮融资。",
    "该结果仅用于课程项目演示。",
  ])("does not render unsafe backend answer text: %s", async (unsafeAnswer) => {
    askGraphRagMock.mockResolvedValue({ answer: unsafeAnswer });

    const wrapper = mount(AskPanel, {
      props: {
        companyName: "浙江数科控股有限公司",
      },
    });

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("未能完成本次追问，请稍后重试。");
    expect(wrapper.text()).not.toContain(unsafeAnswer);
  });

  it("ignores an older answer after the company changes", async () => {
    let resolveFirst!: (value: Record<string, unknown>) => void;
    const firstAnswer = new Promise<Record<string, unknown>>((resolve) => {
      resolveFirst = resolve;
    });
    askGraphRagMock.mockReturnValueOnce(firstAnswer);

    const wrapper = mount(AskPanel, {
      props: {
        companyName: "浙江数科控股有限公司",
      },
    });

    await wrapper.find("form").trigger("submit");
    await wrapper.setProps({ companyName: "杭州风控科技有限公司" });

    resolveFirst({ answer: "旧企业的追问回答。" });
    await flushPromises();

    expect(wrapper.text()).not.toContain("旧企业的追问回答。");
  });

  it("does not submit duplicate questions while loading", async () => {
    askGraphRagMock.mockReturnValue(new Promise(() => {}));

    const wrapper = mount(AskPanel, {
      props: {
        companyName: "浙江数科控股有限公司",
      },
    });

    await wrapper.find("form").trigger("submit");
    await wrapper.find("form").trigger("submit");

    expect(askGraphRagMock).toHaveBeenCalledTimes(1);
  });
});
