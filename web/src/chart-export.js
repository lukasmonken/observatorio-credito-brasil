const escape = value => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
const wrap = (value, width) => {
  const words = String(value ?? "").split(/\s+/), lines = [];
  let line = "";
  for (const word of words) { if ((line + " " + word).length > width && line) { lines.push(escape(line)); line = ""; } line += (line ? " " : "") + word; }
  lines.push(escape(line)); return lines.join("<br>");
};
export function exportFigure(traces, layout, meta, options = {}) {
  const width = [1000, 1200, 1600].includes(Number(options.width)) ? Number(options.width) : 1200;
  const height = [700, 900, 1100].includes(Number(options.height)) ? Number(options.height) : 900;
  const size = [12, 16, 20].includes(Number(options.fontSize)) ? Number(options.fontSize) : 16;
  const dark = options.theme === "dark", fg = dark ? "#eeeeee" : "#24292e", bg = dark ? "#151515" : "#ffffff";
  const points = traces.reduce((n, t) => n + t.y.filter(v => typeof v === "number" && Number.isFinite(v)).length, 0);
  const labels = options.labels === "all" && points > 60 ? "last" : options.labels || "none";
  const cloned = traces.map((trace, index) => {
    const t = structuredClone(trace), scatter = meta.scatter;
    const color = /^#[0-9a-f]{6}$/i.test(options.colors?.[index]) ? options.colors[index] : t.line?.color || t.marker?.color || "#285c50";
    t.visible = true; t.name = wrap(t.name || "Série", 30); t.showlegend = true;
    t.line = { ...t.line, color }; t.marker = { ...t.marker, color, size: 6 };
    t.type = !scatter && options.kind === "bar" ? "bar" : "scatter";
    if (t.type === "bar") { delete t.mode; delete t.line; delete t.connectgaps; }
    else { t.mode = scatter || options.kind === "points" ? "markers" : "lines"; t.connectgaps = false; }
    const last = t.y.findLastIndex(v => typeof v === "number" && Number.isFinite(v));
    t.text = t.y.map((v, i) => typeof v === "number" && Number.isFinite(v) && (labels === "all" || labels === "last" && i === last) ? v.toLocaleString("pt-BR", {maximumFractionDigits: 2}) : "");
    if (labels !== "none") {
      if (t.type !== "bar") t.mode += "+text";
      t.textposition = t.type === "bar" ? "outside" : "top center";
      t.textfont = {color: fg, size}; t.cliponaxis = false;
    }
    return t;
  });
  const axis = base => ({...base, range: undefined, autorange: true, fixedrange: true, visible:true, showticklabels:true, tickfont:{size}, title:{...base?.title,font:{size}}, automargin:true, gridcolor:dark?"#333":"#e5e5e5", zerolinecolor:dark?"#666":"#999"});
  const title = String(options.title || meta.title || "Observatório de Crédito Brasil").slice(0, 180);
  const subtitle = String(options.subtitle || "").slice(0, 160);
  const footer = `${meta.source} · ${meta.period || ""} · Coleta: ${meta.asOf || "não informada"}`;
  const result = {...structuredClone(layout), width, height, autosize:false, template:undefined,
    title:{text:wrap(title, 65)+(subtitle?"<br><sup>"+wrap(subtitle,80)+"</sup>":""),x:0.04,xanchor:"left",y:0.97,yanchor:"top",font:{size:size+6,color:fg}},
    font:{family:"Arial, sans-serif",size,color:fg},paper_bgcolor:bg,plot_bgcolor:bg,separators:",.",
    margin:{l:90,r:330,t:170,b:140},showlegend:true,barmode:"group",
    legend:{orientation:"v",x:1.03,y:1,xanchor:"left",yanchor:"top",font:{size:12,color:fg}},
    xaxis:axis(layout.xaxis),yaxis:axis(layout.yaxis),
    annotations:[{text:wrap(footer,100),xref:"paper",yref:"paper",x:0,y:0,yshift:-95,xanchor:"left",yanchor:"top",showarrow:false,align:"left",font:{size:11,color:fg}}],
  };
  if (layout.yaxis2) { result.yaxis2 = axis(layout.yaxis2); result.margin.r = 380; }
  return {data:cloned,layout:result,notice: options.labels === "all" && points > 60 ? "Para evitar sobreposição em mais de 60 pontos, os rótulos aparecem apenas no último valor de cada série." : ""};
}

export function attachExport(Plotly, node, traces, layout, meta) {
  if (!node.isConnected) return;
  const panel = document.createElement("details"); panel.className = "chart-export";
  const summary = document.createElement("summary"); summary.textContent = "Personalizar e baixar gráfico"; panel.append(summary);
  const form = document.createElement("div"); form.className = "export-controls"; panel.append(form);
  const fields = {};
  function field(key, label, values, initial, type="text") {
    const wrapper = document.createElement("label"); wrapper.textContent=label;
    const control = document.createElement(values ? "select" : "input"); control.setAttribute("aria-label",label);
    control.dataset.exportField=key;
    if(values) for(const [value,text] of values) { const option=document.createElement("option");option.value=value;option.textContent=text;control.append(option); }
    else {control.type=type;control.maxLength=key==="title"?180:160;}
    control.value=initial; wrapper.append(control);form.append(wrapper);fields[key]=control;
  }
  field("title","Título",null,meta.title);
  field("subtitle","Subtítulo",null,"");
  field("kind","Tipo de gráfico",meta.scatter?[["points","Dispersão"]]:[["line","Linhas"],["bar","Barras"],["points","Pontos"]],meta.scatter?"points":"line");
  field("labels","Rótulos de valores",[["none","Sem rótulos"],["last","Último valor"],["all","Todos (até 60 pontos)"]],"last");
  field("theme","Fundo",[["light","Claro"],["dark","Escuro"]],"light");
  field("width","Largura (px)",[[1000,"1000"],[1200,"1200"],[1600,"1600"]],1200);
  field("height","Altura (px)",[[700,"700"],[900,"900"],[1100,"1100"]],900);
  field("fontSize","Tamanho do texto",[[12,"12"],[16,"16"],[20,"20"]],16);
  field("format","Formato da imagem",[["png","PNG"],["svg","SVG (vetorial)"]],"png");
  field("scale","Resolução PNG",[[1,"Normal (1×)"],[2,"Alta (2×)"]],1);
  traces.forEach((t,i)=>field("color"+i,"Cor · "+(t.name||"Série "+(i+1)),null,t.line?.color||t.marker?.color||"#285c50","color"));
  const help=document.createElement("p");help.className="note";help.textContent="A imagem inclui todas as séries e o período selecionados nos filtros, sem aplicar o zoom ou ocultações temporárias da legenda. Fonte, data da coleta e unidades acompanham o arquivo. Rótulos usam até duas casas decimais; os dados não são arredondados.";
  const button=document.createElement("button");button.type="button";button.textContent="Atualizar prévia";
  const status=document.createElement("p");status.setAttribute("role","status");
  const preview=document.createElement("img");preview.className="export-preview";preview.alt="Prévia do arquivo para download";preview.hidden=true;
  const link=document.createElement("a");link.textContent="Baixar imagem";link.className="export-download";link.hidden=true;
  panel.append(help,button,status,preview,link);node.after(panel);
  let version=0;
  form.addEventListener("input",()=>{version++;link.hidden=true;preview.hidden=true;status.textContent="Atualize a prévia para aplicar as alterações.";});
  button.onclick=async()=>{
    const current=++version;button.disabled=true;link.hidden=true;status.textContent="Preparando imagem…";
    const target=document.createElement("div");target.style.cssText="position:absolute;left:-20000px;top:0;";document.body.append(target);
    try{
      const options=Object.fromEntries(Object.entries(fields).map(([key,input])=>[key,input.value]));options.colors=traces.map((_,i)=>options["color"+i]);
      const figure=exportFigure(traces,layout,meta,options);
      await Plotly.newPlot(target,figure.data,figure.layout,{staticPlot:true,displayModeBar:false});
      const url=await Plotly.toImage(target,{format:options.format,width:figure.layout.width,height:figure.layout.height,scale:options.format==="png"?Number(options.scale):1});
      if(current!==version || !panel.isConnected)return;
      preview.src=url;preview.hidden=false;link.href=url;link.download="observatorio-grafico."+options.format;link.hidden=false;
      status.textContent=figure.notice || "Prévia atualizada. O download contém exatamente esta imagem.";
    }catch{status.textContent="Não foi possível gerar a imagem. Tente novamente.";}finally{Plotly.purge(target);target.remove();button.disabled=false;}
  };
}
