import Plotly from "plotly.js-basic-dist-min";
import { finite } from "./model.js";
function chartLayout() {
  const dark = document.documentElement.dataset.theme === "dark";
  return {
  font: { family: "-apple-system, BlinkMacSystemFont, system-ui, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif", size: 14, color: dark ? "#e8e8e8" : "#24292e" },
  paper_bgcolor: dark ? "#151515" : "#fff",
  plot_bgcolor: dark ? "#151515" : "#fff",
  margin: { l: 55, r: 30, t: 15, b: 65 },
  height: 350,
  separators: ",.",
  hovermode: "x unified",
  legend: { orientation: "h", y: -0.22, font: { size: 12 } },
  xaxis: {
    showgrid: false,
    linecolor: dark ? "#444" : "#dfe3e6",
    tickformat: "%m/%Y",
    automargin: true,
  },
  yaxis: { gridcolor: dark ? "#303030" : "#edf0f2", zerolinecolor: dark ? "#444" : "#dfe3e6", automargin: true },
  hoverlabel: { bgcolor: dark ? "#242424" : "#fff", bordercolor: dark ? "#555" : "#ddd", font: { color: dark ? "#eee" : "#24292e" } },
};
}
function themeColor(color) {
  if (document.documentElement.dataset.theme !== "dark" || !/^#[0-9a-f]{6}$/i.test(color)) return color;
  return "#" + color.slice(1).match(/../g).map((v) => Math.round(parseInt(v, 16) * .6 + 255 * .4).toString(16).padStart(2, "0")).join("");
}
export async function drawLines(node, series, units) {
  if (!node.isConnected) return;
  const layout = chartLayout();
  if (!series.some((s) => s.rows.some((r) => finite(r[s.metric])))) {
    node.textContent =
      "Sem valores disponíveis para essa transformação no período.";
    return;
  }
  const traces = series.map((s) => ({
    type: "scatter",
    mode: "lines",
    name: s.name,
    x: s.rows.map((r) => r.date),
    y: s.rows.map((r) => r[s.metric] ?? null),
    connectgaps: false,
    line: { color: themeColor(s.color), width: 2 },
    yaxis: s.unit !== units[0] ? "y2" : "y",
    hovertemplate:
      "%{x|%m/%Y}<br>%{y:,.3f} " + s.unit + "<extra>%{fullData.name}</extra>",
  }));
  node.replaceChildren();
  await Plotly.newPlot(
    node,
    traces,
    {
      ...layout,
      height: units.length > 1 ? 430 : 350,
      yaxis: { ...layout.yaxis, title: { text: units[0] } },
      ...(units.length > 1
        ? {
            yaxis2: {
              title: { text: units[1] },
              overlaying: "y",
              side: "right",
              showgrid: false,
              automargin: true,
            },
          }
        : {}),
    },
    { responsive: true, displaylogo: false, scrollZoom: false },
  );
}
export async function drawScatter(node, pairs, xunit, yunit) {
  if (!node.isConnected) return;
  const layout = chartLayout();
  node.replaceChildren();
  await Plotly.newPlot(
    node,
    [
      {
        type: "scatter",
        mode: "markers",
        x: pairs.map((p) => p.x),
        y: pairs.map((p) => p.y),
        text: pairs.map((p) => p.date.slice(0, 7)),
        marker: { color: themeColor("#285c50"), size: 6, opacity: 0.75 },
        hovertemplate: "%{text}<br>X: %{x:,.3f}<br>Y: %{y:,.3f}<extra></extra>",
      },
    ],
    {
      ...layout,
      hovermode: "closest",
      height: 400,
      xaxis: {
        ...layout.xaxis,
        type: "linear",
        tickformat: undefined,
        title: { text: "X · " + xunit },
      },
      yaxis: { ...layout.yaxis, title: { text: "Y · " + yunit } },
    },
    { responsive: true, displaylogo: false },
  );
}
export function dispose(node) {
  if (node.classList.contains("js-plotly-plot")) Plotly.purge(node);
}
