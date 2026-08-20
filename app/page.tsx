const repoUrl = "https://github.com/jackli0508-ship-it/tianyu2fm-skills";

const skills = [
  {
    index: "01",
    phase: "BEFORE RECORDING",
    name: "TIANYU2FM Scripter",
    slug: "tianyu2fm-scripter",
    tagline: "把嘉宾的作品，变成真正值得追问的问题。",
    summary: "结合嘉宾著作、访谈与已有提纲，寻找尚未被问透的逻辑，把观点转化为有出处、可延展的播客问题。",
    input: "嘉宾信息、著作与文章、现有提纲、节目方向",
    output: "延续性追问、核心观点转化、三段式采访结构、逐题出处",
    owns: "前期研究、问题生成、提纲重排、出处核验",
    notOwns: "虚构嘉宾观点；未经授权改写原稿",
    signal: "RESEARCH → QUESTIONS",
  },
  {
    index: "02",
    phase: "AFTER RECORDING",
    name: "Highlight Selector",
    slug: "tianyu2fm-highlight-selector",
    tagline: "从整期对谈里，找到一开口就让人停下来的十句话。",
    summary: "完整通读带时间码的 transcript，从传播力、独立可懂性和认知张力出发，挑选忠于原话的片头高光。",
    input: "完整 transcript、SRT、VTT 或带时间码字幕稿",
    output: "按吸引力排序的 10 条原文金句与可核对时间码",
    owns: "金句筛选、类别判断、原文复核、剪辑边界定位",
    notOwns: "改写金句；估算或编造时间码；承诺“必火”",
    signal: "TRANSCRIPT → MOMENTS",
  },
  {
    index: "03",
    phase: "VIDEO EDIT",
    name: "FCP Multicam AutoCut",
    slug: "fcp-autocut-multicam",
    tagline: "让双人播客的多机位粗剪，先自动成立。",
    summary: "把 Final Cut Pro 双人 multicam FCPXML 转成以说话人为主、兼顾反应镜头和双人全景的可逆粗剪。",
    input: "Final Cut Pro 导出的 .fcpxml 或 .fcpxmld",
    output: "新的可导入 FCPXML、镜头切换统计与验证结果",
    owns: "说话人机位、反应镜头、密集互动全景、非说话麦克风静音",
    notOwns: "覆盖源文件；直接修改 FCP Library；语义级 ASR 判断",
    signal: "FCPXML → ROUGH CUT",
  },
  {
    index: "04",
    phase: "VIDEO EDIT",
    name: "TIANYU2FM FCP Chapter Tool",
    slug: "tianyu2fm-fcp-chapter-tool",
    tagline: "把一整期对谈的结构，直接写回 Final Cut Pro 时间线。",
    summary: "完整理解带时间码对话，识别真正开启独立讨论的话题转折，并把问句式章节标题写成覆盖对应段落的 FCP title blocks。",
    input: "Final Cut Pro 导出的 .fcpxml 或 .fcpxmld、完整节目时间线",
    output: "带连续章节标题块的新 FCPXML、章节清单与 Apple DTD 验证结果",
    owns: "全文转写、话题分段、标题提炼、精剪时间线映射与 FCPXML 验证",
    notOwns: "覆盖源文件；把追问误判为新章节；直接修改 FCP Library",
    signal: "TIMELINE → CHAPTERS",
  },
  {
    index: "05",
    phase: "VISUAL STORY",
    name: "Collect B-roll",
    slug: "collect-broll",
    tagline: "为抽象观点找到真实、可追溯、能剪进去的画面。",
    summary: "围绕多场景 brief 搜索真实网络素材，逐帧筛选、下载、去重、整理，并保留完整来源与版权状态记录。",
    input: "场景清单、画面要求、数量、清晰度与排除项",
    output: "分类视频素材包、contact sheet、sources.jsonl 与质量报告",
    owns: "跨平台搜寻、视觉筛选、下载验证、去重与来源记录",
    notOwns: "生成式替代素材；绕过 DRM；把公开等同于可商用",
    signal: "BRIEF → REAL FOOTAGE",
  },
  {
    index: "06",
    phase: "PUBLISHING",
    name: "Title Generator",
    slug: "tianyu2fm-title-generator",
    tagline: "把一期节目的核心张力，压进一个让人想点开的标题。",
    summary: "从完整 transcript 提炼议题，再研究 B 站与小红书同类高互动内容，生成兼顾点击欲和节目调性的中文标题。",
    input: "完整 transcript、嘉宾信息、节目气质与平台方向",
    output: "20 个主方案、10 个探索方案与标题研究依据",
    owns: "内容地图、平台调研、标题生成、硬约束校验与排序",
    notOwns: "只读摘要就命名；照抄爆款；堆叠多个钩子",
    signal: "EPISODE → CLICK",
  },
];

const workflow = [
  ["PREP", "提问", "Scripter"],
  ["TAPE", "录制", "Conversation"],
  ["FIND", "选金句", "Highlight"],
  ["CUT", "剪画面", "AutoCut + Chapters + B-roll"],
  ["SHIP", "发布", "Title Generator"],
];

export default function Home() {
  return (
    <main>
      <header className="site-header">
        <a className="brand-lockup" href="#top" aria-label="TIANYU2FM Skill Index 首页">
          <span className="brand-mark">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/t2fm-silhouette-favicon.png" alt="" width="40" height="40" />
          </span>
          <span><strong>TIANYU2FM</strong><small>SKILL INDEX / 2026</small></span>
        </a>
        <nav aria-label="主导航">
          <a href="#system">制作流程</a>
          <a href="#skills">全部 Skills</a>
          <a className="github-link" href={repoUrl} target="_blank" rel="noreferrer">GitHub ↗</a>
        </nav>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow"><span /> OPEN-SOURCE PODCAST TOOLKIT</p>
          <h1>把一场对谈，<em>变成一套内容系统。</em></h1>
          <p className="hero-lede">从嘉宾研究、问题设计，到高光筛选、视频粗剪、B-roll 与标题生成。</p>
          <div className="hero-actions">
            <a className="primary-button" href="#skills">浏览全部 Skills ↓</a>
            <a className="text-link" href={repoUrl} target="_blank" rel="noreferrer">GitHub 公开仓库 ↗</a>
          </div>
        </div>
        <div className="hero-stats" aria-label="项目摘要">
          <div><strong>06</strong><span>个生产工具</span></div>
          <div><strong>01</strong><span>条完整工作流</span></div>
          <div><strong>OPEN</strong><span>全部公开源码</span></div>
        </div>
      </section>

      <section className="system-section" id="system">
        <div className="section-intro">
          <p className="eyebrow"><span /> THE OPERATING SYSTEM</p>
          <h2>一条从「为什么聊」到「为什么点开」的生产线。</h2>
          <p>每个 Skill 只负责自己最擅长的一段。输入清楚，交接清楚，边界也清楚。</p>
        </div>
        <div className="workflow" role="list" aria-label="播客制作流程">
          {workflow.map(([code, action, tool], index) => (
            <div className="workflow-step" role="listitem" key={code}>
              <div className="step-top"><span>{String(index + 1).padStart(2, "0")}</span><i /></div>
              <b>{code}</b><strong>{action}</strong><small>{tool}</small>
            </div>
          ))}
        </div>
      </section>

      <section className="skills-section" id="skills">
        <div className="section-intro compact">
          <p className="eyebrow"><span /> SELECT A MODULE</p>
          <h2>你现在卡在哪一步？</h2>
          <p>不用从头跑完整条流程。找到当前的输入，调用对应模块。</p>
        </div>
        <div className="skill-list">
          {skills.map((skill) => (
            <article className="skill-card" key={skill.slug}>
              <div className="skill-rail"><span>{skill.index}</span><small>{skill.phase}</small></div>
              <div className="skill-main">
                <p className="skill-signal">{skill.signal}</p>
                <h3>{skill.name}</h3><h4>{skill.tagline}</h4>
                <p className="skill-summary">{skill.summary}</p>
                <a className="source-link" href={`${repoUrl}/tree/main/skills/${skill.slug}`} target="_blank" rel="noreferrer">OPEN SOURCE ↗</a>
              </div>
              <div className="skill-spec">
                <dl>
                  <div><dt>INPUT</dt><dd>{skill.input}</dd></div>
                  <div><dt>OUTPUT</dt><dd>{skill.output}</dd></div>
                  <div><dt>负责</dt><dd>{skill.owns}</dd></div>
                  <div><dt>不负责</dt><dd>{skill.notOwns}</dd></div>
                </dl>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="recipes-section">
        <div className="section-intro compact">
          <p className="eyebrow"><span /> QUICK ROUTES</p><h2>三种最常用的组合。</h2>
        </div>
        <div className="recipes">
          <div><span>01 / 采访前</span><h3>“这位嘉宾，我还能问出什么新东西？”</h3><p>Scripter</p></div>
          <div><span>02 / 录完后</span><h3>“两个小时里，哪几句话最值得被听见？”</h3><p>Highlight Selector → Title Generator</p></div>
          <div><span>03 / 做视频</span><h3>“先把粗剪成立，再让结构和画面都清楚。”</h3><p>FCP AutoCut → FCP Chapter Tool → Collect B-roll</p></div>
        </div>
      </section>

      <footer>
        <div><p className="footer-brand">TIANYU<span>2</span>FM</p><p>TOOLS FOR CONVERSATIONS WORTH KEEPING.</p></div>
        <div className="footer-meta"><span>OPEN SOURCE · SHANGHAI · 2026</span><a href={repoUrl} target="_blank" rel="noreferrer">GITHUB REPOSITORY ↗</a></div>
      </footer>
    </main>
  );
}
