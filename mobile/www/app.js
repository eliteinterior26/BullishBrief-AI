const $ = id => document.getElementById(id);
let companyData = null;
let activeTab = "overview";

function fmt(v, suffix="") {
  if (v === null || v === undefined || v === "") return "Unavailable";
  if (typeof v === "number") return v.toLocaleString("en-IN",{maximumFractionDigits:2}) + suffix;
  return String(v);
}
function money(v) { return v == null ? "Unavailable" : "₹" + Number(v).toLocaleString("en-IN",{maximumFractionDigits:2}); }
function metric(label,value){return `<div class="metric"><span>${label}</span><b>${value}</b></div>`}
function row(label,value){return `<div class="row"><span>${label}</span><b>${value ?? "Unavailable"}</b></div>`}
function setMessage(text){$("message").textContent=text;$("message").classList.remove("hidden")}
async function loadMarket(){
  try{
    const r=await fetch("/api/market");const m=await r.json();
    $("market").textContent=m.status;
    $("clock").textContent=m.time_ist+" · "+m.reason;
  }catch(e){$("market").textContent="STATUS UNAVAILABLE"}
}
async function analyse(){
  const symbol=$("symbol").value.trim();
  if(!symbol){setMessage("Enter a company symbol first.");return}
  $("company").classList.add("hidden");setMessage("Loading company research…");
  $("searchBtn").disabled=true;
  try{
    const r=await fetch("/api/company/"+encodeURIComponent(symbol));
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail || "Unable to load this company.");
    companyData=d;
    $("companyName").textContent=d.name+" ("+d.symbol.replace(".NS","")+")";
    $("companyMeta").textContent=[d.sector,d.industry].filter(Boolean).join(" · ") || "Company details";
    $("verdict").textContent=d.research_verdict;
    $("overall").textContent=d.overall_score == null ? "N/A" : d.overall_score+"/10";
    $("message").classList.add("hidden");$("company").classList.remove("hidden");
    renderTab();
  }catch(e){setMessage(e.message+" Yahoo Finance may not have coverage for this symbol.")}
  finally{$("searchBtn").disabled=false}
}
function renderTab(){
  const d=companyData, f=d.fundamentals, t=d.technicals, panel=$("panel");
  if(!d)return;
  if(activeTab==="overview"){
    panel.innerHTML=`<h3>Company Overview</h3><div class="metric-grid">
      ${metric("Latest price",t.available?money(t.price):"Unavailable")}
      ${metric("Daily change",t.available?fmt(t.change_pct,"%"):"Unavailable")}
      ${metric("Market cap",f.market_cap?money(f.market_cap):"Unavailable")}
      ${metric("Sector",d.sector||"Unavailable")}
      ${metric("Industry",d.industry||"Unavailable")}
      ${metric("Employees",fmt(f.employees))}
    </div><h3>About the company</h3><p>${d.fundamentals.description||"Company description is unavailable from the data provider."}</p>
    ${row("Website",f.website?`<a href="${f.website}" target="_blank" rel="noopener">${f.website}</a>`:"Unavailable")}
    <p class="note">${d.data_note}</p>`;
  } else if(activeTab==="fundamentals"){
    panel.innerHTML=`<h3>Fundamentals</h3><div class="metric-grid">
      ${metric("Revenue",money(f.revenue))}${metric("Revenue growth",fmt(f.revenue_growth==null?null:f.revenue_growth*100,"%"))}
      ${metric("Earnings growth",fmt(f.earnings_growth==null?null:f.earnings_growth*100,"%"))}
      ${metric("Trailing EPS",fmt(f.trailing_eps))}${metric("P/E",fmt(f.trailing_pe))}${metric("Price / Book",fmt(f.price_to_book))}
      ${metric("ROE",fmt(f.return_on_equity==null?null:f.return_on_equity*100,"%"))}${metric("Profit margin",fmt(f.profit_margin==null?null:f.profit_margin*100,"%"))}
      ${metric("Debt / Equity",fmt(f.debt_to_equity))}${metric("Beta",fmt(f.beta))}
    </div><p class="note">Valuation should be compared with companies in the same sector. Missing data is not treated as a positive score.</p>`;
  } else if(activeTab==="technical"){
    panel.innerHTML=`<h3>Technical Analysis</h3><div class="metric-grid">
      ${metric("Price",t.available?money(t.price):"Unavailable")}${metric("RSI (14)",fmt(t.rsi_14))}
      ${metric("EMA 20",money(t.ema20))}${metric("EMA 50",money(t.ema50))}
      ${metric("EMA 200",money(t.ema200))}${metric("Technical score",t.available?t.technical_score+"/10":"Unavailable")}
      ${metric("MACD",fmt(t.macd))}${metric("MACD signal",fmt(t.macd_signal))}
    </div>${row("Last data candle",t.data_timestamp||"Unavailable")}`;
  } else if(activeTab==="dividends"){
    const divs=d.dividend_history||[];
    panel.innerHTML=`<h3>Dividend Information</h3><div class="metric-grid">
      ${metric("Dividend yield",fmt(f.dividend_yield==null?null:f.dividend_yield*100,"%"))}
      ${metric("Ex-dividend date",f.ex_dividend_date?new Date(f.ex_dividend_date*1000).toLocaleDateString("en-IN"):"Unavailable")}
    </div><h4>Recent dividend history</h4>${divs.length?divs.map(x=>row(x.date,money(x.amount))).join(""):"<p>Dividend history unavailable from Yahoo Finance.</p>"}`;
  } else if(activeTab==="news"){
    const news=d.news||[];
    panel.innerHTML=`<h3>Latest available news</h3>${news.length?news.map(n=>`<div class="news-item"><a href="${n.link||"#"}" target="_blank" rel="noopener">${n.title}</a><small>${n.publisher||"Publisher unavailable"} · ${n.published||""}</small></div>`).join(""):"<p>No company news was returned by the data provider.</p>"}`;
  } else if(activeTab==="scores"){
    const labels={earnings:"Earnings",fundamentals:"Fundamentals",relative_valuation:"Relative Valuation",risk:"Risk",price_momentum:"Price Momentum"};
    const s=d.scores||{};
    panel.innerHTML=`<h3>Five-category scorecard</h3>${Object.entries(labels).map(([k,label])=>row(label,s[k]==null?"Insufficient data":s[k]+"/10")).join("")}
      <div class="row"><span><b>Overall score</b></span><b>${d.overall_score==null?"Not calculated":d.overall_score+"/10"}</b></div>
      <p>${d.score_note}</p><h4>Analyst rating data</h4>${Object.keys(d.analyst_recommendations||{}).length?Object.entries(d.analyst_recommendations).map(([k,v])=>row(k,fmt(v))).join(""):"<p>Analyst recommendation data unavailable.</p>"}
      <p class="note">The research verdict is a heuristic summary, not a broker analyst consensus or a personalized buy/sell instruction.</p>`;
  }
}
$("searchBtn").addEventListener("click",analyse);
$("symbol").addEventListener("keydown",e=>{if(e.key==="Enter")analyse()});
document.querySelectorAll(".tab").forEach(btn=>btn.addEventListener("click",()=>{
  document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));
  btn.classList.add("active");activeTab=btn.dataset.tab;renderTab();
}));
loadMarket();setInterval(loadMarket,15000);
