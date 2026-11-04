import Plotly from "plotly.js-basic-dist-min";
import { finite } from "./model.js";
const layout = {
  font: { family: "Times New Roman, Times, serif", size: 14, color: "#24292e" },
  paper_bgcolor: "#fff",
  plot_bgcolor: "#fff",
  margin: { l: 55, r: 30, t: 15, b: 65 },
  height: 350,
  separators: ",.",
  hovermode: "x unified",
  legend: { orientation: "h", y: -0.22, font: { size: 12 } },
  xaxis: {
    showgrid: false,
    linecolor: "#dfe3e6",
    tickformat: "%m/%Y",
    automargin: true,
  },
  yaxis: { gridcolor: "#edf0f2", zerolinecolor: "#dfe3e6", automargin: true },
};
export async function drawLines(node, series, units) {
  if (!node.isConnected) return;
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
    line: { color: s.color, width: 2 },
    yaxis: s.unit !== units[0] ? "y2" : "y",
    hovertemplate:
      "%{x|%m/%Y}<br>%{y:,.3f} " + s.unit + "<extra>%{fullData.name}</extra>",
  }));
  await Plotly.newPlot(
    node,
    traces,
    {
      ...layout,
      height: units.length > 1 ? 430 : 350,
      yaxis: { ...layout.yaxis, title: { text: units[0] } },
      yaxis2:
        units.length > 1
          ? {
              title: { text: units[1] },
              overlaying: "y",
              side: "right",
              showgrid: false,
              automargin: true,
            }
          : undefined,
    },
    { responsive: true, displaylogo: false, scrollZoom: false },
  );
}
export async function drawScatter(node, pairs, xunit, yunit) {
  if (!node.isConnected) return;
  await Plotly.newPlot(
    node,
    [
      {
        type: "scatter",
        mode: "markers",
        x: pairs.map((p) => p.x),
        y: pairs.map((p) => p.y),
        text: pairs.map((p) => p.date.slice(0, 7)),
        marker: { color: "#285c50", size: 6, opacity: 0.75 },
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
