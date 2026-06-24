import React, { useState } from 'react';

interface Props {
  state: any;
}

const HERMES_LEVELS = [
  { value: 0, label: '0%', desc: '纯对话', color: 'text-white/30' },
  { value: 25, label: '25%', desc: '辅助模式', color: 'text-blue-400' },
  { value: 50, label: '50%', desc: '协作模式', color: 'text-purple-400' },
  { value: 75, label: '75%', desc: '自主模式', color: 'text-amber-400' },
  { value: 100, label: '100%', desc: '全自动', color: 'text-red-400' },
];

const MODE_CARDS = [
  {
    id: 'ask',
    icon: '🔍',
    color: 'blue',
    name: 'ASK · 智能检索',
    desc: '联网搜索 + 文件阅读 + 知识问答',
    prompt: '你处于ASK模式。你的核心能力是信息检索和知识问答。优先使用搜索工具和文件读取工具获取信息，然后综合分析给出准确回答。不确定的信息标注来源。',
    tags: ['搜索', '文件', '问答'],
    mode: 'ask',
  },
  {
    id: 'plan',
    icon: '📋',
    color: 'purple',
    name: 'PLAN · 智能规划',
    desc: '联网搜索 + 文件READ + 任务分解 + DAG编排',
    prompt: '你处于PLAN模式。你的核心能力是任务规划和分解。先搜索和阅读相关资料，然后用TwoLevelPlanner将复杂目标分解为可执行的DAG工作流。每个步骤要有明确的输入、输出和验收标准。',
    tags: ['规划', 'DAG', '分解'],
    mode: 'plan',
  },
  {
    id: 'craft',
    icon: '🔨',
    color: 'amber',
    name: 'CRAFT · 智能构建',
    desc: '联网搜索 + 编程执行 + 资源管理 + 代码审查',
    prompt: '你处于CRAFT（BUILD）模式。你的核心能力是代码实现和资源管理。搜索参考资料，编写代码，执行脚本，管理文件。每步操作前确认影响范围，执行后验证结果。使用Maker-Checker双重验证关键变更。',
    tags: ['编程', '执行', '审查'],
    mode: 'craft',
  },
  {
    id: 'goal',
    icon: '🎯',
    color: 'red',
    name: 'GOAL · 自主循环',
    desc: 'GoalRunner迭代 + Maker-Checker + LOOP交付',
    prompt: '你处于GOAL模式。你有一个明确的目标，将迭代执行直到目标达成。每轮采取一个具体行动，用Maker-Checker验证结果。检测到"goal achieved"或"目标已达成"时停止。预算耗尽前优先完成核心目标。',
    tags: ['LOOP', '迭代', '自动改进'],
    mode: 'goal',
  },
];

const EXPERT_SOLO = [
  {
    id: 'coding-agent',
    icon: '💻',
    color: 'blue',
    name: '代码开发专家',
    desc: '全栈编程、调试、重构、代码审查',
    prompt: '你是代码开发专家，精通Python/TypeScript/Go等多语言。擅长代码生成、调试、重构和技术文档撰写。根据需求给出高质量实现。',
    tags: ['Python', 'TypeScript', '调试'],
  },
  {
    id: 'data-analysis',
    icon: '📊',
    color: 'green',
    name: '数据分析专家',
    desc: 'SQL查询、数据清洗、可视化、洞察报告',
    prompt: '你是数据分析专家，擅长SQL查询、数据清洗、统计分析和可视化。根据数据或需求给出分析方案和可视化建议。',
    tags: ['SQL', '可视化', '统计'],
  },
  {
    id: 'frontend-design',
    icon: '🎨',
    color: 'pink',
    name: '前端设计专家',
    desc: '产品需求到UI实现，布局配色交互一站搞定',
    prompt: '你是前端设计专家，擅长将产品需求转化为视觉设计方案，精通React/Vue/TailwindCSS。给出具体的布局、配色、交互建议和代码实现。',
    tags: ['React', 'UI', 'TailwindCSS'],
  },
  {
    id: 'lobster-coach',
    icon: '🐉',
    color: 'red',
    name: '龙教练 · 帮你训龙',
    desc: '说出目标，一步步带你训出理想智能体',
    prompt: '你是COGU Loong的龙教练，擅长引导用户通过问答方式，明确期望的AI智能体角色、技能和知识范围，帮助完成智能体的创建和训练。从目标出发，定义角色、选择技能、编写提示词。',
    tags: ['提示词', '训练', '角色'],
  },
];

const EXPERT_TEAMS = [
  {
    id: 'office-claw',
    icon: '📝',
    count: 6,
    name: '办公自动化专家团',
    desc: '文档、表格、PPT、PDF全覆盖的完整交付团队',
    prompt: '你是办公自动化专家团的协调者，团队成员包括文档撰写专家、PPT设计专家、数据分析专家。协调各专家协同完成办公任务。',
    tags: ['Word', 'Excel', 'PPT', 'PDF'],
  },
  {
    id: 'product-dev',
    icon: '🏗️',
    count: 4,
    name: '产品开发专家团',
    desc: '产品→设计→开发→测试全流程交付',
    prompt: '你是产品开发专家团的协调者，团队包括产品经理、UI设计师、开发工程师、测试工程师。按流水线模式协同完成产品交付。',
    tags: ['产品', '设计', '开发', '测试'],
  },
  {
    id: 'research-debate',
    icon: '🔬',
    count: 3,
    name: '深度研究辩论团',
    desc: '多视角辩论、协同洞察、事实核查',
    prompt: '你是深度研究辩论团的协调者，采用辩论模式：提案者提出观点，批评者质疑，综合者整合，事实核查者验证。多轮辩论后形成共识结论。',
    tags: ['辩论', '洞察', '核查'],
  },
];

const LOOP_PATTERNS = [
  { id: 'daily-triage', name: '每日分类', icon: '📋', desc: '扫描CI/Issue/提交', safety: 'L1' },
  { id: 'ci-sweeper', name: 'CI清扫', icon: '🔧', desc: '检测失败，分类修复', safety: 'L2' },
  { id: 'pr-babysitter', name: 'PR保姆', icon: '👀', desc: '监控PR，审查提交', safety: 'L1' },
  { id: 'dep-sweeper', name: '依赖扫描', icon: '📦', desc: '自动patch级更新', safety: 'L2' },
];

export default function HomeView({ state }: Props) {
  const [prompt, setPrompt] = useState('');
  const [hermesLevel, setHermesLevel] = useState(25);

  const handleSend = () => {
    if (!prompt.trim()) return;
    state.setCurrentView('chat');
    setTimeout(() => state.sendMessage(prompt), 100);
    setPrompt('');
  };

  const handleModeClick = (card: typeof MODE_CARDS[0]) => {
    state.setCurrentView('chat');
    setTimeout(() => state.sendMessage(card.prompt), 100);
  };

  const handleExpertClick = (expert: any) => {
    state.setCurrentView('chat');
    setTimeout(() => state.sendMessage(expert.prompt), 100);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const currentHermes = HERMES_LEVELS.find(h => h.value === hermesLevel)!;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-[900px] mx-auto text-center px-6 pt-12 pb-4">
        <div className="w-[68px] h-[68px] rounded-[18px] overflow-hidden mx-auto mb-4 glow-accent">
          <img src="./avatar.jpeg" alt="COGU Loong" className="w-full h-full object-cover" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-white to-accent bg-clip-text text-transparent mb-1.5">
          COGU Loong
        </h1>
        <p className="text-[14px] text-white/40 max-w-[500px] mx-auto leading-relaxed">
          选择模式或专家，帮你把工作做好 🐉
        </p>

        <div className="mt-5 flex items-center justify-center gap-2">
          <span className="text-[11px] text-white/25 font-medium">Hermes 自主进化</span>
          <div className="flex items-center gap-1 bg-surface border border-white/[0.06] rounded-lg px-2 py-1">
            {HERMES_LEVELS.map(level => (
              <button
                key={level.value}
                onClick={() => setHermesLevel(level.value)}
                className={`px-2 py-0.5 rounded text-[10px] font-medium transition-all ${
                  hermesLevel === level.value
                    ? `${level.color} bg-white/[0.08]`
                    : 'text-white/25 hover:text-white/50'
                }`}
                title={level.desc}
              >
                {level.label}
              </button>
            ))}
          </div>
          <span className={`text-[10px] font-medium ${currentHermes.color}`}>{currentHermes.desc}</span>
        </div>

        <div className="mt-5 relative max-w-[680px] mx-auto">
          <textarea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入问题，按 Enter 发送… 支持 / 引用技能"
            rows={1}
            className="w-full bg-surface border border-white/[0.06] rounded-xl px-5 py-4 pr-14 text-sm text-white outline-none resize-none min-h-[56px] max-h-[160px] focus:border-accent focus:shadow-[0_0_0_3px_rgba(99,102,241,0.08)] transition-all placeholder:text-white/20"
          />
          <button
            onClick={handleSend}
            disabled={!prompt.trim()}
            className="absolute right-3 bottom-3 w-9 h-9 rounded-lg bg-accent text-white flex items-center justify-center hover:bg-accent-glow transition-all shadow-[0_0_16px_rgba(99,102,241,0.25)] disabled:opacity-30 disabled:cursor-default"
          >
            ↑
          </button>
        </div>
      </div>

      <div className="max-w-[900px] mx-auto px-6 mt-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-[12px] font-semibold text-white/25 uppercase tracking-wider">工作模式</span>
          <div className="flex-1 h-px bg-gradient-to-r from-white/[0.06] to-transparent" />
        </div>
        <div className="grid grid-cols-4 gap-2.5">
          {MODE_CARDS.map(card => (
            <button
              key={card.id}
              onClick={() => handleModeClick(card)}
              className="bg-surface border border-white/[0.06] rounded-xl p-4 text-left transition-all hover:border-white/[0.12] hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)] group relative overflow-hidden"
            >
              <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-accent to-purple-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center text-base mb-2.5 ${
                card.color === 'blue' ? 'bg-accent/10' :
                card.color === 'purple' ? 'bg-purple-500/10' :
                card.color === 'amber' ? 'bg-amber-500/10' :
                'bg-red-500/10'
              }`}>
                {card.icon}
              </div>
              <div className="text-[13px] font-semibold mb-0.5">{card.name}</div>
              <div className="text-[11px] text-white/35 leading-relaxed">{card.desc}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-[900px] mx-auto px-6 mt-5">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-[12px] font-semibold text-white/25 uppercase tracking-wider">专家</span>
          <div className="flex-1 h-px bg-gradient-to-r from-white/[0.06] to-transparent" />
        </div>
        <div className="grid grid-cols-4 gap-2.5">
          {EXPERT_SOLO.map(expert => (
            <button
              key={expert.id}
              onClick={() => handleExpertClick(expert)}
              className="bg-surface border border-white/[0.06] rounded-xl p-4 text-left transition-all hover:border-white/[0.12] hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)] group relative overflow-hidden"
            >
              <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-accent to-purple-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center text-base mb-2.5 ${
                expert.color === 'blue' ? 'bg-accent/10' :
                expert.color === 'green' ? 'bg-emerald-500/10' :
                expert.color === 'pink' ? 'bg-pink-500/10' :
                'bg-red-500/10'
              }`}>
                {expert.icon}
              </div>
              <div className="text-[13px] font-semibold mb-0.5">{expert.name}</div>
              <div className="text-[11px] text-white/35 leading-relaxed">{expert.desc}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-[900px] mx-auto px-6 mt-5">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-[12px] font-semibold text-white/25 uppercase tracking-wider">专家团</span>
          <div className="flex-1 h-px bg-gradient-to-r from-white/[0.06] to-transparent" />
        </div>
        <div className="grid grid-cols-3 gap-2.5">
          {EXPERT_TEAMS.map(team => (
            <button
              key={team.id}
              onClick={() => handleExpertClick(team)}
              className="bg-surface border border-white/[0.06] rounded-xl p-4 text-left transition-all hover:border-white/[0.12] hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)] group relative overflow-hidden"
            >
              <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-purple-500 to-pink-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="flex items-center gap-2 mb-2">
                <span className="text-base">{team.icon}</span>
                <span className="text-[13px] font-semibold">{team.name}</span>
                <span className="text-[9px] text-white/20 bg-white/[0.04] px-1.5 py-0.5 rounded">{team.count}人</span>
              </div>
              <div className="text-[11px] text-white/35 leading-relaxed">{team.desc}</div>
              <div className="flex gap-1 mt-2 flex-wrap">
                {team.tags.map(t => (
                  <span key={t} className="text-[9px] px-1.5 py-0.5 rounded bg-white/[0.03] text-white/25 border border-white/[0.06]">{t}</span>
                ))}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-[900px] mx-auto px-6 mt-5">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-[12px] font-semibold text-white/25 uppercase tracking-wider">LOOP 自动化</span>
          <div className="flex-1 h-px bg-gradient-to-r from-white/[0.06] to-transparent" />
        </div>
        <div className="grid grid-cols-4 gap-2">
          {LOOP_PATTERNS.map(lp => (
            <button
              key={lp.id}
              onClick={() => { state.setCurrentView('chat'); }}
              className="bg-surface border border-white/[0.06] rounded-lg px-3 py-2.5 flex items-center gap-2 hover:border-white/[0.12] hover:bg-hover transition-colors"
            >
              <span className="text-sm">{lp.icon}</span>
              <div className="min-w-0 flex-1">
                <div className="text-[11px] font-medium truncate">{lp.name}</div>
                <div className="text-[9px] text-white/20 truncate">{lp.desc}</div>
              </div>
              <span className={`text-[8px] font-mono px-1 py-0.5 rounded ${
                lp.safety === 'L2' ? 'bg-amber-500/10 text-amber-400' : 'bg-white/[0.04] text-white/25'
              }`}>{lp.safety}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="text-center text-[11px] text-white/15 pt-6 pb-6">
        COGU Loong 可能会产生不准确的信息，请注意甄别
      </div>
    </div>
  );
}
